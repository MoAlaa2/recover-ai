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


def test_budget_not_mentioned_when_nothing_relaxed():
    def fake(messages, tools=None):
        if not hasattr(fake, "n"):
            fake.n = 0
        fake.n += 1
        if fake.n == 1:
            return tool_call("search_catalog",
                             {"usage": "curtains", "max_price": 200})
        return final_text(block(["FA-LA-01", "FA-LA-02", "FA-LA-03"]))

    out = c.chat("test-no-relax", "curtains please", chat_fn=fake)
    assert "budget" not in out["reply"].lower()
    assert "الميزانية" not in out["reply"]
    assert len(out["recommendations"]) == 3


def test_pet_filter_is_or_and_pet_safe():
    summaries, relaxed = search_catalog(
        usage="upholstery",
        any_features=["pet-friendly", "scratch-resistant"],
        protected=["pet-friendly"], pet_safe=True, limit=10)
    assert summaries, "expected pet-safe matches"
    for item in summaries:
        full = get_fabric(item["code"])
        assert {"pet-friendly", "scratch-resistant"} & set(
            full["features"])
        assert "boucle" not in full["material"]
        assert full["pattern_type"] != "honeycomb"
    assert summaries[0]["material"] in ("performance velvet",
                                       "performance linen")


def test_piece_mismatch_asks_for_confirmation(monkeypatch):
    monkeypatch.setattr(
        c, "analyze_room",
        lambda path: {"furniture": "wingback armchair", "style": "classic"})
    out = c.chat("test-piece", "fabric for my sofa please",
                 image_path="data/catalog/FA-VL-01.jpg",
                 chat_fn=lambda messages, tools=None: final_text(
                     "Nice room. Which mood do you like?"))
    assert "armchair" in out["reply"]
    assert "sofa" in out["reply"]
    assert c.SESSIONS["test-piece"]["detected_piece"] == "armchair"
    assert out["recommendations"] == []


def test_every_fabric_has_snag_risk():
    from app.services.catalog import load_specs
    for item in load_specs():
        assert item.get("snag_risk") in ("low", "medium", "high"), \
            item["code"]


def test_snag_low_only_then_medium_fallback():
    strict, _ = search_catalog(
        usage="upholstery", snag_levels=["low"], pet_safe=True, limit=20)
    assert strict
    assert all(get_fabric(x["code"])["snag_risk"] == "low"
               for x in strict)


def test_snag_medium_widening_is_recorded(monkeypatch):
    import app.services.catalog as cat
    base = dict(name_en="T", name_ar="ت", material="cotton velvet",
                primary_color="red", secondary_colors=[], tone="warm",
                styles=["modern"], features=["stain-resistant"],
                suitable_for=["home"], opacity="opaque",
                price_sar_per_m=100, usage="upholstery",
                pattern_type="solid", image="")
    items = [dict(base, code="T-LOW-%d" % i, snag_risk="low")
             for i in range(2)]
    items += [dict(base, code="T-MED", snag_risk="medium")]
    items += [dict(base, code="T-HI", snag_risk="high")]
    monkeypatch.setattr(cat, "_SPECS", items)
    summaries, relaxed = search_catalog(
        usage="upholstery", snag_levels=["low"], limit=10)
    assert [s["code"] for s in summaries] == ["T-LOW-0", "T-LOW-1",
                                              "T-MED"]
    assert "snag_levels" in relaxed


def test_pet_turn_enforces_low_snag():
    turn = {"seen": [], "relaxed": [], "needs_any": ["pet-friendly"],
            "needs_all": ["easy-clean"], "protected": ["pet-friendly"],
            "pet_safe": True}
    result = c.run_search({"usage": "upholstery", "limit": 20}, turn)
    assert result["fabrics"]
    for summary in result["fabrics"]:
        assert get_fabric(summary["code"])["snag_risk"] in (
            "low", "medium")
    if any(get_fabric(s["code"])["snag_risk"] == "medium"
           for s in result["fabrics"]):
        assert "snag_levels" in turn["relaxed"]


def test_partial_mention_still_discloses_the_rest():
    def fake(messages, tools=None):
        if not hasattr(fake, "n"):
            fake.n = 0
        fake.n += 1
        if fake.n == 1:
            return tool_call("search_catalog",
                             {"usage": "upholstery", "max_price": 100,
                              "snag_levels": ["low"]})
        return final_text(
            "All three fit your budget.\n"
            + block(["FA-VL-01", "FA-VL-03", "FA-VL-04"]))

    import unittest.mock as mock
    real_search = c.search_catalog

    def wrapped(**kwargs):
        summaries, relaxed = real_search(**kwargs)
        if "max_price" not in relaxed:
            relaxed = relaxed + ["max_price"]
        if "snag_levels" not in relaxed:
            relaxed = relaxed + ["snag_levels"]
        return summaries, relaxed

    with mock.patch.object(c, "search_catalog", wrapped):
        out = c.chat("test-partial", "my cat needs sofa fabric",
                     chat_fn=fake)
    assert "claw-safe filter" in out["reply"]
    assert len(out["recommendations"]) == 3


def test_math_question_is_declined_without_model_call():
    def boom(messages, tools=None):
        raise AssertionError("model must not be called")

    out = c.chat("test-scope-math", "what is 1+1", chat_fn=boom)
    assert out["recommendations"] == []
    assert out["reply"] == ("That's outside my expertise — I'm here for "
                            "your fabrics and interiors. What fabric can I "
                            "help you with?")


def test_arabic_decline_without_model_call():
    def boom(messages, tools=None):
        raise AssertionError("model must not be called")

    out = c.chat("test-scope-ar", "من هو رئيس فرنسا؟", chat_fn=boom)
    assert out["recommendations"] == []
    assert "خارج تخصصي" in out["reply"]
    assert "أقمشتك" in out["reply"]


def test_decline_steers_back_to_known_topic():
    def boom(messages, tools=None):
        raise AssertionError("model must not be called")

    c.chat("test-scope-topic", "fabric for my sofa please",
           chat_fn=lambda messages, tools=None: final_text("noted"))
    out = c.chat("test-scope-topic", "who won the election", chat_fn=boom)
    assert out["reply"].endswith("your sofa?")


def test_velvet_cleaning_is_answered():
    def fake(messages, tools=None):
        return final_text("Vacuum velvet weekly with a soft brush.")

    out = c.chat("test-scope-care", "how do I clean velvet", chat_fn=fake)
    assert "outside my expertise" not in out["reply"].lower()
    assert "Vacuum" in out["reply"]


def _fit_of(code, required):
    return len(set(get_fabric(code)["features"]) & set(required))


def test_ranking_orders_by_functional_fit():
    turn = {"seen": [], "relaxed": [], "needs_any": [],
            "needs_all": ["easy-clean"], "protected": [],
            "pet_safe": False, "has_kids": False}
    res = c.run_search({"usage": "upholstery", "limit": 20}, turn)
    assert res["fabrics"]
    fits = [_fit_of(s["code"], ["easy-clean"]) for s in res["fabrics"]]
    assert fits == sorted(fits, reverse=True)


def test_kids_light_fabrics_demoted():
    from app.services import catalog as cat
    turn = {"seen": [], "relaxed": [], "needs_any": [],
            "needs_all": ["easy-clean"], "protected": [],
            "pet_safe": False, "has_kids": True}
    res = c.run_search({"usage": "upholstery", "limit": 20}, turn)
    order = []
    for s in res["fabrics"]:
        item = get_fabric(s["code"])
        order.append((s["code"], _fit_of(s["code"], ["easy-clean"]),
                      item.get("snag_risk"),
                      cat.is_light_unprotected(item)))
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        if (a[1], a[2]) == (b[1], b[2]):
            assert not a[3] or b[3]


def test_budget_preferred_when_fit_equal(monkeypatch):
    import app.services.catalog as cat
    base = dict(name_en="T", name_ar="ت", material="cotton velvet",
                primary_color="red", secondary_colors=[], tone="warm",
                features=["stain-resistant"], suitable_for=["home"],
                opacity="opaque", usage="upholstery",
                pattern_type="solid", image="", snag_risk="low")
    items = [dict(base, code="B-80", price_sar_per_m=80, styles=[]),
             dict(base, code="B-150", price_sar_per_m=150,
                  styles=["modern"]),
             dict(base, code="B-90", price_sar_per_m=90, styles=[])]
    monkeypatch.setattr(cat, "_SPECS", items)
    turn = {"seen": [], "relaxed": [], "needs_any": [], "needs_all": [],
            "protected": [], "pet_safe": False, "has_kids": False}
    res = c.run_search({"usage": "upholstery", "styles": ["modern"],
                        "max_price": 100, "limit": 10}, turn)
    assert [s["code"] for s in res["fabrics"]] == ["B-80", "B-90",
                                                  "B-150"]


def test_kids_light_note_mentions_fabric():
    def fake(messages, tools=None):
        if not hasattr(fake, "n"):
            fake.n = 0
        fake.n += 1
        if fake.n == 1:
            return tool_call("search_catalog", {"usage": "upholstery"})
        return final_text(block(["FA-VL-06", "FA-VL-01", "FA-VL-04"]))

    out = c.chat("test-kids-note", "sofa for my kids please", chat_fn=fake)
    assert "FA-VL-06" in out["reply"]
    assert "extra care with kids" in out["reply"]


def test_room_photo_language_rule():
    assert "never \"sounds\"" in c.SYSTEM_PROMPT
    assert "\"looks\"" in c.SYSTEM_PROMPT


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
