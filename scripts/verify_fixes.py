"""Live verify of the 7 multi-object fixes on the DEPLOYED app.

WebKit iPhone 15 Pro, EN + AR. Real models. Credentials come only
from .env.demo via env (never printed). Usage:
.venv/bin/python scripts/verify_fixes.py [--lang en|ar|both]
Output: recover-ai/uploads/e2e/verify-<lang>.json + screenshots.
"""
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOYED = "https://moalaa2--recover-ai-web.us-east.modal.run"
LIVING = os.path.join(BASE_DIR, "data", "samples", "living.jpg")
OUT_DIR = os.path.join(BASE_DIR, "uploads", "e2e")


def load_demo_creds():
    if os.environ.get("DEMO_USER") and os.environ.get("DEMO_PASS"):
        return os.environ["DEMO_USER"], os.environ["DEMO_PASS"]
    for path in (os.path.join(BASE_DIR, ".env.demo"),
                 os.path.expanduser("~/.env.demo")):
        if os.path.isfile(path):
            creds = {}
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        creds[k.strip()] = v.strip()
            if creds.get("DEMO_USER") and creds.get("DEMO_PASS"):
                return creds["DEMO_USER"], creds["DEMO_PASS"]
    raise FileNotFoundError("demo credentials not found")


def warmup(user, pw, timeout=420):
    """Wait out a cold container after a redeploy (no secrets printed)."""
    import base64 as _b64
    import urllib.request as _url
    head = {"Authorization": "Basic " + _b64.b64encode(
        ("%s:%s" % (user, pw)).encode()).decode()}
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            req = _url.Request(DEPLOYED + "/consult", headers=head)
            with _url.urlopen(req, timeout=60) as resp:
                if resp.status == 200:
                    return round(time.time() - t0, 1)
        except Exception:
            time.sleep(10)
    raise RuntimeError("deployed app never warmed up")


def check(pg, lang, tag):
    out = {"errors": []}
    errs = []
    pg.on("console", lambda m: errs.append(m.text[:200])
          if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))

    def shot(name):
        pg.screenshot(path=os.path.join(OUT_DIR, "verify-%s-%s.png"
                                        % (tag, name)))

    def overflow():
        return pg.evaluate(
            "() => document.documentElement.scrollWidth - "
            "document.documentElement.clientWidth")

    def msgs_text():
        return pg.eval_on_selector_all(
            "#messages .msg", "e => e.map(x => x.innerText)")

    url = DEPLOYED + "/consult" + ("?lang=ar" if lang == "ar" else "")
    pg.goto(url, wait_until="networkidle", timeout=90000)
    pg.wait_for_selector("#composer", timeout=30000)
    # Cold load: composer fully above the toolbar fold.
    box = pg.eval_on_selector(
        "#composer", "e => { const r = e.getBoundingClientRect(); "
        "return [r.top, r.bottom, window.innerHeight]; }")
    out["composer_visible"] = box[1] <= box[2] + 1
    assert out["composer_visible"], "composer hidden: %r" % (box,)
    assert overflow() == 0
    shot("cold")

    cushion_word = "cushion" if lang == "en" else "وسا"
    t0 = time.perf_counter()
    pg.set_input_files("#fileInput", LIVING)
    pg.wait_for_selector(".outline-msg", timeout=600000)
    out["photo_s"] = round(time.perf_counter() - t0, 1)
    taps = pg.eval_on_selector_all(
        ".outline-msg [data-outline]", "e => e.map(x => x.dataset.outline)")
    assert set(taps) >= {"sofa", "cushions", "curtains"}, taps
    cap = pg.eval_on_selector(".outline-msg .chat-outline-cap",
                              "e => e.innerText")
    assert cap.strip(), "outline caption empty"
    shot("outline")

    # Tap the cushions region like a finger (coordinates, not the
    # button handle — nested taps are pointer-transparent by design).
    box = pg.eval_on_selector(
        '.outline-msg [data-outline="cushions"]',
        "e => { const r = e.getBoundingClientRect(); "
        "return [r.x + r.width / 2, r.y + r.height / 2]; }")
    pg.mouse.click(box[0], box[1])
    # First round: choose cushions explicitly (the target under test).
    # Later rounds: answer needs generically until the cards appear.
    t0 = time.perf_counter()
    cushion_key = "cushion" if lang == "en" else "وسا"
    for round_no in range(4):
        try:
            pg.wait_for_selector("#chips:not([hidden])", timeout=90000)
        except Exception:
            break
        texts = pg.eval_on_selector_all(
            "#chips button", "els => els.map(x => x.textContent)")
        if not texts:
            break
        if round_no == 0:
            pick = next((c for c in texts
                         if cushion_key in (c or "").lower()), texts[0])
        else:
            pick = next((c for c in texts
                         if "all" in c.lower() or "mix" in c.lower()
                         or "كل" in c or "just" in c.lower()
                         or "show" in c.lower()), texts[0])
        pg.click("#chips button:has-text('%s')" % pick[:14])
        pg.wait_for_timeout(2500)
        if pg.eval_on_selector_all("#messages .mini-card",
                                   "e => e.length") > 0:
            break
    if pg.eval_on_selector_all("#messages .mini-card",
                               "e => e.length") == 0:
        nudge = ("Warm beige, kids, budget 150 per meter. "
                 "Recommend 3 fabrics now."
                 if lang == "en" else
                 "درجات بيج دافية، عندي أطفال، الميزانية ١٥٠ للمتر. "
                 "رشّح لي ٣ أقمشة الحين.")
        pg.fill("#composerInput", nudge)
        pg.eval_on_selector("#composer", "f => f.requestSubmit()")
        pg.wait_for_selector("#messages .mini-card", timeout=300000)
    # Diagnostics: tap geometry vs the displayed photo.
    diag = pg.evaluate(
        "() => { const img = document.querySelector("
        "'.chat-outline-photo img'); const r = img.getBoundingClientRect();"
        " return { img: [r.x, r.y, r.width, r.height],"
        " taps: Array.from(document.querySelectorAll("
        "'.chat-outline-photo [data-outline]')).map(e => {"
        " const b = e.getBoundingClientRect();"
        " return [e.dataset.outline, b.x, b.y, b.width, b.height]; }) }; }")
    print("TAP-DIAG " + json.dumps(diag)[:900])
    out["rec_s"] = round(time.perf_counter() - t0, 1) - out["photo_s"]
    n_cards = pg.eval_on_selector_all("#messages .mini-card",
                                      "e => e.length")
    assert n_cards == 3, "expected 3 cards, got %d" % n_cards
    heights = pg.eval_on_selector_all(
        "#messages .mini-card", "e => e.map(x => x.offsetHeight)")
    assert max(heights) - min(heights) <= 4, heights
    labels = pg.eval_on_selector_all(
        "#messages .mini-try span", "e => e.map(x => x.innerText)")
    want = "cushion" if lang == "en" else "المخدات"
    assert all(want in (label or "") for label in labels[:3]), labels
    receipts = pg.eval_on_selector_all(
        "#messages .receipt-line", "e => e.map(x => x.innerText)")
    assert len(receipts) >= 3 and all(r.strip() for r in receipts[:3]), \
        receipts
    first_x = pg.eval_on_selector(
        "#messages .mini-card", "e => e.getBoundingClientRect().left")
    row_x = pg.eval_on_selector(
        "#messages .mini-recs", "e => e.getBoundingClientRect().left")
    assert first_x >= row_x - 2, (first_x, row_x)
    shot("recs")
    body_text = "\n".join(msgs_text())
    if lang == "en":
        assert "$" not in body_text, "dollar sign in chat"
    t1 = time.perf_counter()
    pg.click("#messages .mini-try >> nth=0")
    pg.wait_for_selector("#swapResult:not([hidden])", timeout=600000)
    out["swap_s"] = round(time.perf_counter() - t1, 1)
    shot("swap")
    pg.click("#swapClose")
    pg.wait_for_timeout(1000)
    # Exactly one chat message per swap result.
    thumbs = pg.eval_on_selector_all(
        "#messages .chat-swap .swap-thumb",
        "e => e.map(x => x.getAttribute('src'))")
    assert len(thumbs) == len(set(thumbs)) and thumbs, thumbs
    auto_left = pg.eval_on_selector_all(
        "#messages .msg.them[data-auto]", "e => e.length")
    assert auto_left == 0, "unmerged auto bubble left"
    bar = pg.eval_on_selector("#roomBar", "e => e.innerText")
    assert "Your room" not in bar and "غرفتك" not in bar.split("\n")[0], bar
    title_changed = ("cushion" in bar.lower() or "وسا" in bar
                     or "مخد" in bar)
    assert title_changed, "room bar title not fabric: %r" % bar
    assert overflow() == 0
    shot("done")
    out["errors"] = errs
    assert not errs, errs[:3]
    return out


def main():
    which = sys.argv[sys.argv.index("--lang") + 1] \
        if "--lang" in sys.argv else "both"
    langs = ["en", "ar"] if which == "both" else [which]
    os.makedirs(OUT_DIR, exist_ok=True)
    user, pw = load_demo_creds()
    print("WARMUP %ss" % warmup(user, pw))
    results = {}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.webkit.launch()
        device = dict(p.devices["iPhone 15 Pro"])
        device["viewport"] = {"width": 390, "height": 844}

        def one(lang):
            ctx = browser.new_context(
                **device, http_credentials={"username": user,
                                              "password": pw})
            try:
                return check(ctx.new_page(), lang, lang)
            finally:
                ctx.close()

        for lang in langs:
            try:
                results[lang] = one(lang)
            except Exception as exc:
                print("RETRY %s after %s" % (lang, exc)[:200])
                time.sleep(60)
                results[lang] = one(lang)
        browser.close()
    with open(os.path.join(OUT_DIR, "verify.json"), "w") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    print(json.dumps(results, indent=1, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
