"""Unit tests for the eval checker (no model calls)."""
import sys

sys.path.insert(0, "scripts")

import eval_scenarios as ev


def turns(reply, codes):
    return [{"reply": reply, "codes": codes}]


def test_all_have_feature():
    ok, _ = ev.check({"type": "all_have_feature",
                      "feature": "pet-friendly"},
                     turns("", ["FA-NL-01", "FA-NL-02"]), None)
    assert ok
    ok, info = ev.check({"type": "all_have_feature",
                         "feature": "pet-friendly"},
                        turns("", ["FA-NL-01", "FA-NL-03"]), None)
    assert not ok and "FA-NL-03" in info


def test_min_martindale_and_snag():
    ok, _ = ev.check({"type": "min_martindale", "value": 50000},
                     turns("", ["FA-VL-01", "FA-VL-04"]), None)
    assert ok
    ok, _ = ev.check({"type": "max_snag", "value": "low"},
                     turns("", ["FA-VL-01", "FA-NL-02"]), None)
    assert ok
    ok, info = ev.check({"type": "max_snag", "value": "low"},
                        turns("", ["FA-VL-01", "FA-NL-04"]), None)
    assert not ok and "FA-NL-04" in info


def test_reply_lang_detection():
    assert ev.detect_lang("مرحبا بك في ريكوفر") == "ar"
    assert ev.detect_lang("मुझे कपड़ा चाहिए") == "hi"
    assert ev.detect_lang("Voici un tissu pour votre canapé") == "fr"
    assert ev.detect_lang("Esta tela es para tu sofá") == "es"
    assert ev.detect_lang("Here is a fabric for your sofa") == "en"


def test_targets_chosen():
    multi = [{"reply": "a", "codes": [],
              "targets": {"chosen": ["sofa"]}},
             {"reply": "b", "codes": [],
              "targets": {"chosen": ["sofa", "cushions"]}}]
    ok, _ = ev.check({"type": "targets_chosen",
                      "values": ["sofa", "cushions"]}, multi, None)
    assert ok
    ok, info = ev.check({"type": "targets_chosen",
                         "values": ["sofa", "curtains"]}, multi, None)
    assert not ok and "curtains" in info
    ok, _ = ev.check({"type": "targets_chosen", "values": []},
                     turns("x", []), None)
    assert ok


def test_recs_max_count():
    ok, _ = ev.check({"type": "recs_max_count", "value": 0},
                     turns("x", []), None)
    assert ok
    ok, _ = ev.check({"type": "recs_max_count", "value": 2},
                     turns("x", ["A", "B", "C"]), None)
    assert not ok


def test_declined_and_coordinated():
    ok, _ = ev.check({"type": "declined"},
                     turns("That's outside my expertise, sorry.", []), None)
    assert ok
    ok, _ = ev.check({"type": "not_declined"},
                     turns("Sure, which color?", []), None)
    assert ok
    ok, _ = ev.check(
        {"type": "coordinated", "scope": "all"},
        turns("", ["FA-NL-02"]) + turns("", ["FA-LA-01"]), None)
    assert ok
