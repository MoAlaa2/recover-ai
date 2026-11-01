"""Five-language live proof on the deployed app (EN AR HI FR ES).

One living-room session per language: photo -> answers -> recs ->
single Try -> browse -> Apply-all -> summary (quote/CO2/wa.me).
Asserts zero console errors, no horizontal overflow, no '$', and
per-language summary needles. Screenshots per language.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
from live_e2e import (CREDS, LIVING, OUT_DIR, load_demo_creds,  # noqa
                      run_phase, DEPLOYED)

LANGS = {
    "en": {"all": ["all", "mix", "everything", "both"],
           "fallback": ("Warm beige, kids, budget 150 per meter. "
                        "Recommend 3 fabrics now."),
           "needles": ["$", "Total", "Preliminary estimate",
                       "https://wa.me/?text="]},
    "ar": {"all": ["كل", "mix"],
           "fallback": ("درجات بيج دافية، عندي أطفال، الميزانية "
                        "١٥٠ للمتر. رشّح لي ٣ أقمشة الحين."),
           "needles": ["$", "الإجمالي", "تقدير مبدئي",
                       "https://wa.me/?text="]},
    "hi": {"all": ["सब", "सभी", "mix"],
           "fallback": ("गर्म बेज रंग, बच्चे हैं, बजट 150 प्रति मीटर। "
                        "अभी 3 फ़ैब्रिक सुझाएँ।"),
           "needles": ["$", "कुल", "शुरुआती अंदाज़ा",
                       "https://wa.me/?text="]},
    "fr": {"all": ["tout", "tous", "mix"],
           "fallback": ("Beige chaud, enfants, budget 150 par mètre. "
                        "Recommandez 3 tissus maintenant."),
           "needles": ["$", "Total", "Estimation préliminaire",
                       "https://wa.me/?text="]},
    "es": {"all": ["todo", "todos", "mezcla"],
           "fallback": ("Beige cálido, niños, presupuesto 150 por metro. "
                        "Recomienda 3 telas ahora."),
           "needles": ["$", "Total", "Estimación preliminar",
                       "https://wa.me/?text="]},
}

WANT = [a for a in sys.argv[1:] if a in LANGS] or list(LANGS)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    user, pw = load_demo_creds()
    CREDS["user"], CREDS["pw"] = user, pw
    all_timings = {}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.webkit.launch()
        device = dict(p.devices["iPhone 15 Pro"])
        device["viewport"] = {"width": 390, "height": 844}
        for lang in WANT:
            cfg = LANGS[lang]
            for attempt in range(2):
                ctx = browser.new_context(
                    **device, http_credentials={"username": user,
                                                 "password": pw})
                try:
                    timings, errs = run_phase(
                        ctx.new_page(), lang, "multi", LIVING,
                        cfg["all"], cfg["fallback"], want_multi=True,
                        needles=cfg["needles"])
                    break
                except Exception as exc:  # noqa: BLE001 - retry once
                    print("LANG %s attempt %d failed: %r"
                          % (lang, attempt, exc))
                    ctx.close()
                    if attempt == 1:
                        raise
                    continue
            all_timings[lang] = timings
            ctx.close()
        browser.close()
    with open(os.path.join(OUT_DIR, "langs-timings.json"), "w") as f:
        json.dump(all_timings, f, indent=1, ensure_ascii=False)
    print(json.dumps(all_timings, indent=1,
                     ensure_ascii=False)[:3000])
    bad = [e for t in all_timings.values()
           for e in t.get("console_errors", [])]
    assert not bad, "console errors: %s" % bad[:5]


if __name__ == "__main__":
    main()
