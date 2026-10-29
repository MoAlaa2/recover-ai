"""WhatsApp failure logging + text fallback (never silent, never leaks token)."""
import json

import pytest

from app.services import whatsapp as wa

FAKE_ENV = {"WA_TOKEN": "SECRETTOKENXYZ", "WA_PHONE_NUMBER_ID": "pid",
            "WA_APP_SECRET": "sec", "WA_VERIFY_TOKEN": "verify-me"}


@pytest.fixture()
def env(monkeypatch, tmp_path):
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(wa, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(wa, "SYNC_MODE", True)
    return tmp_path


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(wa, "SEND_FN", sent.append)
    return sent


_WAID_COUNTER = [100]


@pytest.fixture()
def waid(env):
    _WAID_COUNTER[0] += 1
    wid = "1555000%04d" % _WAID_COUNTER[0]
    yield wid
    wa.consultant_mod.SESSIONS.pop(wa.wa_session_id(wid), None)


def _text_messages(sent):
    return [p for p in sent if p.get("type") == "text"]


def test_consultant_error_sends_apology_and_logs_traceback(
        env, outbox, waid, monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError("consultant down")
    monkeypatch.setattr(wa.consultant_mod, "chat", boom)
    wa.process_message(waid, {"kind": "text", "id": "m1", "text": "hi"})
    texts = _text_messages(outbox)
    assert texts, "consultant failure must still reply (no silence)"
    assert "try again" in texts[-1]["text"]["body"]
    logged = capsys.readouterr().out
    assert "consultant_error" in logged
    assert "traceback" in logged
    assert "RuntimeError" in logged
    assert "SECRETTOKENXYZ" not in logged
    assert waid not in logged


def test_send_error_sends_apology_and_logs(env, waid, monkeypatch, capsys):
    calls = []

    def flaky(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise RuntimeError("graph down")
        return {"messages": [{"id": "wam"}]}

    monkeypatch.setattr(wa, "SEND_FN", flaky)
    monkeypatch.setattr(
        wa.consultant_mod, "chat",
        lambda *a, **k: {"reply": "hello", "options": [],
                         "recommendations": [], "targets": {},
                         "detected_lang": "en"})
    wa.process_message(waid, {"kind": "text", "id": "m2", "text": "hi"})
    assert len(calls) == 2
    assert "try again" in calls[1]["text"]["body"]
    assert "send_error" in capsys.readouterr().out


def test_post_graph_logs_status_and_body_without_token(
        env, monkeypatch, capsys):
    class FakeResp:
        status_code = 400
        text = json.dumps({"error": {"message": "(#131047) fail",
                                     "code": 131047}})

        def raise_for_status(self):
            import httpx
            raise httpx.HTTPStatusError("bad", request=None,
                                        response=None)

        def json(self):
            return {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr(wa.httpx, "Client", FakeClient)
    with pytest.raises(Exception):
        wa._post_graph("/messages", {"to": "1555", "type": "text"})
    logged = capsys.readouterr().out
    assert "graph_error" in logged
    assert "400" in logged
    assert "131047" in logged
    assert "SECRETTOKENXYZ" not in logged


def test_parse_attaches_metadata_phone_id(env):
    body = {"entry": [{"changes": [{"value": {
        "metadata": {"display_phone_number": "+17116274057",
                     "phone_number_id": "1449726954880802"},
        "contacts": [{"wa_id": "15550009999"}],
        "messages": [{"id": "mvia", "type": "text",
                      "text": {"body": "hi"}}]}}]}]}
    [(wid, msg)] = wa.parse_webhook(body)
    assert wid == "15550009999"
    assert msg["via"] == "1449726954880802"


def test_parse_missing_metadata_falls_back(env):
    body = {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": "15550001112"}],
        "messages": [{"id": "mfb", "type": "text",
                      "text": {"body": "hi"}}]}}]}]}
    [(wid, msg)] = wa.parse_webhook(body)
    assert wid == "15550001112"
    assert msg.get("via", "") == ""


def test_graph_url_uses_arrival_number(env, monkeypatch):
    monkeypatch.setenv("WA_PHONE_NUMBER_ID", "pid")
    assert "/pid/" in wa.graph_url("/messages")
    tok = wa._send_phone_ctx.set("1449726954880802")
    try:
        assert "/1449726954880802/" in wa.graph_url("/messages")
    finally:
        wa._send_phone_ctx.reset(tok)


def test_process_message_replies_from_arrival_number(
        env, waid, monkeypatch, capsys):
    monkeypatch.setattr(
        wa.consultant_mod, "chat",
        lambda *a, **k: {"reply": "hello", "options": [],
                         "recommendations": [], "targets": {},
                         "detected_lang": "en"})
    seen_senders = []

    def fake_send(payload):
        # SEND_FN bypasses graph_url, so capture the routed sender here.
        seen_senders.append(wa._send_phone_id())
        return {"messages": [{"id": "wam"}]}

    monkeypatch.setattr(wa, "SEND_FN", fake_send)
    wa.process_message(waid, {"kind": "text", "id": "mvia2",
                             "text": "hi", "via": "1432888193234143"})
    assert seen_senders and seen_senders == ["1432888193234143"]
    assert wa._send_phone_ctx.get() == ""
    logged = capsys.readouterr().out
    assert "inbound" in logged
    assert "1432888193234143" in logged


def test_temp_files_unique_per_message(env, waid, monkeypatch, tmp_path):
    import re
    monkeypatch.setattr(wa, "UPLOAD_DIR", str(tmp_path))
    srcs = []
    monkeypatch.setattr(wa, "fetch_media", lambda mid: b"rawbytes")
    monkeypatch.setattr(
        wa, "DOWNLOAD_FN", lambda mid: b"rawbytes")
    from app.api import chat as chat_mod
    monkeypatch.setattr(
        chat_mod, "convert_to_jpg",
        lambda src, dest: srcs.append(src) or True)
    monkeypatch.setattr(
        wa.consultant_mod, "chat",
        lambda *a, **k: {"reply": "ok", "options": [],
                         "recommendations": [], "targets": {},
                         "detected_lang": "en"})
    monkeypatch.setattr(wa, "SEND_FN", lambda payload: {"ok": True})
    wa.handle_image(waid, "media-one", "")
    wa.handle_image(waid, "media-two", "")
    assert len(srcs) == 2 and srcs[0] != srcs[1]
    assert not re.search(r"wa-in-\d+\.bin$", srcs[0])
    assert all("wa-in-" in s and s.endswith(".bin") for s in srcs)


def test_try_swap_media_fail_sends_text(
        env, outbox, waid, monkeypatch, tmp_path):
    import os
    from app.services import swap as swap_mod
    (tmp_path / "r.jpg").write_bytes(b"x")
    wa.consultant_mod.SESSIONS[wa.wa_session_id(waid)] = {
        "messages": [], "image_path": "uploads/x.jpg", "lang": "en"}
    monkeypatch.setattr(
        swap_mod, "swap",
        lambda *a, **k: {"result_url": str(tmp_path / "r.jpg")})

    def no_upload(path):
        raise RuntimeError("upload down")
    monkeypatch.setattr(wa, "upload_media", no_upload)
    monkeypatch.setattr(wa, "BASE_DIR", str(tmp_path))
    wa.run_try_swap(waid, "FAKE01", "sofa")
    texts = _text_messages(outbox)
    assert texts, "media-upload failure must still reply (no silence)"
