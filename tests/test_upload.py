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
    # Portrait kept, long side capped (12 MP slows every mask step).
    assert out.size == (1536, 2048)


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


def test_wait_for_image_instant_when_present(tmp_path):
    from app.api import chat as chat_api
    f = tmp_path / "late.jpg"
    f.write_bytes(b"x")
    assert chat_api._wait_for_image(str(f), tries=1) is True


def test_wait_for_image_tolerates_late_file(tmp_path):
    import threading
    from app.api import chat as chat_api
    f = tmp_path / "late.jpg"
    threading.Timer(0.3, lambda: f.write_bytes(b"x")).start()
    assert chat_api._wait_for_image(str(f), tries=5) is True


def test_wait_for_image_false_when_absent(tmp_path):
    from app.api import chat as chat_api
    assert chat_api._wait_for_image(
        str(tmp_path / "never.jpg"), tries=1) is False


def test_oversized_upload_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.chat.UPLOAD_MAX_BYTES", 2000)
    buf = io.BytesIO()
    Image.radial_gradient("L").resize((400, 400)).save(buf, format="PNG")
    assert len(buf.getvalue()) > 2000
    resp = post(client(tmp_path, monkeypatch), "big.png", buf.getvalue(),
                "image/png")
    assert resp.status_code == 413
    assert not list(tmp_path.iterdir()), "nothing kept on disk"
