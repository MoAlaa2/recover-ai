"""Pre-compute the judge-sample cache: analysis, targets, masks.

For each of the 5 new samples: runs room analysis in 6 language slots
(None + en/ar/hi/fr/es), lists + segments targets live via the normal
pipeline, then copies the masks to data/samples/masks/<id>-<target>.png
and writes data/samples/cache/<id>.json. Commit both dirs: the deploy
bakes data/ into the image, so picking a sample needs zero model calls.

Run explicitly after (re)generating the sample images. Prints a
validation report of listed pieces vs the expected set per sample.
"""
import json
import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.services import sample_cache  # noqa: E402
from app.services import targets as targets_mod  # noqa: E402
from app.services.consultant import analyze_room  # noqa: E402

LANGS = [None, "en", "ar", "hi", "fr", "es"]

EXPECTED = {
    "sofa_pillows": {"sofa", "cushions"},
    "sage_curtains": {"curtains"},
    "navy_living": {"sofa", "armchair", "cushions", "curtains"},
    "majlis_burgundy": {"sofa", "cushions", "curtains"},
    "mustard_armchair": {"armchair"},
}


def main():
    os.makedirs(sample_cache.CACHE_DIR, exist_ok=True)
    os.makedirs(sample_cache.MASKS_DIR, exist_ok=True)
    report = {}
    for sid in sample_cache.SAMPLE_IDS:
        rel = os.path.join("data", "samples", sid + ".jpg")
        if not os.path.isfile(os.path.join(BASE_DIR, rel)):
            print("MISSING %s" % rel, flush=True)
            report[sid] = {"error": "missing image"}
            continue
        import hashlib
        with open(os.path.join(BASE_DIR, rel), "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        analyses = {}
        for lang in LANGS:
            key = lang if lang else "null"
            try:
                analyses[key] = analyze_room(rel, lang)
            except Exception as exc:  # noqa: BLE001 - report, keep rest
                print("ANALYSIS-FAIL %s %s: %s" % (sid, key, exc)[:200],
                      flush=True)
                analyses[key] = {"error": str(exc)[:200]}
        try:
            tgts = targets_mod.detect_targets(rel)
        except Exception as exc:  # noqa: BLE001 - report
            print("TARGETS-FAIL %s: %s" % (sid, exc)[:200], flush=True)
            report[sid] = {"error": "targets: %s" % str(exc)[:200]}
            continue
        saved = []
        for item in tgts:
            src = os.path.join(BASE_DIR, item["mask_url"].lstrip("/"))
            dest_name = "%s-%s.png" % (sid, item["type"])
            dest = os.path.join(sample_cache.MASKS_DIR, dest_name)
            shutil.copyfile(src, dest)
            record = dict(item)
            record["mask_url"] = "data/samples/masks/" + dest_name
            saved.append(record)
        entry = {"sample_id": sid, "sha256": sha,
                 "analyses": analyses, "targets": saved}
        with open(os.path.join(sample_cache.CACHE_DIR, sid + ".json"),
                  "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
        got = {t["type"] for t in saved}
        want = EXPECTED[sid]
        status = "OK" if want <= got else "MISSING %s" % sorted(want - got)
        print("WARMED %s sha=%s.. pieces=%s %s"
              % (sid, sha[:12], sorted(got), status), flush=True)
        report[sid] = {"pieces": sorted(got), "status": status,
                       "analyses": sorted(analyses)}
    print("WARM-REPORT " + json.dumps(report, ensure_ascii=False),
          flush=True)


if __name__ == "__main__":
    main()
