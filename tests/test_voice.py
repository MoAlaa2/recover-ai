"""Voice input tests (network calls are mocked)."""
import os
import wave

import pytest

from app.services import voice as v

TMP = "/tmp/recover-voice-test"


def setup_function(_):
    os.makedirs(TMP, exist_ok=True)


def teardown_function(_):
    for name in os.listdir(TMP):
        os.remove(os.path.join(TMP, name))


def make_wav(path, seconds=1, rate=44100):
    frames = b"\x00\x00" * int(seconds * rate)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


class FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_convert_to_16k_mono_wav():
    src = os.path.join(TMP, "in.wav")
    make_wav(src)
    dest = os.path.join(TMP, "out.wav")
    seconds = v.convert_to_wav(src, dest)
    with wave.open(dest, "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
    assert seconds == pytest.approx(1.0, abs=0.05)


def test_convert_rejects_garbage():
    bad = os.path.join(TMP, "bad.txt")
    with open(bad, "w") as f:
        f.write("not audio")
    with pytest.raises(v.VoiceError):
        v.convert_to_wav(bad, os.path.join(TMP, "out.wav"))


def test_convert_rejects_long_audio(monkeypatch):
    monkeypatch.setattr(v, "wav_duration", lambda path: 601.0)
    src = os.path.join(TMP, "in.wav")
    make_wav(src)
    with pytest.raises(v.VoiceError):
        v.convert_to_wav(src, os.path.join(TMP, "out.wav"))


def test_transcribe_wav_reads_transcript(monkeypatch):
    import httpx
    src = os.path.join(TMP, "in.wav")
    make_wav(src)
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: FakeResp(200, {"transcript": "hello sofa"}))
    assert v.transcribe_wav(src) == "hello sofa"


def test_transcribe_wav_falls_back_to_turns(monkeypatch):
    import httpx
    src = os.path.join(TMP, "in.wav")
    make_wav(src)
    payload = {"transcript": "",
               "turns": [{"transcript": "warm"}, {"transcript": "beige"}]}
    monkeypatch.setattr(httpx, "post",
                        lambda *a, **k: FakeResp(200, payload))
    assert v.transcribe_wav(src) == "warm beige"


def test_transcribe_wav_http_error(monkeypatch):
    import httpx
    src = os.path.join(TMP, "in.wav")
    make_wav(src)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(500, {}))
    with pytest.raises(v.VoiceError):
        v.transcribe_wav(src)


def test_transcribe_returns_text_and_language(monkeypatch):
    import httpx
    src = os.path.join(TMP, "in.wav")
    make_wav(src)
    called = {}

    def fake_post(*a, **k):
        called["files"] = k.get("files")
        return FakeResp(200, {"transcript": "أبغى قماش للكنبة"})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = v.transcribe(src)
    assert out["text"] == "أبغى قماش للكنبة"
    assert out["language"] == "ar"
    assert called["files"]["request"][2] == "application/json"


def test_voice_endpoint_rejects_bad_type():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.post("/api/voice",
                       files={"file": ("photo.jpg", b"data",
                                       "image/jpeg")})
    assert resp.status_code == 400


def test_voice_endpoint_returns_text(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setattr("app.api.chat.transcribe",
                        lambda path: {"text": "warm beige", "language": "en"})
    client = TestClient(app)
    resp = client.post("/api/voice",
                       files={"file": ("rec.webm", b"fake-audio",
                                       "audio/webm")})
    assert resp.status_code == 200
    assert resp.json() == {"text": "warm beige"}
