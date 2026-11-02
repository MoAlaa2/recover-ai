"""Page shell: version-busted assets, never-cached HTML."""
from fastapi.testclient import TestClient

from app.main import app


def test_consult_html_versioned_and_uncached():
    client = TestClient(app)
    resp = client.get("/consult")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"
    assert "/app.js?v=" in resp.text
    assert "/styles.css?v=" in resp.text


def test_landing_html_versioned_and_uncached():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"
    assert "/landing.js?v=" in resp.text


def test_versioned_asset_immutable_on_get_and_head():
    client = TestClient(app)
    for method in ("get", "head"):
        resp = getattr(client, method)("/app.js?v=x")
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == (
            "public, max-age=604800, immutable")
