"""B2: sessions/logs out of served /uploads; serving+minting allow-listed."""
import os

from fastapi.testclient import TestClient

from app.core.config import PRIVATE_DIR, UPLOAD_DIR, runtime_logs_dir
from app.services import share as share_mod
from app.services import whatsapp as wa


def test_private_dirs_outside_uploads():
    assert os.path.realpath(PRIVATE_DIR) != os.path.realpath(UPLOAD_DIR)
    assert "private" in os.path.realpath(wa.sessions_dir())
    assert "private" in os.path.realpath(wa.media_cache_path())
    assert "private" in os.path.realpath(runtime_logs_dir())
    assert not os.path.realpath(wa.sessions_dir()).startswith(
        os.path.realpath(UPLOAD_DIR) + os.sep)


def test_is_public_upload():
    good = ["swap/abc.jpg", "swap/mask-1.png", "masks/x.png",
            "a" * 32 + ".jpg", "wa-" + "b" * 12 + ".jpg"]
    bad = ["logs/grounding_log.json", "wa_sessions/1555.json",
           "media_cache.json", "swap/../app/main.py", "", "swap/a b.jpg",
           "upload-abc.webm", "wa-in-abc.bin", "x.jpg", "../x.jpg"]
    for rel in good:
        assert share_mod.is_public_upload(rel), rel
    for rel in bad:
        assert not share_mod.is_public_upload(rel), rel


def test_serving_blocks_private_prefixes():
    from app.main import app
    client = TestClient(app)
    assert client.get("/uploads/logs/grounding_log.json").status_code == 404
    assert client.get("/uploads/wa_sessions/1.json").status_code == 404
    assert client.get("/uploads/media_cache.json").status_code == 404
    assert client.get("/uploads/swap/../../app/main.py").status_code == 404


def test_serving_allows_public_names():
    from app.main import app
    client = TestClient(app)
    pub = os.path.join(UPLOAD_DIR, "swap", "t-b2.jpg")
    priv = os.path.join(UPLOAD_DIR, "logs", "t-b2.json")
    os.makedirs(os.path.dirname(pub), exist_ok=True)
    os.makedirs(os.path.dirname(priv), exist_ok=True)
    with open(pub, "wb") as f:
        f.write(b"jpg")
    with open(priv, "w") as f:
        f.write("{}")
    try:
        assert client.get("/uploads/swap/t-b2.jpg").status_code == 200
        assert client.get("/uploads/logs/t-b2.json").status_code == 404
    finally:
        for p in (pub, priv):
            try:
                os.remove(p)
            except OSError:
                pass


def test_share_mint_rejects_private():
    from app.main import app
    client = TestClient(app)
    priv = os.path.join(UPLOAD_DIR, "logs", "t-b2-share.json")
    os.makedirs(os.path.dirname(priv), exist_ok=True)
    with open(priv, "w") as f:
        f.write("{}")
    try:
        res = client.post("/api/share",
                          json={"result_url": "uploads/logs/t-b2-share.json"})
        assert res.status_code == 404
    finally:
        try:
            os.remove(priv)
        except OSError:
            pass
