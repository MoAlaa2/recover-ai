"""Scripted scenario eval for the ReCover consultant.

Runs each scenario in data/scenarios.json as a live multi-turn
conversation and checks the returned recommendations against
data/fabric_specs.json fields (never the model's words). Prints a
pass/fail table. A failing scenario is retried once, then recorded
as an error without crashing the run. Only a full run with zero
errors writes data/eval_report.json; scoped (--only) or incomplete
runs write data/eval_report_partial.json instead.
"""
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from app.services import consultant as c
from app.services.catalog import (contains_egyptian, get_fabric,
                                  is_light_unprotected, load_specs)

SPECS_PATH = os.path.join(BASE_DIR, "data", "fabric_specs.json")
SCEN_PATH = os.path.join(BASE_DIR, "data", "scenarios.json")
REPORT_PATH = os.path.join(BASE_DIR, "data", "eval_report.json")

SNAG_RANK = {"low": 0, "medium": 1, "high": 2}
DISCLOSURE_WORDS = ["relax", "note:", "خفف", "ملاحظة", "budget",
                    "الميزانية", "to find these", "stretched",
                    "widened", "eased", "slightly", "عشان ألقى",
                    "الأنسب", "وسّعت", "فتحت", "شوي"]
CARE_WORDS = ["extra care", "light-colored", "light colored", "stain",
              "عناية", "فاتح", "مقاوم للبقع"]
DECLINE_MARKERS = ["outside my expertise", "خارج تخصصي"]
FR_MARKERS = ["tissu", "canap", "voici", "recommande", "votre", "rideaux",
              "maison", "pour"]
ES_MARKERS = ["tela", "sofá", "para", "estos", "recomiendo",
              "tapicer", "cojines", "salón"]


def detect_lang(text):
    t = text or ""
    if re.search(r"[\u0600-\u06FF]", t):
        return "ar"
    if re.search(r"[\u0900-\u097F]", t):
        return "hi"
    low = t.lower()
    fr = sum(low.count(w) for w in FR_MARKERS)
    es = sum(low.count(w) for w in ES_MARKERS)
    if fr > es and fr > 0:
        return "fr"
    if es > fr and es > 0:
        return "es"
    return "en"


def specs_of(codes):
    return [get_fabric(code) for code in codes]


def union_codes(turns):
    seen = []
    for t in turns:
        for code in t["codes"]:
            if code not in seen:
                seen.append(code)
    return seen


def check(check, turns, specs):
    ctype = check["type"]
    idx = check.get("turn", len(turns) - 1)
    codes = turns[idx]["codes"] if idx < len(turns) else []
    reply = turns[idx]["reply"] if idx < len(turns) else ""
    items = [s for s in specs_of(codes) if s]

    if ctype == "recs_min_count":
        ok = len(codes) >= check["value"]
        return ok, "%d recs" % len(codes)
    if ctype == "recs_max_count":
        ok = len(codes) <= check.get("value", 0)
        return ok, "%d recs (max %s)" % (len(codes),
                                         check.get("value", 0))
    if ctype == "all_have_feature":
        bad = [i["code"] for i in items
               if check["feature"] not in i["features"]]
        return not bad, "missing: %s" % bad if bad else "all match"
    if ctype == "each_has_any_feature":
        bad = [i["code"] for i in items
               if not set(check["features"]) & set(i["features"])]
        return not bad, "missing: %s" % bad if bad else "all match"
    if ctype == "min_martindale":
        bad = [i["code"] for i in items
               if (i.get("martindale") or 0) < check["value"]]
        return not bad, "below: %s" % bad if bad else "all match"
    if ctype == "all_field_in":
        bad = [i["code"] for i in items
               if i.get(check["field"]) not in check["values"]]
        return not bad, "mismatch: %s" % bad if bad else "all match"
    if ctype == "any_pattern":
        ok = any(i.get("pattern_type") == check["value"] for i in items)
        return ok, "no %s found" % check["value"] if not ok else "found"
    if ctype == "max_snag":
        limit = SNAG_RANK[check["value"]]
        bad = [i["code"] for i in items
               if SNAG_RANK.get(i.get("snag_risk"), 9) > limit]
        return not bad, "too risky: %s" % bad if bad else "all match"
    if ctype == "reply_contains_any":
        ok = any(v in reply for v in check["values"])
        return ok, "none mentioned" if not ok else "mentioned"
    if ctype == "receipt_contains_any":
        # Budget/need disclosure lives on the card receipt by design
        # (prose must not repeat it on rec turns).
        recs = turns[idx].get("receipts", []) \
            if idx < len(turns) else []
        joined = " ".join(r for r in recs if r)
        ok = any(v in joined for v in check["values"])
        return ok, "not on cards" if not ok else "on cards"
    if ctype == "reply_lang":
        got = detect_lang(reply)
        return got == check["lang"], "got %s" % got
    if ctype == "no_egyptian":
        ok = not contains_egyptian(reply)
        return ok, "egyptian markers!" if not ok else "saudi dialect"
    if ctype == "declined":
        ok = (not codes and any(m in reply for m in DECLINE_MARKERS))
        return ok, "not declined" if not ok else "declined"
    if ctype == "not_declined":
        ok = not any(m in reply for m in DECLINE_MARKERS)
        return ok, "wrongly declined" if not ok else "continued"
    if ctype == "usages_present":
        scope = union_codes(turns) if check.get("scope") == "all" else codes
        have = {get_fabric(x)["usage"] for x in scope if get_fabric(x)}
        missing = [u for u in check["values"] if u not in have]
        return not missing, "missing: %s" % missing if missing else (
            "have %s" % sorted(have))
    if ctype == "coordinated":
        scope = union_codes(turns) if check.get("scope") == "all" else codes
        ups = [get_fabric(x) for x in scope
               if get_fabric(x) and get_fabric(x)["usage"] == "upholstery"]
        cur = [get_fabric(x) for x in scope
               if get_fabric(x) and get_fabric(x)["usage"] == "curtains"]
        ok = False
        for u in ups:
            for cc in cur:
                ucol = set([u["primary_color"].lower()] +
                           [s.lower() for s in u.get("secondary_colors",
                                                     [])])
                ccol = set([cc["primary_color"].lower()] +
                           [s.lower() for s in cc.get("secondary_colors",
                                                      [])])
                if u["tone"] == cc["tone"] or ucol & ccol:
                    ok = True
        return ok, "no coordinated pair" if not ok else "coordinated"
    if ctype == "hypo_or_disclosed":
        if all("hypoallergenic" in i["features"] for i in items) and items:
            return True, "all hypoallergenic"
        low = reply.lower()
        if any(w in low or w in reply for w in DISCLOSURE_WORDS):
            return True, "relaxation disclosed"
        # Cards carry the one-line receipt on rec turns (prose must
        # not repeat it), so a receipt naming the need discloses too.
        recs = turns[idx].get("receipts", []) \
            if idx < len(turns) else []
        joined = " ".join(r for r in recs if r).lower()
        if "hypoallergenic" in joined or "للحساسية" in joined:
            return True, "receipt disclosed"
        return False, "not disclosed"
    if ctype == "lux_or_jacquard":
        bad = [i["code"] for i in items
               if not (i["collection"] == "Velvet Luxe"
                       or "jacquard" in i["material"])]
        return not bad, "not luxe: %s" % bad if bad else "all luxe"
    if ctype == "reply_nonempty":
        ok = bool(reply and reply.strip())
        return ok, "empty reply" if not ok else "reply has prose"
    if ctype == "targets_chosen":
        got = set()
        for t in turns:
            got |= set(((t.get("targets") or {}).get("chosen")) or [])
        missing = [v for v in check.get("values", []) if v not in got]
        return not missing, ("missing: %s" % missing) if missing else (
            "chosen %s" % sorted(got))
    if ctype == "light_warning":
        flagged = [i["code"] for i in items if is_light_unprotected(i)]
        if not flagged:
            return True, "no risky light fabric shown"
        low = reply.lower()
        warned = any(w in low or w in reply for w in CARE_WORDS)
        return warned, "no warning for %s" % flagged if not warned else (
            "warned for %s" % flagged)
    return False, "unknown check " + ctype


def run_turns(sid, messages):
    turns = []
    for m in messages:
        if isinstance(m, dict):
            out = c.chat(sid, m.get("message", ""), m.get("image"))
        else:
            out = c.chat(sid, m)
        turns.append({"reply": out["reply"],
                      "codes": [r["code"] for r in
                                out["recommendations"]],
                      "receipts": [r.get("receipt", "") for r in
                                   out["recommendations"]],
                      "targets": out.get("targets", {})})
    return turns


def scenario_entry(sc):
    """Run one scenario. Returns its report entry (may raise)."""
    if "variants" in sc:
        detail = []
        ok_all = True
        for n, var in enumerate(sc["variants"]):
            turns = run_turns("eval-%s-%d" % (sc["id"], n),
                              [var["message"]])
            for chk in var["checks"]:
                ok, info = check(chk, turns, None)
                detail.append("%s:%s %s (%s)" % (
                    var["lang"], chk["type"],
                    "PASS" if ok else "FAIL", info))
                ok_all = ok_all and ok
        return {"id": sc["id"], "pass": ok_all, "detail": detail}
    turns = run_turns("eval-" + sc["id"], sc["turns"])
    detail = []
    ok_all = True
    for chk in sc["checks"]:
        ok, info = check(chk, turns, None)
        detail.append("%s %s (%s)" % (
            chk["type"], "PASS" if ok else "FAIL", info))
        ok_all = ok_all and ok
    return {"id": sc["id"], "pass": ok_all, "detail": detail}


PARTIAL_PATH = os.path.join(BASE_DIR, "data", "eval_report_partial.json")


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="",
                        help="comma-separated scenario ids")
    args = parser.parse_args(argv)
    with open(SCEN_PATH, encoding="utf-8") as f:
        scenarios = json.load(f)
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        scenarios = [s for s in scenarios if s["id"] in wanted]
    load_specs()
    report = {"scenarios": []}
    errors = 0
    for sc in scenarios:
        try:
            entry = scenario_entry(sc)
        except Exception:  # noqa: BLE001 - retry once, then record
            try:
                entry = scenario_entry(sc)
            except Exception as exc:  # noqa: BLE001 - never crash run
                entry = {"id": sc["id"], "pass": False, "status": "error",
                         "detail": ["error: %s" % exc]}
                errors += 1
        report["scenarios"].append(entry)
        print("%-20s %s" % (entry["id"],
                            "ERROR" if entry.get("status") == "error"
                            else "PASS" if entry["pass"] else "FAIL"),
              flush=True)
    if args.only or errors:
        # Scoped or incomplete runs never touch the full report.
        with open(PARTIAL_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        if errors and not args.only:
            print("wrote %s (%d errored); %s untouched"
                  % (PARTIAL_PATH, errors, REPORT_PATH))
    else:
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    passed = sum(1 for s in report["scenarios"] if s["pass"])
    print("passed %d/%d" % (passed, len(report["scenarios"])))
    for s in report["scenarios"]:
        if not s["pass"]:
            for d in s["detail"]:
                if "FAIL" in d:
                    print("  %s: %s" % (s["id"], d))
    return 0 if passed == len(report["scenarios"]) else 1


if __name__ == "__main__":
    sys.exit(main())
