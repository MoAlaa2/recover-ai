"""A7-A10: repeated-reply guard, auto-apply, photo reset, grounding."""
from app.services import consultant as C


def test_a7_guard_strips_blocks_before_compare():
    prev = "Which fabric do you like?\n```options\n[\"a\",\"b\"]\n```"
    reply = "Which fabric do you like?"
    # Raw comparison scores low (the old bug); stripped scores 1.0.
    assert C.similar_reply(reply, prev) < 0.9
    prev_clean = C.strip_options(C.strip_block(prev))
    reply_clean = C.strip_options(C.strip_block(reply))
    assert C.similar_reply(reply_clean, prev_clean) >= 0.9


def test_a8_auto_apply_uses_session_image():
    import inspect

    src = inspect.getsource(C._chat)
    assert 'turn.get("image")' in src


def test_a9_new_photo_resets_targets():
    import inspect

    src = inspect.getsource(C._chat)
    assert 'session["available_targets"] = []' in src
    assert 'session["chosen_targets"] = []' in src
    assert 'session["assignments"] = {}' in src


def test_a10_rejects_duplicates_and_get_fabric_does_not_seed_seen():
    import inspect

    seen = ["FA-LN-01", "FA-LN-02", "FA-LN-03"]
    recs = [{"code": seen[0]}, {"code": seen[0]}, {"code": seen[0]}]
    got, bad = C.valid_recommendations(recs, seen)
    assert got is None and bad == seen[0]
    src = inspect.getsource(C._execute_tool)
    # get_fabric branch must not append to seen anymore.
    branch = src.split('if name == "get_fabric":')[1].split(
        'if name == "preview_fabric":')[0]
    assert 'turn["seen"].append' not in branch


def test_a10_fallback_dedupes():
    import inspect

    src = inspect.getsource(C._chat)
    assert "dict.fromkeys(seen_codes)" in src


def _photo_turn(monkeypatch, tmp_path, sid, path, text="hello"):
    from PIL import Image as PILImage
    p = tmp_path / path
    PILImage.new("RGB", (32, 24), (1, 2, 3)).save(str(p))
    monkeypatch.setattr(C, "analyze_room", lambda *a, **k: {
        "room_type": "living", "furniture": "sofa", "wall_colors": [],
        "light_level": "high", "style": "modern"})
    return C.chat(sid, text, image_path=str(p),
                  chat_fn=lambda messages, tools=None: {
                      "choices": [{"message": {
                          "content": "Nice room. Which item first?"}}]})


def test_a9_new_photo_resets_items(monkeypatch, tmp_path):
    sid = "t-a9-reset"
    C.SESSIONS.pop(sid, None)
    _photo_turn(monkeypatch, tmp_path, sid, "one.jpg")
    C.SESSIONS[sid]["available_targets"] = ["sofa"]
    C.SESSIONS[sid]["chosen_targets"] = ["sofa"]
    C.SESSIONS[sid]["assignments"] = {"sofa": "FA-AC-01"}
    _photo_turn(monkeypatch, tmp_path, sid, "two.jpg")
    session = C.SESSIONS[sid]
    assert session["available_targets"] == []
    assert session["chosen_targets"] == []
    assert session["assignments"] == {}
    C.SESSIONS.pop(sid, None)


def test_a9_same_photo_keeps_items(monkeypatch, tmp_path):
    sid = "t-a9-keep"
    C.SESSIONS.pop(sid, None)
    out = _photo_turn(monkeypatch, tmp_path, sid, "same.jpg")
    C.SESSIONS[sid]["chosen_targets"] = ["sofa"]
    before = C.SESSIONS[sid]["image_path"]
    _photo_turn(monkeypatch, tmp_path, sid, "same.jpg")
    assert C.SESSIONS[sid]["image_path"] == before
    assert C.SESSIONS[sid]["chosen_targets"] == ["sofa"]
    C.SESSIONS.pop(sid, None)
