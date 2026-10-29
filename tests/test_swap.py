"""Fabric swap tests (model calls are faked or offline)."""
import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services import swap as s

TMP = "/tmp/recover-swap-test"


def setup_function(_):
    os.makedirs(TMP, exist_ok=True)


def solid(color, size=(64, 48)):
    return Image.new("RGB", size, color)


def test_composite_keeps_rest_pixel_identical():
    original = solid((10, 20, 30))
    edited = solid((200, 210, 220))
    mask = s.paste_mask(original, edited, (8, 8, 24, 24),
                        margin=0.0, feather=0)
    result = original.copy()
    result.paste(edited, (0, 0), mask)
    outside = result.crop((0, 0, 8, 48)).tobytes()
    assert outside == original.crop((0, 0, 8, 48)).tobytes()
    inside = result.crop((12, 12, 20, 20)).tobytes()
    assert inside == edited.crop((12, 12, 20, 20)).tobytes()


def test_paste_mask_empty_when_unchanged():
    original = solid((10, 20, 30))
    mask = s.paste_mask(original, original.copy(), (0, 0, 64, 48),
                        margin=0.05, feather=2)
    assert max(mask.getextrema()) == 0


def test_verify_parsing(monkeypatch):
    import app.services.swap as mod

    def fake_post(url, payload, api_key, timeout, **kw):
        return {"choices": [{"message": {"content":
                 "Scores: {\"color\": 9, \"pattern\": 8, "
                 "\"scale\": 9, \"isolation\": 7}"}}]}
    monkeypatch.setattr(mod, "_post_json", fake_post)
    scores = s.verify(b"sw", solid((1, 2, 3)), {"plain_or_patterned":
                                               "plain"}, "sofa", "key")
    assert scores == {"color": 9, "pattern": 8, "scale": 9,
                      "isolation": 7}


def test_verify_rejects_garbage(monkeypatch):
    import app.services.swap as mod

    def fake_post(url, payload, api_key, timeout, **kw):
        return {"choices": [{"message": {"content": "no json here"}}]}
    monkeypatch.setattr(mod, "_post_json", fake_post)
    with pytest.raises(s.SwapError):
        s.verify(b"sw", solid((1, 2, 3)), {}, "sofa", "key")


def test_swap_rejects_unknown_fabric(tmp_path):
    room = tmp_path / "room.jpg"
    solid((5, 5, 5)).save(str(room))
    with pytest.raises(s.SwapError):
        s.swap(str(room), "FA-XX-99", "sofa")


def test_swap_endpoint_shape(monkeypatch):
    from app.main import app
    monkeypatch.setattr("app.api.chat.swap",
                        lambda *a, **k: {"result_url": "uploads/swap/r.jpg",
                                         "mask_url": "uploads/swap/m.png",
                                         "scores": {"color": 9,
                                                     "pattern": 9,
                                                     "scale": 8,
                                                     "isolation": 8},
                                         "attempts": 1})
    client = TestClient(app)
    resp = client.post("/api/swap", json={"session_id": "s",
                                          "image_path": "uploads/x.jpg",
                                          "fabric_code": "FA-NL-02"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["attempts"] == 1
    assert body["scores"]["color"] == 9


def test_swap_endpoint_unknown_fabric():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/api/swap", json={"session_id": "s",
                                          "image_path": "uploads/x.jpg",
                                          "fabric_code": "FA-XX-99"})
    assert resp.status_code == 400


def test_preview_store_roundtrip():
    from app.api import chat as chat_api
    chat_api.PREVIEWS.clear()
    res = {"result_url": "uploads/swap/r.jpg",
           "mask_url": "uploads/swap/m.png",
           "scores": {"color": 9, "pattern": 9, "scale": 9,
                      "isolation": 9},
           "attempts": 1}
    chat_api.record_preview("sess-1", "FA-NL-02", res)
    got = chat_api.get_previews("sess-1")
    assert len(got) == 1
    assert got[0]["fabric_code"] == "FA-NL-02"
    assert got[0]["scores"]["color"] == 9
    assert got[0]["created_at"] > 0
    assert chat_api.get_previews("other") == []
    chat_api.PREVIEWS.clear()


def test_preview_store_caps_length():
    from app.api import chat as chat_api
    chat_api.PREVIEWS.clear()
    res = {"result_url": "r.jpg", "mask_url": "m.png", "scores": {},
           "attempts": 1}
    for _ in range(chat_api.MAX_PREVIEWS + 5):
        chat_api.record_preview("sess-2", "FA-NL-02", res)
    assert len(chat_api.get_previews("sess-2")) == chat_api.MAX_PREVIEWS
    chat_api.PREVIEWS.clear()
