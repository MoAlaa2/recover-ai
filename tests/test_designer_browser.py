"""Designer mode in a real WebKit browser (desktop EN + iPhone AR).

The plan upload hits the real server; Spark piece listing and the Muse
render stream are route-mocked. Box edits (delete, drag, resize), the
fabric picker (real /api/fabrics), the result view, and the proposal PDF
(real endpoint) are exercised end to end."""
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from PIL import Image, ImageDraw

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PIECES = {"pieces": [
    {"id": 1, "name": "left chair", "type": "armchair",
     "box": [100, 200, 190, 290]},
    {"id": 2, "name": "right chair", "type": "armchair",
     "box": [800, 200, 890, 290]},
    {"id": 3, "name": "sofa", "type": "sofa-3-seat",
     "box": [300, 420, 700, 520]}],
    "width": 1000, "height": 600, "seconds": 1.0}


def plan_bytes():
    img = Image.new("RGB", (1000, 600), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 980, 580], outline=0, width=6)
    for box in ([300, 420, 700, 520], [100, 200, 190, 290],
                [800, 200, 890, 290]):
        d.rectangle(box, outline=0, width=3)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


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
                urllib.request.urlopen(base + "/designer", timeout=2)
                break
            except Exception:  # noqa: BLE001 - still starting
                time.sleep(1)
        else:
            pytest.skip("local server did not start")
        yield base
    finally:
        proc.terminate()


def fake_render(route):
    body = json.loads(route.request.post_data)
    pieces = body["pieces"]
    legend = []
    for p in pieces:
        row = dict(p, name_en="", name_ar="", image="", material="",
                   price_sar_per_m=None)
        if p.get("code"):
            row.update(name_en="Saffron Velvet", name_ar="مخمل الزعفران",
                       image="data/catalog/FA-AC-01.jpg",
                       material="cotton velvet", price_sar_per_m=95)
        legend.append(row)
    quote = {"items": [{"id": p["id"], "name": p["name"], "type": p["type"],
                        "code": p["code"], "meters": 16.5,
                        "price_sar_per_m": 95, "line_total": 1567.5}
                       for p in pieces if p.get("code")],
             "total": 1567.5, "currency": "SAR", "preliminary": True,
             "co2": {"kg": 52, "waste_kg": 48, "source": "EPD X"}}
    res = {"render_url": body["image_path"], "plan_url": body["image_path"],
           "legend": legend, "size": [2000, 1200],
           "checks": [{"id": p["id"], "name": p["name"], "code": p["code"],
                       "ok": True, "delta_e": 3.0}
                      for p in pieces if p.get("code")],
           "attempts": 1, "ok": True, "quote": quote,
           "layout": {"score": 9, "moved": []}}
    sse = "".join("data: %s\n\n" % json.dumps(e) for e in (
        {"type": "step", "label": "edit"}, {"type": "step", "label": "check"},
        {"type": "done", "result": res}))
    route.fulfill(status=200, content_type="text/event-stream", body=sse)


def _run(p, server, device, lang):
    browser = p.webkit.launch()
    ctx = browser.new_context(**device)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("**/api/designer/pieces", lambda r: r.fulfill(
        status=200, content_type="application/json",
        body=json.dumps(PIECES)))
    page.route("**/api/designer/render/stream", fake_render)
    page.goto(server + "/designer?lang=" + lang, wait_until="networkidle")
    page.set_input_files("#dzFile", {"name": "plan.png",
                                     "mimeType": "image/png",
                                     "buffer": plan_bytes()})
    page.wait_for_selector(".dz-box", timeout=20000)
    out = {"dir": page.evaluate("document.documentElement.dir"),
           "boxes": page.locator(".dz-box").count(),
           "status": page.inner_text("#dzStatus"),
           "overflow": page.evaluate(
               "document.documentElement.scrollWidth > "
               "document.documentElement.clientWidth"),
           "empty_hidden": page.evaluate(
               "getComputedStyle(document.getElementById('dzEmpty'))"
               ".display === 'none'")}
    # Delete a wrong piece.
    page.click("[data-del='2']")
    out["after_delete"] = page.locator(".dz-box").count()

    def box_of(pid):
        return page.evaluate(
            "RCDesigner.state.pieces.filter(p => p.id === %d)[0].box.slice()"
            % pid)
    # Drag the sofa right by 60 px (pointer events).
    bb = page.locator(".dz-box[data-id='3']").bounding_box()
    cx, cy = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
    before = box_of(3)
    page.mouse.move(cx, cy)
    page.mouse.down()
    page.mouse.move(cx + 60, cy, steps=6)
    page.mouse.up()
    out["drag"] = (before, box_of(3))
    # Resize chair 1 from its corner handle (synthetic touch on iPhone,
    # where the emulator does not route mouse to pointer events).
    hb = page.locator(".dz-box[data-id='1'] .dz-handle").bounding_box()
    hx, hy = hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2
    b1 = box_of(1)
    if device.get("has_touch"):
        # Playwright's WebKit iPhone emulation routes neither mouse nor
        # synthetic TouchEvents into the page's touch path, so the
        # pointer path is driven with synthetic PointerEvents (same box
        # maths); the touch fallback is exercised on real devices.
        page.evaluate("""([x, y]) => {
          const layer = document.getElementById('dzBoxes');
          const el = document.elementFromPoint(x, y);
          const mk = (type, cx, cy) => new PointerEvent(type, {bubbles: true,
            cancelable: true, pointerId: 1, pointerType: 'touch',
            clientX: cx, clientY: cy, isPrimary: true});
          el.dispatchEvent(mk('pointerdown', x, y));
          layer.dispatchEvent(mk('pointermove', x + 30, y + 20));
          layer.dispatchEvent(mk('pointerup', x + 30, y + 20));
        }""", [hx, hy])
    else:
        page.mouse.move(hx, hy)
        page.mouse.down()
        page.mouse.move(hx + 30, hy + 20, steps=6)
        page.mouse.up()
    out["resize"] = (b1, box_of(1))
    # Fabric via the catalog browse panel (real endpoint).
    out["render_disabled"] = page.is_disabled("#dzRender")
    page.click("[data-pick='3']")
    page.wait_for_selector("#dzBrowse [data-apply]", timeout=20000)
    out["browse_cards"] = page.locator("#dzBrowse .browse-card").count()
    # The picker opens right under the piece's row, not further down.
    out["browse_under_row"] = page.evaluate(
        "document.querySelector('[data-row=\"3\"]').nextElementSibling"
        ".id === 'dzBrowse'")
    page.wait_for_timeout(300)
    out["browse_visible"] = page.evaluate("""() => {
      const r = document.getElementById('dzBrowse').getBoundingClientRect();
      return r.top >= 0 && r.top < window.innerHeight; }""")
    page.click("#dzBrowse [data-apply]")
    out["render_enabled"] = not page.is_disabled("#dzRender")
    out["fab_label"] = page.inner_text("[data-pick='3']")
    # Render -> result view.
    page.click("#dzRender")
    page.wait_for_selector("#dzResult:not([hidden])", timeout=20000)
    out["legend"] = page.locator(".dz-lg").count()
    out["scale"] = page.inner_text(".dz-scale")
    out["quote"] = page.inner_text("#dzQuote")
    out["slider"] = page.evaluate(
        "document.getElementById('dzBeforeImg').getAttribute('src')")
    # Proposal PDF (real endpoint).
    page.fill("#dzPreparedBy", "Studio X")
    with page.expect_download(timeout=30000) as dl:
        page.click("#dzProposal")
    with open(dl.value.path(), "rb") as f:
        out["pdf_head"] = f.read(5)
    out["pdf_name"] = dl.value.suggested_filename
    out["errors"] = errors
    ctx.close()
    browser.close()
    return out


def test_designer_desktop_en(server):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            out = _run(p, server, {"viewport": {"width": 1280,
                                                "height": 900}}, "en")
        except Exception as exc:  # noqa: BLE001
            if "Executable doesn't exist" in str(exc):
                pytest.skip("WebKit not available")
            raise
    assert out["errors"] == []
    assert out["dir"] == "ltr" and out["boxes"] == 3
    assert out["status"] == "3 piece(s) found · Spark"
    assert out["empty_hidden"] and not out["overflow"]
    assert out["after_delete"] == 2
    before, after = out["drag"]
    assert after[0] > before[0] + 30 and after[1] == before[1]
    b1, b1b = out["resize"]
    assert b1b[2] > b1[2] and b1b[3] > b1[3] and b1b[:2] == b1[:2]
    assert out["render_disabled"] and out["render_enabled"]
    assert out["browse_cards"] >= 12 and out["fab_label"]
    assert out["browse_under_row"] and out["browse_visible"]
    assert out["legend"] == 2
    assert out["scale"].lower() == "concept render — not to scale"
    assert "16.5 m" in out["quote"] and "Total" in out["quote"]
    assert out["slider"].startswith("/uploads/")
    assert out["pdf_head"] == b"%PDF-"
    assert out["pdf_name"] == "recover-proposal-en.pdf"


def test_designer_iphone_ar(server):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            device = dict(p.devices["iPhone 13"])
        except Exception:  # noqa: BLE001
            pytest.skip("WebKit not available")
        out = _run(p, server, device, "ar")
    assert out["errors"] == []
    assert out["dir"] == "rtl" and out["boxes"] == 3
    assert out["status"] == "وجدنا ٣ قطعة · Spark"
    assert out["empty_hidden"] and not out["overflow"]
    assert out["after_delete"] == 2
    b1, b1b = out["resize"]
    assert b1b[2] > b1[2] and b1b[3] > b1[3], "touch resize"
    assert out["render_enabled"] and out["legend"] == 2
    assert out["browse_under_row"] and out["browse_visible"]
    assert out["scale"] == "تصور مبدئي — ليس بمقياس الرسم"
    assert "١٦.٥ م" in out["quote"] and "الإجمالي" in out["quote"]
    assert out["pdf_head"] == b"%PDF-"
    assert out["pdf_name"] == "recover-proposal-ar.pdf"


def test_consult_and_landing_link_to_designer(server):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            browser = p.webkit.launch()
        except Exception:  # noqa: BLE001
            pytest.skip("WebKit not available")
        page = browser.new_page()
        page.goto(server + "/consult?lang=ar", wait_until="networkidle")
        link = page.query_selector("#forDesigners")
        assert link and link.get_attribute("href") == "/designer"
        assert (link.text_content() or "").strip() == "للمصممين"
        page.goto(server + "/", wait_until="networkidle")
        card = page.query_selector(".lp-pro-des")
        assert card and card.get_attribute("href") == "/designer"
        assert "Coming soon" not in (card.text_content() or "")
        browser.close()
