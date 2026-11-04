"""Multi-item swap tests (model calls are faked)."""
import io
import json
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services import swap as s


TMP = "/tmp/recover-swapmulti-test"


@pytest.fixture(autouse=True)
def _checks_pass(monkeypatch):
    """These fakes paint grey solids: the deterministic colour/coverage
    checks are covered in test_swap_checks.py, so pass them here."""
    monkeypatch.setattr(s.swap_checks, "run_checks", lambda *a, **k: {
        "delta_e": 1.0, "coverage": 1.0, "ok": True, "fail": None})


def setup_function(_):
    os.makedirs(TMP, exist_ok=True)


def solid(color, size=(64, 48)):
    return Image.new("RGB", size, color)


def make_room(tmp_path):
    room = tmp_path / "room.jpg"
    solid((10, 20, 30)).save(str(room))
    return str(room)


@pytest.fixture
def fakes(monkeypatch):
    calls = {"segment": [], "edit": [], "verify": 0}

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        calls["segment"].append(concept)
        if concept == "sofa":
            return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]
        return [{"box": (10, 10, 30, 30), "frame_size": (100, 100)}]

    def fake_mask(records, size):
        return Image.new("L", size, 255)

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None, timeout=300):
        calls["edit"].append(concept)
        shade = 100 if concept == "sofa" else 180
        return solid((shade, shade, shade))

    def fake_verify(swatch_bytes, result, fabric, concept, key=None,
                    timeout=120):
        calls["verify"] += 1
        return {"color": 8, "pattern": 8, "scale": 8, "isolation": 8}

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask", fake_mask)
    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify", fake_verify)
    return calls


def test_multi_largest_first_and_files(tmp_path, fakes):
    room = make_room(tmp_path)
    out = tmp_path / "out"
    res = s.swap_multi(room, [{"target": "cushions", "code": "FA-AC-02"},
                              {"target": "sofa", "code": "FA-AC-01"}],
                       api_key="k", out_dir=str(out))
    # Edits run in parallel (completion order varies); results stay
    # largest-first.
    assert sorted(fakes["edit"]) == sorted(
        [s.TARGET_CONCEPTS["cushions"], "sofa"])
    assert [r["target"] for r in res["results"]] == ["sofa", "cushions"]
    assert all(r["attempts"] == 1 and r["cached"] is False
               for r in res["results"])
    for r in res["results"]:
        assert os.path.exists(os.path.join(str(out), os.path.basename(
            r["result_url"])))
    assert os.path.exists(os.path.join(
        str(out), os.path.basename(res["final_url"])))


def test_multi_cache_reuses_without_calls(tmp_path, fakes):
    room = make_room(tmp_path)
    out = tmp_path / "out"
    first = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                         api_key="k", out_dir=str(out))
    assert first["results"][0]["cached"] is False
    fakes["segment"].clear()
    fakes["edit"].clear()
    second = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                          api_key="k", out_dir=str(out))
    assert second["results"][0]["cached"] is True
    assert fakes["segment"] == [] and fakes["edit"] == []


def test_multi_retry_once_on_low_scores(tmp_path, monkeypatch):
    room = make_room(tmp_path)
    # A low scale score retries; colour alone would not (ΔE gate), and
    # for this plain fabric neither would the pattern score.
    scores = [{"color": 8, "pattern": 8, "scale": 5, "isolation": 8},
              {"color": 8, "pattern": 8, "scale": 8, "isolation": 8}]
    edits = []

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room",
                        lambda *a, **k: edits.append(1) or solid((9, 9, 9)))
    monkeypatch.setattr(s, "verify",
                        lambda *a, **k: scores[min(len(edits) - 1, 1)])
    res = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                       api_key="k", out_dir=str(tmp_path / "o"))
    assert res["results"][0]["attempts"] == 2
    assert len(edits) == 2
    assert res["results"][0]["scores"]["scale"] == 8


def test_multi_skips_failed_item_keeps_rest(tmp_path, monkeypatch):
    room = make_room(tmp_path)

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        # No pillows under any prompt, the sofa prompt included.
        if "pillow" in concept or "cushion" in concept:
            return []
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room",
                        lambda *a, **k: solid((9, 9, 9)))
    monkeypatch.setattr(s, "verify",
                        lambda *a, **k: {"color": 8, "pattern": 8,
                                         "scale": 8, "isolation": 8})
    res = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"},
                              {"target": "cushions",
                               "code": "FA-AC-02"}],
                       api_key="k", out_dir=str(tmp_path / "o"))
    assert [r["target"] for r in res["results"]] == ["sofa"]
    assert res["skipped"][0]["target"] == "cushions"
    assert "could not find" in res["skipped"][0]["reason"]
    assert os.path.exists(os.path.join(
        str(tmp_path / "o"), os.path.basename(res["final_url"])))


def test_multi_skips_edit_failure(tmp_path, monkeypatch):
    room = make_room(tmp_path)

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None, timeout=300):
        if concept == s.TARGET_CONCEPTS["cushions"]:
            raise s.SwapError("fabric edit failed: boom")
        return solid((9, 9, 9))

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify",
                        lambda *a, **k: {"color": 8, "pattern": 8,
                                         "scale": 8, "isolation": 8})
    res = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"},
                              {"target": "cushions",
                               "code": "FA-AC-02"}],
                       api_key="k", out_dir=str(tmp_path / "o"))
    assert [r["target"] for r in res["results"]] == ["sofa"]
    assert res["skipped"][0]["code"] == "FA-AC-02"


def test_paste_strict_resizes_mismatched_edit():
    orig = solid((10, 20, 30), (64, 48))
    big_edit = solid((200, 100, 50), (128, 96))
    mask = Image.new("L", (64, 48), 255)
    out = s.paste_strict(orig, big_edit, mask)
    assert out.size == (64, 48)
    assert out.getpixel((5, 5)) == (200, 100, 50)


def test_small_copy_caps_dimensions():
    big = Image.new("RGB", (2400, 1800), (1, 2, 3))
    buf = io.BytesIO()
    big.save(buf, "JPEG", quality=90)
    small = s._small_copy(buf.getvalue(), 1600)
    got = Image.open(io.BytesIO(small))
    assert max(got.size) <= 1600
    tiny = s._small_copy(buf.getvalue(), 5000)
    assert Image.open(io.BytesIO(tiny)).size == (2400, 1800)


def test_multi_segments_capped_copy(tmp_path, monkeypatch):
    room = make_room(tmp_path)
    seen = {}

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        seen[concept] = Image.open(
            io.BytesIO(room_bytes)).size
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room",
                        lambda *a, **k: solid((9, 9, 9)))
    monkeypatch.setattr(s, "verify",
                        lambda *a, **k: {"color": 8, "pattern": 8,
                                         "scale": 8, "isolation": 8})
    s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                 api_key="k", out_dir=str(tmp_path / "o3"))
    assert max(seen["sofa"]) <= 1600


def test_multi_unexpected_error_becomes_skip(tmp_path, monkeypatch):
    room = make_room(tmp_path)

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None, timeout=300):
        if concept == s.TARGET_CONCEPTS["cushions"]:
            raise ValueError("images do not match")
        return solid((9, 9, 9))

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify",
                        lambda *a, **k: {"color": 8, "pattern": 8,
                                         "scale": 8, "isolation": 8})
    res = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"},
                              {"target": "cushions",
                               "code": "FA-AC-02"}],
                       api_key="k", out_dir=str(tmp_path / "o2"))
    assert [r["target"] for r in res["results"]] == ["sofa"]
    assert res["skipped"][0]["target"] == "cushions"


def test_multi_item_budget_expiry_skips(tmp_path, monkeypatch):
    room = make_room(tmp_path)
    calls = []
    ticks = iter([0.0, 1000.0, 1000.0, 1000.0])

    def fake_now():
        try:
            return next(ticks)
        except StopIteration:
            return 1000.0

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        calls.append((concept, timeout))
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room",
                        lambda *a, **k: solid((9, 9, 9)))
    monkeypatch.setattr(s, "verify",
                        lambda *a, **k: {"color": 8, "pattern": 8,
                                         "scale": 8, "isolation": 8})
    with pytest.raises(s.SwapError) as exc:
        s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                     api_key="k", out_dir=str(tmp_path / "o4"),
                     budget=60, _now=fake_now)
    assert calls == []
    assert "timed out after 60s" in str(exc.value)


def test_multi_call_timeouts_bounded(tmp_path, monkeypatch):
    room = make_room(tmp_path)
    seen = []

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        seen.append(timeout)
        return [{"box": (0, 0, 90, 90), "frame_size": (100, 100)}]

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None, timeout=300):
        seen.append(timeout)
        return solid((9, 9, 9))

    def fake_verify(swatch_bytes, result, fabric, concept, key=None,
                    timeout=120):
        seen.append(timeout)
        return {"color": 8, "pattern": 8, "scale": 8, "isolation": 8}

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify", fake_verify)
    res = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                       api_key="k", out_dir=str(tmp_path / "o5"))
    assert len(res["results"]) == 1
    assert seen and all(t <= 60 for t in seen)


def test_multi_all_fail_still_raises(tmp_path, monkeypatch):
    room = make_room(tmp_path)
    monkeypatch.setattr(s, "segment", lambda *a, **k: [])
    res_before = None
    with pytest.raises(s.SwapError):
        s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"}],
                     api_key="k", out_dir=str(tmp_path / "o"))
    assert res_before is None


def test_multi_rejects_bad_input(tmp_path):
    room = make_room(tmp_path)
    with pytest.raises(s.SwapError):
        s.swap_multi(room, [], api_key="k",
                     out_dir=str(tmp_path / "o"))
    with pytest.raises(s.SwapError):
        s.swap_multi(room, [{"target": "lamp", "code": "FA-AC-01"}],
                     api_key="k", out_dir=str(tmp_path / "o"))
    with pytest.raises(s.SwapError):
        s.swap_multi(room, [{"target": "sofa", "code": "NOPE"}],
                     api_key="k", out_dir=str(tmp_path / "o"))


def test_multi_endpoint_shape(monkeypatch, tmp_path):
    from app.main import app
    room = make_room(tmp_path)
    rel = os.path.relpath(room, os.getcwd() + "/recover-ai") \
        if room.startswith(os.getcwd()) else room

    def fake_multi(room_path, assignments, **kwargs):
        return {"results": [{"target": a["target"], "code": a["code"],
                             "result_url": "uploads/swap/r.jpg",
                             "mask_url": "uploads/swap/m.png",
                             "scores": {"color": 8}, "attempts": 1,
                             "cached": False} for a in assignments],
                "final_url": "uploads/swap/final.jpg"}

    monkeypatch.setattr("app.services.swap.swap_multi", fake_multi)
    # B1: routes only serve uploads/samples roots; admit the tmp room.
    monkeypatch.setattr("app.api.chat.UPLOAD_DIR", str(tmp_path))
    client = TestClient(app)
    resp = client.post(
        "/api/swap/multi",
        json={"session_id": "t-multi", "image_path": room,
              "assignments": [{"target": "sofa", "code": "FA-AC-01"}]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["final_url"].endswith("final.jpg")
    assert body["results"][0]["target"] == "sofa"


def test_multi_endpoint_rejects(monkeypatch, tmp_path):
    from app.main import app
    room = make_room(tmp_path)
    # Admit the tmp room so the 400s come from assignment validation.
    monkeypatch.setattr("app.api.chat.UPLOAD_DIR", str(tmp_path))
    client = TestClient(app)
    bad_target = client.post(
        "/api/swap/multi",
        json={"session_id": "t-m", "image_path": room,
              "assignments": [{"target": "lamp", "code": "FA-AC-01"}]})
    assert bad_target.status_code == 400
    bad_code = client.post(
        "/api/swap/multi",
        json={"session_id": "t-m", "image_path": room,
              "assignments": [{"target": "sofa", "code": "NOPE"}]})
    assert bad_code.status_code == 400
    missing = client.post(
        "/api/swap/multi",
        json={"session_id": "t-m", "image_path": "uploads/nope.jpg",
              "assignments": [{"target": "sofa", "code": "FA-AC-01"}]})
    assert missing.status_code == 400


def test_fabrics_browse_filters():
    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/fabrics",
                      params={"suitable_for": "curtains",
                              "usage": "curtains", "limit": 5})
    assert resp.status_code == 200
    fabrics = resp.json()["fabrics"]
    assert 1 <= len(fabrics) <= 5
    assert all("code" in f and "price_usd_per_m" in f for f in fabrics)


def test_assignments_roundtrip():
    from app.main import app
    client = TestClient(app)
    put = client.post("/api/session/t-asg/assignments",
                      json={"target": "sofa", "code": "FA-AC-01"})
    assert put.status_code == 200
    assert put.json()["assignments"] == {"sofa": "FA-AC-01"}
    bad = client.post("/api/session/t-asg/assignments",
                      json={"target": "lamp", "code": "FA-AC-01"})
    assert bad.status_code == 400
    wipe = client.delete("/api/session/t-asg/assignments")
    assert wipe.status_code == 200
    assert wipe.json() == {"assignments": {}}


def test_chained_pillows_edit_on_sofa_result_and_land_on_top(tmp_path,
                                                              monkeypatch):
    """Sofa + pillows: the pillow edit must receive the SOFA RESULT as
    its input (not the original), its residue search spans sofa ∪
    pillows, and the pillows composite last."""
    room = make_room(tmp_path)
    seen = {"edit_inputs": {}, "residue_masks": {}}
    sofa_box = (0, 0, 60, 48)
    pillow_box = (10, 10, 30, 30)

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        if concept == "sofa":
            return [{"box": (0, 0, 90, 100), "frame_size": (100, 100)}]
        if concept == s.SOFA_WOOD_CONCEPT:
            return []  # no exposed wood in this room
        return [{"box": (15, 20, 45, 60), "frame_size": (100, 100)}]

    def fake_mask(records, size):
        m = Image.new("L", size, 0)
        box = sofa_box if records[0]["box"][0] == 0 else pillow_box
        for x in range(box[0], box[2]):
            for y in range(box[1], box[3]):
                m.putpixel((x, y), 255)
        return m

    def fake_edit(room_bytes, swatch_bytes, fabric, concept, key=None,
                  corrective=None, timeout=300):
        seen["edit_inputs"][concept] = room_bytes
        shade = 60 if concept == "sofa" else 220
        return solid((shade, shade, shade))

    real_checks = s.swap_checks.run_checks

    def spy_checks(original, result, mask, swatch, base=None,
                   residue_mask=None, **kw):
        seen["residue_masks"][mask.getbbox()] = (
            residue_mask.getbbox() if residue_mask is not None else None)
        return {"delta_e": 1.0, "coverage": 1.0, "changed": 1.0,
                "residue": 0.0, "ok": True, "fail": None}

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask", fake_mask)
    monkeypatch.setattr(s, "edit_room", fake_edit)
    monkeypatch.setattr(s, "verify", lambda *a, **k: {
        "color": 9, "pattern": 9, "scale": 9, "isolation": 9})
    monkeypatch.setattr(s.swap_checks, "run_checks", spy_checks)
    res = s.swap_multi(room, [{"target": "sofa", "code": "FA-AC-01"},
                              {"target": "cushions", "code": "FA-AC-08"}],
                       api_key="k", out_dir=str(tmp_path / "o"))
    with open(room, "rb") as f:
        original = f.read()
    pillow_concept = s.TARGET_CONCEPTS["cushions"]
    assert seen["edit_inputs"]["sofa"] == original
    assert seen["edit_inputs"][pillow_concept] != original
    sofa_result = Image.open(io.BytesIO(seen["edit_inputs"][pillow_concept]))
    assert sofa_result.getpixel((50, 40))[0] < 90, "sofa already recoloured"
    # Residue search for the pillows spans sofa ∪ pillow (the pillow
    # mask is dilated a little, so match the key by containment).
    pillow_keys = [k for k in seen["residue_masks"]
                   if k != sofa_box and k[0] <= pillow_box[0]
                   and k[2] >= pillow_box[2]]
    assert pillow_keys and seen["residue_masks"][pillow_keys[0]] == sofa_box
    final = Image.open(os.path.join(os.getcwd(), res["final_url"]))
    assert final.getpixel((20, 20))[0] > 150, "pillow on top"
    assert final.getpixel((50, 40))[0] < 90, "sofa fabric around it"
    assert [r["target"] for r in res["results"]] == ["sofa", "cushions"]


def test_pillow_prompt_forbids_duplicates():
    from app.services.catalog import get_fabric
    text = s.edit_prompt(get_fabric("FA-AC-08"), s.TARGET_CONCEPTS["cushions"])
    assert "exactly ONE pillow" in text
    assert "duplicate" in text
    assert "duplicate" not in s.edit_prompt(get_fabric("FA-AC-01"), "sofa")


def test_multi_refines_seat_slivers_past_a_throw(tmp_path, monkeypatch):
    """Apply all: a sofa whose SAM mask has a notch under a throw gets
    the second aimed edit; the strip is recoloured in the item and in
    the final composite, the throw is not."""
    size = (200, 200)
    room = tmp_path / "room.jpg"
    solid((120, 120, 120), size).save(str(room))
    seat = Image.new("L", size, 0)
    seat.paste(255, (40, 40, 160, 160))
    seat.paste(0, (90, 40, 110, 100))                   # notch
    throw = Image.new("L", size, 0)
    throw.paste(255, (92, 40, 108, 70))

    def fake_segment(room_bytes, concept, key=None, timeout=120):
        if concept in ("sofa", "throw blanket"):
            return [{"concept": concept, "box": (40, 40, 160, 160),
                     "frame_size": size}]
        return []
    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask", lambda records, sz: (
        seat if records[0]["concept"] == "sofa" else throw))
    monkeypatch.setattr(s, "sofa_full_mask",
                        lambda *a, **k: ([{"concept": "sofa",
                                           "box": (40, 40, 160, 160)}],
                                         seat))
    monkeypatch.setattr(s, "REFINE_CLOSE_FRAC", 0.2)
    monkeypatch.setattr(s, "edit_room",
                        lambda *a, **k: solid((20, 60, 140), size))
    monkeypatch.setattr(s, "verify", lambda *a, **k: {
        "color": 9, "pattern": 9, "scale": 9, "isolation": 9})
    res = s.swap_multi(str(room), [{"target": "sofa", "code": "FA-AC-01"}],
                       api_key="k", out_dir=str(tmp_path / "out"))
    sofa = res["results"][0]
    assert sofa["checks"].get("refined", 0) > 0.01, sofa["checks"]
    final = Image.open(os.path.join(os.getcwd(), res["final_url"])).convert(
        "RGB")
    assert max(abs(a - b) for a, b in zip(final.getpixel((100, 90)),
                                          (20, 60, 140))) <= 12
    assert max(abs(a - b) for a, b in zip(final.getpixel((100, 50)),
                                          (20, 60, 140))) > 40
    assert all(abs(c - 120) <= 3 for c in final.getpixel((10, 10)))


def test_multi_rejects_a_result_that_reframed_the_photo(tmp_path, monkeypatch):
    """The final composite must leave everything outside the pieces as
    the photo; a paste that changed the room is a bug, not a result."""
    room = tmp_path / "room.jpg"
    solid((120, 120, 120), (100, 100)).save(str(room))
    monkeypatch.setattr(s, "segment", lambda *a, **k: [
        {"box": (0, 0, 90, 90), "frame_size": (100, 100)}])
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, size: Image.new("L", size, 255))
    monkeypatch.setattr(s, "edit_room", lambda *a, **k: solid((9, 9, 9)))
    monkeypatch.setattr(s, "verify", lambda *a, **k: {
        "color": 8, "pattern": 8, "scale": 8, "isolation": 8})
    # A paste that ignores its mask and returns the edited frame whole.
    monkeypatch.setattr(s, "paste_strict",
                        lambda original, edited, mask, feather=6, keep_out=None: edited.resize(original.size))
    small = Image.new("L", (100, 100), 0)
    small.paste(255, (40, 40, 60, 60))
    monkeypatch.setattr(s, "sofa_full_mask",
                        lambda *a, **k: ([{"box": (40, 40, 60, 60)}], small))
    with pytest.raises(s.SwapError):
        s.swap_multi(str(room), [{"target": "sofa", "code": "FA-AC-01"}],
                     api_key="k", out_dir=str(tmp_path / "o"))


def test_frame_changed_share_is_zero_for_a_strict_composite():
    orig = solid((120, 120, 120), (200, 100))
    edit = solid((240, 200, 40), (200, 100))
    mask = Image.new("L", (200, 100), 0)
    mask.paste(255, (50, 20, 150, 80))
    out = s.paste_strict(orig, edit, mask)
    assert s.frame_changed_share(orig, out, mask) == 0.0
    assert s.frame_changed_share(orig, edit, mask) > 0.5


def test_apply_all_soft_edge_never_writes_over_another_piece():
    """Each piece is edited from the original photo, so its soft edge
    carries the old colour of its neighbours. With keep_out the pillow's
    edge stops at the curtain's mask: the curtain keeps its new colour
    right up to the pillow."""
    from PIL import ImageDraw
    from app.services import swap as s
    size = (120, 80)
    room = Image.new("RGB", size, (200, 190, 170))          # beige curtain everywhere
    curtain_mask = Image.new("L", size, 255)
    pillow_mask = Image.new("L", size, 0)
    ImageDraw.Draw(pillow_mask).rectangle((40, 30, 80, 60), fill=255)
    ImageDraw.Draw(curtain_mask).rectangle((40, 30, 80, 60), fill=0)
    curtain_edit = Image.new("RGB", size, (190, 90, 60))     # terracotta
    ImageDraw.Draw(curtain_edit).rectangle((40, 30, 80, 60), fill=(200, 190, 170))
    pillow_edit = room.copy()
    ImageDraw.Draw(pillow_edit).rectangle((40, 30, 80, 60), fill=(20, 90, 110))
    final = s.paste_strict(room, curtain_edit, curtain_mask, keep_out=pillow_mask)
    plain = s.paste_strict(final, pillow_edit, pillow_mask)
    clipped = s.paste_strict(final, pillow_edit, pillow_mask, keep_out=curtain_mask)
    above = (60, 28)                                          # curtain pixel just above the pillow
    assert plain.getpixel(above) != (190, 90, 60)             # the old beige leaked
    assert clipped.getpixel(above) == (190, 90, 60)           # curtain intact
    assert clipped.getpixel((60, 45)) == (20, 90, 110)        # pillow painted
