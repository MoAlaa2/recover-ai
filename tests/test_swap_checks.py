"""Deterministic colour (ΔE2000) + coverage checks on swap candidates."""
import io
import os

import pytest
import numpy as np
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
    def fake_segment(room_bytes, concept, key=None, timeout=120):
        # No throw pillows in this room: the sofa keeps its full mask.
        if concept == s.TARGET_CONCEPTS["cushions"]:
            return []
        return [{"box": (8, 8, 40, 40), "frame_size": (64, 48)}]

    monkeypatch.setattr(s, "segment", fake_segment)
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

    rec = [{"box": (8, 8, 40, 40), "frame_size": (64, 48)}]
    monkeypatch.setattr(s, "segment", lambda *a, **k: list(rec))
    monkeypatch.setattr(s, "sam_mask", lambda records, size: box_mask(size))
    # The sofa stage would cut the (same-box) pillows out of its mask;
    # fake it so the sofa keeps the box and the pillow job is judged.
    monkeypatch.setattr(s, "sofa_full_mask",
                        lambda *a, **k: (list(rec), box_mask((64, 48))))

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


def test_residue_check_flags_leftover_old_fabric():
    """A beige patch of the old sofa left inside the mask (1% of the
    image) fails; a fully covered mask passes; like-for-like skips."""
    BEIGE = (200, 180, 150)
    size = (200, 200)
    room = solid(BEIGE, size)
    mask = box_mask(size, (20, 20, 180, 180))
    full = room.copy()
    full.paste(solid(PURPLE, size), (0, 0), mask)
    ok = sc.run_checks(room, full, mask, png_bytes(solid(PURPLE)))
    assert ok["ok"] and ok["residue"] == 0.0
    leftover = full.copy()
    leftover.paste(solid(BEIGE, size), (0, 0), box_mask(size, (60, 60, 80, 80)))
    bad = sc.run_checks(room, leftover, mask, png_bytes(solid(PURPLE)))
    assert bad["fail"] == sc.REASON_RESIDUE
    assert bad["residue"] >= 0.006  # 1% patch, edges softened by blur
    # Like-for-like (oat on beige): the residue test cannot tell them
    # apart, so it is skipped rather than failing an honest swap.
    like = sc.residue_check(room, room, mask, png_bytes(solid(BEIGE)))
    assert like["skipped"] and like["ok"]


def test_array_delta_e_matches_scalar():
    import numpy as np
    labs = np.array([sc.mean_lab(solid(c)) for c in
                     [YELLOW, PURPLE, (10, 10, 10), (240, 240, 240)]])
    ref = sc.mean_lab(solid((120, 90, 60)))
    arr = sc._de2000_array(labs, ref)
    for i, lab in enumerate(labs):
        assert abs(arr[i] - sc.delta_e2000(lab, ref)) < 1e-6


def test_residue_ignores_new_sofa_fabric_that_resembles_the_old():
    """Mustard pillow on a sand sofa over a beige original: the sand
    sofa pixels inside sofa ∪ pillow look like the old beige but ARE
    the new sofa fabric (extra swatch), so they are not residue."""
    BEIGE, SAND = (200, 180, 150), (205, 185, 160)
    size = (200, 200)
    room = solid(BEIGE, size)
    union = box_mask(size, (20, 20, 180, 180))
    pillow = box_mask(size, (60, 60, 100, 100))
    result = solid(SAND, size)
    result.paste(solid(YELLOW, size), (0, 0), pillow)
    out = sc.residue_check(room, result, union, png_bytes(solid(YELLOW)),
                           extra_swatches=[png_bytes(solid(SAND))])
    assert out["ok"] and out["residue"] == 0.0
    # Without the sofa swatch the sand sofa would (wrongly) read as old.
    naive = sc.residue_check(room, result, union, png_bytes(solid(YELLOW)))
    assert not naive["ok"]


def test_pillow_pieces_pass_when_only_some_pieces_recoloured():
    """Two separate pillows in the mask, the edit recolours one: the
    whole-mask coverage fails, but with pieces=True (cushions) the
    recoloured pillow passes on its own and the kept mask is just it.
    Real case: SAM's pillow mask included the sofa's loose back
    cushions and the edit left those beige (coverage 0.75)."""
    size = (96, 48)
    left = box_mask(size, (4, 8, 40, 40))
    right = box_mask(size, (56, 8, 92, 40))
    both = Image.fromarray(np.maximum(np.asarray(left), np.asarray(right)))
    room = solid((120, 120, 120), size)
    res = room.copy()
    res.paste(solid(YELLOW, size), (0, 0), left)
    whole = sc.run_checks(room, res, both, png_bytes(solid(YELLOW)))
    assert whole["fail"] == sc.REASON_COVERAGE
    out = sc.run_checks(room, res, both, png_bytes(solid(YELLOW)),
                        pieces=True)
    assert out["ok"] and out["fail"] is None
    assert out["pieces"] == {"covered": 1, "total": 2}
    # Overlapping pillows are ONE blob; the segmenter's per-object
    # masks still split them.
    overlap = box_mask(size, (30, 8, 70, 40))
    one_blob = Image.fromarray(np.maximum(np.asarray(both),
                                          np.asarray(overlap)))
    assert len(sc.mask_components(one_blob)) == 1
    res2 = room.copy()
    res2.paste(solid(YELLOW, size), (0, 0), left)
    res2.paste(solid(YELLOW, size), (0, 0), overlap)
    assert sc.run_checks(room, res2, one_blob, png_bytes(solid(YELLOW)),
                         pieces=True)["fail"] == sc.REASON_COVERAGE
    out2 = sc.run_checks(room, res2, one_blob, png_bytes(solid(YELLOW)),
                         pieces=[left, overlap, right])
    assert out2["ok"] and out2["pieces"] == {"covered": 2, "total": 3}
    kept = np.asarray(out["_mask"]) > 127
    assert kept[20, 20] and not kept[20, 70]
    # A single-blob mask (a sofa) never gets the per-piece leniency.
    half = room.copy()
    half.paste(solid(YELLOW, size), (0, 0), box_mask(size, (4, 8, 40, 24)))
    assert sc.run_checks(room, half, left, png_bytes(solid(YELLOW)),
                         pieces=True)["fail"] == sc.REASON_COVERAGE
    # Nothing recoloured at all: still an honest failure.
    assert not sc.run_checks(room, room, both, png_bytes(solid(YELLOW)),
                             pieces=True)["ok"]


def test_single_swap_cushions_keeps_only_recoloured_pillows(
        tmp_path, room, monkeypatch):
    """Through swap(): the cushions mask is two pillows, the edit
    recolours one. The swap is applied, the saved mask covers only the
    recoloured pillow and the other keeps the photo's pixels."""
    mean_rgb, _ = swatch_mean("FA-AC-01")
    monkeypatch.setattr(s, "require_api_key", lambda: "k")
    monkeypatch.setattr(s, "segment", lambda *a, **k: [
        {"box": (4, 8, 40, 40), "frame_size": (96, 48)},
        {"box": (56, 8, 92, 40), "frame_size": (96, 48)}])
    two = Image.fromarray(np.maximum(
        np.asarray(box_mask((96, 48), (4, 8, 40, 40))),
        np.asarray(box_mask((96, 48), (56, 8, 92, 40)))))
    monkeypatch.setattr(s, "sam_mask", lambda records, size: two
                        if len(records) > 1 else box_mask(
                            size, tuple(records[0]["box"])))

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None, timeout=300):
        img = solid((120, 120, 120), (96, 48))
        img.paste(solid(mean_rgb, (96, 48)), (0, 0),
                  box_mask((96, 48), (4, 8, 40, 40)))
        # The model re-rendered the untouched pillow slightly off.
        img.paste(solid((110, 110, 110), (96, 48)), (0, 0),
                  box_mask((96, 48), (56, 8, 92, 40)))
        return img

    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify", lambda *a, **k: {
        "color": 9, "pattern": 9, "scale": 9, "isolation": 9})
    wide = str(tmp_path / "wide.jpg")
    solid((120, 120, 120), (96, 48)).save(wide)
    res = s.swap(wide, "FA-AC-01", "cushions", out_dir=str(tmp_path))
    assert res["checks"]["ok"]
    assert res["checks"]["pieces"] == {"covered": 1, "total": 2}
    assert "_mask" not in res["checks"]
    saved_mask = np.asarray(Image.open(os.path.join(
        os.getcwd(), res["mask_url"])).convert("L")) > 127
    assert saved_mask[20, 20] and not saved_mask[20, 70]
    out = Image.open(os.path.join(os.getcwd(), res["result_url"]))
    assert out.getpixel((70, 20)) != (110, 110, 110)


def test_patterned_fabric_must_visibly_change_the_mask():
    """Like-for-like colour: a gingham near the old off-white passes
    the colour cells even where nothing was painted. With min_changed
    the patches edit fails as low coverage; without it, it passes."""
    size = (96, 48)
    mask = box_mask(size, (0, 0, 96, 48))
    room = solid((200, 200, 196), size)
    res = room.copy()
    # The model painted only the left third (a slightly darker check).
    res.paste(solid((176, 176, 172), size), (0, 0),
              box_mask(size, (0, 0, 32, 48)))
    swatch = png_bytes(solid((196, 196, 192)))
    assert sc.run_checks(room, res, mask, swatch)["ok"]
    out = sc.run_checks(room, res, mask, swatch, min_changed=0.4)
    assert out["fail"] == sc.REASON_COVERAGE and out["changed"] < 0.4
    full = room.copy()
    full.paste(solid((176, 176, 172), size), (0, 0), mask)
    assert sc.run_checks(room, full, mask, swatch, min_changed=0.4)["ok"]
