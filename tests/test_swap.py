"""Fabric swap tests (model calls are faked or offline)."""
import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services import swap as s

TMP = "/tmp/recover-swap-test"


def setup_function(_):
    os.makedirs(TMP, exist_ok=True)


def solid(color, size=(64, 48)):
    return Image.new("RGB", size, color)


def test_composite_keeps_rest_pixel_identical():
    original = solid((10, 20, 30))
    edited = solid((200, 210, 220))
    mask = s.paste_mask(original, edited, (8, 8, 24, 24),
                        margin=0.0, feather=0)
    result = original.copy()
    result.paste(edited, (0, 0), mask)
    outside = result.crop((0, 0, 8, 48)).tobytes()
    assert outside == original.crop((0, 0, 8, 48)).tobytes()
    inside = result.crop((12, 12, 20, 20)).tobytes()
    assert inside == edited.crop((12, 12, 20, 20)).tobytes()


def test_paste_mask_empty_when_unchanged():
    original = solid((10, 20, 30))
    mask = s.paste_mask(original, original.copy(), (0, 0, 64, 48),
                        margin=0.05, feather=2)
    assert max(mask.getextrema()) == 0


def test_verify_parsing(monkeypatch):
    import app.services.swap as mod

    def fake_post(url, payload, api_key, timeout, **kw):
        return {"choices": [{"message": {"content":
                 "Scores: {\"color\": 9, \"pattern\": 8, "
                 "\"scale\": 9, \"isolation\": 7}"}}]}
    monkeypatch.setattr(mod, "_post_json", fake_post)
    scores = s.verify(b"sw", solid((1, 2, 3)), {"plain_or_patterned":
                                               "plain"}, "sofa", "key")
    assert scores == {"color": 9, "pattern": 8, "scale": 9,
                      "isolation": 7}


def test_verify_rejects_garbage(monkeypatch):
    import app.services.swap as mod

    def fake_post(url, payload, api_key, timeout, **kw):
        return {"choices": [{"message": {"content": "no json here"}}]}
    monkeypatch.setattr(mod, "_post_json", fake_post)
    with pytest.raises(s.SwapError):
        s.verify(b"sw", solid((1, 2, 3)), {}, "sofa", "key")


def test_swap_rejects_unknown_fabric(tmp_path):
    room = tmp_path / "room.jpg"
    solid((5, 5, 5)).save(str(room))
    with pytest.raises(s.SwapError):
        s.swap(str(room), "FA-XX-99", "sofa")


def test_swap_endpoint_shape(monkeypatch):
    from app.main import app
    monkeypatch.setattr("app.api.chat.swap",
                        lambda *a, **k: {"result_url": "uploads/swap/r.jpg",
                                         "mask_url": "uploads/swap/m.png",
                                         "scores": {"color": 9,
                                                     "pattern": 9,
                                                     "scale": 8,
                                                     "isolation": 8},
                                         "attempts": 1})
    client = TestClient(app)
    resp = client.post("/api/swap", json={"session_id": "s",
                                          "image_path": "data/samples/living.jpg",
                                          "fabric_code": "FA-NL-02"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["attempts"] == 1
    assert body["scores"]["color"] == 9


def test_swap_endpoint_unknown_fabric():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/api/swap", json={"session_id": "s",
                                          "image_path": "uploads/x.jpg",
                                          "fabric_code": "FA-XX-99"})
    assert resp.status_code == 400


def test_preview_store_roundtrip():
    from app.api import chat as chat_api
    chat_api.PREVIEWS.clear()
    res = {"result_url": "uploads/swap/r.jpg",
           "mask_url": "uploads/swap/m.png",
           "scores": {"color": 9, "pattern": 9, "scale": 9,
                      "isolation": 9},
           "attempts": 1}
    chat_api.record_preview("sess-1", "FA-NL-02", res)
    got = chat_api.get_previews("sess-1")
    assert len(got) == 1
    assert got[0]["fabric_code"] == "FA-NL-02"
    assert got[0]["scores"]["color"] == 9
    assert got[0]["created_at"] > 0
    assert chat_api.get_previews("other") == []
    chat_api.PREVIEWS.clear()


def test_preview_store_caps_length():
    from app.api import chat as chat_api
    chat_api.PREVIEWS.clear()
    res = {"result_url": "r.jpg", "mask_url": "m.png", "scores": {},
           "attempts": 1}
    for _ in range(chat_api.MAX_PREVIEWS + 5):
        chat_api.record_preview("sess-2", "FA-NL-02", res)
    assert len(chat_api.get_previews("sess-2")) == chat_api.MAX_PREVIEWS
    chat_api.PREVIEWS.clear()


def _box(size, box, fill=255):
    m = Image.new("L", size, 0)
    m.paste(fill, box)
    return m


def test_sofa_full_mask_cuts_out_the_wooden_base(monkeypatch):
    """SAM's sofa record covers the wooden plinth; the wood segment is
    subtracted so the swap leaves it alone."""
    size = (100, 100)
    sofa = [{"box": (0, 0, 100, 100), "frame_size": (100, 100)}]
    wood = [{"box": (0, 80, 100, 100), "frame_size": (100, 100)}]

    def fake_segment(img, concept, key=None, timeout=1):
        if concept == s.SOFA_WOOD_CONCEPT:
            return wood
        if concept == s.TARGET_CONCEPTS["sofa"]:
            return sofa
        return []

    def fake_sam_mask(records, sz):
        return _box(sz, tuple(records[0]["box"]))

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask", fake_sam_mask)
    _, mask = s.sofa_full_mask(b"x", size, "k", 5)
    assert mask.getpixel((50, 50)) == 255, "upholstery stays"
    assert mask.getpixel((50, 90)) == 0, "wood is cut out"


def test_sofa_full_mask_ignores_a_wood_mask_that_is_the_whole_sofa(
        monkeypatch):
    size = (100, 100)
    rec = [{"box": (0, 0, 100, 100), "frame_size": (100, 100)}]

    def fake_segment(img, concept, key=None, timeout=1):
        # Sofa, cushions and "wood" all come back as the whole sofa.
        if concept == s.TARGET_CONCEPTS["cushions"]:
            return []
        return rec

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, sz: _box(sz, (0, 0, 100, 100)))
    _, mask = s.sofa_full_mask(b"x", size, "k", 5)
    assert mask.getpixel((50, 50)) == 255, "a whole-sofa wood mask is ignored"


def test_edit_prompt_protects_wood_for_sofa_not_pillows():
    fabric = {"name_en": "X", "material": "velvet", "primary_color": "red",
              "pattern_type": "plain"}
    assert "wooden" in s.edit_prompt(fabric, "sofa")
    assert "wooden" not in s.edit_prompt(
        fabric, s.TARGET_CONCEPTS["cushions"])


def test_needs_retry_only_on_checks_or_motif_scores():
    ok = {"ok": True}
    assert s.needs_retry({"ok": False}, {"color": 9, "pattern": 9,
                                         "scale": 9, "isolation": 9})
    assert not s.needs_retry(ok, {"color": 4, "pattern": 7, "scale": 6,
                                  "isolation": 3}), \
        "colour and isolation are covered deterministically"
    assert s.needs_retry(ok, {"color": 9, "pattern": 5, "scale": 9,
                              "isolation": 9})
    assert s.needs_retry(ok, {"color": 9, "pattern": 9, "scale": 5,
                              "isolation": 9})


def test_single_swap_composites_only_inside_the_mask(tmp_path, monkeypatch):
    """The model re-renders the whole frame; only the masked item may
    change in the result (the wooden base keeps the photo's pixels)."""
    from app.services import swap_checks as sc
    from app.services.catalog import get_fabric
    fabric = get_fabric("FA-AC-01")
    swatch = Image.open(os.path.join(os.getcwd(), fabric["image"]))
    want = swatch.convert("RGB").resize((1, 1), Image.BOX).getpixel((0, 0))
    size = (160, 120)
    room = tmp_path / "room.jpg"
    solid((120, 120, 120), size).save(str(room))
    item = (40, 40, 120, 100)
    monkeypatch.setattr(s, "require_api_key", lambda: "k")
    monkeypatch.setattr(s, "sofa_full_mask",
                        lambda *a, **k: ([{"box": item, "frame_size": size}],
                                         _box(size, item)))
    # No occluders in this photo (the refinement pass finds no gap).
    monkeypatch.setattr(s, "segment", lambda *a, **k: [])
    # The edit paints the WHOLE image in the new colour (as if the model
    # recoloured the wood and the wall too).
    monkeypatch.setattr(s, "edit_room", lambda *a, **k: solid(want, size))
    monkeypatch.setattr(s, "verify", lambda *a, **k: {
        "color": 9, "pattern": 9, "scale": 9, "isolation": 9})
    res = s.swap(str(room), "FA-AC-01", "sofa", out_dir=str(tmp_path))
    assert res["checks"]["ok"] and res["attempts"] == 1
    out = Image.open(os.path.join(os.getcwd(), res["result_url"])).convert(
        "RGB")
    # Well clear of the 6px feather; JPEG noise allowed.
    outside = out.getpixel((8, 8))
    assert all(abs(c - 120) <= 3 for c in outside), (
        "outside untouched", outside)
    inside = out.getpixel((80, 70))
    assert sc.delta_e2000(sc._srgb_to_lab([c / 255.0 for c in inside]),
                          sc._srgb_to_lab([c / 255.0 for c in want])) < 3


def test_upload_caps_the_photo_side(tmp_path):
    from app.api import chat as chat_api
    big = tmp_path / "big.jpg"
    Image.new("RGB", (3000, 4000), (90, 90, 90)).save(str(big), quality=60)
    im = chat_api._open_photo(str(big))
    assert max(im.size) == chat_api.PHOTO_MAX_SIDE == 2048
    assert im.size == (1536, 2048)


def test_plain_fabric_ignores_spark_pattern_score():
    ok = {"ok": True}
    low = {"color": 9, "pattern": 0, "scale": 9, "isolation": 9}
    assert not s.needs_retry(ok, low, {"plain_or_patterned": "plain"})
    assert s.needs_retry(ok, low, {"plain_or_patterned": "patterned"})
    assert s.needs_retry(ok, {"color": 9, "pattern": 0, "scale": 4,
                              "isolation": 9}, {"plain_or_patterned": "plain"})


def test_gap_mask_fills_concavities_not_occluders():
    """The notch a throw cuts into the seat mask is a candidate sliver;
    the throw itself (an occluder) and the open room are not."""
    size = (200, 200)
    seat = _box(size, (40, 40, 160, 160))
    seat.paste(0, (90, 40, 110, 100))          # notch under a "throw"
    throw = _box(size, (92, 40, 108, 70))       # the throw covers its top
    gap = s.gap_mask(seat, throw, close_frac=0.2, ring_frac=0.0)
    assert gap.getpixel((100, 90)) == 255, "seat strip below the throw"
    assert gap.getpixel((100, 50)) == 0, "the throw itself is excluded"
    assert gap.getpixel((20, 20)) == 0 and gap.getpixel((100, 180)) == 0
    assert s.mask_share(gap, seat) > 0.01


def test_single_swap_refines_the_sliver_past_an_occluder(tmp_path,
                                                         monkeypatch):
    """SAM's seat mask has a notch where a throw sits; the strict
    composite leaves that strip in the old colour and the second, aimed
    edit recolours it (and only it)."""
    from app.services.catalog import get_fabric
    fabric = get_fabric("FA-AC-01")
    swatch = Image.open(os.path.join(os.getcwd(), fabric["image"]))
    want = swatch.convert("RGB").resize((1, 1), Image.BOX).getpixel((0, 0))
    size = (200, 200)
    room = tmp_path / "room.jpg"
    solid((120, 120, 120), size).save(str(room))
    seat = _box(size, (40, 40, 160, 160))
    seat.paste(0, (90, 40, 110, 100))                  # notch
    monkeypatch.setattr(s, "require_api_key", lambda: "k")
    throw = _box(size, (92, 40, 108, 70))             # covers the notch top

    def fake_segment(img, concept, key=None, timeout=1):
        if concept in ("armchair", "throw blanket"):
            return [{"concept": concept, "box": (0, 0, 1, 1),
                     "frame_size": size}]
        return []
    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask", lambda records, sz: (
        seat if records[0]["concept"] == "armchair" else throw))
    monkeypatch.setattr(s, "REFINE_CLOSE_FRAC", 0.2)
    # Both edits paint the whole frame in the new colour.
    monkeypatch.setattr(s, "edit_room", lambda *a, **k: solid(want, size))
    monkeypatch.setattr(s, "verify", lambda *a, **k: {
        "color": 9, "pattern": 9, "scale": 9, "isolation": 9})
    res = s.swap(str(room), "FA-AC-01", "armchair", out_dir=str(tmp_path))
    assert res["checks"]["ok"] and res["checks"].get("refined", 0) > 0.01
    out = Image.open(os.path.join(os.getcwd(), res["result_url"])).convert(
        "RGB")
    strip = out.getpixel((100, 90))
    assert all(abs(a - b) <= 12 for a, b in zip(strip, want)), (
        "notch recoloured", strip)
    wall = out.getpixel((10, 10))
    assert all(abs(c - 120) <= 3 for c in wall), ("room untouched", wall)
    # The throw sits inside the seat's notch, within the first pass's
    # 6px feather, so it carries a faint tint; it must not be recoloured.
    throw_px = out.getpixel((100, 50))
    assert max(abs(a - b) for a, b in zip(throw_px, want)) > 40, (
        "throw not recoloured", throw_px, want)


def test_match_score_ignores_pattern_for_plain_fabrics():
    scores = {"color": 9, "pattern": 0, "scale": 9, "isolation": 10}
    assert s.match_score(scores, {"plain_or_patterned": "plain"}) == 9
    assert s.match_score(scores, {"plain_or_patterned": "patterned"}) == 0
    assert s.match_score(scores, None) == 0
    assert s.match_score({"color": 7, "scale": 8, "isolation": 9,
                          "pattern": 9}, {"plain_or_patterned": "plain"}) == 7


def test_sofa_full_mask_falls_back_to_the_seat_cushion(monkeypatch):
    """A bench seat has no 'sofa' for SAM; the seat cushion prompt
    finds the upholstered part so the swap does not report
    'not visible in this photo'."""
    size = (100, 100)
    seat = [{"box": (0, 50, 100, 100), "frame_size": (100, 100)}]
    asked = []

    def fake_segment(img, concept, key=None, timeout=1):
        asked.append(concept)
        if concept == "seat cushion":
            return seat
        return []

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, sz: _box(sz, tuple(records[0]["box"])))
    records, mask = s.sofa_full_mask(b"x", size, "k", 5)
    assert records == seat
    assert mask.getpixel((50, 75)) == 255
    assert mask.getpixel((50, 25)) == 0
    assert "seat cushion" in asked


def test_sofa_full_mask_still_fails_when_nothing_is_upholstered(
        monkeypatch):
    monkeypatch.setattr(s, "segment",
                        lambda img, concept, key=None, timeout=1: [])
    with pytest.raises(s.SwapError, match="could not find the sofa"):
        s.sofa_full_mask(b"x", (10, 10), "k", 5)


def test_pillow_guard_keeps_the_edited_pillows_out_of_the_paste(monkeypatch):
    """The edit redraws a pillow bigger than the photo's; its overhang
    must not be pasted (the ghost second pillow)."""
    size = (100, 100)
    seat = _box(size, (0, 40, 100, 100))
    # SAM finds the redrawn pillow at 30..60 x 40..75 on the edited image.
    monkeypatch.setattr(s, "segment", lambda img, concept, key=None, timeout=1: [
        {"box": (30, 40, 60, 75), "frame_size": (100, 100)}])
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, sz: _box(sz, tuple(records[0]["box"])))
    out = s.pillow_guard(Image.new("RGB", size, (90, 60, 40)), seat, "k", 5, size)
    assert out.getpixel((45, 60)) == 0, "redrawn pillow left out"
    assert out.getpixel((45, 75)) == 0, "and a dilated margin around it"
    assert out.getpixel((10, 90)) == 255, "the seat body still pastes"


def test_pillow_guard_leaves_the_mask_when_nothing_or_too_much_is_found(
        monkeypatch):
    size = (100, 100)
    seat = _box(size, (0, 40, 100, 100))
    edited = Image.new("RGB", size, (90, 60, 40))
    monkeypatch.setattr(s, "segment",
                        lambda img, concept, key=None, timeout=1: [])
    assert s.pillow_guard(edited, seat, "k", 5, size) is seat
    # A "pillow" mask covering most of the seat is the seat cushions,
    # not throw pillows: ignore it.
    monkeypatch.setattr(s, "segment", lambda img, concept, key=None, timeout=1: [
        {"box": (0, 40, 100, 100), "frame_size": (100, 100)}])
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, sz: _box(sz, tuple(records[0]["box"])))
    assert s.pillow_guard(edited, seat, "k", 5, size) is seat
    # A SAM failure never breaks the composite.
    def boom(img, concept, key=None, timeout=1):
        raise s.SwapError("down")
    monkeypatch.setattr(s, "segment", boom)
    assert s.pillow_guard(edited, seat, "k", 5, size) is seat


def test_cushions_fall_back_to_a_bed_pillow(monkeypatch):
    """"throw pillows on the sofa" finds nothing on a floor mattress;
    the cushions swap then asks SAM for a plain pillow."""
    asked = []

    def fake_segment(img, concept, key=None, timeout=1):
        asked.append(concept)
        if concept == "pillow":
            return [{"box": (10, 10, 50, 40), "frame_size": (100, 100)}]
        return []

    monkeypatch.setattr(s, "segment", fake_segment)
    recs = s.segment_with_fallback(b"x", s.TARGET_CONCEPTS["cushions"],
                                   "cushions", "k", 5)
    assert recs and asked == [s.TARGET_CONCEPTS["cushions"], "pillow"]
    assert s.segment_with_fallback(b"x", "window curtains", "curtains",
                                   "k", 5) == []


def test_partial_pillows_retry_rank_and_corrective():
    ok = {"ok": True, "pieces": {"covered": 4, "total": 6}}
    full = {"ok": True, "pieces": {"covered": 6, "total": 6}}
    good = {"color": 9, "pattern": 9, "scale": 9, "isolation": 9}
    assert s.needs_retry(ok, good)
    assert not s.needs_retry(full, good)
    assert s.pieces_missing(ok) == 2 and s.pieces_missing({"ok": True}) == 0
    weaker = {"color": 7, "pattern": 7, "scale": 7, "isolation": 7}
    assert s._rank({"scores": weaker, "checks": full}) > \
        s._rank({"scores": good, "checks": ok})
    text = s._corrective(good, "throw pillows on the sofa", ok)
    assert "EVERY pillow" in text and "6" in text and "2" in text
    assert s.min_changed_for({"plain_or_patterned": "patterned"}) == \
        s.PATTERN_MIN_CHANGED
    assert s.min_changed_for({"plain_or_patterned": "plain"}) == 0.0


def test_refine_pieces_recolours_the_skipped_pillows(monkeypatch):
    """Two pillows, the first edit did one; the aimed pass paints the
    other and only that pillow is pasted and counted."""
    size = (100, 60)
    left = _box(size, (5, 5, 45, 55))
    right = _box(size, (55, 5, 95, 55))
    room = solid((120, 120, 120), size)
    yellow = (240, 200, 40)
    first = room.copy()
    first.paste(solid(yellow, size), (0, 0), left)
    best = {"result": first, "mask": left, "scores": {"color": 9},
            "checks": {"ok": True, "pieces": {"covered": 1, "total": 2}}}
    swatch = io.BytesIO()
    solid(yellow).save(swatch, "PNG")
    monkeypatch.setattr(s, "edit_room",
                        lambda *a, **k: solid(yellow, (1, 1)))
    out = s.refine_pieces(best, room, [left, right], swatch.getvalue(),
                          {"code": "X"}, "throw pillows on the sofa", "k",
                          remaining_s=60, timeout=10)
    assert out["checks"]["pieces"] == {"covered": 2, "total": 2}
    assert out["checks"]["refine_pieces"] == 1
    assert out["result"].getpixel((75, 30))[:3] == yellow
    outside = out["result"].getpixel((50, 2))[:3]
    assert max(abs(c - 120) for c in outside) <= 6, \
        "nothing outside the pillows changes (feather aside): %r" % (outside,)
    assert out["mask"].getpixel((75, 30)) == 255
