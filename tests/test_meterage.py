"""Meterage, uplift, rounding, curtains and quote tests."""
import os

from fastapi.testclient import TestClient

from app.services import meterage as m

PLAIN = {"code": "P", "plain_or_patterned": "plain",
         "pattern_type": "solid", "price_sar_per_m": 100,
         "name_en": "P", "name_ar": "P"}
PATTERNED = {"code": "Q", "plain_or_patterned": "patterned",
             "pattern_type": "stripes", "price_sar_per_m": 200,
             "name_en": "Q", "name_ar": "Q"}


def test_round_up_half():
    assert m.round_up_half(16.5) == 16.5
    assert m.round_up_half(16.51) == 17.0
    assert m.round_up_half(6.6) == 7.0
    assert m.round_up_half(6.5) == 6.5
    assert m.round_up_half(0.1) == 0.5


def test_is_patterned():
    assert m.is_patterned(PATTERNED) is True
    assert m.is_patterned(PLAIN) is False
    assert m.is_patterned({"pattern_type": "floral"}) is True
    assert m.is_patterned({}) is False
    assert m.is_patterned(None) is False


def test_sofa_plain_and_patterned():
    assert m.estimate_item("sofa", PLAIN) == (16.5, "")
    assert m.estimate_item("sofa", PATTERNED) == (19.0, "")


def test_armchair_and_ottoman():
    assert m.estimate_item("armchair", PLAIN) == (5.5, "")
    assert m.piece_meters("ottoman", PLAIN) == 3.5
    assert m.piece_meters("wingback", PATTERNED) == 10.5


def test_cushions_seat_only_plus_pillows():
    assert m.estimate_item("cushions", PLAIN) == (7.0,
                                                 "seat cushions only")
    meters, note = m.estimate_item("cushions", PLAIN, pillow_count=2)
    assert meters == 8.0
    assert "2" in note


def test_curtains_formula_and_missing():
    meters, note = m.estimate_item(
        "curtains", PLAIN, {"width_m": 3, "height_m": 2.5})
    assert meters == 12.0
    assert note == ""
    meters, note = m.estimate_item("curtains", PLAIN, {})
    assert meters is None
    assert note == "needs measurements"
    meters, note = m.estimate_item("curtains", PLAIN, None)
    assert meters is None


def test_unknown_target():
    meters, note = m.estimate_item("lamp", PLAIN)
    assert meters is None


def test_quote_totals():
    res = m.quote({"sofa": "P", "cushions": "Q"},
                  {"P": PLAIN, "Q": PATTERNED})
    by_target = {i["target"]: i for i in res["items"]}
    assert by_target["sofa"]["line_total"] == 1650.0
    assert by_target["sofa"]["meters"] == 16.5
    assert by_target["cushions"]["meters"] == 8.0
    assert by_target["cushions"]["line_total"] == 1600.0
    assert res["total"] == 3250.0
    assert res["missing"] == []
    assert res["currency"] == "SAR"


def test_quote_missing_measurements():
    res = m.quote({"curtains": "P"}, {"P": PLAIN})
    assert res["items"][0]["meters"] is None
    assert res["items"][0]["line_total"] is None
    assert res["missing"] == ["curtains"]
    assert res["total"] == 0.0


def test_estimate_cost_tool_sofa():
    from app.services import consultant as c
    session = {"assignments": {"sofa": "FA-AC-01"},
               "chosen_targets": ["sofa"]}
    out = c.execute_tool("estimate_cost", {"target": "sofa"},
                         {"session": session, "seen": []})
    assert out["target"] == "sofa"
    assert out["meters"] is not None
    assert out["currency"] == "SAR"
    assert out["preliminary"] is True


def test_estimate_cost_tool_curtains_dims():
    from app.services import consultant as c
    session = {"assignments": {"curtains": "FA-AC-01"},
               "chosen_targets": ["curtains"]}
    need = c.execute_tool("estimate_cost", {"target": "curtains",
                                            "code": "FA-AC-01"},
                          {"session": session, "seen": []})
    assert need["error"] == "needs measurements"
    assert session.get("curtain_dims") in (None, {})
    got = c.execute_tool("estimate_cost",
                         {"target": "curtains", "code": "FA-AC-01",
                          "width_m": 3, "height_m": 2.5},
                         {"session": session, "seen": []})
    assert got["meters"] == 12.0
    assert session["curtain_dims"]["width_m"] == 3


def test_estimate_cost_auto_counts_pillows(tmp_path):
    from PIL import Image, ImageDraw
    from app.services import consultant as c
    img = Image.new("L", (200, 200), 0)
    draw = ImageDraw.Draw(img)
    draw.ellipse([10, 10, 60, 60], fill=255)
    draw.ellipse([80, 20, 140, 70], fill=255)
    mask = tmp_path / "cush.png"
    img.save(str(mask))
    session = {"assignments": {"cushions": "FA-AC-02"},
               "chosen_targets": ["cushions"],
               "targets": {"image_path": "uploads/r.jpg",
                           "targets": [{"id": "cushions",
                                        "mask_url": str(mask)}]}}
    out = c.execute_tool("estimate_cost", {"target": "cushions"},
                         {"session": session, "seen": []})
    assert out["pillows"] == 2
    assert out["meters"] == 8.0
    assert "+ 2 throw pillow" in out["note"]
    fixed = c.execute_tool("estimate_cost",
                           {"target": "cushions", "pillows": 5},
                           {"session": session, "seen": []})
    assert fixed["pillows"] == 5
    assert session["pillow_counts"] == {"cushions": 5}
    bare = c.execute_tool("estimate_cost", {"target": "cushions"},
                          {"session": {"assignments":
                                       {"cushions": "FA-AC-02"}},
                           "seen": []})
    assert bare["pillows"] == 0
    assert bare["meters"] == 7.0


def test_unreadable_photo_friendly_reply(tmp_path):
    from app.services import consultant as c
    garbage = tmp_path / "garbage.jpg"
    garbage.write_bytes(os.urandom(512))
    out = c.chat("t-unread", "hello", image_path=str(garbage))
    assert out["recommendations"] == []
    assert "JPG" in out["reply"] or "jpg" in out["reply"].lower()


def test_estimate_cost_tool_no_fabric():
    from app.services import consultant as c
    out = c.execute_tool("estimate_cost", {"target": "sofa"},
                         {"session": {}, "seen": []})
    assert out["error"] == "no assigned fabric yet"


def test_quote_endpoint():
    from app.main import app
    from app.services import consultant as c
    c.SESSIONS["t-quote"] = {"messages": [],
                             "assignments": {"sofa": "FA-AC-01"}}
    client = TestClient(app)
    resp = client.get("/api/session/t-quote/quote")
    assert resp.status_code == 200
    body = resp.json()
    assert body["preliminary"] is True
    assert len(body["items"]) == 1
    assert body["items"][0]["meters"] is not None
