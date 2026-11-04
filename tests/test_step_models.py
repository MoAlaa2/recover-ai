"""Step events carry the powering model for badges + trace."""
import json

from app.api import chat as chat_api


def test_step_event_models():
    assert chat_api.step_event("segment") == {
        "type": "step", "label": "segment", "model": "sam-3.1"}
    assert chat_api.step_event("edit")["model"] == "muse-image-1.0"
    assert chat_api.step_event("verify")["model"] == "muse-spark-1.3"
    assert chat_api.step_event("search")["model"] == "muse-spark-1.3"
    assert "model" not in chat_api.step_event("composite")
    assert "model" not in chat_api.step_event("nonsense")


def test_swap_stream_step_carries_model(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from PIL import Image

    from app.main import app

    # /api/swap/stream validates image_path like /api/swap: real file
    # under the uploads dir.
    monkeypatch.setattr(chat_api, "UPLOAD_DIR", str(tmp_path))
    Image.new("RGB", (8, 8)).save(str(tmp_path / "x.jpg"))

    def fake_swap(image_path, fabric_code, target, on_step=None):
        if on_step:
            on_step("segment")
            on_step("edit")
        return {"result_url": "uploads/swap/r.jpg", "mask_url": "",
                "scores": {}, "attempts": 1}

    monkeypatch.setattr(chat_api, "swap", fake_swap)
    client = TestClient(app)
    resp = client.post("/api/swap/stream",
                       json={"session_id": "s",
                             "image_path": str(tmp_path / "x.jpg"),
                             "fabric_code": "FA-NL-02", "target": "sofa"})
    assert resp.status_code == 200
    models = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            evt = json.loads(line[5:])
        except ValueError:
            continue
        if evt.get("type") == "step":
            models.append((evt["label"], evt.get("model")))
    assert ("segment", "sam-3.1") in models
    assert ("edit", "muse-image-1.0") in models
