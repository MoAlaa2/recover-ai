"""B1: every image_path rides one allow-listed, size-capped resolver."""
import os

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_mod


def test_rejects_absolute_outside_roots():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        chat_mod.resolve_client_image("/etc/passwd")
    with pytest.raises(HTTPException):
        chat_mod.resolve_client_image("/dev/zero")


def test_rejects_traversal(tmp_path, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(chat_mod, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(chat_mod, "SAMPLES_DIR", str(tmp_path / "s"))
    with pytest.raises(HTTPException):
        chat_mod.resolve_client_image("uploads/../../app/main.py")
    with pytest.raises(HTTPException):
        chat_mod.resolve_client_image("")


def test_accepts_uploads_and_samples(tmp_path, monkeypatch):
    up = tmp_path / "uploads"
    smp = tmp_path / "samples"
    up.mkdir()
    smp.mkdir()
    (up / "a.jpg").write_bytes(b"x" * 10)
    (smp / "b.jpg").write_bytes(b"y" * 10)
    monkeypatch.setattr(chat_mod, "UPLOAD_DIR", str(up))
    monkeypatch.setattr(chat_mod, "SAMPLES_DIR", str(smp))
    monkeypatch.setattr(chat_mod, "BASE_DIR", str(tmp_path))
    got = chat_mod.resolve_client_image("uploads/a.jpg")
    assert got.endswith(os.path.join("uploads", "a.jpg"))


def test_rejects_oversize(tmp_path, monkeypatch):
    up = tmp_path / "up"
    up.mkdir()
    big = up / "big.jpg"
    big.write_bytes(b"z")
    monkeypatch.setattr(chat_mod, "UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setattr(chat_mod, "SAMPLES_DIR", str(tmp_path / "nope"))
    monkeypatch.setattr(chat_mod, "IMAGE_MAX_BYTES", 0)
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        chat_mod.resolve_client_image(
            str(big).replace(str(tmp_path) + "/", ""))


def test_chat_route_rejects_dev_zero():
    from app.main import app
    client = TestClient(app)
    res = client.post("/api/chat", json={"session_id": "b1",
                                         "message": "hi",
                                         "image_path": "/dev/zero"})
    assert res.status_code == 400


def test_no_analyze_room_tool():
    import inspect
    from app.services import consultant as c
    names = [t["function"]["name"] for t in c.TOOLS]
    assert "analyze_room" not in names
    # No handler branch left: the server analyzes the photo itself.
    assert "analyze_room" not in inspect.getsource(c._execute_tool)


def test_swap_endpoint_rejects_bad_image_and_unknown_target(tmp_path,
                                                            monkeypatch):
    """/api/swap validates like the stream and multi endpoints: a bad
    image_path or a named unknown piece is a 400, never a 500 or a
    silent sofa swap."""
    from app.main import app
    monkeypatch.setattr(chat_mod, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(chat_mod, "swap",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("swap must not run")))
    client = TestClient(app)
    for bad in ("/etc/passwd", "../../etc/passwd", "uploads/missing.jpg", ""):
        r = client.post("/api/swap", json={"image_path": bad,
                                           "fabric_code": "FA-VL-01",
                                           "target": "sofa"})
        assert r.status_code == 400, (bad, r.status_code, r.text)
    r = client.post("/api/swap", json={"image_path": "data/samples/living.jpg",
                                       "fabric_code": "FA-VL-01",
                                       "target": "bed"})
    assert r.status_code == 400 and "unknown target" in r.text


def test_fabric_list_filters_by_piece(tmp_path, monkeypatch):
    from app.main import app
    client = TestClient(app)
    curt = client.get("/api/fabrics?suitable_for=curtains&limit=40").json()
    sofa = client.get("/api/fabrics?suitable_for=sofa&limit=40").json()
    assert curt["usage"] == "curtains" and sofa["usage"] == "upholstery"
    ccodes = {f["code"] for f in curt["fabrics"]}
    scodes = {f["code"] for f in sofa["fabrics"]}
    assert ccodes and scodes and ccodes != scodes
    from app.services.catalog import get_fabric
    assert all(get_fabric(c)["usage"] == "curtains" for c in ccodes)
