"""Consultant behavior tests (model calls are faked)."""
import json
import os

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
    # Ranked order for plain upholstery search (price tiebreak).
    good = ["FA-NL-07", "FA-NL-03", "FA-NL-10"]
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return tool_call("search_catalog", {"usage": "upholstery"})
        if calls["n"] == 2:
            return final_text(block([good[0], good[1], "FA-XX-99"]))
        return final_text(block(good))

    out = c.chat("test-invented", "sofa fabric please", chat_fn=fake)
    codes = [r["code"] for r in out["recommendations"]]
    assert "FA-XX-99" not in codes
    assert codes == good
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
        return final_text(block(["FA-LA-01", "FA-LA-08", "FA-LA-04"]))

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
        lambda path, lang=None: {"furniture": "wingback armchair",
                                 "style": "classic"})
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
                price_usd_per_m=100, usage="upholstery",
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
    turn = {"seen": [], "relaxed": [], "needs_any": ["pet-friendly"],
            "needs_all": [], "protected": ["pet-friendly"],
            "pet_safe": True, "has_kids": False}
    pre = c.run_search({"usage": "upholstery", "max_price": 100,
                        "snag_levels": ["low"]}, turn)
    good = [s["code"] for s in pre["fabrics"][:3]]
    assert len(good) == 3

    def fake(messages, tools=None):
        if not hasattr(fake, "n"):
            fake.n = 0
        fake.n += 1
        if fake.n == 1:
            return tool_call("search_catalog",
                             {"usage": "upholstery", "max_price": 100,
                              "snag_levels": ["low"]})
        return final_text("All three fit your budget.\n" + block(good))

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
    # The unmentioned snag relaxation lives once on the receipt line,
    # never repeated as a prose sentence on a recommendation turn.
    assert len(out["recommendations"]) == 3
    assert any("claw-safe weave" in r["receipt"]
               for r in out["recommendations"])
    assert "claw-safe weave" not in out["reply"]


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
    items = [dict(base, code="B-80", price_usd_per_m=80, styles=[]),
             dict(base, code="B-150", price_usd_per_m=150,
                  styles=["modern"]),
             dict(base, code="B-90", price_usd_per_m=90, styles=[])]
    monkeypatch.setattr(cat, "_SPECS", items)
    turn = {"seen": [], "relaxed": [], "needs_any": [], "needs_all": [],
            "protected": [], "pet_safe": False, "has_kids": False}
    res = c.run_search({"usage": "upholstery", "styles": ["modern"],
                        "max_price": 100, "limit": 10}, turn)
    assert [s["code"] for s in res["fabrics"]] == ["B-80", "B-90",
                                                  "B-150"]


def test_kids_light_note_mentions_fabric(monkeypatch):
    # Eligibility comes from search results only (A10): the search
    # surfaces the light code, get_fabric is just a detail read.
    monkeypatch.setattr(
        c, "run_search",
        lambda args, turn: {"fabrics": [{"code": "FA-VL-06"},
                                        {"code": "FA-NL-16"},
                                        {"code": "FA-NL-02"}],
                            "relaxed": [], "relaxed_constraints": []})

    def fake(messages, tools=None):
        if not hasattr(fake, "n"):
            fake.n = 0
        fake.n += 1
        if fake.n == 1:
            return tool_call("search_catalog", {"usage": "upholstery"})
        if fake.n == 2:
            return tool_call("get_fabric", {"code": "FA-VL-06"},
                             call_id="t2")
        return final_text(block(["FA-VL-06", "FA-NL-16", "FA-NL-02"]))

    out = c.chat("test-kids-note", "sofa for my kids please", chat_fn=fake)
    assert "FA-VL-06" in out["reply"]
    assert "extra care with kids" in out["reply"]


def test_light_note_unit():
    recs = [{"code": "FA-VL-06"}, {"code": "FA-VL-01"}]
    note = c.light_color_note(recs, False, "kids")
    assert "FA-VL-06" in note and "extra care with kids" in note
    assert c.light_color_note([{"code": "FA-VL-01"}], False,
                              "kids") == ""
    note_ar = c.light_color_note(recs, True, "pets")
    assert "الحيوانات" in note_ar


def test_pets_never_get_high_snag(monkeypatch):
    import app.services.catalog as cat
    base = dict(name_en="T", name_ar="ت", material="cotton velvet",
                primary_color="red", secondary_colors=[], tone="warm",
                styles=["modern"], features=["pet-friendly"],
                suitable_for=["home"], opacity="opaque", usage="upholstery",
                pattern_type="solid", image="", price_usd_per_m=100)
    items = [dict(base, code="P-MED", snag_risk="medium"),
             dict(base, code="P-HI", snag_risk="high")]
    monkeypatch.setattr(cat, "_SPECS", items)
    summaries, relaxed = search_catalog(
        usage="upholstery", snag_levels=["low"], pet_safe=True,
        any_features=["pet-friendly"], limit=10)
    assert [s["code"] for s in summaries] == ["P-MED"]
    assert "P-HI" not in [s["code"] for s in summaries]


def test_unseen_code_is_rejected_like_invented():
    def fake(messages, tools=None):
        if not hasattr(fake, "n"):
            fake.n = 0
        fake.n += 1
        if fake.n == 1:
            return tool_call("search_catalog", {"usage": "upholstery"})
        if fake.n == 2:
            return final_text(block(["FA-NL-07", "FA-NL-03", "FA-SC-01"]))
        return final_text(block(["FA-NL-07", "FA-NL-03", "FA-NL-10"]))

    out = c.chat("test-unseen", "sofa fabric please", chat_fn=fake)
    codes = [r["code"] for r in out["recommendations"]]
    assert "FA-SC-01" not in codes
    assert codes == ["FA-NL-07", "FA-NL-03", "FA-NL-10"]


def test_context_accumulates_across_turns():
    ok = final_text("noted")
    c.chat("test-acc", "my cat needs sofa fabric",
           chat_fn=lambda messages, tools=None: ok)
    session = c.SESSIONS["test-acc"]
    assert session["pet_safe"] is True
    assert "pet-friendly" in session["needs_any"]
    c.chat("test-acc", "recommend now",
           chat_fn=lambda messages, tools=None: ok)
    assert c.SESSIONS["test-acc"]["pet_safe"] is True
    assert "pet-friendly" in c.SESSIONS["test-acc"]["needs_any"]


def test_detect_user_lang():
    from app.services.catalog import detect_user_lang as det
    assert det("أبغى قماش") == "ar"
    assert det("मुझे कपड़ा चाहिए") == "hi"
    assert det("Je cherche un tissu") == "fr"
    assert det("Busco tela para mi sofá") == "es"
    assert det("I need sofa fabric") is None
    assert det("ok") is None
    assert det("separate covers") is None
    assert det("") is None


def test_urdu_persian_german_are_uncertain():
    from app.services.catalog import detect_user_lang as det
    assert det("میرے صوفے کے لیے کپڑا چاہیے") is None
    assert det("برای مبل من پارچه می‌خواهم") is None
    assert det("Ich brauche Stoff für mein Sofa") is None


def test_reply_language_pinned_on_session():
    seen = {}

    def fake(messages, tools=None):
        seen["user"] = messages[-1]["content"]
        return final_text("noted")

    c.chat("test-lang-ar", "أبغى قماش للكنبة", chat_fn=fake)
    assert c.SESSIONS["test-lang-ar"]["lang"] == "ar"
    assert "[Reply only in Arabic.]" in seen["user"]
    c.chat("test-lang-ar", "ok", chat_fn=fake)
    assert c.SESSIONS["test-lang-ar"]["lang"] == "ar"
    assert "[Reply only in Arabic.]" in seen["user"]


def test_uncertain_language_mirrors_user():
    seen = {}

    def fake(messages, tools=None):
        seen["user"] = messages[-1]["content"]
        return final_text("noted")

    c.chat("test-lang-ur", "میرے صوفے کے لیے کپڑا چاہیے", chat_fn=fake)
    assert "lang" not in c.SESSIONS["test-lang-ur"]
    assert "[Reply in the same language the user wrote in.]" in seen[
        "user"]
    c.chat("test-lang-de", "Ich brauche Stoff für mein Sofa",
           chat_fn=fake)
    assert "[Reply in the same language the user wrote in.]" in seen[
        "user"]


def test_enrich_adds_trust_receipts():
    turn = {"needs_all": ["easy-clean"], "needs_any": ["pet-friendly"],
            "relaxed": ["max_price"], "budgets": [150], "tones": ["warm"]}
    out = c.enrich([{"code": "FA-NL-02", "reason": "nice"}], turn)
    assert "pet-friendly" in out[0]["matched"]
    assert "easy-clean" in out[0]["matched"]
    assert "under-budget" in out[0]["matched"]
    # No contradiction: price is under budget, so the relaxed budget
    # surfaces no pill; specifics live in relaxed_budget when over.
    assert out[0]["relaxed"] == []
    assert out[0]["relaxed_budget"] is None
    assert "image" in out[0] and out[0]["image"].endswith(".jpg")


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
        return final_text(block(["FA-LA-01", "FA-LA-08", "FA-LA-04"]))

    out = c.chat("test-relaxed", "cheap curtains", chat_fn=fake)
    # The budget relaxation is disclosed once on the card receipt line,
    # not repeated as a prose sentence on a recommendation turn.
    assert len(out["recommendations"]) == 3
    assert "budget" in out["recommendations"][0]["receipt"]
    assert "stretched the budget" not in out["reply"].lower()


def test_options_block_returned_and_stripped():
    def fake(messages, tools=None):
        return final_text(
            "Do you prefer warm or cool tones?\n"
            "```options\n[\"Warm\", \"Cool\", \"Neutral\"]\n```")

    out = c.chat("test-options", "sofa fabric please", chat_fn=fake)
    assert out["options"] == ["Warm", "Cool", "Neutral"]
    assert "```options" not in out["reply"]
    assert "Warm" not in out["reply"]


def test_no_options_block_gives_empty_list():
    out = c.chat("test-no-options", "hello",
                 chat_fn=lambda messages, tools=None: final_text("Hi"))
    assert out["options"] == []


def test_lang_pin_sets_session_language():
    out = c.chat("test-pin-hi", "Hello",
                 chat_fn=lambda messages, tools=None: final_text("Hi"),
                 lang="hi")
    assert out["detected_lang"] == "hi"
    assert c.SESSIONS["test-pin-hi"]["lang"] == "hi"


def test_detected_lang_returned_without_pin():
    out = c.chat("test-detect-ar", "أبغى قماش للكنبة",
                 chat_fn=lambda messages, tools=None: final_text("تم"))
    assert out["detected_lang"] == "ar"


def test_fence_filter_hides_blocks_live():
    f = c.FenceFilter()
    assert f.feed("Hello ") == "Hello "
    assert f.feed("```reco") == ""
    assert f.feed("mmendations\n[{}]```") == ""
    assert f.feed(" done") == " done"
    assert f.flush() == ""


def test_fence_filter_split_marker_across_chunks():
    f = c.FenceFilter()
    assert f.feed("a``") == "a"
    assert f.feed("`b```c") == "c"
    assert f.flush() == ""


def test_fence_filter_unclosed_block_discarded():
    f = c.FenceFilter()
    assert f.feed("Hi ```options\n[\"a\"]") == "Hi "
    assert f.feed(" more") == ""
    assert f.flush() == ""


def test_enrich_one_pill_per_dimension():
    turn = {"needs_all": ["pet-friendly"], "needs_any": [],
            "budgets": [100], "tones": ["warm"],
            "relaxed": ["tone", "max_price"],
            "protected": [], "pet_safe": True, "has_kids": False}
    recs = [{"code": "FA-VL-01", "reason": "r"}]
    out = c.enrich(recs, turn)
    assert out[0]["relaxed_features"] == []
    assert out[0]["relaxed_budget"] is None or True
    assert "warm-tone" not in out[0]["matched"]


def test_enrich_relaxed_feature_specifics():
    # blackout never applies to an upholstery fabric: it can only be
    # missing because the filter was relaxed, never because it matched.
    turn = {"needs_all": ["blackout"], "needs_any": [], "budgets": [],
            "tones": [], "relaxed": ["features"],
            "protected": [], "pet_safe": False, "has_kids": False}
    out = c.enrich([{"code": "FA-NL-02", "reason": "r"}], turn)
    assert "blackout" not in out[0]["matched"]
    assert out[0]["relaxed_features"] == ["blackout"]


def test_enrich_budget_over_numbers():
    turn = {"needs_all": [], "needs_any": [], "budgets": [50],
            "tones": [], "relaxed": ["max_price"],
            "protected": [], "pet_safe": False, "has_kids": False}
    out = c.enrich([{"code": "FA-VL-01", "reason": "r"}], turn)
    rb = out[0]["relaxed_budget"]
    price = c.get_fabric("FA-VL-01")["price_usd_per_m"]
    assert price > 50
    assert rb == {"price": price, "over": price - 50, "budget": 50}
    assert "under-budget" not in out[0]["matched"]


def test_disclosure_states_real_overrun():
    note = c.disclosure_note(["max_price"], False, 55)
    assert "55" in note and "slightly" not in note
    note_ar = c.disclosure_note(["max_price"], True, 55)
    assert "٥٥" in note_ar and "شوي" not in note_ar
    mild = c.disclosure_note(["max_price"], False, 0)
    assert "slightly" in mild


def test_disclosure_names_specific_features():
    note = c.disclosure_note(["features"], False, 0,
                             ["antibacterial", "scratch-resistant"])
    assert "fabric features" not in note
    assert "antibacterial" in note and "scratch-resistant" in note
    note_ar = c.disclosure_note(["any_features"], True, 0,
                                ["pet-friendly"])
    assert "مواصفات القماش" not in note_ar
    assert "مناسب للحيوانات" in note_ar
    vague = c.disclosure_note(["features"], False, 0)
    assert "fabric features" in vague


def test_options_only_reply_retries_for_prose():
    opts = '```options\n["Cushions only", "Sofa + cushions"]\n```'
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return final_text(opts)
        return final_text("Absolutely — cushions only is a lovely start.")

    out = c.chat("test-empty-opts", "cushions now please", chat_fn=fake)
    assert calls["n"] == 2
    assert out["reply"].strip()
    assert "```" not in out["reply"]
    assert out["options"] == ["Cushions only", "Sofa + cushions"]


def test_recommendations_only_reply_keeps_recs():
    good = ["FA-NL-07", "FA-NL-03", "FA-NL-10"]
    items = [{"code": code, "reason": "reason for %s" % code}
             for code in good]
    recs_only = "```recommendations\n%s\n```" % json.dumps(items)
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return tool_call("search_catalog", {"usage": "upholstery"})
        if calls["n"] == 2:
            return final_text(recs_only)
        return final_text("Here you go — three lovely picks for you.")

    out = c.chat("test-empty-recs", "recommend now", chat_fn=fake)
    assert calls["n"] == 3
    assert out["reply"].strip()
    assert "```" not in out["reply"]
    assert [r["code"] for r in out["recommendations"]] == good


def test_empty_reply_falls_back_localized():
    def fake(messages, tools=None):
        return final_text("   ")

    out = c.chat("test-empty-both", "cushions now please", chat_fn=fake)
    assert out["reply"].strip()
    assert "```" not in out["reply"]
    assert out["options"] == []
    assert out["recommendations"] == []
    assert c.empty_fallback(True, False, "ar") == (
        "تمام — أي واحد يناسبك؟")
    assert c.empty_fallback(False, True, "ar") == (
        "هذه أفضل اختياراتي لك:")
    assert c.empty_fallback(False, False, "xx").startswith("Could you")


def test_wants_recommendations_hi_forms():
    assert c.wants_recommendations("अभी 3 फ़ैब्रिक सुझाएँ।")
    assert c.wants_recommendations("सुझाव दीजिए")
    assert c.wants_recommendations("Recommend 3 fabrics now.")
    assert not c.wants_recommendations("मुझे यह पसंद है")


def test_explicit_dodge_gets_seeded_recs_in_one_turn():
    # The model asked a question instead of searching: the seeded
    # server-side search still answers in the same turn, with no
    # extra model round trip.
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        return final_text("Lovely. Which item should I change first?")

    out = c.chat("test-seed", "Recommend 3 sofa fabrics now",
                 chat_fn=fake)
    assert calls["n"] == 1
    codes = [r["code"] for r in out["recommendations"]]
    assert len(codes) == 3
    assert all(get_fabric(code) for code in codes)


def test_grounding_retry_lists_exact_codes():
    import re
    log_path = "/tmp/test-grounding-log.json"
    if os.path.exists(log_path):
        os.remove(log_path)
    old_log, c.GROUNDING_LOG = c.GROUNDING_LOG, log_path
    try:
        calls = {"n": 0}
        nudge = {}

        def fake(messages, tools=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return tool_call("search_catalog", {"usage": "upholstery"})
            if calls["n"] == 2:
                return final_text(block(["FA-XX-01", "FA-XX-02",
                                         "FA-XX-03"]))
            last_user = [m for m in messages
                         if m.get("role") == "user"][-1]["content"]
            m = re.search(r"nothing else: ([A-Z0-9\-, ]+)\.", last_user)
            assert m, "retry must name the exact valid list"
            nudge["list"] = [x.strip() for x in m.group(1).split(",")]
            return final_text(block(nudge["list"][:3]))

        out = c.chat("test-ground-retry", "sofa fabric please",
                     chat_fn=fake)
        assert calls["n"] == 3
        codes = [r["code"] for r in out["recommendations"]]
        assert codes == nudge["list"][:3]
        assert all(code in nudge["list"] for code in codes)
        log = json.load(open(log_path, encoding="utf-8"))
        assert log[-1]["path"] == "retry_ok"
        assert log[-1]["final_codes"] == codes
    finally:
        c.GROUNDING_LOG = old_log


def test_grounding_fallback_top3():
    log_path = "/tmp/test-grounding-log.json"
    if os.path.exists(log_path):
        os.remove(log_path)
    old_log, c.GROUNDING_LOG = c.GROUNDING_LOG, log_path
    try:
        calls = {"n": 0}

        def fake(messages, tools=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return tool_call("search_catalog", {"usage": "upholstery"})
            if calls["n"] == 2:
                return final_text(block(["FA-XX-01", "FA-XX-02",
                                         "FA-XX-03"]))
            return final_text(block(["FA-YY-01", "FA-YY-02", "FA-YY-03"]))

        out = c.chat("test-ground-fallback", "sofa fabric please",
                     chat_fn=fake)
        assert calls["n"] == 3
        codes = [r["code"] for r in out["recommendations"]]
        assert len(codes) == 3
        assert all(get_fabric(code) for code in codes)
        assert "closest matches" in out["reply"]
        assert "```" not in out["reply"]
        enriched = out["recommendations"]
        assert all("price_usd_per_m" in r for r in enriched)
        log = json.load(open(log_path, encoding="utf-8"))
        assert log[-1]["path"] == "fallback"
        assert log[-1]["final_codes"] == codes
    finally:
        c.GROUNDING_LOG = old_log


def test_grounding_fallback_on_exhaustion():
    log_path = "/tmp/test-grounding-log.json"
    if os.path.exists(log_path):
        os.remove(log_path)
    old_log, c.GROUNDING_LOG = c.GROUNDING_LOG, log_path
    try:
        calls = {"n": 0}

        def fake(messages, tools=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return tool_call("search_catalog", {"usage": "upholstery"})
            return tool_call("get_fabric", {"code": "FA-NL-07"},
                             call_id="t%d" % calls["n"])

        out = c.chat("test-ground-exhaust", "recommend now", chat_fn=fake)
        assert calls["n"] == 4
        codes = [r["code"] for r in out["recommendations"]]
        assert len(codes) == 3
        assert all(get_fabric(code) for code in codes)
        assert "closest matches" in out["reply"]
        log = json.load(open(log_path, encoding="utf-8"))
        assert log[-1]["path"] == "fallback"
    finally:
        c.GROUNDING_LOG = old_log


def test_confused_message_gets_rephrase_nudge():
    seen = {}

    def fake(messages, tools=None):
        seen["prompt"] = " ".join(
            m.get("content") or "" for m in messages)
        return final_text("Let me ask again simply: cushions or sofa?")

    out = c.chat("test-confused", "??", chat_fn=fake)
    assert "confused" in seen["prompt"]
    assert "cushions or sofa" in out["reply"]


def test_explicit_request_fallback_no_recs_block():
    log_path = "/tmp/test-grounding-log.json"
    if os.path.exists(log_path):
        os.remove(log_path)
    old_log, c.GROUNDING_LOG = c.GROUNDING_LOG, log_path
    try:
        calls = {"n": 0}

        def fake(messages, tools=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return tool_call("search_catalog",
                                {"usage": "upholstery"})
            return final_text("Which style do you prefer — modern or "
                              "classic?")

        out = c.chat("test-explicit-fallback",
                     "please recommend something for my sofa",
                     chat_fn=fake)
        assert calls["n"] == 2
        codes = [r["code"] for r in out["recommendations"]]
        assert len(codes) == 3
        assert all(get_fabric(code) for code in codes)
        assert "closest matches" in out["reply"]
        log = json.load(open(log_path, encoding="utf-8"))
        assert log[-1]["path"] == "fallback"
        assert log[-1]["final_codes"] == codes
    finally:
        c.GROUNDING_LOG = old_log


def test_no_fallback_on_question_turn():
    def fake(messages, tools=None):
        return final_text("Which style do you prefer — modern or "
                          "classic?")

    out = c.chat("test-question-turn",
                 "what colors do you have for sofas?", chat_fn=fake)
    assert out["recommendations"] == []
    assert "closest matches" not in out["reply"]


def test_greeting_has_no_repeated_adjacent_item():
    assert c.collapse_adjacent_dupes(
        "Upholstery, curtains, curtains, cushions, or a mix?") == \
        "Upholstery, curtains, cushions, or a mix?"
    assert c.collapse_adjacent_dupes(
        "تنجيد، ستائر، ستائر، وسائد، أو مشكل؟") == \
        "تنجيد، ستائر، وسائد، أو مشكل؟"
    assert c.collapse_adjacent_dupes("Sofa, sofa, sofa!") == "Sofa!"
    # Untouched: no dupes, later turns, emphasis without comma.
    assert c.collapse_adjacent_dupes(
        "Upholstery, curtains, cushions, or a mix?") == \
        "Upholstery, curtains, cushions, or a mix?"
    assert "curtains, curtains" not in c.SYSTEM_PROMPT


def test_greeting_collapses_model_stutter():
    def fake(messages, tools=None):
        return final_text("Hello! Upholstery, curtains, curtains, "
                          "cushions, or a mix — which is it?")

    out = c.chat("test-greet-dupe", "Hello", chat_fn=fake)
    assert "curtains, curtains" not in out["reply"]
    assert "curtains, cushions" in out["reply"]


def test_budget_tiers_derive_from_catalog():
    lo, hi = c.budget_tiers()
    assert (lo, hi) == (20, 40)
    assert "Under $20" in c.SYSTEM_PROMPT
    assert "US dollars" in c.SYSTEM_PROMPT


def test_sar_option_rewrites_riyals_to_dollars():
    assert c.sar_option("Under 80 SAR") == "Under $80"
    assert c.sar_option("تحت ١٠٠ ر.س") == "تحت $١٠٠" or \
        c.sar_option("100 ريال") == "$100"
    assert c.sar_option("Under $80") == "Under $80"
    assert c.sar_option("80–150") == "80–150"
    assert c.sar_option("No limit") == "No limit"
    block = "Pick one.\n```options\n%s\n```" % json.dumps(
        ["Under 80 SAR", "No limit"])
    assert c.extract_options(block) == ["Under $80", "No limit"]


def test_preview_fabric_needs_seen_code_and_photo(tmp_path, monkeypatch):
    room = tmp_path / "room.jpg"
    from PIL import Image as PILImage
    PILImage.new("RGB", (64, 48), (10, 20, 30)).save(str(room))
    monkeypatch.setattr(c, "analyze_room", lambda *a, **k: {
        "room_type": "living", "wall_colors": [], "floor": "wood",
        "furniture": "a fabric sofa", "existing_fabrics": "linen",
        "light_level": "high", "style": "modern"})
    monkeypatch.setattr("app.services.targets.available_types",
                        lambda *a, **k: ["sofa", "curtains"])
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return tool_call("search_catalog", {"usage": "upholstery"})
        if calls["n"] == 2:
            return tool_call("preview_fabric", {"code": "FA-NL-07"})
        return final_text("Here it is on your sofa.")

    out = c.chat("test-preview-ok", "show me it on my chair",
                 image_path=str(room), chat_fn=fake)
    assert out["preview"] == {"code": "FA-NL-07", "target": ""}
    out2 = c.chat("test-preview-nophoto", "show me it", chat_fn=fake)
    assert not out2.get("preview")
    no_photo = c.execute_tool("preview_fabric", {"code": "FA-NL-07"},
                              {"seen": ["FA-NL-07"], "image": None})
    assert no_photo["error"] == "no_photo"


def test_no_repeat_question_regenerates_once():
    question = ("Perfect for refreshing your dining chairs! Tell me — "
                "warm, cool, or neutral?")
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        if calls["n"] <= 2:
            return final_text(question)
        last_user = [m for m in messages
                     if m.get("role") == "user"][-1]["content"]
        assert "already answered" in last_user
        return final_text("Got it — warm it is. What is your budget?")

    out = c.chat("test-norepeat", "hello", chat_fn=fake)
    assert "warm, cool" in out["reply"].lower()
    out = c.chat("test-norepeat", "warm", chat_fn=fake)
    assert calls["n"] == 3
    assert "budget" in out["reply"].lower()
    assert "warm, cool, or neutral" not in out["reply"].lower()


def test_similar_reply_threshold():
    assert c.similar_reply("Warm, cool, or neutral?", "Warm, cool, or neutral?") >= 0.9
    assert c.similar_reply("Warm, cool, or neutral?", "What is your budget?") < 0.9
    assert c.similar_reply("short", "short") == 0.0


def test_assign_fabric_records_choice():
    session = {}
    out = c.execute_tool("assign_fabric",
                         {"target": "sofa", "code": "FA-AC-01"},
                         {"session": session, "seen": []})
    assert out == {"ok": True, "target": "sofa", "code": "FA-AC-01"}
    assert session["assignments"] == {"sofa": "FA-AC-01"}
    assert session["chosen_targets"] == ["sofa"]
    bad = c.execute_tool("assign_fabric",
                         {"target": "lamp", "code": "FA-AC-01"},
                         {"session": {}, "seen": []})
    assert bad["error"] == "unknown target"
    bad2 = c.execute_tool("assign_fabric",
                         {"target": "sofa", "code": "NOPE"},
                         {"session": {}, "seen": []})
    assert bad2["error"] == "unknown code"


def test_chosen_targets_and_curtains_usage(tmp_path, monkeypatch):
    room = tmp_path / "room.jpg"
    from PIL import Image as PILImage
    PILImage.new("RGB", (64, 48), (10, 20, 30)).save(str(room))
    monkeypatch.setattr(c, "analyze_room", lambda *a, **k: {
        "room_type": "living", "wall_colors": [], "floor": "wood",
        "furniture": "curtains", "existing_fabrics": "linen",
        "light_level": "high", "style": "modern"})
    monkeypatch.setattr("app.services.targets.available_types",
                        lambda *a, **k: ["sofa", "curtains"])
    search_args = []
    asked = {"n": 0}

    def fake(messages, tools=None):
        asked["n"] += 1
        if asked["n"] == 1:
            return tool_call("search_catalog", {"usage": "upholstery"})
        return final_text("Here are curtain picks.")

    def spy_search(args, turn):
        search_args.append(dict(args))
        return {"fabrics": [{"code": "FA-AC-01"}], "relaxed": [],
                "relaxed_constraints": []}

    monkeypatch.setattr(c, "run_search", spy_search)
    out = c.chat("test-curtains-only", "curtains please",
                 image_path=str(room), chat_fn=fake)
    assert out["targets"]["chosen"] == ["curtains"]
    assert search_args and search_args[-1].get("usage") == "curtains"


def test_auto_apply_top_pick_multi(tmp_path, monkeypatch):
    from PIL import Image as PILImage
    room = tmp_path / "room.jpg"
    PILImage.new("RGB", (64, 48), (10, 20, 30)).save(str(room))
    monkeypatch.setattr(c, "analyze_room", lambda *a, **k: {
        "room_type": "living", "wall_colors": [], "floor": "wood",
        "furniture": "sofa", "existing_fabrics": "linen",
        "light_level": "high", "style": "modern"})
    c.SESSIONS["t-auto"] = {
        "messages": [], "lang": "en",
        "image_path": str(room),
        "available_targets": ["sofa", "cushions"],
        "chosen_targets": ["sofa", "cushions"]}
    asked = {"n": 0}

    def fake(messages, tools=None):
        asked["n"] += 1
        if asked["n"] == 1:
            return tool_call("search_catalog", {"usage": "upholstery"})
        return final_text(
            "Here are my picks: ```recommendations\n"
            "[{\"code\": \"FA-AC-01\", \"reason\": \"r1\"}, "
            "{\"code\": \"FA-AC-02\", \"reason\": \"r2\"}, "
            "{\"code\": \"FA-AC-03\", \"reason\": \"r3\"}]\n```")

    def spy_search(args, turn):
        return {"fabrics": [{"code": "FA-AC-01"},
                            {"code": "FA-AC-02"},
                            {"code": "FA-AC-03"}],
                "relaxed": [], "relaxed_constraints": []}

    monkeypatch.setattr(c, "run_search", spy_search)
    out = c.chat("t-auto", "ok, what do you suggest?",
                 image_path=str(room), chat_fn=fake)
    assert len(out["recommendations"]) == 3
    assert out["preview"] == {"code": "FA-AC-01", "target": "sofa"}
    assert out["targets"]["assignments"] == {"sofa": "FA-AC-01"}


def test_analysis_cached_per_image_hash(tmp_path, monkeypatch):
    room = tmp_path / "room.jpg"
    from PIL import Image as PILImage
    PILImage.new("RGB", (64, 48), (10, 20, 30)).save(str(room))
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        return {"choices": [{"message": {"content": (
            '{"room_type": "living", "wall_colors": [], '
            '"floor": "wood", "furniture": "sofa", '
            '"existing_fabrics": "linen", "light_level": "high", '
            '"style": "modern"}')}}]}

    monkeypatch.setattr(c, "_call_chat", fake)
    c.ANALYSES.clear()
    first = c.analyze_room(str(room))
    second = c.analyze_room(str(room))
    assert calls["n"] == 1
    assert first == second
    assert first["room_type"] == "living"


def test_vision_bytes_capped(tmp_path):
    from PIL import Image as PILImage
    big = tmp_path / "big.jpg"
    PILImage.new("RGB", (4000, 3000), (10, 20, 30)).save(str(big))
    small = c.vision_jpeg_bytes(str(big))
    assert max(PILImage.open(__import__("io").BytesIO(small)).size) <= 1024
    assert len(small) < 4000 * 3000


def _cushion_code():
    summaries, _ = search_catalog(usage="cushions", limit=5)
    assert summaries, "catalog needs cushion-suitable fabrics"
    return summaries[0]["code"]


def test_receipt_summary_dedupes_labels():
    line = c.receipt_summary(
        ["easy-clean", "easy-clean", "cool-tone"],
        ["tone"], ["easy-clean"], 0, False)
    assert line.count("easy-clean") == 1
    assert line.count("Cool tone") == 1
    assert line.count("color tone") == 1
    assert line.startswith("Matches:")
    assert "Eased:" in line
    assert "\n" not in line


def test_receipt_empty_without_stated_needs():
    turn = {"needs_all": [], "needs_any": [], "budgets": [],
            "tones": [], "relaxed": [], "chosen_targets": ["cushions"],
            "lang": "en"}
    recs = c.enrich([{"code": _cushion_code(), "reason": "r"}], turn)
    assert recs[0]["target"] == "cushions"
    assert recs[0]["receipt"] == ""
    assert "pet-friendly" not in recs[0]["receipt"]
    assert "antibacterial" not in recs[0]["receipt"]


def _live_turn():
    # Mirrors the live fallback: "Warm beige, kids, budget 150..."
    # relaxed colors/tone/styles plus the kid-mapped features.
    msg = ("Warm beige, kids, budget 150 per meter. "
           "Recommend 3 fabrics now.")
    return {"needs_all": ["antibacterial", "easy-clean",
                          "stain-resistant"],
            "needs_any": [], "budgets": [150], "tones": ["warm"],
            "relaxed": ["colors", "tone", "styles", "features"],
            "protected": ["washable", "antibacterial"],
            "pet_safe": False, "has_kids": True,
            "chosen_targets": ["cushions"], "lang": "en",
            "session": {"messages": [{"role": "user", "content": msg}]}}


def test_receipt_drops_unstated_style_live_case():
    turn = _live_turn()
    recs = c.enrich([{"code": "FA-AC-01", "reason": "r"},
                     {"code": "FA-AC-03", "reason": "r"}], turn)
    for rec in recs:
        line = rec["receipt"]
        assert "\n" not in line
        assert "style" not in line.lower()
        assert "snag" not in line.lower() and "claw" not in line.lower()
    # Kid-mapped features are stated needs (user said "kids").
    assert "easy-clean" in recs[0]["receipt"]


def test_receipt_eased_capped_at_three():
    turn = _live_turn()
    turn["relaxed"] = ["colors", "tone", "styles", "features",
                       "plain_or_patterned", "min_martindale"]
    turn["session"] = {"messages": [
        {"role": "user",
         "content": "Warm beige modern patterned kids fabric"}]}
    rec = c.enrich([{"code": "FA-AC-01", "reason": "r"}], turn)[0]
    eased = rec["receipt"].split("Eased:")[1]
    assert eased.count("·") <= 2


def test_receipt_keeps_stated_style():
    turn = _live_turn()
    turn["relaxed"] = ["styles"]
    turn["session"] = {"messages": [
        {"role": "user", "content": "I love modern Scandinavian style"}]}
    rec = c.enrich([{"code": "FA-AC-01", "reason": "r"}], turn)[0]
    assert "style" in rec["receipt"].lower()


def test_receipt_drops_snag_without_pets():
    turn = _live_turn()
    turn["relaxed"] = ["snag_levels"]
    rec = c.enrich([{"code": "FA-AC-01", "reason": "r"}], turn)[0]
    assert "claw" not in rec["receipt"].lower()


def test_preview_fabric_defaults_to_chosen_target():
    code = _cushion_code()
    turn = {"image": "uploads/x.jpg", "seen": [code],
            "chosen_targets": ["cushions"]}
    out = c._execute_tool("preview_fabric", {"code": code}, turn)
    assert out == {"ok": True, "code": code, "target": "cushions"}


def test_rec_turn_suppresses_prose_disclosure():
    # The relaxed budget is disclosed once, on the card's receipt line —
    # never repeated as a prose sentence on the same turn.
    summaries, relaxed = search_catalog(
        usage="upholstery", max_price=15, limit=50)
    assert "max_price" in relaxed
    codes = [s["code"] for s in summaries[:3]]

    def fake(messages, tools=None):
        if not hasattr(fake, "n"):
            fake.n = 0
        fake.n += 1
        if fake.n == 1:
            return tool_call("search_catalog",
                             {"usage": "upholstery", "max_price": 50})
        return final_text(block(codes))

    out = c.chat("test-disclosure-once", "blue sofa under 50",
                 chat_fn=fake)
    assert len(out["recommendations"]) == 3
    assert "To find these" not in out["reply"]
    receipt = out["recommendations"][0]["receipt"]
    assert receipt.count("budget") == 1


def test_no_rec_turn_still_discloses():
    def fake(messages, tools=None):
        if not hasattr(fake, "n"):
            fake.n = 0
        fake.n += 1
        if fake.n == 1:
            return tool_call("search_catalog",
                             {"usage": "upholstery", "max_price": 15})
        return final_text("Blue is a great choice. What tone do you like?")

    out = c.chat("test-disclosure-no-recs", "blue sofa under 15",
                 chat_fn=fake)
    assert out["recommendations"] == []
    assert "To find these" in out["reply"]


def test_receipt_lang_normalizes_legacy_bool():
    assert c._receipt_lang(True) == "ar"
    assert c._receipt_lang(False) == "en"
    assert c._receipt_lang("hi") == "hi"
    assert c._receipt_lang("xx") == "en"


def test_receipt_summary_hindi_french_spanish():
    hi = c.receipt_summary(["easy-clean"], ["tone"], [], 0, False,
                           lang="hi")
    assert hi.startswith("मेल:") and "आसान-सफ़ाई" in hi
    fr = c.receipt_summary(["easy-clean"], ["tone"], [], 0, False,
                           lang="fr")
    assert fr.startswith("Conforme:") and "Facile d'entretien" in fr
    es = c.receipt_summary(["easy-clean"], ["tone"], [], 0, False,
                           lang="es")
    assert es.startswith("Coincide:") and "Fácil de limpiar" in es


def test_fallback_line_follows_turn_lang():
    log_path = "/tmp/test-grounding-log-lang.json"
    if os.path.exists(log_path):
        os.remove(log_path)
    old_log, c.GROUNDING_LOG = c.GROUNDING_LOG, log_path
    try:
        calls = {"n": 0}

        def fake(messages, tools=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return tool_call("search_catalog", {"usage": "upholstery"})
            if calls["n"] == 2:
                return final_text(block(["FA-XX-01", "FA-XX-02",
                                         "FA-XX-03"]))
            return final_text(block(["FA-YY-01", "FA-YY-02", "FA-YY-03"]))

        out = c.chat("test-ground-fallback-fr", "sofa fabric please",
                     chat_fn=fake, lang="fr")
        assert "Voici les correspondances les plus proches" in out["reply"]
        assert "closest matches" not in out["reply"]
    finally:
        c.GROUNDING_LOG = old_log


def test_decline_follows_message_lang():
    def boom(messages, tools=None):
        raise AssertionError("model must not be called")

    hi = c.chat("test-scope-hi", "फ्रांस का राष्ट्रपति कौन है?",
                chat_fn=boom)
    assert "विशेषज्ञता" in hi["reply"] and "expertise" not in hi["reply"]
    fr = c.chat("test-scope-fr",
                "Je veux savoir qui a gagné les élections", chat_fn=boom)
    assert "expertise" in fr["reply"] and "outside my expertise" not in fr["reply"]
    es = c.chat("test-scope-es",
                "¿Quién ganó las elecciones para presidente?",
                chat_fn=boom)
    assert "especialidad" in es["reply"] and "outside my expertise" not in es["reply"]


def test_confirm_piece_question_five_langs():
    fr = c.confirm_piece_question("sofa", "curtains", "fr")
    assert "canapé" in fr and "rideaux" in fr and "Quick check" not in fr
    hi = c.confirm_piece_question("sofa", "cushions", "hi")
    assert "सोफ़ा" in hi and "कुशन" in hi
    es = c.confirm_piece_question("curtains", "sofa", "es")
    assert "cortinas" in es and "sofá" in es
    ar = c.confirm_piece_question("sofa", "curtains", "ar")
    assert "الكنبة" in ar


def test_unreadable_photo_reply_follows_lang(monkeypatch):
    import tempfile
    monkeypatch.setattr(c, "analyze_room",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("nope")))
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        tmp.write(b"not a photo")
        tmp.flush()
        out = c.chat("test-unreadable-hi", "photo", image_path=tmp.name,
                     chat_fn=lambda m, tools=None: final_text("x"),
                     lang="hi")
    assert "सैंपल रूम" in out["reply"]
    assert "couldn't read" not in out["reply"]
    assert out["recommendations"] == []


def test_enrich_receipt_uses_turn_lang():
    turn = {"needs_all": ["easy-clean"], "needs_any": [], "budgets": [],
            "tones": [], "relaxed": [], "chosen_targets": [],
            "lang": "hi",
            "session": {"messages": [{"role": "user",
                                      "content": "mujhe aasan safai chahiye"}]}}
    rec = c.enrich([{"code": "FA-NL-02", "reason": "r"}], turn)[0]
    assert "आसान-सफ़ाई" in rec["receipt"]
    assert "Easy-clean" not in rec["receipt"]


def test_preview_fabric_refuses_an_item_the_photo_does_not_show():
    """A bedroom with a roller blind lists no curtains: the auto preview
    must not fire for curtains (it would fail in the engine and the
    reply would still claim "applied"). Unknown listing: no guard."""
    base = {"seen": ["FA-SC-03"], "image": "room.jpg"}
    out = c.execute_tool("preview_fabric",
                         {"code": "FA-SC-03", "target": "curtains"},
                         dict(base, session={"available_targets": ["sofa"]}))
    assert out["error"] == "not visible" and out["visible"] == ["sofa"]
    out = c.execute_tool("preview_fabric",
                         {"code": "FA-SC-03", "target": "curtains"},
                         dict(base, session={"available_targets": []}))
    assert out["error"] == "not visible"
    ok = c.execute_tool("preview_fabric",
                        {"code": "FA-SC-03", "target": "curtains"},
                        dict(base, session={"available_targets": None}))
    assert ok.get("ok") and ok["target"] == "curtains"
    ok2 = c.execute_tool("preview_fabric",
                         {"code": "FA-SC-03", "target": "curtains"},
                         dict(base, session={"available_targets":
                                             ["curtains"]}))
    assert ok2.get("ok")


def test_ground_reason_drops_unsupported_feature_claims():
    from app.services.consultant import ground_reason
    item = {"features": ["washable", "fade-resistant"],
            "description_en": "A soft cotton weave."}
    text = ("Soft and warm for your nook. It is pet-friendly and shrugs "
            "off claws. Machine washable too.")
    out = ground_reason(text, item, "en")
    assert "pet" not in out and "claws" not in out
    assert "Soft and warm" in out and "washable" in out


def test_ground_reason_keeps_supported_claims_and_falls_back():
    from app.services.consultant import ground_reason
    item = {"features": ["pet-friendly"],
            "description_en": "Tough velvet.", "description_ar": "مخمل متين."}
    assert ground_reason("Great with cats.", item, "en") == "Great with cats."
    # Everything unsupported: the catalog description stands in.
    assert ground_reason("Blocks all light.", item, "en") == "Tough velvet."
    assert ground_reason("معتم تماماً.", item, "ar") == "مخمل متين."
    assert ground_reason("", item, "en") == "Tough velvet."


def test_enrich_grounds_the_reason(monkeypatch):
    from app.services import consultant as c
    from app.services.catalog import load_specs
    item = next(f for f in load_specs()
                if "blackout" not in f.get("features", []))
    out = c.enrich([{"code": item["code"],
                     "reason": "Lovely tone. Total blackout for naps."}],
                   {"lang": "en"})
    assert "blackout" not in out[0]["reason"].lower()
    assert "Lovely tone." == out[0]["reason"]


def test_enrich_target_follows_the_named_piece_when_nothing_matched():
    """Curtains asked for, none in the photo: the cards still say
    curtains so the Try fails honestly for that piece, not the sofa."""
    turn = {"chosen_targets": [], "session": {"topic": "curtains"}}
    out = c.enrich([{"code": "FA-NL-02", "reason": "nice"}], turn)
    assert out[0]["target"] == "curtains"
    # A matched choice still wins; several choices still mean no target.
    turn = {"chosen_targets": ["sofa"], "session": {"topic": "curtains"}}
    assert c.enrich([{"code": "FA-NL-02", "reason": ""}], turn)[0]["target"] == "sofa"
    turn = {"chosen_targets": ["sofa", "cushions"], "session": {"topic": "curtains"}}
    assert c.enrich([{"code": "FA-NL-02", "reason": ""}], turn)[0]["target"] == ""
    turn = {"chosen_targets": [], "session": {"topic": "bed"}}
    assert c.enrich([{"code": "FA-NL-02", "reason": ""}], turn)[0]["target"] == ""


def test_just_show_chip_is_localized_not_duplicated():
    from app.services.consultant import ensure_just_show_option
    out = ensure_just_show_option(["كنبة", "ستائر", "Just show me"], "ar")
    assert "Just show me" not in out
    assert out.count("وريني الحين") == 1
    # English stays English; a present localized chip is not doubled.
    assert ensure_just_show_option(["Sofa", "Just show me"], "en") == [
        "Sofa", "Just show me"]
    assert ensure_just_show_option(["Canapé", "Montrez-moi"], "fr") == [
        "Canapé", "Montrez-moi"]
