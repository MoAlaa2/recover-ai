"""Photo upload ingest (HEIC, large JPEG, alpha PNG, garbage)."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image


def client(tmp_path, monkeypatch):
    from app.main import app
    monkeypatch.setattr("app.api.chat.UPLOAD_DIR", str(tmp_path))
    return TestClient(app)


def post(client, name, payload, ctype):
    return client.post("/api/upload",
                       files={"file": (name, payload, ctype)})


def test_heic_upload_becomes_jpeg(tmp_path, monkeypatch):
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 100, 50)).save(buf, format="HEIF")
    resp = post(client(tmp_path, monkeypatch), "photo.HEIC", buf.getvalue(),
                "image/heic")
    assert resp.status_code == 200, resp.text
    out = Image.open(str(tmp_path / resp.json()["image_path"].split(
        "uploads/")[1]))
    assert out.format == "JPEG"
    assert out.size == (64, 48)


def test_large_jpeg_exif_transposed(tmp_path, monkeypatch):
    buf = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6  # rotate 90 CW (iPhone portrait)
    Image.new("RGB", (4000, 3000), (10, 120, 200)).save(
        buf, "JPEG", exif=exif)
    resp = post(client(tmp_path, monkeypatch), "IMG_12MP.JPG",
                buf.getvalue(), "image/jpeg")
    assert resp.status_code == 200, resp.text
    out = Image.open(str(tmp_path / resp.json()["image_path"].split(
        "uploads/")[1]))
    assert out.size == (3000, 4000)


def test_png_alpha_flattened(tmp_path, monkeypatch):
    buf = io.BytesIO()
    Image.new("RGBA", (32, 24), (10, 20, 30, 0)).save(buf, "PNG")
    resp = post(client(tmp_path, monkeypatch), "room.png", buf.getvalue(),
                "image/png")
    assert resp.status_code == 200, resp.text
    out = Image.open(str(tmp_path / resp.json()["image_path"].split(
        "uploads/")[1]))
    assert out.mode == "RGB"


def test_garbage_rejected(tmp_path, monkeypatch):
    resp = post(client(tmp_path, monkeypatch), "photo.jpg",
                b"not an image at all", "image/jpeg")
    assert resp.status_code == 400


def test_unsupported_type_rejected(tmp_path, monkeypatch):
    resp = post(client(tmp_path, monkeypatch), "anim.gif", b"GIF89a",
                "image/gif")
    assert resp.status_code == 400
