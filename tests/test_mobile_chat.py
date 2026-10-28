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
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
      "Mobile/15E148 Safari/604.1")

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
    if not os.path.exists(CHROME):
        pytest.skip("system Chrome not available")
    pw = pytest.importorskip("playwright.sync_api")
    errors = []
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 390, "height": 844},
                                  user_agent=UA, is_mobile=True,
                                  has_touch=True)
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(m.text)
              if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))

        def chat_mock(route):
            data = route.request.post_data_json or {}
            if data.get("image_path") or (
                    data.get("message", "") not in ("Hello", "")):
                body = dict(IMG_TURN)
            else:
                body = dict(GREET)
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(body))

        pg.route("**/api/chat", chat_mock)
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
    assert page.eval_on_selector_all(
        "#welcomeMsg [data-sample]", "e => e.length") == 3
    assert page.eval_on_selector_all(
        "#welcomeMsg [data-upload]", "e => e.length") == 1
    box = page.evaluate("() => ({sw: document.documentElement.scrollWidth,"
                        " cw: document.documentElement.clientWidth})")
    assert box["sw"] == box["cw"]


def test_sample_photo_beats_greeting(server, page):
    seen = []
    page.route("**/api/chat", lambda r: (
        seen.append(r.request.post_data_json) or r.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(IMG_TURN))))
    page.goto(server + "/consult?sample=living",
              wait_until="networkidle")
    page.wait_for_selector("#roomBar:not([hidden])", timeout=15000)
    with_image = [d for d in seen if d.get("image_path")]
    assert with_image, "sample turn must chat with the photo: %s" % seen
    first = seen[0]
    assert first.get("image_path"), \
        "first turn must carry the photo, got: %s" % first


def test_room_bar_sheet_and_stream_bubble(server, page):
    page.goto(server + "/consult", wait_until="networkidle")
    page.wait_for_selector("#welcomeMsg", timeout=15000)
    page.set_input_files("#fileInput",
                         os.path.join(BASE_DIR, "data/samples/living.jpg"))
    page.wait_for_selector("#roomBar:not([hidden])", timeout=15000)
    assert "Nordic Linen" in (page.text_content("#roomFabric") or "")
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
    assert texts[-1].startswith("Sure"), texts[-1]
