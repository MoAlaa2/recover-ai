"""Fabric swap tests (model calls are faked or offline)."""
import io
import numpy as np
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
    left = _box(size, (10, 10, 40, 50))
    right = _box(size, (60, 10, 90, 50))
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
    outside = out["result"].getpixel((50, 30))[:3]
    assert max(abs(c - 120) for c in outside) <= 6, \
        "nothing outside the pillows changes (feather aside): %r" % (outside,)
    assert out["mask"].getpixel((75, 30)) == 255


def test_fill_holes_closes_enclosed_gaps_only():
    from PIL import ImageDraw
    m = Image.new("L", (200, 120), 0)
    d = ImageDraw.Draw(m)
    d.rectangle((20, 20, 180, 100), fill=255)
    d.rectangle((90, 40, 110, 60), fill=0)     # a shadow patch: enclosed
    d.rectangle((120, 0, 140, 100), fill=0)    # open to the border: kept
    out = s.fill_holes(m)
    assert out.getpixel((100, 50)) == 255
    assert out.getpixel((130, 50)) == 0 and out.getpixel((5, 5)) == 0
    # A hole bigger than the share limit is a real opening.
    big = Image.new("L", (200, 120), 0)
    ImageDraw.Draw(big).rectangle((0, 0, 199, 119), fill=255)
    ImageDraw.Draw(big).rectangle((40, 30, 160, 90), fill=0)
    assert s.fill_holes(big, max_share=0.08).getpixel((100, 60)) == 0


def test_sofa_full_mask_adds_the_arm_panels_near_the_sofa(monkeypatch):
    """SAM's "sofa" record drops the right arm's outer face; the
    armrest records that touch the sofa box are unioned in, a chair's
    arm across the room is not."""
    size = (200, 100)
    sofa = [{"box": (20, 20, 150, 90), "frame_size": (200, 100)}]
    arms = [{"box": (150, 40, 170, 90), "frame_size": (200, 100)},
            {"box": (185, 40, 199, 90), "frame_size": (200, 100)}]

    def fake_segment(img, concept, key=None, timeout=1):
        if concept == s.TARGET_CONCEPTS["sofa"]:
            return sofa
        if concept == s.SOFA_ARM_CONCEPT:
            return arms
        return []

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, sz: _union(sz, records))
    _, mask = s.sofa_full_mask(b"x", size, "k", 5)
    assert mask.getpixel((160, 60)) == 255, "adjacent arm joins the sofa"
    assert mask.getpixel((192, 60)) == 0, "a far arm is not the sofa"
    assert s._box_touches(arms[0], sofa) and not s._box_touches(arms[1], sofa)


def test_sofa_full_mask_adds_the_backrest_behind_a_stain(monkeypatch):
    """The sofa record stops short of a stained back cushion; the
    backrest record fills it in, and the pillows still come out."""
    size = (200, 100)
    sofa = [{"box": (20, 40, 180, 90), "frame_size": (200, 100)}]
    back = [{"box": (20, 10, 180, 45), "frame_size": (200, 100)}]
    pillow = [{"box": (30, 20, 60, 50), "frame_size": (200, 100)}]

    def fake_segment(img, concept, key=None, timeout=1):
        if concept == s.TARGET_CONCEPTS["sofa"]:
            return sofa
        if concept == s.SOFA_BACK_CONCEPT:
            return back
        if concept == s.TARGET_CONCEPTS["cushions"]:
            return pillow
        return []

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask",
                        lambda records, sz: _union(sz, records))
    _, mask = s.sofa_full_mask(b"x", size, "k", 5)
    assert mask.getpixel((120, 25)) == 255, "backrest joins the sofa"
    assert mask.getpixel((45, 35)) == 0, "the pillow is still cut out"
    assert mask.getpixel((100, 70)) == 255


def _union(size, records):
    out = Image.new("L", size, 0)
    for r in records:
        out.paste(255, tuple(int(v) for v in r["box"]))
    return out


def test_sofa_mask_drops_the_armchair_beside_it(monkeypatch):
    """SAM's sofa record covered the sofa AND the armchair; the edit
    recoloured the sofa only and coverage failed at 70%. The armchair
    is cut out when it is a distinct, smaller piece."""
    size = (200, 100)
    sofa = [{"box": (10, 30, 190, 90), "frame_size": (200, 100)}]   # swallows the chair
    chair = [{"box": (140, 40, 190, 90), "frame_size": (200, 100)}]

    def fake_segment(img, concept, key=None, timeout=1):
        if concept == s.TARGET_CONCEPTS["sofa"]:
            return sofa
        if concept == s.TARGET_CONCEPTS["armchair"]:
            return chair
        return []

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask", lambda records, sz: _union(sz, records))
    _, mask = s.sofa_full_mask(b"x", size, "k", 5)
    assert mask.getpixel((60, 60)) == 255, "sofa stays"
    assert mask.getpixel((170, 70)) == 0, "the armchair is cut out"
    # The whole seat is "the other seat" (SAM returned the same object
    # for both prompts): nothing is cut.
    same = _union(size, sofa)
    assert s.separate_seats(same, sofa, size).getpixel((170, 70)) == 255


def test_open_mask_drops_a_leg_sliver_and_keeps_the_arm():
    size = (800, 400)
    m = Image.new("L", size, 0)
    m.paste(255, (100, 100, 700, 300))      # body
    m.paste(255, (100, 300, 108, 380))      # 8 px leg sliver hanging off it
    m.paste(255, (60, 100, 100, 300))       # 40 px arm
    out = s.open_mask(m, 0.014)
    assert out.getpixel((104, 350)) == 0, "leg sliver dropped"
    assert out.getpixel((80, 200)) == 255, "arm kept"
    assert out.getpixel((400, 200)) == 255


def test_sofa_full_mask_cuts_the_legs_out(monkeypatch):
    size = (200, 100)
    sofa = [{"box": (20, 20, 180, 90), "frame_size": (200, 100)}]
    legs = [{"box": (22, 80, 30, 90), "frame_size": (200, 100)},
            {"box": (170, 80, 178, 90), "frame_size": (200, 100)}]

    def fake_segment(img, concept, key=None, timeout=1):
        if concept == s.TARGET_CONCEPTS["sofa"]:
            return sofa
        if concept == s.SOFA_LEGS_CONCEPT:
            return legs
        return []

    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask", lambda records, sz: _union(sz, records))
    monkeypatch.setattr(s, "open_mask", lambda m, *a, **k: m)
    _, mask = s.sofa_full_mask(b"x", size, "k", 5)
    assert mask.getpixel((25, 85)) == 0 and mask.getpixel((174, 85)) == 0
    assert mask.getpixel((100, 50)) == 255


def test_paste_strict_feathers_outward_no_halo():
    """Every pixel inside the mask takes the edited colour at full
    opacity; the soft edge lies outside the mask."""
    size = (120, 80)
    orig = solid((120, 120, 120), size)
    edit = solid((240, 200, 40), size)
    mask = _box(size, (30, 20, 90, 60))
    out = s.paste_strict(orig, edit, mask, feather=6)
    arr = np.asarray(out).astype(int)
    inside = arr[21:59, 31:89]
    assert np.abs(inside - np.array([240, 200, 40])).max() <= 2, "no ring of the old colour inside"
    # 1 px inside the edge is still full opacity
    assert np.abs(arr[20, 60] - np.array([240, 200, 40])).max() <= 3
    # Far outside the mask the original is untouched
    assert tuple(arr[5, 5]) == (120, 120, 120)
    assert tuple(arr[75, 115]) == (120, 120, 120)


def test_curtains_judged_per_panel_and_no_retry_for_the_sheer(monkeypatch):
    """SAM's curtains mask takes the sheer between the drapes; the editor
    leaves the sheer white. Curtains are judged per record like pillows,
    and a panel left alone does not cost a second edit (pillows do)."""
    monkeypatch.setattr(s, "sam_mask", lambda recs, size: Image.new(
        "L", size, 255))
    recs = [{"label": "curtain"}, {"label": "curtain"}]
    assert len(s.piece_masks("curtains", recs, (40, 30))) == 2
    assert len(s.piece_masks("cushions", recs, (40, 30))) == 2
    assert s.piece_masks("sofa", recs, (40, 30)) is False
    partial = {"ok": True, "pieces": {"covered": 2, "total": 3}}
    good = {"color": 9, "pattern": 9, "scale": 9, "isolation": 9}
    assert s.needs_retry(partial, good, retry_missing=True)
    assert not s.needs_retry(partial, good, retry_missing=False)
    assert s.needs_retry({"ok": False, "pieces": {"covered": 0,
                                                 "total": 3}}, good,
                         retry_missing=False)


def test_curtain_mask_grows_into_the_recoloured_hem():
    """SAM's drape record stops above the hem; the editor recolours the
    hem too. The mask grows into adjacent pixels that were the old
    fabric and are now the new one, and nowhere else (the wall the
    editor also touched stays out; a far-away patch stays out)."""
    w, h = 200, 150
    sage, terracotta, wall = (120, 140, 110), (190, 100, 70), (235, 232, 225)
    orig = Image.new("RGB", (w, h), wall)
    from PIL import ImageDraw
    ImageDraw.Draw(orig).rectangle((40, 10, 90, 130), fill=sage)   # drape + hem
    ImageDraw.Draw(orig).rectangle((40, 125, 90, 130), fill=(60, 70, 55))  # hem in shadow
    ImageDraw.Draw(orig).rectangle((150, 100, 190, 140), fill=sage)  # far patch
    edited = Image.new("RGB", (w, h), (200, 190, 180))              # wall retouched
    ImageDraw.Draw(edited).rectangle((40, 10, 90, 130), fill=terracotta)
    ImageDraw.Draw(edited).rectangle((150, 100, 190, 140), fill=terracotta)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle((40, 10, 90, 124), fill=255)      # no hem
    buf = io.BytesIO(); Image.new("RGB", (8, 8), terracotta).save(buf, "PNG")
    out = np.asarray(s.grow_to_recoloured(orig, edited, mask, buf.getvalue()))
    assert out[128, 60] > 127            # hem joined
    assert out[5, 60] == 0 and out[60, 110] == 0   # wall stays out
    assert out[120, 170] == 0            # far patch stays out
    same = io.BytesIO(); Image.new("RGB", (8, 8), sage).save(same, "PNG")
    assert np.array_equal(np.asarray(s.grow_to_recoloured(
        orig, edited, mask, same.getvalue())), np.asarray(mask))


def test_sofa_mask_takes_a_touching_bench_but_not_a_far_or_bigger_one(monkeypatch):
    """A majlis: SAM's "sofa" record is the side seats; the bench under
    the window comes back under "upholstered bench seat". A bench that
    touches the sofa and is no bigger joins the mask; a bench across the
    room, or one bigger than the sofa, does not."""
    size = (200, 100)
    def rec(box):
        return {"box": box, "frame_size": size}
    def fake_segment(img, concept, key=None, timeout=1):
        if concept == s.TARGET_CONCEPTS["sofa"]:
            return [rec((0, 40, 60, 90))]
        if concept == s.SOFA_BENCH_CONCEPT:
            return [rec((58, 50, 120, 90)), rec((150, 50, 199, 90)),
                    rec((0, 0, 199, 99))]
        return []
    def fake_sam_mask(records, sz):
        m = Image.new("L", sz, 0)
        from PIL import ImageDraw
        for r in records:
            ImageDraw.Draw(m).rectangle(r["box"], fill=255)
        return m
    monkeypatch.setattr(s, "segment", fake_segment)
    monkeypatch.setattr(s, "sam_mask", fake_sam_mask)
    monkeypatch.setattr(s, "open_mask", lambda m, frac=0.0, **k: m)
    _, mask = s.sofa_full_mask(b"x", size, "k", 5)
    a = np.asarray(mask) > 127
    assert a[70, 30] and a[70, 100]       # sofa and the touching bench
    assert not a[70, 175] and not a[10, 100]   # far bench, whole-frame record
