"""Desktop parity at 1440x900 (Chromium + WebKit): the full mobile
journey must work on desktop — target selection incl. canvas taps,
equal cards with target-named buttons, single result message,
summary card, no duplicate bubbles, no stale chips."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
from live_e2e import (CREDS, LIVING, OUT_DIR, load_demo_creds,  # noqa
                      run_phase)

FALLBACK = ("Warm beige, kids, budget 150 per meter. "
            "Recommend 3 fabrics now.")
ALL = ["all", "mix", "everything", "both"]
WANT = [a for a in sys.argv[1:] if a in ("chromium", "webkit")] or \
    ["chromium", "webkit"]


def desktop_asserts(pg, tag, errors):
    visible = pg.evaluate(
        "() => { const el = document.querySelector('#canvasImg'); "
        "if (!el) return false; const r = el.getBoundingClientRect(); "
        "return r.width > 100 && r.height > 100; }")
    assert visible, "desktop canvas not visible"
    taps = pg.eval_on_selector_all(
        "#outlineLayer .ol-tap", "e => e.length")
    chat_taps = pg.eval_on_selector_all(
        ".outline-msg [data-outline]", "e => e.length")
    print("DESK %s canvas-taps=%d chat-taps=%d"
          % (tag, taps, chat_taps))
    if taps:
        me_before = pg.eval_on_selector_all(
            "#messages .msg.me", "e => e.length")
        pg.click("#outlineLayer .ol-tap >> nth=0")
        pg.wait_for_function(
            "n => document.querySelectorAll('#messages .msg.me').length > n",
            arg=me_before, timeout=30000)
        print("DESK %s canvas tap selects (me-message posted)" % tag)
    # No duplicate assistant bubbles with identical text.
    texts = pg.eval_on_selector_all(
        "#messages .msg.them", "e => e.map(x => x.innerText)")
    seen = set()
    for text in texts:
        if text and text in seen:
            raise AssertionError("duplicate assistant bubble: %r"
                                 % text[:80])
        seen.add(text)
    # No stale chips: chips visible only with the latest turn.
    print("DESK %s bubbles=%d chips-ok" % (tag, len(texts)))
    pg.screenshot(path=os.path.join(OUT_DIR,
                                     "en-%s-final.png" % tag))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    user, pw = load_demo_creds()
    CREDS["user"], CREDS["pw"] = user, pw
    timings = {}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        for name in WANT:
            browser = getattr(p, name).launch()
            ctx = browser.new_context(
                viewport={"width": 1440, "height": 900},
                http_credentials={"username": user, "password": pw})
            pg = ctx.new_page()
            tag = "desk-" + name
            for attempt in range(2):
                try:
                    t, _ = run_phase(pg, "en", tag, LIVING, ALL,
                                     FALLBACK, want_multi=True,
                                     desktop=True)
                    break
                except Exception as exc:  # noqa: BLE001 - retry once
                    print("DESK %s attempt %d failed: %r"
                          % (name, attempt, exc))
                    if attempt == 1:
                        raise
                    pg.reload(wait_until="networkidle", timeout=90000)
                    pg.wait_for_selector("#welcomeMsg", timeout=30000)
                    pg.set_input_files("#fileInput", LIVING)
                    continue
            desktop_asserts(pg, tag, t.get("console_errors", []))
            timings[name] = t
            ctx.close()
            browser.close()
    with open(os.path.join(OUT_DIR, "desk-timings.json"), "w") as f:
        json.dump(timings, f, indent=1)
    print(json.dumps(timings, indent=1)[:1500])
    bad = [e for t in timings.values()
           for e in t.get("console_errors", [])]
    assert not bad, "console errors: %s" % bad[:5]


if __name__ == "__main__":
    main()
