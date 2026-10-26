"""Consultant behavior tests (model calls are faked)."""
import json

from app.services import consultant as c
from app.services.catalog import (contains_egyptian, get_fabric, is_arabic,
                                  map_needs_to_features, search_catalog)


def tool_call(name, args, call_id="t1"):
    return {"choices": [{"message": {
        "content": None,
        "tool_calls": [{
            "id": call_id, "type": "function",
            "function": {"name": name,
                         "arguments": json.dumps(args)}}]}}]}


def final_text(text):
    return {"choices": [{"message": {"content": text}}]}


def block(codes):
    items = [{"code": code, "reason": "reason for %s" % code}
             for code in codes]
    return "Here are my picks.\n```recommendations\n%s\n```" % json.dumps(
        items, ensure_ascii=False)


def test_rejects_invented_codes():
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return tool_call("search_catalog", {"usage": "upholstery"})
        if calls["n"] == 2:
            return final_text(block(["FA-XX-99", "FA-VL-01", "FA-VL-02"]))
        return final_text(block(["FA-VL-01", "FA-VL-02", "FA-NL-01"]))

    out = c.chat("test-invented", "sofa fabric please", chat_fn=fake)
    codes = [r["code"] for r in out["recommendations"]]
    assert "FA-XX-99" not in codes
    assert codes == ["FA-VL-01", "FA-VL-02", "FA-NL-01"]
    assert all(get_fabric(code) for code in codes)


def test_feature_mapping():
    assert "pet-friendly" in map_needs_to_features("my dog ruins sofas")
    assert "scratch-resistant" in map_needs_to_features("we have a cat")
    kids = map_needs_to_features("kids spill everything")
    assert {"easy-clean", "stain-resistant", "antibacterial"} <= set(kids)
    assert "fire-resistant" in map_needs_to_features("hotel lobby chairs")
    assert "fire-resistant" in map_needs_to_features("كراسي مطعم")
    assert "blackout" in map_needs_to_features(
        "blackout bedroom curtains")
    assert "blackout" in map_needs_to_features("ستائر غرفة نوم")
    assert map_needs_to_features("just a blue sofa") == []


def test_arabic_reply_has_no_egyptian_markers():
    assert contains_egyptian("عايز قماش كده علشان الكنبة")
    assert contains_egyptian("ازيك، فين القماش الحلو؟")
    assert not contains_egyptian("أبغى قماش زين لمجلسي الحين")
    assert not contains_egyptian("ودي بستارة فاتحة للصالة")
    assert is_arabic("أبغى قماش")
    assert not is_arabic("I want fabric")
    assert "Saudi" in c.SYSTEM_PROMPT
    assert "عايز" in c.SYSTEM_PROMPT


def test_opening_turn_has_no_recommendations_or_tip():
    def fake(messages, tools=None):
        return final_text(
            "I'm ReCover, your luxury fabric consultant.\n"
            "I recommend fabrics, analyze room photos, and preview "
            "furniture in new fabrics.\n"
            "Which would you like to explore first?\n"
            "Tip: choose a high martindale for heavy use.")

    out = c.chat("test-opening", "hello", chat_fn=fake)
    assert out["recommendations"] == []
    assert "tip" not in out["reply"].lower()
    assert "تلميح" not in out["reply"]
    assert "نصيحة" not in out["reply"]


def test_relaxed_constraint_message():
    summaries, relaxed = search_catalog(usage="curtains", max_price=10)
    assert "max_price" in relaxed
    assert len(summaries) >= 3

    def fake(messages, tools=None):
        if not hasattr(fake, "n"):
            fake.n = 0
        fake.n += 1
        if fake.n == 1:
            return tool_call("search_catalog",
                             {"usage": "curtains", "max_price": 10})
        return final_text(block(["FA-LA-01", "FA-LA-02", "FA-LA-03"]))

    out = c.chat("test-relaxed", "cheap curtains", chat_fn=fake)
    assert "budget" in out["reply"].lower()
    assert len(out["recommendations"]) == 3
