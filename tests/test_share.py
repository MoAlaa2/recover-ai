"""Public share-link tests (no model calls, no secrets in repo)."""
import os
import time

import pytest
from fastapi.testclient import TestClient

from app.services import share as sh


@pytest.fixture()
def jpg(tmp_path, monkeypatch):
    monkeypatch.setattr(sh, "UPLOAD_DIR", str(tmp_path))
    import app.api.chat as chat_api
    monkeypatch.setattr(chat_api, "UPLOAD_DIR", str(tmp_path))
    room = tmp_path / "swap"
    room.mkdir()
    target = room / "r.jpg"
    target.write_bytes(b"\xff\xd8\xff fake-jpeg")
    return "swap/r.jpg"


def test_roundtrip(jpg, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "k")
    token, exp = sh.create_token(jpg)
    assert exp > time.time()
    assert sh.verify_token(token) == jpg
    assert sh.verify_token(token + ".jpg") == jpg


def test_tampered_and_expired(jpg, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "k")
    token, _ = sh.create_token(jpg)
    body, _, mac = token.rpartition(".")
    assert sh.verify_token(body + ".AAAA") is None
    assert sh.verify_token("garbage") is None
    assert sh.verify_token("") is None
    old, _ = sh.create_token(jpg, ttl_s=-10)
    assert sh.verify_token(old) is None


def test_resolve_rejects(jpg):
    assert sh.resolve_result("uploads/../../app/main.py") is None
    assert sh.resolve_result("swap/secret.txt") is None
    assert sh.resolve_result("swap/missing.jpg") is None
    assert sh.resolve_result("") is None


def test_serve_endpoint(jpg, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "k")
    from app.main import app
    client = TestClient(app)
    made = client.post("/api/share", json={"result_url": jpg})
    assert made.status_code == 200, made.text
    token = made.json()["token"]
    assert made.json()["share_path"].endswith(".jpg")
    assert made.json()["expires_at"] > time.time()
    got = client.get("/share/" + token + ".jpg")
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/jpeg"
    assert "noindex" in got.headers.get("x-robots-tag", "")
    bare = client.get("/share/" + token)
    assert bare.status_code == 200


def test_serve_rejects(jpg, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "k")
    from app.main import app
    client = TestClient(app)
    assert client.get("/share/garbage.jpg").status_code == 404
    token, _ = sh.create_token(jpg)
    bad = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert client.get("/share/" + bad).status_code == 404
    missing = client.post("/api/share",
                          json={"result_url": "swap/nope.jpg"})
    assert missing.status_code == 404
    wrong_ext = client.post("/api/share",
                            json={"result_url": "swap/x.txt"})
    assert wrong_ext.status_code == 404
