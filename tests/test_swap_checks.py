"""Deterministic colour (ΔE2000) + coverage checks on swap candidates."""
import io
import os

import pytest
from PIL import Image

from app.services import swap as s
from app.services import swap_checks as sc


def solid(color, size=(64, 48)):
    return Image.new("RGB", size, color)


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


YELLOW = (235, 190, 40)
PURPLE = (90, 40, 140)


def box_mask(size=(64, 48), box=(8, 8, 40, 40)):
    m = Image.new("L", size, 0)
    for x in range(box[0], box[2]):
        for y in range(box[1], box[3]):
            m.putpixel((x, y), 255)
    return m


def test_delta_e_identical_and_far():
    assert sc.delta_e2000(sc.mean_lab(solid(YELLOW)),
                          sc.mean_lab(solid(YELLOW))) < 0.01
    assert sc.delta_e2000(sc.mean_lab(solid(YELLOW)),
                          sc.mean_lab(solid(PURPLE))) > 20


def test_colour_check_yellow_swatch_vs_purple_result():
    mask = box_mask()
    room = solid((120, 120, 120))
    purple = room.copy()
    purple.paste(solid(PURPLE), (0, 0), mask)
    out = sc.run_checks(room, purple, mask, png_bytes(solid(YELLOW)))
    assert out["fail"] == sc.REASON_COLOUR
    assert out["delta_e"] > 20 and not out["ok"]
    yellow = room.copy()
    yellow.paste(solid(YELLOW), (0, 0), mask)
    good = sc.run_checks(room, yellow, mask, png_bytes(solid(YELLOW)))
    assert good["ok"] and good["delta_e"] < 1 and good["coverage"] == 1.0


def test_coverage_check_half_painted_fails():
    mask = box_mask()
    room = solid((120, 120, 120))
    half = room.copy()
    half.paste(solid(YELLOW), (0, 0), box_mask(box=(8, 8, 40, 24)))
    out = sc.run_checks(room, half, mask, png_bytes(solid(YELLOW)))
    assert out["fail"] == sc.REASON_COVERAGE
    assert 0.4 < out["coverage"] < 0.6
    assert 0.4 < out["changed"] < 0.6


def test_colour_ignores_room_shading_but_not_hue_or_extreme_lightness():
    saffron = sc.mean_lab(solid((235, 190, 40)))
    shaded = saffron.copy()
    shaded[0] -= 27          # a lit room darkens the sofa, same hue
    de, dl, ok = sc.colour_match(shaded, saffron)
    assert ok and de < 5 and abs(dl + 27) < 0.01
    navy = sc.mean_lab(solid((20, 30, 70)))
    beige = sc.mean_lab(solid((210, 195, 170)))
    assert not sc.colour_match(navy, beige)[2]      # lightness guard
    assert not sc.colour_match(saffron, sc.mean_lab(solid(PURPLE)))[2]


def test_drop_small_components():
    m = Image.new("L", (200, 200), 0)
    for x in range(20, 120):
        for y in range(20, 120):
            m.putpixel((x, y), 255)
    for x in range(170, 176):          # 36 px: far under 3% of 10000
        for y in range(170, 176):
            m.putpixel((x, y), 255)
    out = s.drop_small_components(m)
    assert out.getpixel((60, 60)) == 255
    assert out.getpixel((172, 172)) == 0
    # A second blob above 3% survives.
    for x in range(150, 190):
        for y in range(150, 190):
            m.putpixel((x, y), 255)
    out2 = s.drop_small_components(m)
    assert out2.getpixel((172, 172)) == 255


@pytest.fixture
def room(tmp_path):
    path = tmp_path / "room.jpg"
    solid((120, 120, 120)).save(str(path))
    return str(path)


def _fake_pipeline(monkeypatch, edit_colors, verify_scores=None):
    calls = {"edit": 0, "corrective": []}
    monkeypatch.setattr(s, "require_api_key", lambda: "k")
    monkeypatch.setattr(s, "segment", lambda *a, **k: [
        {"box": (8, 8, 40, 40), "frame_size": (64, 48)}])
    monkeypatch.setattr(s, "sam_mask", lambda records, size: box_mask(size))

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None, timeout=300):
        calls["corrective"].append(corrective)
        color = edit_colors[min(calls["edit"], len(edit_colors) - 1)]
        calls["edit"] += 1
        img = solid((120, 120, 120))
        img.paste(solid(color), (0, 0), box_mask())
        return img

    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify", lambda *a, **k: dict(
        verify_scores or {"color": 9, "pattern": 9, "scale": 9,
                          "isolation": 9}))
    return calls


def swatch_mean(code):
    from app.services.catalog import get_fabric
    img = Image.open(os.path.join(
        os.getcwd(), get_fabric(code)["image"])).convert("RGB")
    lab = sc.mean_lab(img)
    arr = img.resize((1, 1), Image.BOX).getpixel((0, 0))
    return arr, lab


def test_single_swap_colour_fail_retries_then_not_applied(
        tmp_path, room, monkeypatch):
    calls = _fake_pipeline(monkeypatch, [PURPLE, PURPLE])
    with pytest.raises(s.CheckFailed) as exc:
        s.swap(room, "FA-AC-01", "sofa", out_dir=str(tmp_path))
    assert exc.value.reason == sc.REASON_COLOUR
    assert calls["edit"] == 2, "one corrective retry"
    assert "colour" in (calls["corrective"][1] or "")
    assert "not applied" in str(exc.value)


def test_single_swap_passes_when_colour_matches(tmp_path, room,
                                                monkeypatch):
    mean_rgb, _ = swatch_mean("FA-AC-01")
    calls = _fake_pipeline(monkeypatch, [PURPLE, mean_rgb])
    res = s.swap(room, "FA-AC-01", "sofa", out_dir=str(tmp_path))
    assert calls["edit"] == 2
    assert res["checks"]["ok"] and res["attempts"] == 2
    assert res["checks"]["delta_e"] <= 20
    assert res["checks"]["coverage"] >= 0.85
    assert res["target"] == "sofa"


def test_multi_colour_fail_is_honest_skip(tmp_path, room, monkeypatch):
    mean_rgb, _ = swatch_mean("FA-AC-01")
    monkeypatch.setattr(s, "require_api_key", lambda: "k")
    monkeypatch.setattr(s, "segment", lambda *a, **k: [
        {"box": (8, 8, 40, 40), "frame_size": (64, 48)}])
    monkeypatch.setattr(s, "sam_mask", lambda records, size: box_mask(size))

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None, timeout=300):
        img = solid((120, 120, 120))
        color = mean_rgb if fabric["code"] == "FA-AC-01" else PURPLE
        img.paste(solid(color), (0, 0), box_mask())
        return img

    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify", lambda *a, **k: {
        "color": 9, "pattern": 9, "scale": 9, "isolation": 9})
    out = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"},
                              {"target": "cushions", "code": "FA-AC-05"}],
                       out_dir=str(tmp_path))
    assert [r["target"] for r in out["results"]] == ["sofa"]
    assert out["results"][0]["checks"]["ok"]
    assert out["skipped"][0]["target"] == "cushions"
    assert out["skipped"][0]["reason"] == sc.REASON_COLOUR
    assert out["skipped"][0]["checks"]["delta_e"] > 20
