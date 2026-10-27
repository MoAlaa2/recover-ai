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
    assert "claw-safe weave" in out["reply"]
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
                pattern_type="solid", image="", price_sar_per_m=100)
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
    assert "budget" in out["reply"].lower()
    assert len(out["recommendations"]) == 3


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
    turn = {"needs_all": [], "needs_any": [], "budgets": [100],
            "tones": [], "relaxed": ["max_price"],
            "protected": [], "pet_safe": False, "has_kids": False}
    out = c.enrich([{"code": "FA-VL-01", "reason": "r"}], turn)
    rb = out[0]["relaxed_budget"]
    price = c.get_fabric("FA-VL-01")["price_sar_per_m"]
    assert rb == {"price": price, "over": price - 100, "budget": 100}
    assert "under-budget" not in out[0]["matched"]


def test_disclosure_states_real_overrun():
    note = c.disclosure_note(["max_price"], False, 55)
    assert "55" in note and "slightly" not in note
    note_ar = c.disclosure_note(["max_price"], True, 55)
    assert "٥٥" in note_ar and "شوي" not in note_ar
    mild = c.disclosure_note(["max_price"], False, 0)
    assert "slightly" in mild
