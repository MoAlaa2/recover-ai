"""The item the user picks (tap / chip / words) owns every preview and
assignment, whatever target the model passes; after the pick the
consultant asks at most one question and always offers Just show me."""
import json

from PIL import Image

from app.services import consultant as c


def tool_call(name, args, call_id="t1"):
    return {"choices": [{"message": {
        "content": None,
        "tool_calls": [{"id": call_id, "type": "function",
                        "function": {"name": name,
                                     "arguments": json.dumps(args)}}]}}]}


def final_text(text):
    return {"choices": [{"message": {"content": text}}]}


RECS = ("Here are my picks.\n```recommendations\n"
        "[{\"code\": \"FA-AC-12\", \"reason\": \"r1\"}, "
        "{\"code\": \"FA-AC-02\", \"reason\": \"r2\"}, "
        "{\"code\": \"FA-AC-03\", \"reason\": \"r3\"}]\n```")


def spy_search(args, turn):
    return {"fabrics": [{"code": "FA-AC-12"}, {"code": "FA-AC-02"},
                        {"code": "FA-AC-03"}],
            "relaxed": [], "relaxed_constraints": []}


def session_with_photo(tmp_path, sid):
    room = tmp_path / "room.jpg"
    Image.new("RGB", (64, 48), (10, 20, 30)).save(str(room))
    c.SESSIONS[sid] = {"messages": [], "lang": "en",
                       "image_path": str(room),
                       "available_targets": ["sofa", "cushions"]}
    return str(room)


def test_model_assign_cannot_retarget_user_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "run_search", spy_search)
    sid = "t-choice-wins"
    session_with_photo(tmp_path, sid)
    asked = {"n": 0}

    def fake(messages, tools=None):
        asked["n"] += 1
        if asked["n"] == 1:
            return final_text("Lovely. Warm or cool mood?\n```options\n"
                              "[\"Warm\", \"Cool\"]\n```")
        if asked["n"] == 2:
            return tool_call("search_catalog", {"usage": "upholstery"})
        if asked["n"] == 3:
            # The model guesses the sofa: it must not win.
            return tool_call("assign_fabric",
                             {"target": "sofa", "code": "FA-AC-12"}, "t2")
        return final_text(RECS)

    one = c.chat(sid, "Cushions", chat_fn=fake)
    assert one["targets"]["chosen"] == ["cushions"]
    assert one["recommendations"] == []
    assert "Just show me" in one["options"], one["options"]
    two = c.chat(sid, "Cool", chat_fn=fake)
    assert len(two["recommendations"]) == 3
    assert two["preview"] == {"code": "FA-AC-12", "target": "cushions"}
    assert two["targets"]["assignments"] == {"cushions": "FA-AC-12"}
    assert two["targets"]["chosen"] == ["cushions"]


def test_preview_tool_follows_user_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "run_search", spy_search)
    sid = "t-preview-choice"
    session_with_photo(tmp_path, sid)
    asked = {"n": 0}

    def fake(messages, tools=None):
        asked["n"] += 1
        if asked["n"] == 1:
            return final_text("Which mood?\n```options\n[\"Warm\"]\n```")
        if asked["n"] == 2:
            return tool_call("search_catalog", {})
        if asked["n"] == 3:
            return tool_call("preview_fabric",
                             {"code": "FA-AC-12", "target": "sofa"}, "t2")
        return final_text(RECS)

    c.chat(sid, "cushions please", chat_fn=fake)
    out = c.chat(sid, "Just show me", chat_fn=fake)
    assert out["targets"]["chosen"] == ["cushions"]
    assert out["preview"]["target"] == "cushions"


def test_second_question_after_choice_is_forced_to_recommend(
        tmp_path, monkeypatch):
    monkeypatch.setattr(c, "run_search", spy_search)
    sid = "t-one-question"
    session_with_photo(tmp_path, sid)
    seen = []

    def fake(messages, tools=None):
        seen.append(messages[-1]["content"])
        return final_text("Warm or cool?\n```options\n[\"Warm\"]\n```")

    one = c.chat(sid, "Cushions", chat_fn=fake)
    assert "ONE question at most" in seen[-1]
    assert one["options"][-1] == "Just show me"
    c.chat(sid, "Cool", chat_fn=fake)
    # The model asked a second time: the next turn carries the order to
    # recommend and the prefetch would fire if needs were known.
    c.chat(sid, "modern", chat_fn=fake)
    assert "[Recommend now" in seen[-1]
    assert "Do not ask another question" in seen[-1]


def test_just_show_me_is_localized():
    assert c.ensure_just_show_option(["Warm", "Cool"], "ar")[-1] == \
        "وريني الحين"
    assert c.ensure_just_show_option(["a", "b", "c", "d"], "en") == \
        ["a", "b", "c", "Just show me"]
    assert c.ensure_just_show_option(["Just show me"], "en") == \
        ["Just show me"]
    from app.services import targets as t
    for lang, line in c.JUST_SHOW_LINES.items():
        _, flags = t.match_targets(line, ["sofa", "cushions"])
        assert flags.get("skip"), (lang, line)
