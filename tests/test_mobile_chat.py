"""Mobile consult flows (no model calls; /api/chat is route-mocked).

Covers Fix 3 (in-chat empty state, sticky room bar, full-screen sheet),
Fix 4 (streaming empty reply still yields a non-empty assistant bubble
with the options lead-in), and Fix 5 (?sample= chats with the photo, so
room analysis precedes the first reply).
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GREET = {"reply": "Hello! Show me your room and I will find fabrics.",
         "recommendations": [], "options": [], "room_analysis": None,
         "detected_lang": "en"}
IMG_TURN = {
    "reply": "I can see a sofa in a bright room. Which style do you like?",
    "recommendations": [{
        "code": "FA-NL-07", "name_en": "Nordic Linen",
        "name_ar": "كتان نورديك", "price_sar_per_m": 155,
        "image": "data/catalog/FA-AC-01.jpg", "features": [],
        "snag_risk": "low", "reason": "Good match.",
        "matched": [], "relaxed": [], "relaxed_features": [],
        "relaxed_budget": None}],
    "options": ["Sofa only", "Cushions too"],
    "room_analysis": {
        "room_type": "living room", "style": "modern",
        "light_level": "high", "furniture": "a fabric sofa",
        "wall_colors": [{"name": "white", "hex": "#FFFFFF"}]},
    "detected_lang": "en"}
EMPTY_STREAM = {"reply": "", "recommendations": [],
                "options": ["Sofa only"], "detected_lang": "en"}


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="module")
def server():
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--port", str(port)],
        cwd=BASE_DIR, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/", timeout=2)
                break
            except Exception:  # noqa: BLE001 - still starting
                time.sleep(1)
        else:
            pytest.skip("local server did not start")
        yield base
    finally:
        proc.terminate()


@pytest.fixture()
def page(server):
    pw = pytest.importorskip("playwright.sync_api")
    errors = []
    with pw.sync_playwright() as p:
        try:
            browser = p.webkit.launch()
            device = dict(p.devices["iPhone 15 Pro"])
        except Exception:  # noqa: BLE001 - WebKit not installed here
            pytest.skip("WebKit not available")
        device["viewport"] = {"width": 390, "height": 844}
        ctx = browser.new_context(**device)
        pg = ctx.new_page()
        # Browser-generated network noise ("Failed to load resource") and
        # the intentional "upload failed <status>" diagnostic (asserted
        # via UI in the negative test) are not app faults; real JS
        # faults still fail teardown below.
        def on_console(m):
            if m.type != "error":
                return
            text = m.text or ""
            if text.startswith("Failed to load resource"):
                return
            if text.startswith("upload failed"):
                return
            errors.append(text)
        pg.on("console", on_console)
        pg.on("pageerror", lambda e: errors.append(str(e)))

        def canned(data):
            data = data or {}
            if data.get("image_path") or (
                    data.get("message", "") not in ("Hello", "")):
                return dict(IMG_TURN)
            return dict(GREET)

        def chat_mock(route):
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(
                              canned(route.request.post_data_json)))

        def stream_mock(route):
            data = route.request.post_data_json or {}
            seen_step = ("data: %s\n\n" % json.dumps(
                {"type": "step", "label": "room"})
                if data.get("image_path") else "")
            route.fulfill(
                status=200, content_type="text/event-stream",
                body=seen_step + "data: %s\n\n" % json.dumps(
                    {"type": "done", "result": canned(data)}))

        pg.route("**/api/chat", chat_mock)
        pg.route("**/api/chat/stream", stream_mock)
        yield pg
        assert errors == [], "console errors: %s" % errors[:5]
        ctx.close()
        browser.close()


def bubbles(pg):
    return pg.eval_on_selector_all(
        "#messages .msg.them",
        "els => els.map(e => (e.textContent || '').trim())")


def test_welcome_empty_state(server, page):
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#welcomeMsg", timeout=15000)
    page.wait_for_function("document.fonts.status === 'loaded'",
                           timeout=15000)
    assert page.eval_on_selector_all(
        "#welcomeMsg [data-sample]", "e => e.length") == 4
    assert page.eval_on_selector_all(
        "#welcomeMsg [data-upload]", "e => e.length") == 1
    box = page.evaluate("() => ({sw: document.documentElement.scrollWidth,"
                        " cw: document.documentElement.clientWidth})")
    assert box["sw"] == box["cw"]
    vis = page.evaluate("""() => {
      const c = document.querySelector('.composer');
      const r = c.getBoundingClientRect();
      return {bottom: Math.round(r.bottom), vh: window.innerHeight};
    }""")
    assert vis["bottom"] <= vis["vh"], "composer hidden on cold load: %s" % vis
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(400)
    vis = page.evaluate("""() => {
      const c = document.querySelector('.composer');
      const r = c.getBoundingClientRect();
      return {bottom: Math.round(r.bottom), vh: window.innerHeight};
    }""")
    assert vis["bottom"] <= vis["vh"], "composer hidden after scroll: %s" % vis


def test_sample_photo_beats_greeting(server, page):
    seen = []
    page.route("**/api/chat/stream", lambda r: (
        seen.append(r.request.post_data_json) or r.fulfill(
            status=200, content_type="text/event-stream",
            body="data: %s\n\n" % json.dumps(
                {"type": "done", "result": IMG_TURN}))))
    page.goto(server + "/consult?sample=living",
              wait_until="networkidle")
    page.wait_for_selector("#roomBar:not([hidden])", timeout=15000)
    with_image = [d for d in seen if d.get("image_path")]
    assert with_image, "sample turn must chat with the photo: %s" % seen
    first = seen[0]
    assert first.get("image_path"), \
        "first turn must carry the photo, got: %s" % first


def test_failed_chat_leaves_no_broken_room(server, page):
    page.route("**/api/chat/stream", lambda r: r.fulfill(status=400))
    page.route("**/api/chat", lambda r: r.fulfill(status=400))
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#welcomeMsg", timeout=15000)
    page.set_input_files("#fileInput",
                         os.path.join(BASE_DIR, "data/samples/living.jpg"))
    # The upload turn must end with no pending bubble left behind.
    page.wait_for_selector("#pending", state="detached", timeout=30000)
    assert page.get_attribute("#roomBar", "hidden") is not None
    assert page.get_attribute("#roomThumb", "src") in (None, "")
    texts = bubbles(page)
    assert texts and "went wrong" in texts[-1]


def test_undecodable_upload_shows_upload_fail(server, page):
    page.route("**/api/upload", lambda r: r.fulfill(status=400))
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#welcomeMsg", timeout=15000)
    page.set_input_files("#fileInput",
                         os.path.join(BASE_DIR, "data/samples/living.jpg"))
    page.wait_for_function(
        """() => [...document.querySelectorAll('#messages .msg.them')]
           .some(e => (e.textContent || '').includes('Upload failed'))""",
        timeout=30000)
    assert page.get_attribute("#roomBar", "hidden") is not None


def test_room_bar_sheet_and_stream_bubble(server, page):
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#welcomeMsg", timeout=15000)
    page.set_input_files("#fileInput",
                         os.path.join(BASE_DIR, "data/samples/living.jpg"))
    page.wait_for_selector("#roomBar:not([hidden])", timeout=15000)
    assert (page.text_content("#roomFabric") or "").strip() == "Your room"
    assert (page.text_content("#roomSub") or "").strip() == "living room"
    cards = page.eval_on_selector_all(
        "#messages .mini-card", "els => els.map(e => e.outerHTML)")
    assert len(cards) == 1, "recs must live in the chat, not a panel"
    assert 'data-try="FA-NL-07"' in cards[0]
    assert "Try on my photo" in cards[0]
    assert "155 SAR" in cards[0]
    assert "$" not in cards[0]
    assert page.get_attribute("#recs", "hidden") is not None or \
        page.evaluate("getComputedStyle(document.getElementById('recs'))"
                      ".display") == "none"
    page.click("#roomView")
    page.wait_for_timeout(500)
    assert page.evaluate(
        "document.body.classList.contains('sheet-open')")
    box = page.evaluate("() => ({sw: document.documentElement.scrollWidth,"
                        " cw: document.documentElement.clientWidth})")
    assert box["sw"] == box["cw"]
    page.click("#sheetClose")
    page.wait_for_timeout(300)
    assert page.evaluate(
        "!document.body.classList.contains('sheet-open')")
    page.route("**/api/chat/stream", lambda r: r.fulfill(
        status=200, content_type="text/event-stream",
        body="data: %s\n\n" % json.dumps(
            {"type": "done", "result": EMPTY_STREAM})))
    page.fill("#composerInput", "Sofa only")
    page.click('.composer button[type="submit"]')
    page.wait_for_timeout(1500)
    texts = bubbles(page)
    assert texts, "assistant must answer the streaming turn"
    assert all(texts), "no assistant bubble may be empty: %s" % texts
    assert any(t.startswith("Sure") for t in texts), texts


SWAP_MOCK = {"result_url": "data/samples/living.jpg",
             "mask_url": "data/samples/living.jpg",
             "scores": {"color": 9, "pattern": 9, "scale": 9,
                        "isolation": 9},
             "attempts": 1}


def swap_stream(result):
    body = "".join(
        "data: %s\n\n" % json.dumps({"type": "step", "label": label})
        for label in ("segment", "edit", "verify"))
    return body + "data: %s\n\n" % json.dumps(
        {"type": "done", "result": result})


def upload_photo(page):
    page.wait_for_selector("#welcomeMsg", timeout=15000)
    page.set_input_files("#fileInput",
                         os.path.join(BASE_DIR, "data/samples/living.jpg"))
    page.wait_for_selector("#roomBar:not([hidden])", timeout=15000)


def test_try_runs_swap_with_steps_and_bubble(server, page):
    page.route("**/api/swap/stream", lambda r: r.fulfill(
        status=200, content_type="text/event-stream",
        body=swap_stream(SWAP_MOCK)))
    page.goto(server + "/consult", wait_until="networkidle")
    upload_photo(page)
    page.click('#messages [data-try="FA-NL-07"]')
    page.wait_for_selector("#swapResult:not([hidden])", timeout=30000)
    assert "Checking the result" in (
        page.text_content("#swapSteps") or "")
    page.click("#swapClose")
    page.wait_for_timeout(400)
    thumbs = page.eval_on_selector_all(
        "#messages img.swap-thumb", "e => e.length")
    assert thumbs >= 1, "swap result must post as a chat image bubble"
    assert (page.text_content("#roomFabric") or "").strip() == \
        "Nordic Linen"
    page.click("#messages img.swap-thumb")
    page.wait_for_timeout(500)
    assert page.evaluate("!document.getElementById('swapModal').hidden")
    page.click("#swapClose")
    page.wait_for_timeout(300)
    assert page.evaluate("document.getElementById('swapModal').hidden")


def test_preview_result_autoruns_swap(server, page):
    with_preview = dict(IMG_TURN)
    with_preview["preview"] = {"code": "FA-NL-07", "target": ""}

    def text_only(route):
        data = route.request.post_data_json or {}
        body = with_preview if data.get("message") else IMG_TURN
        route.fulfill(
            status=200, content_type="text/event-stream",
            body="data: %s\n\n" % json.dumps(
                {"type": "done", "result": body}))

    page.route("**/api/chat/stream", text_only)
    page.route("**/api/swap/stream", lambda r: r.fulfill(
        status=200, content_type="text/event-stream",
        body=swap_stream(SWAP_MOCK)))
    page.goto(server + "/consult", wait_until="networkidle")
    upload_photo(page)
    page.fill("#composerInput", "show me it on my chair")
    page.click('.composer button[type="submit"]')
    page.wait_for_selector("#swapModal:not([hidden])", timeout=30000)
    page.click("#swapClose")


def test_no_photo_try_opens_sheet(server, page):
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#welcomeMsg", timeout=15000)
    page.fill("#composerInput", "recommend something for my sofa")
    page.click('.composer button[type="submit"]')
    page.wait_for_selector("#messages .mini-card", timeout=30000)
    page.click('#messages [data-try="FA-NL-07"]')
    page.wait_for_timeout(500)
    assert page.evaluate(
        "document.body.classList.contains('sheet-open')"), \
        "no photo: Try must open the sheet with upload + samples"
    assert page.evaluate("document.getElementById('swapModal').hidden")
    page.click("#sheetClose")


def test_step_labels_live_during_upload(server, page):
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#welcomeMsg", timeout=15000)
    page.evaluate("""() => {
      window.__steps = [];
      new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          if (m.target.classList &&
              m.target.classList.contains('agent-step') &&
              m.target.textContent.trim()) {
            window.__steps.push(m.target.textContent.trim());
          }
        });
      }).observe(document.getElementById('messages'),
                 {childList: true, subtree: true, characterData: true,
                  characterDataOldValue: false});
    }""")
    page.set_input_files("#fileInput",
                         os.path.join(BASE_DIR, "data/samples/living.jpg"))
    page.wait_for_selector("#roomBar:not([hidden])", timeout=15000)
    steps = page.evaluate("window.__steps || []")
    assert any("photo" in s.lower() or "Preparing" in s for s in steps), \
        "photo step label never showed: %s" % steps
    assert any("room" in s.lower() or "Looking" in s for s in steps), \
        "room step label never showed: %s" % steps
    assert all(steps), "empty step label shown: %s" % steps


def test_arabic_cards_and_titles(server, page):
    greet_ar = dict(GREET)
    greet_ar["reply"] = "أهلاً! أرني غرفتك وسأجد لك الأقمشة."
    greet_ar["detected_lang"] = "ar"
    turn_ar = dict(IMG_TURN)
    turn_ar["reply"] = "أرى كنبة في غرفة مضيئة. أي ستايل يعجبك؟"
    rec_ar = dict(IMG_TURN["recommendations"][0])
    rec_ar["price_sar_per_m"] = 155
    turn_ar["recommendations"] = [rec_ar]
    turn_ar["options"] = ["كنبة فقط"]
    turn_ar["room_analysis"] = dict(IMG_TURN["room_analysis"])
    turn_ar["detected_lang"] = "ar"

    def canned_ar(route):
        data = route.request.post_data_json or {}
        body = turn_ar if data.get("image_path") else greet_ar
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))

    def stream_ar(route):
        data = route.request.post_data_json or {}
        body = turn_ar if data.get("image_path") else greet_ar
        route.fulfill(status=200, content_type="text/event-stream",
                      body="data: %s\n\n" % json.dumps(
                          {"type": "done", "result": body}))

    page.route("**/api/chat", canned_ar)
    page.route("**/api/chat/stream", stream_ar)
    page.goto(server + "/consult?lang=ar", wait_until="networkidle")
    page.wait_for_selector("#welcomeMsg", timeout=15000)
    page.set_input_files("#fileInput",
                         os.path.join(BASE_DIR, "data/samples/living.jpg"))
    page.wait_for_selector("#roomBar:not([hidden])", timeout=15000)
    card = page.eval_on_selector(
        "#messages .mini-card", "e => e.outerHTML")
    assert "جرّبه على صورتي" in card
    assert "ر.س" in card
    assert "$" not in card
    title = (page.text_content("#roomFabric") or "").strip()
    sub = (page.text_content("#roomSub") or "").strip()
    assert title != sub or not sub, "room bar must not repeat: %r / %r" % (
        title, sub)


MULTI_MASKS = {"targets": [
    {"id": "sofa", "type": "sofa", "label_en": "Sofa",
     "label_ar": "الكنبة", "mask_url": "data/samples/living.jpg",
     "box": [20, 120, 620, 520]},
    {"id": "cushions", "type": "cushions", "label_en": "Cushions",
     "label_ar": "الوسائد", "mask_url": "data/samples/living.jpg",
     "box": [120, 220, 520, 360]}]}

MULTI_SCORES = {"color": 9, "pattern": 9, "scale": 9, "isolation": 9}


def multi_stream_from_assignments(assignments):
    results = [{
        "target": a.get("target", "sofa"),
        "code": a.get("code", "FA-AC-01"),
        "result_url": "data/samples/living.jpg",
        "mask_url": "data/samples/living.jpg",
        "scores": dict(MULTI_SCORES), "attempts": 1,
        "cached": False} for a in assignments]
    body = "".join(
        "data: %s\n\n" % json.dumps({"type": "step", "label": label})
        for label in ("segment", "edit", "verify"))
    return body + "data: %s\n\n" % json.dumps(
        {"type": "done",
         "result": {"results": results,
                    "final_url": "data/samples/living.jpg"}})


def test_multi_assign_flow(server, page):
    turn1 = {"reply": "I can see a sofa and cushions. What would you "
                      "like to change?",
             "recommendations": [], "room_analysis": None,
             "options": ["Sofa only", "Cushions too", "All of them"],
             "targets": {"available": ["sofa", "cushions"], "chosen": [],
                         "assignments": {}},
             "detected_lang": "en"}
    turnN = dict(IMG_TURN)
    turnN["targets"] = {"available": ["sofa", "cushions"],
                        "chosen": ["sofa", "cushions"],
                        "assignments": {}}

    def chat_route(route):
        data = route.request.post_data_json or {}
        if data.get("image_path"):
            body = turn1
        elif (data.get("message") or "") in ("Hello", ""):
            body = GREET
        else:
            body = turnN
        route.fulfill(status=200, content_type="text/event-stream",
                      body="data: %s\n\n" % json.dumps(
                          {"type": "done", "result": body}))

    def targets_route(route):
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(MULTI_MASKS))

    def multi_route(route):
        data = route.request.post_data_json or {}
        assigns = data.get("assignments") or [
            {"target": "sofa", "code": "FA-AC-01"}]
        route.fulfill(status=200, content_type="text/event-stream",
                      body=multi_stream_from_assignments(assigns))

    page.route("**/api/chat/stream", chat_route)
    page.route("**/targets*", targets_route)
    page.route("**/api/swap/stream", lambda r: r.fulfill(
        status=200, content_type="text/event-stream",
        body=swap_stream(SWAP_MOCK)))
    page.route("**/api/swap/multi/stream", multi_route)
    page.goto(server + "/consult", wait_until="networkidle")
    upload_photo(page)
    page.wait_for_selector("#chips:not([hidden])", timeout=15000)
    page.click("#chips button:has-text('All of them')")
    page.wait_for_timeout(2000)
    # Outlines, chips and browse live in the full-screen viewer on
    # phones: open it and drive the multi flow from there.
    page.click("#roomView")
    page.wait_for_selector("#assignRow:not([hidden])", timeout=15000)
    chips = page.eval_on_selector_all(
        "#assignRow .assign-chip", "els => els.map(e => e.textContent)")
    assert len(chips) == 2, chips
    assert page.evaluate(
        "document.body.classList.contains('sheet-open')")
    assert page.eval_on_selector_all(
        "#outlineLayer .ol-tap", "e => e.length") == 2
    # Tapping an outline shares the chip state: same answer, same turn.
    before = len(bubbles(page))
    at = page.eval_on_selector(
        "#outlineLayer .ol-tap",
        "e => { const r = e.getBoundingClientRect(); "
        "return [r.x + r.width / 2, r.y + r.height / 2]; }")
    page.mouse.click(at[0], at[1])
    page.wait_for_timeout(2500)
    assert len(bubbles(page)) > before, \
        "outline tap must share the chip answer state"
    page.click("#assignRow .assign-chip")
    page.wait_for_selector("#browsePanel:not([hidden])", timeout=15000)
    page.wait_for_selector("#browsePanel .browse-card", timeout=15000)
    page.click("#browsePanel [data-apply]")
    page.wait_for_selector("#swapResult:not([hidden])", timeout=30000)
    page.click("#swapClose")
    page.wait_for_timeout(400)
    page.click("#applyAllBtn")
    page.wait_for_selector("#messages .sum-card", timeout=60000)
    assert page.eval_on_selector_all("#pending", "e => e.length") == 0
    card = page.eval_on_selector(
        "#messages .sum-card", "e => e.outerHTML")
    assert "Your picks" in card
    assert "FA-" in card
    assert "SAR" in card
    assert "$" not in card
    assert "Preliminary estimate" in card
    assert "Total" in card
    assert "https://wa.me/?text=" in card
    assert "Send to upholsterer" in card
    assert "Copy summary" in card
    assert "EPD NEPD-1805-759" in card
    page.click("#sheetClose")
    page.wait_for_timeout(400)
    page.click("#messages .sum-copy")
    page.wait_for_timeout(500)
    assert "Copied" in (page.text_content("#messages .sum-copy") or "")
    box = page.evaluate("() => ({sw: document.documentElement.scrollWidth,"
                        " cw: document.documentElement.clientWidth})")
    assert box["sw"] == box["cw"]
    texts = bubbles(page)
    assert all(texts), "no assistant bubble may be empty: %s" % texts


def test_multi_assign_flow_ar(server, page):
    turn1 = {"reply": "شايفة كنبة ووسائد. وش تبغى تغيّر؟",
             "recommendations": [], "room_analysis": None,
             "options": ["الكنبة فقط", "الوسائد بعد", "كلها"],
             "targets": {"available": ["sofa", "cushions"], "chosen": [],
                         "assignments": {}},
             "detected_lang": "ar"}
    turnN = dict(IMG_TURN)
    turnN["targets"] = {"available": ["sofa", "cushions"],
                        "chosen": ["sofa", "cushions"],
                        "assignments": {}}
    turnN["detected_lang"] = "ar"

    def chat_route(route):
        data = route.request.post_data_json or {}
        if data.get("image_path"):
            body = turn1
        elif (data.get("message") or "") in ("Hello", ""):
            body = GREET
        else:
            body = turnN
        route.fulfill(status=200, content_type="text/event-stream",
                      body="data: %s\n\n" % json.dumps(
                          {"type": "done", "result": body}))

    page.route("**/api/chat/stream", chat_route)
    page.route("**/targets*", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(MULTI_MASKS)))
    page.route("**/api/swap/stream", lambda r: r.fulfill(
        status=200, content_type="text/event-stream",
        body=swap_stream(SWAP_MOCK)))
    page.route("**/api/swap/multi/stream", lambda r: r.fulfill(
        status=200, content_type="text/event-stream",
        body=multi_stream_from_assignments(
            (r.request.post_data_json or {}).get("assignments") or [
                {"target": "sofa", "code": "FA-AC-01"}])))
    page.goto(server + "/consult?lang=ar", wait_until="networkidle")
    upload_photo(page)
    page.wait_for_selector("#chips:not([hidden])", timeout=15000)
    page.click("#chips button:has-text('كلها')")
    page.wait_for_timeout(2000)
    page.click("#roomView")
    page.wait_for_selector("#assignRow:not([hidden])", timeout=15000)
    assert page.evaluate(
        "document.body.classList.contains('sheet-open')")
    assert page.eval_on_selector_all(
        "#outlineLayer .ol-tap", "e => e.length") == 2
    before = len(bubbles(page))
    at = page.eval_on_selector(
        "#outlineLayer .ol-tap",
        "e => { const r = e.getBoundingClientRect(); "
        "return [r.x + r.width / 2, r.y + r.height / 2]; }")
    page.mouse.click(at[0], at[1])
    page.wait_for_timeout(2500)
    assert len(bubbles(page)) > before, \
        "outline tap must share the chip answer state"
    page.click("#assignRow .assign-chip")
    page.wait_for_selector("#browsePanel .browse-card", timeout=15000)
    page.click("#browsePanel [data-apply]")
    page.wait_for_selector("#swapResult:not([hidden])", timeout=30000)
    page.click("#swapClose")
    page.wait_for_timeout(400)
    page.click("#applyAllBtn")
    page.wait_for_selector("#messages .sum-card", timeout=60000)
    card = page.eval_on_selector(
        "#messages .sum-card", "e => e.outerHTML")
    assert "اختياراتك" in card
    assert "ر.س" in card
    assert "$" not in card
    assert "تقدير مبدئي" in card
    assert "الإجمالي" in card
    assert "https://wa.me/?text=" in card
    assert "أرسل للمنجّد" in card
    assert "EPD NEPD-1805-759" in card
    box = page.evaluate("() => ({sw: document.documentElement.scrollWidth,"
                        " cw: document.documentElement.clientWidth})")
    assert box["sw"] == box["cw"]


def test_double_try_fires_one_swap(server, page):
    """Auto-preview + manual tap on the same fabric must not start two
    swaps (twin bubbles, double model burn): the second tap rides the
    in-flight swap."""
    hits = []

    def slow_swap(route):
        # A genuinely slow swap: the request stays pending for the whole
        # test. (A fulfilled one-event body closes the stream, which the
        # client rightly reads as a dropped connection: it retries once
        # and then fails, so the "in-flight" window would be gone before
        # the second tap.)
        hits.append(1)

    page.route("**/api/swap/stream", slow_swap)
    page.goto(server + "/consult", wait_until="networkidle")
    upload_photo(page)
    tap = ("document.querySelector('#messages [data-try=\"FA-NL-07\"]')"
           ".click()")
    page.evaluate(tap)
    page.wait_for_timeout(400)
    page.evaluate(tap)
    page.wait_for_timeout(1200)
    assert hits == [1], "second tap must ride the in-flight swap"
    assert page.evaluate("!document.getElementById('swapModal').hidden")


def test_second_swap_same_fabric_refreshes_bubble(server, page):
    """Try X, then Apply X from Browse: the second result refreshes the
    existing bubble instead of posting a twin."""
    second = dict(SWAP_MOCK)
    second["result_url"] = "data/samples/majlis.jpg"
    queue = [SWAP_MOCK, second]

    def two_swaps(route):
        route.fulfill(status=200, content_type="text/event-stream",
                      body=swap_stream(queue.pop(0) if queue else second))

    page.route("**/api/swap/stream", two_swaps)
    page.goto(server + "/consult", wait_until="networkidle")
    upload_photo(page)
    tap = ("document.querySelector('#messages [data-try=\"FA-NL-07\"]')"
           ".click()")
    page.evaluate(tap)
    page.wait_for_selector("#swapResult:not([hidden])", timeout=30000)
    page.click("#swapClose")
    page.wait_for_timeout(400)
    page.evaluate(tap)
    page.wait_for_selector("#swapResult:not([hidden])", timeout=30000)
    page.click("#swapClose")
    page.wait_for_timeout(400)
    thumbs = page.eval_on_selector_all(
        "#messages .chat-swap .swap-thumb", "e => e.map(x => x.src)")
    assert len(thumbs) == 1, "same fabric must keep one bubble"
    assert "majlis" in thumbs[0], "bubble must show the latest result"
    matches = [t for t in bubbles(page) if "Fabric match" in t]
    assert len(matches) == 1


def test_view_again_opens_result_without_reswap(server, page):
    """Desktop 'View again' must show the finished result, never burn a
    second swap (and post a twin bubble)."""
    hits = []

    def counting_swap(route):
        hits.append(1)
        route.fulfill(status=200, content_type="text/event-stream",
                      body=swap_stream(SWAP_MOCK))

    page.route("**/api/swap/stream", counting_swap)
    page.goto(server + "/consult", wait_until="networkidle")
    upload_photo(page)
    page.evaluate("document.querySelector('#messages [data-try=\"FA-NL-07\"]')"
                  ".click()")
    page.wait_for_selector("#swapResult:not([hidden])", timeout=30000)
    page.click("#swapClose")
    page.wait_for_timeout(400)
    assert len(hits) == 1
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(400)
    page.click("#canvasRow .ccard.previewing")
    page.wait_for_selector("#swapResult:not([hidden])", timeout=15000)
    page.wait_for_timeout(800)
    assert len(hits) == 1, "View again must not start a new swap"


def test_canvas_image_retries_once_after_404(server, page):
    """A just-written volume file can 404 the first GET: canvasImg must
    retry once and recover instead of staying broken."""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 3), (10, 120, 200)).save(buf, "PNG")
    png = buf.getvalue()
    hits = []

    def probe(route):
        hits.append(1)
        if len(hits) == 1:
            route.fulfill(status=404, body="nope")
        else:
            route.fulfill(status=200, content_type="image/png",
                          body=png)

    page.route("**/uploads/retry-probe.jpg*", probe)
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#canvasImg", state="attached", timeout=15000)
    page.evaluate("document.querySelector('#canvasImg').src ="
                 " '/uploads/retry-probe.jpg'")
    page.wait_for_function(
        "document.querySelector('#canvasImg').naturalWidth > 0",
        timeout=15000)
    assert len(hits) >= 2, "canvas must refetch after the first 404"


def test_auto_preview_swaps_chosen_target(server, page):
    """Chosen target = cushions -> the auto-applied pick and the Try
    buttons call /api/swap/stream with target cushions, never sofa."""
    bodies = []
    with_preview = dict(IMG_TURN)
    with_preview["preview"] = {"code": "FA-NL-07", "target": "cushions"}
    with_preview["targets"] = {"available": ["sofa", "cushions"],
                               "chosen": ["cushions"], "assignments": {}}

    def chat_route(route):
        data = route.request.post_data_json or {}
        body = with_preview if data.get("message") else IMG_TURN
        route.fulfill(status=200, content_type="text/event-stream",
                      body="data: %s\n\n" % json.dumps(
                          {"type": "done", "result": body}))

    def swap_route(route):
        bodies.append(route.request.post_data_json or {})
        route.fulfill(status=200, content_type="text/event-stream",
                      body=swap_stream(SWAP_MOCK))

    page.route("**/api/chat/stream", chat_route)
    page.route("**/api/swap/stream", swap_route)
    page.goto(server + "/consult", wait_until="networkidle")
    upload_photo(page)
    page.fill("#composerInput", "Cushions")
    page.click('.composer button[type="submit"]')
    page.wait_for_selector("#swapResult:not([hidden])", timeout=30000)
    assert bodies and bodies[0].get("target") == "cushions", bodies
    assert "Try again" not in (page.text_content("#swapLoading") or "") \
        or page.get_attribute("#swapRetryBtn", "hidden") is not None
    page.click("#swapClose")
    page.wait_for_timeout(300)
    # A manual Try on another fabric keeps the chosen item too.
    page.evaluate("document.querySelector('#messages [data-try]').click()")
    page.wait_for_timeout(1200)
    assert all(b.get("target") == "cushions" for b in bodies), bodies


QUOTE_TURN = {
    "reply": "About 16.5 m at 95 SAR/m — 1,567.5 SAR, preliminary.",
    "recommendations": [], "options": [], "detected_lang": "en",
    "quote": {"target": "sofa", "code": "FA-NL-07", "meters": 16.5,
              "price_sar_per_m": 155, "line_total": 2557.5},
    "targets": {"available": ["sofa"], "chosen": ["sofa"],
                "assignments": {"sofa": "FA-NL-07"}}}

QUOTE_BODY = {"items": [{"target": "sofa", "code": "FA-NL-07",
                         "fabric_name_en": "Nordic Linen",
                         "fabric_name_ar": "كتان نورديك",
                         "meters": 16.5, "price_sar_per_m": 155,
                         "line_total": 2557.5, "note": ""}],
              "total": 2557.5, "missing": [], "currency": "SAR",
              "preliminary": True,
              "co2": {"kg": 52, "waste_kg": 48, "source": "EPD NEPD-1805-759"}}


def test_single_quote_posts_summary_card_and_actions(server, page):
    """Any quote (one item, no Apply-all) shows the summary card with
    meters, total, CO2 and Send / Copy, plus action chips — and no
    picks pointer or recommendation chips."""
    def chat_route(route):
        data = route.request.post_data_json or {}
        msg = data.get("message") or ""
        body = QUOTE_TURN if "meters" in msg else (
            IMG_TURN if data.get("image_path") or msg not in ("Hello", "")
            else GREET)
        route.fulfill(status=200, content_type="text/event-stream",
                      body="data: %s\n\n" % json.dumps(
                          {"type": "done", "result": body}))

    page.route("**/api/chat/stream", chat_route)
    page.route("**/api/session/*/quote", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(QUOTE_BODY)))
    page.goto(server + "/consult", wait_until="networkidle")
    upload_photo(page)
    cards_before = page.eval_on_selector_all("#messages .mini-card",
                                             "e => e.length")
    page.fill("#composerInput", "how many meters / how much?")
    page.click('.composer button[type="submit"]')
    page.wait_for_selector("#messages .sum-card", timeout=30000)
    card = page.eval_on_selector("#messages .sum-card", "e => e.innerText")
    assert "16.5 m" in card and "2557.5 SAR" in card
    assert "Total" in card and "52" in card
    assert page.query_selector("#messages .sum-card .sum-actions a")
    assert page.query_selector("#messages .sum-card .sum-copy")
    chips = page.eval_on_selector_all(
        "#chips button", "els => els.map(e => e.textContent.trim())")
    assert chips == ["Send to upholsterer", "Try another fabric"], chips
    # The quote turn re-posts neither the mini cards nor the picks line.
    assert page.eval_on_selector_all("#messages .mini-card",
                                     "e => e.length") == cards_before
    assert page.eval_on_selector_all("#messages .recs-line",
                                     "e => e.length") == 0


def test_refresh_restores_session(server, page):
    """A reload rebuilds chat, photo, picks and last recs from
    /api/session/<id>/state instead of greeting again."""
    state_body = {
        "session_id": "x", "lang": "en",
        "image_path": "data/samples/living.jpg",
        "room_analysis": IMG_TURN["room_analysis"],
        "detected_piece": "sofa",
        "messages": [{"who": "me", "text": "Sofa"},
                     {"who": "them", "text": "Here are three picks."}],
        "targets": {"available": ["sofa"], "chosen": ["sofa"],
                    "assignments": {"sofa": "FA-NL-07"}},
        "last_recs": IMG_TURN["recommendations"],
        "quote": QUOTE_BODY, "quoted": True, "previews": []}
    greets = []

    def chat_route(route):
        greets.append(1)
        route.fulfill(status=200, content_type="text/event-stream",
                      body="data: %s\n\n" % json.dumps(
                          {"type": "done", "result": GREET}))

    page.route("**/api/chat/stream", chat_route)
    page.route("**/api/chat", chat_route)
    page.route("**/api/session/*/state", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(state_body)))
    page.route("**/api/session/*/quote", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(QUOTE_BODY)))
    page.route("**/api/session/*/targets*", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"targets": []})))
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#messages .sum-card", timeout=30000)
    texts = page.eval_on_selector_all(
        "#messages .msg", "els => els.map(e => e.innerText.slice(0, 40))")
    assert any("Sofa" in x for x in texts)
    assert any("Here are three picks" in x for x in texts)
    assert page.eval_on_selector_all("#messages .mini-card",
                                     "e => e.length") == 1
    assert page.is_visible("#roomBar")
    assert page.evaluate("document.getElementById('welcomeMsg') === null")
    assert greets == [], "no greeting on a restored session"


def test_restored_picker_tap_sends_item_name(server, page):
    """After a refresh the picker is rebuilt from the server; a tap on
    an item that has no matching option and is not chosen yet must
    send the item's name as a message (the tap IS the choice), and the
    last turn's chips must be back on screen."""
    state_body = {
        "session_id": "x", "lang": "en",
        "image_path": "data/samples/living.jpg",
        "room_analysis": IMG_TURN["room_analysis"],
        "detected_piece": "sofa",
        "options": ["Upholstery", "Curtains", "Cushions", "A mix"],
        "messages": [{"who": "them", "text": "What would you change?"}],
        "targets": {"available": ["sofa", "curtains", "cushions"],
                    "chosen": [], "assignments": {}},
        "last_recs": [], "quote": None, "quoted": False, "previews": []}
    sent = []

    def chat_route(route):
        sent.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(status=200, content_type="text/event-stream",
                      body="data: %s\n\n" % json.dumps(
                          {"type": "done", "result": GREET}))

    page.route("**/api/chat/stream", chat_route)
    page.route("**/api/chat", chat_route)
    page.route("**/api/session/*/state", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(state_body)))
    page.route("**/api/session/*/targets*", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"targets": [
            {"id": "sofa", "box": [100, 300, 700, 600],
             "size": [800, 600]},
            {"id": "curtains", "box": [200, 50, 600, 300],
             "size": [800, 600]}]})))
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#messages .item-thumb", timeout=30000)
    chips = page.eval_on_selector_all(
        "#chips button", "els => els.map(e => e.textContent)")
    assert chips == ["Upholstery", "Curtains", "Cushions", "A mix"]
    # The option that names the item wins when there is one...
    page.click('#messages .item-thumb[data-outline="curtains"]')
    page.wait_for_function("() => document.querySelectorAll('#messages .msg.me').length >= 1", timeout=10000)
    assert sent and sent[-1]["message"] == "Curtains"
    # ...and an item no option mentions is sent by its own name
    # (before the fix this opened the fabric browser: a dead tap).
    page.wait_for_function("() => !document.body.classList.contains('chat-busy')", timeout=10000)
    page.click('#messages .item-thumb[data-outline="sofa"]')
    page.wait_for_function("() => document.querySelectorAll('#messages .msg.me').length >= 2", timeout=10000)
    assert sent[-1]["message"].lower() == "sofa"
    # With no options at all the same holds.
    state_body["options"] = []
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#messages .item-thumb", timeout=30000)
    assert page.evaluate("document.getElementById('chips').hidden")
    page.click('#messages .item-thumb[data-outline="curtains"]')
    page.wait_for_function("() => document.querySelectorAll('#messages .msg.me').length >= 1", timeout=10000)
    assert sent[-1]["message"].lower() == "curtains"
    assert page.evaluate("document.getElementById('browsePanel') === null || document.getElementById('browsePanel').hidden")
