"""SAM mask sanity: scores, per-record and merged coverage caps."""
import pytest
from PIL import Image

from app.services import sam_codec
from app.services import targets as t
from app.services.swap import sam_mask, SwapError


def _rec(score=1.0, box=(0, 0, 19, 19), frame=(20, 20), origin=(0, 0)):
    # Default box spans the whole 20x20 frame so the fake 20x20 rasters
    # below land on the full canvas and the coverage caps are exercised.
    return {"id": 0, "frame": 0, "box": box,
            "frame_size": frame, "score": score,
            "mask_origin": origin, "mask_size": (20, 20),
            "mask_encoding": "one_bit", "mask_payload": "!x"}


def _raster(white_frac, w=20, h=20, tail=False):
    n = w * h
    white = int(n * white_frac)
    body = [1] * white + [0] * (n - white)
    if tail:
        body = [0] * (n - white) + [1] * white
    return bytes(body), w, h


def test_parse_keeps_confidence(monkeypatch=None):
    line = ("0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10;c=0.31|>"
            "<|mask;x=0;y=0;c=0.77;data=5,5,!XXXXX|>")
    recs = sam_codec.parse_output_text(line)
    assert len(recs) == 1
    assert recs[0]["score"] == pytest.approx(0.77)


def test_parse_defaults_score_when_absent():
    line = ("0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>"
            "<|mask;x=0;y=0;data=5,5,!XXXXX|>")
    recs = sam_codec.parse_output_text(line)
    assert recs[0]["score"] == 1.0


def _patch_decode(monkeypatch, fracs):
    it = iter(fracs)

    def fake(record):
        frac = next(it)
        if isinstance(frac, tuple):
            return _raster(*frac)
        return _raster(frac)
    monkeypatch.setattr(sam_codec, "decode_record", fake)


def test_low_score_record_dropped(monkeypatch):
    _patch_decode(monkeypatch, [0.5])
    with pytest.raises(SwapError):
        sam_mask([_rec(score=0.1)], (20, 20))


def test_full_frame_record_dropped(monkeypatch):
    _patch_decode(monkeypatch, [1.0, 0.05])
    mask = sam_mask([_rec(), _rec()], (20, 20))
    white = sum(mask.histogram()[128:])
    assert white / 400 <= 0.60


def test_merged_full_frame_raises(monkeypatch):
    _patch_decode(monkeypatch, [(0.4, 20, 20, False),
                                (0.35, 20, 20, True)])
    with pytest.raises(SwapError):
        sam_mask([_rec(), _rec()], (20, 20))


def test_sane_small_mask_kept(monkeypatch):
    _patch_decode(monkeypatch, [0.05])
    mask = sam_mask([_rec()], (20, 20))
    white = sum(mask.histogram()[128:])
    assert 0 < white / 400 <= 0.60


def _white(w, h):
    return bytes([1] * (w * h)), w, h


def _assert_placed(mask, size):
    width, height = size
    white = sum(mask.histogram()[128:])
    assert white == 50 * 40
    assert white / (width * height) == pytest.approx(0.0025)
    px = mask.load()
    assert px[100, 200] == 255 and px[149, 239] == 255
    assert px[99, 200] == 0 and px[100, 199] == 0
    assert px[150, 239] == 0 and px[149, 240] == 0
    assert px[0, 0] == 0 and px[width - 1, height - 1] == 0


def test_cropped_record_pasted_at_box_origin(monkeypatch):
    # Real SAM shape: raster is box-sized (w+1 x h+1), mask x,y = 0.
    monkeypatch.setattr(sam_codec, "decode_record", lambda r: _white(50, 40))
    rec = _rec(box=(100, 200, 149, 239), frame=(1000, 800))
    _assert_placed(sam_mask([rec], (1000, 800)), (1000, 800))


def test_mask_origin_offsets_from_box_corner(monkeypatch):
    monkeypatch.setattr(sam_codec, "decode_record", lambda r: _white(50, 40))
    rec = _rec(box=(0, 0, 999, 799), frame=(1000, 800), origin=(100, 200))
    _assert_placed(sam_mask([rec], (1000, 800)), (1000, 800))


def test_cropped_record_scales_to_room_size(monkeypatch):
    monkeypatch.setattr(sam_codec, "decode_record", lambda r: _white(50, 40))
    rec = _rec(box=(100, 200, 149, 239), frame=(1000, 800))
    mask = sam_mask([rec], (500, 400))
    white = sum(mask.histogram()[128:])
    assert white / (500 * 400) == pytest.approx(0.0025, rel=0.05)
    px = mask.load()
    assert px[50, 100] == 255 and px[74, 119] == 255
    assert px[49, 100] == 0 and px[75, 119] == 0


def test_subtract_skipped_when_cushions_garbage():
    sofa = Image.new("L", (40, 40), 200)
    cushions = Image.new("L", (40, 40), 200)
    out = t._subtract_cushions(sofa, cushions)
    assert list(out.getdata()) == list(sofa.getdata())


def test_masks_for_hides_garbage_target(monkeypatch, tmp_path):
    from PIL import Image as PILImage
    p = tmp_path / "room.jpg"
    PILImage.new("RGB", (40, 30), (9, 9, 9)).save(str(p))
    monkeypatch.setattr(t, "segment", lambda *a, **k: [{"id": 1}])
    monkeypatch.setattr(
        t, "sam_mask",
        lambda records, size: (_ for _ in ()).throw(
            SwapError("target covers the whole photo, not detected")))
    assert t.masks_for(str(p), ["sofa"]) == {}
