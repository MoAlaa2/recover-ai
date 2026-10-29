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


def test_grounding_log_defaults_to_volume_dir(tmp_path, monkeypatch):
    import json

    import app.core.config as config_mod
    from app.services import consultant as c
    monkeypatch.setattr(config_mod, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(c, "GROUNDING_LOG", None)
    c.log_grounding("s", "bad", "p", ["FA-AC-01"])
    dest = tmp_path / "logs" / "grounding_log.json"
    assert dest.exists()
    assert json.load(open(dest))[0]["session_id"] == "s"


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


def test_hypo_receipt_discloses():
    t = [{"reply": "Here are 3 picks.", "codes": ["FA-NL-01"],
          "receipts": ["Eased: hypoallergenic"]}]
    ok, info = ev.check({"type": "hypo_or_disclosed"}, t, None)
    assert ok and info == "receipt disclosed"


def test_hypo_silent_everywhere_fails():
    t = [{"reply": "Here are 3 picks.", "codes": ["FA-NL-01"],
          "receipts": ["Matches: budget"]}]
    ok, info = ev.check({"type": "hypo_or_disclosed"}, t, None)
    assert not ok and info == "not disclosed"


def test_hypo_reply_disclosure_still_passes():
    t = [{"reply": "I eased the requirements.", "codes": ["FA-NL-01"],
          "receipts": []}]
    ok, _ = ev.check({"type": "hypo_or_disclosed"}, t, None)
    assert ok


def test_receipt_contains_any():
    t = [{"reply": "Here are picks.", "codes": ["FA-VL-06"],
          "receipts": ["Eased: budget (+85 SAR)"]}]
    ok, _ = ev.check({"type": "receipt_contains_any",
                      "values": ["budget", "الميزانية"]}, t, None)
    assert ok
    t2 = [{"reply": "Here are picks.", "codes": ["FA-VL-06"],
           "receipts": ["Matches: tone"]}]
    ok, info = ev.check({"type": "receipt_contains_any",
                         "values": ["budget", "الميزانية"]}, t2, None)
    assert not ok and info == "not on cards"
