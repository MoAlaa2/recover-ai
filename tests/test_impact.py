"""Sourced CO2 factor-table tests (no model calls)."""
from app.services import impact as im


def test_sofa_sourced_figures():
    co2, waste = im.avoided({"sofa": "FA-AC-01"})
    assert co2 == 52.0
    assert waste == 48.0


def test_sofa_and_cushions_count_once():
    co2, waste = im.avoided({"sofa": "FA-AC-01", "cushions": "FA-AC-02"})
    assert (co2, waste) == (52.0, 48.0)


def test_cushions_alone_count_nothing():
    """Re-covering loose pillows is not a sofa kept out of landfill."""
    assert im.avoided({"cushions": "FA-AC-02"}) == (0.0, 0.0)


def test_armchair_scales():
    co2, waste = im.avoided({"armchair": "FA-AC-01"})
    assert co2 == round(52.0 * 0.35, 1)
    assert waste == round(48.0 * 0.35, 1)


def test_curtains_and_unknown_count_zero():
    assert im.avoided({"curtains": "FA-AC-01"}) == (0.0, 0.0)
    assert im.avoided({"lamp": "FA-AC-01"}) == (0.0, 0.0)
    assert im.avoided({}) == (0.0, 0.0)


def test_quote_carries_co2():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import consultant as c
    c.SESSIONS["t-co2"] = {"messages": [],
                           "assignments": {"sofa": "FA-AC-01"}}
    body = TestClient(app).get("/api/session/t-co2/quote").json()
    assert body["co2"]["kg"] == 52.0
    assert "NEPD-1805-759" in body["co2"]["source"]
