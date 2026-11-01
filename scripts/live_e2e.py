"""Live E2E proof on the DEPLOYED app with real models.

Reads demo credentials from .env.demo into memory only (never
printed, logged or committed). Real iPhone-15-Pro WebKit sessions:
Phase A uploads the real iPhone HEIC (kitchen) through a single
curtain Try; Phase B uploads the multi sample (living room) through
recs, single Try, Browse apply and multi Apply-all.
Timings + screenshots per stage. Usage:
.venv/bin/python scripts/live_e2e.py [--lang en|ar]
Output: recover-ai/uploads/e2e/<lang>-timings.json + screenshots.
(uploads/ is gitignored, so screenshots never touch the repo.)
"""
import json
import os
import re
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOYED = "https://moalaa2--recover-ai-web.us-east.modal.run"
HEIC = os.path.join(BASE_DIR, "tests", "fixtures", "IMG_6327.HEIC")
LIVING = os.path.join(BASE_DIR, "data", "samples", "living.jpg")
OUT_DIR = os.path.join(BASE_DIR, "uploads", "e2e")

CANDIDATE_ENV_FILES = [
    os.path.join(BASE_DIR, ".env.demo"),
    os.path.join(os.path.dirname(BASE_DIR), ".env.demo"),
    os.path.expanduser("~/.env.demo"),
]


def load_demo_creds():
    if os.environ.get("DEMO_USER") and os.environ.get("DEMO_PASS"):
        return os.environ["DEMO_USER"], os.environ["DEMO_PASS"]
    for path in CANDIDATE_ENV_FILES:
        if not os.path.isfile(path):
            continue
        creds = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    creds[key.strip()] = value.strip()
        if creds.get("DEMO_USER") and creds.get("DEMO_PASS"):
            return creds["DEMO_USER"], creds["DEMO_PASS"]
    raise FileNotFoundError("demo credentials not found")


def _api_get(path, user, pw):
    import base64 as _b64
    import urllib.request as _url
    auth = {"Authorization": "Basic " + _b64.b64encode(
        ("%s:%s" % (user, pw)).encode()).decode()}
    url = DEPLOYED + path if path.startswith("/") \
        else DEPLOYED + "/" + path
    req = _url.Request(url, headers=auth)
    with _url.urlopen(req, timeout=120) as resp:
        return resp.read()


CREDS = {}


def dump_state(pg, tag, stage):
    try:
        pg.screenshot(path=os.path.join(
            OUT_DIR, "%s-fail-%s.png" % (tag, stage)))
        msgs = pg.eval_on_selector_all(
            "#messages .msg", "e => e.map(x => x.innerText)")
        print("DUMP %s/%s msgs=%r" % (tag, stage, msgs[-3:]))
    except Exception as ex:  # noqa: BLE001
        print("dump failed: %s" % ex)


def wait_swap(pg, tag, trigger, timeout=300000):
    """Wait for the swap result; re-fire the trigger once on timeout.

    The client gives up on a silent stream after ~75s while a slow
    server keeps working, so the retry (warmed caches) usually lands.
    """
    for attempt in range(2):
        try:
            pg.wait_for_selector("#swapResult:not([hidden])",
                                 timeout=timeout)
            return
        except Exception as exc:  # noqa: BLE001
            dump_state(pg, tag, "swap-timeout-%d" % attempt)
            msgs = pg.eval_on_selector_all(
                "#messages .msg", "e => e.map(x => x.innerText)")
            print("SWAP-DUMP %s attempt %d tail=%r" % (
                tag, attempt, msgs[-2:]))
            try:
                if pg.evaluate("() => !document.querySelector"
                               "('#swapModal').hidden"):
                    pg.click("#swapClose")
                    pg.wait_for_timeout(1000)
            except Exception:  # noqa: BLE001
                pass
            if attempt == 0:
                trigger()
            else:
                raise


def run_phase(pg, lang, tag, photo, all_words, fallback_text,
              want_multi, try_single=True, needles=None, desktop=False):
    """One photo session. Returns timings dict.

    lang doubles as the ?lang= code (en has no suffix). needles
    overrides the summary-card assertions for other languages.
    desktop skips the mobile-only room-bar View tap: the assign row
    is directly visible in the canvas pane.
    """
    timings = {}
    errors = []
    def _console(m):
        if m.type != "error":
            return
        try:
            loc = m.location or {}
            url = loc.get("url", "") if isinstance(loc, dict) \
                else getattr(loc, "url", "")
        except Exception:
            url = ""
        errors.append(("%s <%s>" % (m.text, url))[:260])
    pg.on("console", _console)
    pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
    pg.on("response", lambda r: errors.append(
        ("HTTP %s <%s>" % (r.status, r.url))[:260])
        if r.status >= 400 else None)
    dump = lambda stage: dump_state(pg, lang + "-" + tag, stage)  # noqa: E731

    def shot(name):
        pg.screenshot(path=os.path.join(OUT_DIR, "%s-%s-%s.png"
                                        % (lang, tag, name)))

    def overflow():
        return pg.evaluate(
            "() => document.documentElement.scrollWidth - "
            "document.documentElement.clientWidth")

    url = DEPLOYED + "/consult" + ("" if lang == "en"
                                       else "?lang=" + lang)
    pg.goto(url, wait_until="networkidle", timeout=90000)
    if desktop:
        # Desktop empty state lives in the canvas pane; the welcome
        # chat bubble is mobile-only by design.
        pg.wait_for_selector("#dropzone", timeout=30000)
    else:
        pg.wait_for_selector("#welcomeMsg", timeout=30000)
    assert overflow() == 0

    t0 = time.perf_counter()
    pg.set_input_files("#fileInput", photo)
    # The photo turn is done when the assistant reply posts. The room
    # bar is only a secondary readiness signal (it has a known race).
    pg.wait_for_function(
        "() => document.querySelectorAll("
        "'#messages .msg.them').length >= 2", timeout=300000)
    timings["photo_turn_s"] = round(time.perf_counter() - t0, 1)
    try:
        pg.wait_for_selector("#roomBar:not([hidden])", timeout=30000)
        timings["room_bar"] = True
    except Exception:
        timings["room_bar"] = False
        dump("roombar")
    shot("photo")
    assert overflow() == 0

    # Answer chip rounds until rec cards appear (max 6: piece, mood,
    # style, light, budget), else nudge.
    t1 = time.perf_counter()
    for _ in range(6):
        try:
            pg.wait_for_selector("#chips:not([hidden])", timeout=60000)
        except Exception:
            break
        texts = pg.eval_on_selector_all(
            "#chips button", "els => els.map(e => e.textContent)")
        if not texts:
            break
        pick = next((c for c in texts
                     if any(w in c.lower() for w in all_words)),
                    texts[0])
        pg.click("#chips button:has-text('%s')" % pick[:14])
        pg.wait_for_timeout(2500)
        # Let the reply finish: a nudge typed while a turn is pending
        # is dropped by the composer.
        pg.wait_for_function(
            "() => !document.getElementById('pending')", timeout=120000)
        if pg.eval_on_selector_all(
                "#recs .card" if desktop else "#messages .mini-card",
                "e => e.length") > 0:
            break
    if pg.eval_on_selector_all(
            "#recs .card" if desktop else "#messages .mini-card",
            "e => e.length") == 0:
        pg.fill("#composerInput", fallback_text)
        pg.eval_on_selector("#composer", "f => f.requestSubmit()")
        try:
            pg.wait_for_selector(
                "#recs .card" if desktop else "#messages .mini-card",
                timeout=180000)
        except Exception:
            print("RECS-ERRORS %r" % (errors,))
            dump_state(pg, lang + "-" + tag, "no-recs")
            raise
    timings["rec_turn_s"] = round(time.perf_counter() - t1, 1)
    shot("recs")
    assert overflow() == 0


    def settle_auto_preview():
        # The app auto-previews the top pick after recs; let that swap
        # finish and close it so taps reach the chat cards beneath.
        if pg.evaluate("() => !document.getElementById('swapModal')"
                       ".hidden"):
            pg.wait_for_selector("#swapResult:not([hidden])",
                                 timeout=300000)
            pg.click("#swapClose")
            pg.wait_for_timeout(500)

    if try_single:
        t2 = time.perf_counter()
        settle_auto_preview()
        # A stray open sheet (fixed overlay) would cover the chat card
        # button for real taps too; close it before trying.
        if pg.evaluate("() => document.body.classList.contains("
                       "'sheet-open')"):
            try:
                pg.click("#sheetClose", timeout=5000)
            except Exception:
                pg.evaluate("() => document.body.classList.remove("
                            "'sheet-open')")
            pg.wait_for_timeout(500)
        once_try = lambda: pg.click(  # noqa: E731
            "#recs .card .seeit >> nth=0" if desktop else
            "#messages .mini-try >> nth=0")
        once_try()
        wait_swap(pg, lang + "-" + tag, once_try)
        timings["swap_s"] = round(time.perf_counter() - t2, 1)
        shot("swap")
        pg.click("#swapClose")
        pg.wait_for_timeout(500)

    if want_multi:
        settle_auto_preview()
        if not desktop:
            pg.click("#roomView")
        try:
            pg.wait_for_selector("#assignRow:not([hidden])",
                                 timeout=60000)
        except Exception:
            print("ASSIGN-ERRORS %r" % (errors,))
            dump_state(pg, lang + "-" + tag, "no-assign")
            raise
        assert pg.eval_on_selector_all(
            "#assignRow .assign-chip", "e => e.length") >= 1
        at = pg.eval_on_selector(
            "#assignRow .assign-chip",
            "e => { const r = e.getBoundingClientRect(); "
            "return [r.x + r.width / 2, r.y + r.height / 2]; }")
        pg.mouse.click(at[0], at[1])
        pg.wait_for_selector("#browsePanel .browse-card",
                             timeout=120000)
        shot("browse")
        once_apply = lambda: pg.click(  # noqa: E731
            "#browsePanel [data-apply]")
        once_apply()
        wait_swap(pg, lang + "-" + tag, once_apply)
        pg.click("#swapClose")
        pg.wait_for_timeout(500)
        t3 = time.perf_counter()
        pg.click("#applyAllBtn")
        for mi in range(25):
            if pg.eval_on_selector_all("#messages .sum-card",
                                       "e => e.length"):
                break
            tail = pg.eval_on_selector_all(
                "#messages .msg", "e => e.map(x => x.innerText)")[-2:]
            print("MULTI-WAIT %s %ds tail=%r" % (tag, mi * 10, tail))
            if any("preview failed" in (m or "").lower()
                   or "تعذّرت المعاينة" in (m or "") for m in tail):
                dump_state(pg, lang + "-" + tag, "multi-fail")
                raise RuntimeError("multi swap failed: %r" % (tail,))
            pg.wait_for_timeout(10000)
        pg.wait_for_selector("#messages .sum-card", timeout=120000)
        timings["multi_s"] = round(time.perf_counter() - t3, 1)
        shot("summary")
        card = pg.eval_on_selector(
            "#messages .sum-card", "e => e.outerHTML")
        # EPD only when a CO2-counted piece was assigned (curtains /
        # pillows alone correctly show no CO2 line).
        try:
            sid = pg.evaluate(
                "() => window.localStorage.getItem('recover_sid')")
            quote = json.loads(_api_get(
                "/api/session/" + sid + "/quote",
                CREDS["user"], CREDS["pw"]).decode())
            need_epd = quote.get("co2", {}).get("kg", 0) > 0
        except Exception:
            need_epd = True
        if needles is None:
            needles = (["$", "Total", "Preliminary estimate",
                        "https://wa.me/?text="]
                       if lang == "en" else
                       ["$", "الإجمالي", "تقدير مبدئي",
                        "https://wa.me/?text="])
        if need_epd and "EPD NEPD-1805-759" not in needles:
            needles = needles + ["EPD NEPD-1805-759"]
        for needle in needles:
            assert needle in card, "summary missing: %s" % needle
        assert "SAR" not in card and "ر.س" not in card
        wa_text = pg.evaluate(
            "() => decodeURIComponent(document.querySelector("
            "'#messages .sum-card .sum-actions a.seeit').href"
            ".split('?text=')[1])")
        found = re.findall(r"https?://[^\s'\"]+/share/[^\s'\"]+",
                           wa_text)
        assert found, "no share link in wa.me text"
        timings["share_in_wa"] = True
        assert overflow() == 0

    timings["console_errors"] = settle_console_errors(pg, errors)
    return timings, timings["console_errors"]


def settle_console_errors(pg, errors):
    """Refetch every 404'd URL once at end of run.

    A first-GET 404 that serves 200 a moment later is a volume-sync
    transient the UI already recovered from (retry/re-render) — report
    it as a warning, not a failure. Anything still failing (or any
    non-404 console error) stays fatal.
    """
    urls = []
    for entry in errors:
        m = re.search(r"<(https?://[^>\s]+)>", entry or "")
        if m and m.group(1) not in urls:
            urls.append(m.group(1))
    fatal, recovered = [], []
    for url in urls:
        try:
            status = pg.evaluate(
                "u => fetch(u, {method: 'GET', cache: 'reload'})"
                ".then(function (r) { return r.status; })"
                ".catch(function () { return -1; })", url)
        except Exception:  # noqa: BLE001 - page may be mid-reload
            status = -1
        (recovered if status == 200 else fatal).append(url)
    if recovered:
        print("RECOVERED-404 (transient, serves 200 now): %r" % recovered)
    out = []
    for entry in errors:
        m = re.search(r"<(https?://[^>\s]+)>", entry or "")
        if m and m.group(1) in recovered:
            continue
        if m and m.group(1) in fatal:
            entry = entry + " [persistent]"
        out.append(entry)
    return out


def compare_region_change(before_bytes, after_bytes, mask_bytes,
                         erode=7):
    """Mean abs diff inside the eroded mask interior (0-255)."""
    import io as _io
    from PIL import Image, ImageChops, ImageFilter, ImageStat
    before = Image.open(_io.BytesIO(before_bytes)).convert("RGB")
    after = Image.open(_io.BytesIO(after_bytes)).convert("RGB")
    if before.size != after.size:
        after = after.resize(before.size)
    mask = Image.open(_io.BytesIO(mask_bytes)).convert("L")
    if mask.size != before.size:
        mask = mask.resize(before.size)
    inner = mask.filter(ImageFilter.MinFilter(erode))
    diff = ImageChops.difference(before, after).convert("L")
    masked = ImageChops.multiply(diff, inner)
    mean = ImageStat.Stat(masked).mean[0]
    area = ImageStat.Stat(inner).mean[0] / 255.0 or 1.0
    return round(mean / area, 2)


def run_target_phase(device, user, pw, browser, lang):
    """Cushions-target pixel test: sofa body must stay, pillows change."""
    import base64 as _b64
    import urllib.request as _url
    _auth = {"Authorization": "Basic " + _b64.b64encode(
        ("%s:%s" % (user, pw)).encode()).decode()}

    def _get(path):
        url = DEPLOYED + path if path.startswith("/") \
            else DEPLOYED + "/" + path
        req = _url.Request(url, headers=_auth)
        with _url.urlopen(req, timeout=120) as resp:
            return resp.read()
    ctx = browser.new_context(
        **device, http_credentials={"username": user,
                                     "password": pw})
    pg = ctx.new_page()
    errors = []
    def _console(m):
        if m.type != "error":
            return
        try:
            loc = m.location or {}
            url = loc.get("url", "") if isinstance(loc, dict) \
                else getattr(loc, "url", "")
        except Exception:
            url = ""
        errors.append(("%s <%s>" % (m.text, url))[:260])
    pg.on("console", _console)
    pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
    pg.on("response", lambda r: errors.append(
        ("HTTP %s <%s>" % (r.status, r.url))[:260])
        if r.status >= 400 else None)
    tag = "target"
    pg.goto(DEPLOYED + "/consult", wait_until="networkidle",
            timeout=90000)
    pg.wait_for_selector("#welcomeMsg", timeout=30000)
    pg.set_input_files("#fileInput", LIVING)
    try:
        pg.wait_for_selector("#chips:not([hidden])", timeout=300000)
    except Exception:
        print("PHOTO-ERRORS %r" % (errors,))
        dump_state(pg, tag, "photo-retry")
        pg.reload(wait_until="networkidle", timeout=90000)
        pg.wait_for_selector("#welcomeMsg", timeout=30000)
        pg.set_input_files("#fileInput", LIVING)
        pg.wait_for_selector("#chips:not([hidden])", timeout=300000)
    me_before = pg.eval_on_selector_all(
        "#messages .msg.me", "e => e.length")
    # Prefer the tap; fall back to the chip, then plain text. The pixel
    # proof below runs only when a cushions tap rendered (sane masks).
    tap = pg.query_selector('.outline-msg [data-outline="cushions"]')
    pixel_proof = tap is not None
    if tap:
        box = pg.eval_on_selector(
            '.outline-msg [data-outline="cushions"]',
            "e => { const r = e.getBoundingClientRect(); "
            "return [r.x + r.width / 2, r.y + r.height / 2]; }")
        pg.mouse.click(box[0], box[1])
    else:
        texts = pg.eval_on_selector_all(
            "#chips button", "els => els.map(x => x.textContent)")
        pick = next((c for c in texts if "cushion" in (c or "").lower()),
                     "Cushions")
        if pick == "Cushions":
            pg.fill("#composerInput", "Cushions")
            pg.eval_on_selector("#composer", "f => f.requestSubmit()")
        else:
            pg.click("#chips button:has-text('%s')" % pick[:14])
    try:
        pg.wait_for_function(
            "n => document.querySelectorAll('#messages .msg.me').length > n",
            arg=me_before, timeout=30000)
    except Exception:
        pass
    me = pg.eval_on_selector_all(
        "#messages .msg.me", "e => e.map(x => x.innerText)")
    if not any("cushion" in (m or "").lower() for m in me[me_before:]):
        pg.fill("#composerInput", "Cushions")
        pg.eval_on_selector("#composer", "f => f.requestSubmit()")
        pg.wait_for_timeout(8000)
    t0 = time.perf_counter()
    for _ in range(4):
        try:
            pg.wait_for_selector("#chips:not([hidden])", timeout=60000)
        except Exception:
            break
        texts = pg.eval_on_selector_all(
            "#chips button", "els => els.map(e => e.textContent)")
        if not texts:
            break
        pick = next((c for c in texts
                     if "all" in c.lower() or "mix" in c.lower()
                     or "كل" in c), texts[0])
        pg.click("#chips button:has-text('%s')" % pick[:14])
        pg.wait_for_timeout(2500)
        # Let the reply finish: a nudge typed while a turn is pending
        # is dropped by the composer.
        pg.wait_for_function(
            "() => !document.getElementById('pending')", timeout=120000)
        if pg.eval_on_selector_all("#messages .mini-card",
                                   "e => e.length") > 0:
            break
    if pg.eval_on_selector_all("#messages .mini-card",
                               "e => e.length") == 0:
        pg.fill("#composerInput", "Warm beige, kids. Recommend 3 now.")
        pg.eval_on_selector("#composer", "f => f.requestSubmit()")
        pg.wait_for_selector("#messages .mini-card", timeout=180000)
    before_url = pg.eval_on_selector(
        "#roomThumb", "e => e.getAttribute('src')")
    labels = pg.eval_on_selector_all(
        "#messages .mini-try span", "e => e.map(x => x.innerText)")
    assert all("cushion" in (label or "").lower()
               for label in labels[:3]), labels
    # Capture the swap request: the chosen target must reach the backend.
    sent = {}
    pg.route("**/api/swap/stream",
             lambda route: (sent.update(
                 json.loads(route.request.post_data or "{}")),
                 route.continue_()))
    once_try = lambda: pg.click(  # noqa: E731
        "#messages .mini-try >> nth=0")
    # The app auto-previews the top pick after recs; the modal must be
    # closed before a Try button under it can be clicked.
    if pg.evaluate("() => !document.getElementById('swapModal').hidden"):
        pg.wait_for_selector("#swapResult:not([hidden]), "
                             "#swapRetryBtn:not([hidden])",
                             timeout=300000)
        pg.click("#swapClose")
        pg.wait_for_timeout(500)
    once_try()
    wait_swap(pg, lang + "-target", once_try, timeout=600000)
    secs = round(time.perf_counter() - t0, 1)
    assert sent.get("target") == "cushions", sent
    pg.click("#swapClose")
    pg.wait_for_timeout(1000)
    after_url = pg.eval_on_selector_all(
        "#messages .chat-swap .swap-thumb",
        "e => e.map(x => x.getAttribute('src'))")[-1]
    sid = pg.evaluate("() => window.localStorage.getItem('recover_sid')")
    from urllib.parse import quote as _quote
    masks = json.loads(_get(
        "/api/session/" + sid + "/targets?image_path=" + _quote(
            before_url.lstrip("/"), safe="")).decode())["targets"]
    by_id = {m["id"]: m for m in masks}
    before_b = _get(before_url)
    after_b = _get(after_url)
    result = {"swap_s": secs, "swap_target": sent.get("target"),
              "pixel_proof": pixel_proof,
              "console_errors": errors}
    if pixel_proof:
        cush = compare_region_change(
            before_b, after_b, _get(by_id["cushions"]["mask_url"]))
        sofa = compare_region_change(
            before_b, after_b, _get(by_id["sofa"]["mask_url"]))
        result.update(cushions_diff=cush, sofa_diff=sofa)
        # Routing proof is the request target (hard); pixels are
        # supporting evidence with lenient bounds (masks vary per call).
        assert cush > 5, "pillow region barely changed: %s" % cush
        assert sofa < 8, "sofa body changed too much: %s" % sofa
        assert cush > 1.8 * sofa, (cush, sofa)
    else:
        result["masks_note"] = "no cushions tap rendered; masks unusable"
    assert not errors, errors[:3]
    pg.screenshot(path=os.path.join(OUT_DIR, "%s-%s.png" % (lang, tag)))
    ctx.close()
    return result


def main():
    lang = "ar" if "--lang" in sys.argv and "ar" in sys.argv[
        sys.argv.index("--lang") + 1:] else "en"
    os.makedirs(OUT_DIR, exist_ok=True)
    user, pw = load_demo_creds()
    CREDS["user"], CREDS["pw"] = user, pw
    all_timings = {}

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.webkit.launch()
        device = dict(p.devices["iPhone 15 Pro"])
        device["viewport"] = {"width": 390, "height": 844}
        if lang == "en":
            all_words = ["all", "mix", "everything", "both"]
            fallback = ("Warm beige, kids, budget 150 per meter. "
                        "Recommend 3 fabrics now.")
        else:
            all_words = ["كل", "mix"]
            fallback = ("درجات بيج دافية، عندي أطفال، الميزانية "
                        "١٥٠ للمتر. رشّح لي ٣ أقمشة الحين.")
        # Phase A: real iPhone HEIC up to recs. No single Try here:
        # the kitchen fixture has no usable changeable item, and a
        # targetless swap hangs instead of failing fast. Single Try
        # is covered on the multi sample in phase B.
        ctx_a = browser.new_context(
            **device, http_credentials={"username": user,
                                         "password": pw})
        timings_a, errors_a = run_phase(
            ctx_a.new_page(), lang, "heic", HEIC, all_words,
            fallback, want_multi=False, try_single=False)
        all_timings["heic_recs"] = timings_a
        ctx_a.close()
        # Phase B: multi sample, single Try + full multi flow.
        # Retry once on a fresh context: a transient model stall must
        # not fail the whole proof run.
        for attempt in range(2):
            ctx_b = browser.new_context(
                **device, http_credentials={"username": user,
                                             "password": pw})
            try:
                timings_b, errors_b = run_phase(
                    ctx_b.new_page(), lang, "multi", LIVING,
                    all_words, fallback, want_multi=True)
            except Exception as exc:  # noqa: BLE001 - retry once
                print("PHASE-B attempt %d failed: %r" % (attempt, exc))
                ctx_b.close()
                if attempt == 1:
                    raise
                continue
            break
        all_timings["multi"] = timings_b
        ctx_b.close()
        if lang == "en":
            # Phase C: cushions-target pixel proof (sofa stays).
            all_timings["target"] = run_target_phase(
                device, user, pw, browser, lang)
        browser.close()
    with open(os.path.join(OUT_DIR, "%s-timings.json" % lang),
              "w") as f:
        json.dump(all_timings, f, indent=1)
    print(json.dumps(all_timings, indent=1)[:2000])
    bad = (all_timings["heic_recs"]["console_errors"]
           + all_timings["multi"]["console_errors"]
           + all_timings.get("target",
                             {}).get("console_errors", []))
    assert not bad, "console errors: %s" % bad[:3]


if __name__ == "__main__":
    main()
