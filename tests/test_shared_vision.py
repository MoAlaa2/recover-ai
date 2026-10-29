"""C2: one shared cached vision listing for chat + /targets, in parallel."""
import time

from app.services import consultant as C
from app.services import targets as T


def _room(tmp_path, name="room.jpg"):
    from PIL import Image as PILImage
    p = tmp_path / name
    PILImage.new("RGB", (48, 32), (4, 5, 6)).save(str(p))
    return str(p)


def test_listing_shared_with_targets(monkeypatch, tmp_path):
    calls = {"n": 0}

    def fake_list(image_path):
        calls["n"] += 1
        return ["sofa", "cushions"]

    monkeypatch.setattr(T, "list_types", fake_list)
    monkeypatch.setattr(T, "masks_for", lambda *a, **k: {})
    T.TARGETS_CACHE.clear()
    img = _room(tmp_path)
    assert T.available_types(img) == ["sofa", "cushions"]
    assert T.detect_targets(img) == []
    assert calls["n"] == 1, "chat and /targets must share one listing"


def _fake_chat_fn(text="Nice room. Which item first?"):
    return lambda messages, tools=None: {
        "choices": [{"message": {"content": text}}]}


def test_cold_photo_turn_calls_vision_once_each(monkeypatch, tmp_path):
    counts = {"analyze": 0, "listing": 0}

    def fake_analyze(path, lang=None):
        counts["analyze"] += 1
        return {"room_type": "living", "furniture": "sofa",
                "wall_colors": [], "light_level": "high",
                "style": "modern"}

    def fake_available(image_path, api_key=None):
        counts["listing"] += 1
        return ["sofa"]

    monkeypatch.setattr(C, "analyze_room", fake_analyze)
    monkeypatch.setattr(T, "available_types", fake_available)
    sid = "t-c2-once"
    C.SESSIONS.pop(sid, None)
    try:
        out = C.chat(sid, "hello", image_path=_room(tmp_path),
                     chat_fn=_fake_chat_fn())
        assert counts == {"analyze": 1, "listing": 1}
        assert out["targets"]["available"] == ["sofa"]
        before = dict(counts)
        C.chat(sid, "sofa", chat_fn=_fake_chat_fn())
        assert counts == before, "warm turn must reuse caches"
    finally:
        C.SESSIONS.pop(sid, None)


def test_listing_and_analysis_run_in_parallel(monkeypatch, tmp_path):
    def slow_analyze(path, lang=None):
        time.sleep(0.5)
        return {"room_type": "living", "furniture": "sofa",
                "wall_colors": [], "light_level": "high",
                "style": "modern"}

    def slow_available(image_path, api_key=None):
        time.sleep(0.5)
        return ["sofa"]

    monkeypatch.setattr(C, "analyze_room", slow_analyze)
    monkeypatch.setattr(T, "available_types", slow_available)
    sid = "t-c2-parallel"
    C.SESSIONS.pop(sid, None)
    try:
        t0 = time.time()
        C.chat(sid, "hello", image_path=_room(tmp_path),
               chat_fn=_fake_chat_fn())
        elapsed = time.time() - t0
        assert elapsed < 0.95, \
            "sequential vision would take >= 1.0s, took %.2fs" % elapsed
    finally:
        C.SESSIONS.pop(sid, None)
