"""Mobile overflow guard: no sideways scrolling on phones.

Runs the real static pages in headless Chrome (iPhone UA) at 360/390/430px
and asserts documentElement.scrollWidth == clientWidth for: landing,
consult empty, switcher open, and consult with photo + rec cards.
Photo/rec states are injected into the DOM (no model calls) because this
test guards layout, not the chat flow.
"""
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
WIDTHS = (360, 390, 430)
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
      "Mobile/15E148 Safari/604.1")

INJECT_PHOTO = """() => {
  document.getElementById('canvasEmpty').hidden = true;
  const w = document.getElementById('canvasPhotoWrap');
  w.hidden = false;
  document.getElementById('canvasImg').src = '/data/samples/living.jpg';
}"""

INJECT_RECS = """() => {
  const row = document.getElementById('canvasRow');
  row.hidden = false;
  row.innerHTML = ('<button class="ccard">' +
    '<img src="/data/samples/living.jpg">' +
    '<span class="cc-t"><span class="cc-n">Test Fabric</span>' +
    '<span class="cc-m">FA-NL-07 &middot; 155 SAR/m</span>' +
    '<span class="cc-s">See it</span></span></button>').repeat(3);
}"""


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


def measure(pg, url, setup=None):
    pg.goto(url, wait_until="networkidle")
    if setup == "switcher":
        pg.click(".rcsw-btn")
        pg.wait_for_timeout(400)
    if setup in ("photo", "recs"):
        pg.evaluate(INJECT_PHOTO)
        pg.wait_for_timeout(300)
    if setup == "recs":
        pg.evaluate(INJECT_RECS)
        pg.wait_for_timeout(300)
    return pg.evaluate("() => ({sw: document.documentElement.scrollWidth,"
                       " cw: document.documentElement.clientWidth})")


@pytest.mark.parametrize("width", WIDTHS)
def test_no_horizontal_overflow(server, width):
    if not shutil.which("node") or not os.path.exists(CHROME):
        pytest.skip("system Chrome not available")
    pw = pytest.importorskip("playwright.sync_api")
    states = [("/", None), ("/consult", None),
              ("/consult", "switcher"), ("/consult", "photo"),
              ("/consult", "recs")]
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME,
                                    args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": width, "height": 844}, user_agent=UA,
            is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        try:
            for path, setup in states:
                box = measure(pg, server + path, setup)
                assert box["sw"] == box["cw"], \
                    "%s %s: scrollWidth %s != clientWidth %s" % (
                        path, setup, box["sw"], box["cw"])
        finally:
            ctx.close()
            browser.close()
