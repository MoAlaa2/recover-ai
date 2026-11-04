"""Swap stream done-event carries catalog fabric meta (name/price/image)."""
import json

from fastapi.testclient import TestClient


def _events(resp):
    out = []
    for chunk in resp.iter_lines():
        if not chunk or not chunk.startswith("data:"):
            continue
        out.append(json.loads(chunk[len("data:"):].strip()))
    return out


def test_swap_stream_done_includes_fabric_meta(monkeypatch, tmp_path):
    from PIL import Image

    from app.main import app
    import app.api.chat as chat

    # /api/swap/stream validates image_path like /api/swap.
    monkeypatch.setattr(chat, "UPLOAD_DIR", str(tmp_path))
    Image.new("RGB", (8, 8)).save(str(tmp_path / "x.jpg"))
    monkeypatch.setattr(
        chat, "swap",
        lambda *a, **k: {"result_url": "uploads/r.jpg",
                         "mask_url": "uploads/m.png",
                         "scores": {"color": 8, "pattern": 8,
                                    "scale": 8, "isolation": 8},
                         "attempts": 1})
    client = TestClient(app)
    resp = client.post("/api/swap/stream",
                       json={"session_id": "meta-test",
                             "image_path": str(tmp_path / "x.jpg"),
                             "fabric_code": "FA-VL-01",
                             "target": "sofa"})
    assert resp.status_code == 200, resp.text
    done = [e for e in _events(resp) if e.get("type") == "done"]
    assert len(done) == 1
    fabric = done[0]["result"].get("fabric") or {}
    assert fabric.get("code") == "FA-VL-01"
    # Real catalog name, not the code echoed back.
    assert fabric.get("name_en") == "Emerald Royale"
    assert fabric.get("name_ar")
    assert isinstance(fabric.get("price_usd_per_m"), (int, float))
    assert fabric.get("image")
