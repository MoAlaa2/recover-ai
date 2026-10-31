"""Designer mode (plan -> render) and the client proposal PDF.

Model calls are faked; the plan is drawn with PIL."""
import io
import json
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.services import designer as dz
from app.services import proposal

SIZE = (1000, 600)


def plan_png(path=None, size=SIZE):
    img = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, size[0] - 20, size[1] - 20], outline=0, width=6)
    d.rectangle([300, 420, 700, 520], outline=0, width=3)   # sofa
    d.rectangle([100, 200, 190, 290], outline=0, width=3)   # chair
    d.rectangle([800, 200, 890, 290], outline=0, width=3)   # chair
    if path:
        img.save(path)
    return img


SPARK_TEXT = ('Here you go: {"pieces": [{"name": "sofa", "type": "sofa", '
              '"box": [300, 420, 700, 520]}, {"name": "right chair", '
              '"type": "chair", "box": [890, 290, 800, 200]}, '
              '{"name": "left chair", "type": "armchair", '
              '"box": [100, 200, 190, 290]}, {"name": "dup", "type": '
              '"chair", "box": [102, 202, 192, 292]}, {"name": "speck", '
              '"type": "stool", "box": [5, 5, 8, 8]}, {"name": "bad", '
              '"box": "nope"}]} done.')


# --- parsing -----------------------------------------------------------

def test_parse_pieces_orders_numbers_and_cleans():
    pieces = dz.parse_pieces(SPARK_TEXT, SIZE)
    # Reading order: the two chairs (same row) left to right, then sofa.
    assert [p["name"] for p in pieces] == ["left chair", "right chair",
                                           "sofa"]
    assert [p["id"] for p in pieces] == [1, 2, 3]
    # Swapped corners are ordered; duplicates and specks are dropped.
    assert pieces[1]["box"] == [800, 200, 890, 290]
    assert pieces[0]["type"] == "armchair"
    assert pieces[2]["type"] == "sofa-3-seat"


def test_parse_pieces_caps_at_max_and_clamps():
    raw = {"pieces": [{"name": "c%d" % i, "type": "chair",
                       "box": [i * 70 - 30, 100, i * 70 + 20, 180]}
                      for i in range(20)]}
    pieces = dz.parse_pieces(json.dumps(raw), SIZE)
    assert len(pieces) == dz.MAX_PIECES
    assert all(0 <= p["box"][0] and p["box"][2] <= SIZE[0] for p in pieces)


def test_parse_pieces_garbage_is_empty():
    assert dz.parse_pieces("no json here", SIZE) == []
    assert dz.parse_pieces('{"pieces": "x"}', SIZE) == []


# --- box edits ----------------------------------------------------------

def test_normalize_pieces_keeps_edits_and_drops_bad_boxes():
    edited = [
        {"id": 3, "name": "sofa", "type": "sofa-3-seat",
         "box": [310.4, 430, 690, 530], "code": "FA-AC-01"},
        {"id": 1, "name": "left chair", "box": [-50, 200, 190, 9999]},
        {"id": 9, "name": "gone", "box": [10, 10, 12, 12]},
        "junk",
    ]
    out = dz.normalize_pieces(edited, SIZE)
    assert [p["id"] for p in out] == [3, 1]
    assert out[0]["box"] == [310, 430, 690, 530] and out[0]["code"] == \
        "FA-AC-01"
    assert out[1]["box"] == [0, 200, 190, SIZE[1]]
    assert out[1]["type"] == "armchair" and out[1]["code"] is None


def test_normalize_pieces_caps_and_dedupes_ids():
    many = [{"id": 1, "name": "c", "box": [0, i * 40, 60, i * 40 + 30]}
            for i in range(15)]
    out = dz.normalize_pieces(many, SIZE)
    assert len(out) == dz.MAX_PIECES
    assert len({p["id"] for p in out}) == dz.MAX_PIECES


# --- prompt + aspect ----------------------------------------------------

def test_build_prompt_carries_the_spike_fixes_and_counts():
    fabric = {"name_en": "Saffron Velvet", "material": "cotton velvet",
              "primary_color": "saffron yellow"}
    text = dz.build_prompt([(fabric, ["sofa 3"], 3),
                            (fabric, ["left chair 1", "right chair 2"], 5)],
                           (2000, 1200))
    for must in ("STRICTLY ORTHOGRAPHIC", "no visible wall faces",
                 "never skylights", "to the walls with no border",
                 "2000 x 1200 pixels (5:3)", "3 upholstered piece(s)",
                 "ONLY on the 1 piece(s) outlined in magenta in image 3",
                 "ONLY on the 2 piece(s) outlined in magenta in image 5",
                 "NO lines, outlines, marks, labels or text"):
        assert must in text, must
    assert "Correction" not in text
    assert "Correction for this retry: fix" in dz.build_prompt(
        [(fabric, ["sofa 3"], 3)], (2000, 1200), corrective="fix")


def test_fit_aspect_restores_the_plan_ratio():
    target = (2000, 1200)
    same = Image.new("RGB", (1000, 600), (1, 2, 3))
    assert dz.fit_aspect(same, target).size == target
    wide = Image.new("RGB", (1984, 1280), (0, 0, 0))   # the spike's drift
    out = dz.fit_aspect(wide, target)
    assert out.size == target
    tall = Image.new("RGB", (1200, 1200), (0, 0, 0))
    assert dz.fit_aspect(tall, target).size == target


def test_outline_map_marks_only_the_given_boxes():
    plan2x = Image.new("RGB", (400, 200), (255, 255, 255))
    omap = dz.outline_map(plan2x, [[20, 20, 120, 100]])
    assert omap.getpixel((20, 60)) == (255, 0, 255)
    assert omap.getpixel((300, 150)) == (255, 255, 255)


def test_check_piece_passes_matching_colour_and_fails_wrong():
    from app.services.catalog import get_fabric
    fab = get_fabric("FA-AC-01")
    with open(os.path.join(os.getcwd(), fab["image"]), "rb") as f:
        swatch = f.read()
    mean = Image.open(io.BytesIO(swatch)).convert("RGB").resize(
        (1, 1), Image.BOX).getpixel((0, 0))
    render = Image.new("RGB", (400, 300), (120, 120, 120))
    render.paste(mean, (100, 100, 300, 250))
    assert dz.check_piece(render, [100, 100, 300, 250], swatch)["ok"]
    purple = Image.new("RGB", (400, 300), (120, 20, 160))
    assert not dz.check_piece(purple, [100, 100, 300, 250], swatch)["ok"]
    # An L-shaped sectional: fabric on the left column and top row of
    # its box, floor elsewhere -> still passes (5 of 9 cells).
    lshape = Image.new("RGB", (400, 300), (120, 120, 120))
    lshape.paste(mean, (100, 100, 170, 250))
    lshape.paste(mean, (100, 100, 300, 150))
    res = dz.check_piece(lshape, [100, 100, 300, 250], swatch)
    assert res["ok"] and res["cells"] >= 5
    # Only one corner painted -> not the piece's fabric.
    corner = Image.new("RGB", (400, 300), (120, 120, 120))
    corner.paste(mean, (100, 100, 150, 140))
    assert not dz.check_piece(corner, [100, 100, 300, 250], swatch)["ok"]


# --- plan import ----------------------------------------------------------

def test_plan_image_reads_png_and_pdf_first_page(tmp_path):
    png = tmp_path / "plan.png"
    plan_png(str(png), (3000, 1800))
    img = dz.plan_image(str(png), ".png")
    assert max(img.size) == dz.PLAN_MAX_SIDE
    pdf = tmp_path / "plan.pdf"
    p1 = plan_png(None, (800, 500))
    p2 = Image.new("RGB", (800, 500), (0, 0, 0))
    p1.save(str(pdf), "PDF", save_all=True, append_images=[p2])
    img = dz.plan_image(str(pdf), ".pdf")
    assert img.width > img.height
    # First page (white plan), not the black second page.
    assert img.getpixel((img.width // 2, 10))[0] > 200


def test_plan_image_rejects_garbage(tmp_path):
    bad = tmp_path / "x.png"
    bad.write_bytes(b"not an image")
    with pytest.raises(dz.DesignerError):
        dz.plan_image(str(bad), ".png")
    with pytest.raises(dz.DesignerError):
        dz.plan_image(str(bad), ".pdf")


# --- render + quote (faked edit) -----------------------------------------

def _fake_edit(colors_by_round):
    calls = {"n": 0, "prompts": []}

    def fake(plan2x, groups, prompt, key, timeout):
        calls["prompts"].append(prompt)
        img = Image.new("RGB", plan2x.size, (200, 200, 200))
        d = ImageDraw.Draw(img)
        for (box, color) in colors_by_round[min(calls["n"],
                                                len(colors_by_round) - 1)]:
            d.rectangle([v * 2 for v in box], fill=color)
        calls["n"] += 1
        return img
    return fake, calls


def _swatch_mean(code):
    from app.services.catalog import get_fabric
    img = Image.open(os.path.join(
        os.getcwd(), get_fabric(code)["image"])).convert("RGB")
    return img.resize((1, 1), Image.BOX).getpixel((0, 0))


def test_render_checks_each_piece_and_retries_once(tmp_path, monkeypatch):
    plan = plan_png(None)
    sofa, chair = [300, 420, 700, 520], [100, 200, 190, 290]
    pieces = [{"id": 1, "name": "chair", "type": "armchair", "box": chair,
               "code": "FA-NL-03"},
              {"id": 2, "name": "sofa", "type": "sofa-3-seat", "box": sofa,
               "code": "FA-AC-01"},
              {"id": 3, "name": "spare", "type": "armchair",
               "box": [800, 200, 890, 290], "code": None}]
    good = [(sofa, _swatch_mean("FA-AC-01")), (chair, _swatch_mean("FA-NL-03"))]
    bad = [(sofa, (130, 20, 160)), (chair, _swatch_mean("FA-NL-03"))]
    fake, calls = _fake_edit([bad, good])
    monkeypatch.setattr(dz, "_edit", fake)
    monkeypatch.setattr(dz, "layout_check", lambda *a, **k: {"score": 9,
                                                              "moved": []})
    steps = []
    res = dz.render(plan, pieces, api_key="k", out_dir=str(tmp_path),
                    on_step=steps.append)
    assert calls["n"] == 2 and res["attempts"] == 2 and res["ok"]
    assert "retry" in steps
    assert "sofa" in calls["prompts"][1] and "Correction" in calls["prompts"][1]
    assert [c["ok"] for c in res["checks"]] == [True, True]
    assert len(res["legend"]) == 3 and res["legend"][2]["code"] is None
    assert res["size"] == [2000, 1200]
    assert os.path.exists(os.path.join(os.getcwd(), res["render_url"]))


def test_render_keeps_the_better_attempt_when_both_fail(tmp_path,
                                                         monkeypatch):
    plan = plan_png(None)
    sofa = [300, 420, 700, 520]
    pieces = [{"id": 1, "name": "sofa", "type": "sofa-3-seat", "box": sofa,
               "code": "FA-AC-01"}]
    fake, calls = _fake_edit([[(sofa, (130, 20, 160))]])
    monkeypatch.setattr(dz, "_edit", fake)
    monkeypatch.setattr(dz, "layout_check", lambda *a, **k: {"score": None,
                                                              "moved": []})
    res = dz.render(plan, pieces, api_key="k", out_dir=str(tmp_path))
    assert calls["n"] == 2 and not res["ok"]
    assert res["checks"][0]["ok"] is False


def test_render_retries_when_spark_says_the_layout_moved(tmp_path,
                                                          monkeypatch):
    """Colours pass but the bed and bath moved: one corrective retry that
    names what moved; the higher layout score wins."""
    plan = plan_png(None)
    sofa = [300, 420, 700, 520]
    pieces = [{"id": 1, "name": "sofa", "type": "sofa-3-seat", "box": sofa,
               "code": "FA-AC-01"}]
    fake, calls = _fake_edit([[(sofa, _swatch_mean("FA-AC-01"))]])
    monkeypatch.setattr(dz, "_edit", fake)
    scores = iter([{"score": 4, "moved": ["bed moved to the right wall",
                                          "bath flipped"]},
                   {"score": 9, "moved": []}])
    monkeypatch.setattr(dz, "layout_check", lambda *a, **k: next(scores))
    res = dz.render(plan, pieces, api_key="k", out_dir=str(tmp_path))
    assert calls["n"] == 2 and res["attempts"] == 2 and res["ok"]
    assert "bed moved to the right wall" in calls["prompts"][1]
    assert "back exactly where the plan draws it" in calls["prompts"][1]
    assert res["layout"] == {"score": 9, "moved": []}


def test_render_keeps_better_layout_when_both_drift(tmp_path, monkeypatch):
    plan = plan_png(None)
    sofa = [300, 420, 700, 520]
    pieces = [{"id": 1, "name": "sofa", "type": "sofa-3-seat", "box": sofa,
               "code": "FA-AC-01"}]
    fake, calls = _fake_edit([[(sofa, _swatch_mean("FA-AC-01"))]])
    monkeypatch.setattr(dz, "_edit", fake)
    scores = iter([{"score": 5, "moved": ["bed"]}, {"score": 3, "moved": ["all"]}])
    monkeypatch.setattr(dz, "layout_check", lambda *a, **k: next(scores))
    res = dz.render(plan, pieces, api_key="k", out_dir=str(tmp_path))
    assert res["attempts"] == 2 and res["layout"]["score"] == 5


def test_render_accepts_a_middling_layout_without_a_second_edit(
        tmp_path, monkeypatch):
    """6-7/10 is shown as a badge with Spark's notes; only a clearly
    drifted layout (<6) pays for the ~60s retry."""
    plan = plan_png(None)
    sofa = [300, 420, 700, 520]
    pieces = [{"id": 1, "name": "sofa", "type": "sofa-3-seat", "box": sofa,
               "code": "FA-AC-01"}]
    fake, calls = _fake_edit([[(sofa, _swatch_mean("FA-AC-01"))]])
    monkeypatch.setattr(dz, "_edit", fake)
    monkeypatch.setattr(dz, "layout_check", lambda *a, **k: {
        "score": 6, "moved": ["bed flipped"]})
    res = dz.render(plan, pieces, api_key="k", out_dir=str(tmp_path))
    assert calls["n"] == 1 and res["attempts"] == 1
    assert res["layout"] == {"score": 6, "moved": ["bed flipped"]}


def test_parse_layout_and_prompt_template_wording():
    assert dz.parse_layout('ok {"score": 11, "moved": ["bed", "", 3]}') == \
        {"score": 10, "moved": ["bed", "3"]}
    assert dz.parse_layout("nope") == {"score": None, "moved": []}
    assert dz.parse_layout('{"score": "x", "moved": "bed"}') == \
        {"score": None, "moved": []}
    text = dz.build_prompt([({"name_en": "A", "material": "m",
                              "primary_color": "c"}, ["sofa 1"], 3)],
                           (2000, 1200))
    assert "precise template" in text and "move nothing" in text


def test_render_needs_an_assignment():
    with pytest.raises(dz.DesignerError):
        dz.render(plan_png(None), [{"id": 1, "name": "x", "type": "armchair",
                                    "box": [0, 0, 50, 50], "code": None}],
                  api_key="k")


def test_quote_pieces_uses_standard_yardage_and_co2():
    q = dz.quote_pieces([
        {"id": 1, "name": "sofa", "type": "sofa-3-seat", "code": "FA-AC-01"},
        {"id": 2, "name": "chair", "type": "armchair", "code": "FA-NL-03"},
        {"id": 3, "name": "none", "type": "armchair", "code": None}])
    assert [i["meters"] for i in q["items"]] == [16.5, 5.5]
    assert q["total"] == 16.5 * 95 + 5.5 * 110
    assert q["co2"]["kg"] == pytest.approx(52 * 1.35, abs=0.1)
    assert q["preliminary"] is True


# --- endpoints -----------------------------------------------------------

@pytest.fixture()
def client(tmp_path):
    # Plans land in the real uploads/ dir (the image resolver allow-lists
    # it); renders go to tmp via out_dir where the test controls it.
    from app.main import app
    return TestClient(app), tmp_path


def test_plan_endpoint_accepts_png_pdf_rejects_others(client):
    c, tmp = client
    buf = io.BytesIO()
    plan_png(None, (1200, 700)).save(buf, "PNG")
    r = c.post("/api/designer/plan", files={"file": ("plan.png",
                                                     buf.getvalue(),
                                                     "image/png")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["image_path"].startswith("uploads/") and body["width"] == 1200
    pdf = io.BytesIO()
    plan_png(None, (900, 500)).save(pdf, "PDF")
    r = c.post("/api/designer/plan", files={"file": ("plan.pdf",
                                                     pdf.getvalue(),
                                                     "application/pdf")})
    assert r.status_code == 200 and r.json()["width"] > r.json()["height"]
    r = c.post("/api/designer/plan", files={"file": ("x.gif", b"GIF89a",
                                                     "image/gif")})
    assert r.status_code == 400
    r = c.post("/api/designer/plan", files={"file": ("x.png", b"junk",
                                                     "image/png")})
    assert r.status_code == 400


def test_pieces_and_render_stream_endpoints(client, monkeypatch):
    c, tmp = client
    buf = io.BytesIO()
    plan_png(None).save(buf, "PNG")
    path = c.post("/api/designer/plan", files={
        "file": ("plan.png", buf.getvalue(), "image/png")}).json()[
            "image_path"]
    monkeypatch.setattr(dz, "list_pieces",
                        lambda plan, api_key=None, timeout=90: (
                            dz.parse_pieces(SPARK_TEXT, plan.size),
                            SPARK_TEXT, 1.2))
    r = c.post("/api/designer/pieces", json={"image_path": path})
    assert r.status_code == 200
    pieces = r.json()["pieces"]
    assert [p["id"] for p in pieces] == [1, 2, 3]
    sofa = [p for p in pieces if p["name"] == "sofa"][0]
    sofa["code"] = "FA-AC-01"
    fake, calls = _fake_edit([[(sofa["box"], _swatch_mean("FA-AC-01"))]])
    monkeypatch.setattr(dz, "_edit", fake)
    monkeypatch.setattr(dz, "layout_check", lambda *a, **k: {"score": 8,
                                                              "moved": []})
    monkeypatch.setattr(dz, "require_api_key", lambda: "k")
    with c.stream("POST", "/api/designer/render/stream",
                  json={"image_path": path, "pieces": pieces}) as s:
        events = [json.loads(line[5:]) for line in s.iter_lines()
                  if line.startswith("data:")]
    types = [e["type"] for e in events]
    assert types[-1] == "done" and "step" in types
    res = events[-1]["result"]
    assert res["ok"] and res["attempts"] == 1
    assert res["layout"]["score"] == 8
    assert res["quote"]["items"][0]["code"] == "FA-AC-01"
    assert res["plan_url"] == path
    # No assignment at all -> 400, not a stream.
    for p in pieces:
        p["code"] = None
    r = c.post("/api/designer/render/stream",
               json={"image_path": path, "pieces": pieces})
    assert r.status_code == 400


def test_proposal_pdf_endpoint_en_and_ar(client):
    c, tmp = client
    for lang in ("en", "ar"):
        r = c.post("/api/proposal/pdf", json={
            "lang": lang, "mode": "photo", "prepared_by": "Studio",
            "before_url": "data/samples/living.jpg",
            "after_url": "/uploads/does-not-exist.jpg",
            "items": [{"label": "Sofa", "code": "FA-AC-01", "meters": 16.5,
                       "line_total": 1567.5},
                      {"label": "Cushions", "code": "FA-AC-08",
                       "meters": 2, "line_total": 210}],
            "total": 1777.5,
            "co2": {"kg": 52, "waste_kg": 48, "source": "EPD X"}})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF-")
        assert ("proposal-%s.pdf" % lang) in r.headers["content-disposition"]


def test_render_proposal_shapes_arabic_and_fits_one_page():
    import pypdfium2 as pdfium
    items = [{"label": "الكنبة", "code": "FA-AC-01", "name": "مخمل",
              "material": "cotton velvet", "price_sar_per_m": 95,
              "meters": 16.5, "line_total": 1567.5, "swatch": None}] * 6
    pdf = proposal.render_proposal(
        {"mode": "plan", "prepared_by": "x", "before": None, "after": None,
         "items": items, "total": 9405,
         "co2": {"kg": 52, "waste_kg": 48, "source": "EPD"}}, "ar")
    doc = pdfium.PdfDocument(pdf)
    assert len(doc) == 1
    w, h = doc[0].get_size()
    assert abs(w / h - 210 / 297.0) < 0.01
    assert proposal.shape("الكنبة", "ar") != "الكنبة"   # reshaped glyphs
    assert proposal.shape("Sofa", "ar") == "Sofa"
    assert proposal.fmt_num(16.5, "ar") == "١٦.٥"
    assert proposal.fmt_num(1567.5, "en", 2) == "1567.50"
