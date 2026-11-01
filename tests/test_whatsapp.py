"""WhatsApp bot tests (no network, no model calls)."""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.services import whatsapp as wa

FAKE_ENV = {"WA_TOKEN": "tok", "WA_PHONE_NUMBER_ID": "pid",
            "WA_APP_SECRET": "sec", "WA_VERIFY_TOKEN": "verify-me"}


@pytest.fixture()
def env(monkeypatch, tmp_path):
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(wa, "UPLOAD_DIR", str(tmp_path))
    # Sessions now live in the private dir: keep them per-test too.
    monkeypatch.setattr(wa, "PRIVATE_DIR", str(tmp_path / "private"))
    monkeypatch.setattr(wa, "SYNC_MODE", True)
    return tmp_path


@pytest.fixture()
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(wa, "SEND_FN", sent.append)
    return sent


_WAID_COUNTER = [0]


@pytest.fixture()
def waid(env):
    _WAID_COUNTER[0] += 1
    wid = "1555000%04d" % _WAID_COUNTER[0]
    yield wid
    wa.consultant_mod.SESSIONS.pop(wa.wa_session_id(wid), None)


def signed(body):
    raw = json.dumps(body).encode("utf-8")
    sig = hmac.new(b"sec", raw, "sha256").hexdigest()
    return raw, "sha256=" + sig


def meta_message(mid="m1", wa_id="15550001111", kind="text",
                 text="hello"):
    return {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": wa_id}],
        "messages": [{"id": mid, "type": kind,
                      "text": {"body": text}}]}}]}]}


def test_signature():
    assert wa.verify_signature(b"{}", "sha256=" + hmac.new(
        b"sec", b"{}", "sha256").hexdigest()) in (True, False)
    import os
    os.environ["WA_APP_SECRET"] = "sec"
    try:
        assert wa.verify_signature(b"{}", "sha256=" + hmac.new(
            b"sec", b"{}", "sha256").hexdigest()) is True
        assert wa.verify_signature(b"{}", "sha256=dead") is False
        assert wa.verify_signature(b"{}", "") is False
        assert wa.verify_signature(b"{x}", "sha256=" + hmac.new(
            b"sec", b"{}", "sha256").hexdigest()) is False
    finally:
        del os.environ["WA_APP_SECRET"]


def test_challenge_ok_and_forbidden(env):
    from app.main import app
    client = TestClient(app)
    good = client.get("/webhook/whatsapp",
                      params={"hub.mode": "subscribe",
                              "hub.verify_token": "verify-me",
                              "hub.challenge": "CHAL"})
    assert good.status_code == 200
    assert good.text == "CHAL"
    bad = client.get("/webhook/whatsapp",
                     params={"hub.mode": "subscribe",
                             "hub.verify_token": "nope",
                             "hub.challenge": "CHAL"})
    assert bad.status_code == 403


def test_challenge_unconfigured(monkeypatch):
    from app.main import app
    for key in FAKE_ENV:
        monkeypatch.delenv(key, raising=False)
    client = TestClient(app)
    resp = client.get("/webhook/whatsapp",
                      params={"hub.mode": "subscribe",
                              "hub.verify_token": "x",
                              "hub.challenge": "CHAL"})
    assert resp.status_code == 404


def test_post_rejects_bad_signature(env):
    from app.main import app
    client = TestClient(app)
    resp = client.post("/webhook/whatsapp", content=b"{}",
                       headers={"X-Hub-Signature-256": "sha256=dead"})
    assert resp.status_code == 403


def test_post_unconfigured(monkeypatch):
    from app.main import app
    for key in FAKE_ENV:
        monkeypatch.delenv(key, raising=False)
    client = TestClient(app)
    resp = client.post("/webhook/whatsapp", content=b"{}",
                       headers={"X-Hub-Signature-256": "sha256=x"})
    assert resp.status_code == 404


def test_dedupe_and_text_turn(env, outbox, waid, monkeypatch):
    from app.main import app
    calls = []

    def fake_chat(sid, message, image_path=None, **kwargs):
        calls.append(message)
        return {"reply": "Pick one", "recommendations": [],
                "options": ["Sofa only", "Cushions too"],
                "targets": {}, "detected_lang": "en"}

    monkeypatch.setattr(wa.consultant_mod, "chat", fake_chat)
    client = TestClient(app)
    body = meta_message(mid="dup1", wa_id=waid, text="hi")
    raw, sig = signed(body)
    headers = {"X-Hub-Signature-256": sig}
    first = client.post("/webhook/whatsapp", content=raw,
                        headers=headers)
    second = client.post("/webhook/whatsapp", content=raw,
                         headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert calls == ["hi"], "Meta retries must not re-run the turn"
    texts = [p for p in outbox if p.get("type") == "text"]
    assert texts and texts[0]["text"]["body"] == "Pick one"
    buttons = [p for p in outbox if p.get("type") == "interactive"]
    assert buttons
    action = buttons[0]["interactive"]["action"]["buttons"]
    assert [b["reply"]["id"] for b in action] == [
        "chip:Sofa only", "chip:Cushions too"]


def test_many_options_become_list(env, outbox, waid, monkeypatch):
    opts = ["one", "two", "three", "four"]

    def fake_chat(sid, message, image_path=None, **kwargs):
        return {"reply": "Choose", "recommendations": [],
                "options": opts, "targets": {}, "detected_lang": "en"}

    monkeypatch.setattr(wa.consultant_mod, "chat", fake_chat)
    wa.process_message(waid, {"kind": "text", "id": "m-list",
                              "text": "go"})
    lists = [p for p in outbox
             if p.get("interactive", {}).get("type") == "list"]
    assert lists
    rows = lists[0]["interactive"]["action"]["sections"][0]["rows"]
    assert len(rows) == 4


def test_long_titles_become_list(env, outbox, waid, monkeypatch):
    opts = ["A very long option title here", "short"]

    def fake_chat(sid, message, image_path=None, **kwargs):
        return {"reply": "Choose", "recommendations": [],
                "options": opts, "targets": {}, "detected_lang": "en"}

    monkeypatch.setattr(wa.consultant_mod, "chat", fake_chat)
    wa.process_message(waid, {"kind": "text", "id": "m-long",
                              "text": "go"})
    assert any(p.get("interactive", {}).get("type") == "list"
               for p in outbox)


def test_targets_question_forces_list(env, outbox, waid, monkeypatch):
    def fake_chat(sid, message, image_path=None, **kwargs):
        return {"reply": "What would you like to change?",
                "recommendations": [],
                "options": ["Sofa only", "All of them"],
                "targets": {"available": ["sofa", "cushions"],
                            "chosen": []},
                "detected_lang": "en"}

    monkeypatch.setattr(wa.consultant_mod, "chat", fake_chat)
    wa.process_message(waid, {"kind": "text", "id": "m-tq",
                              "text": "photo"})
    assert any(p.get("interactive", {}).get("type") == "list"
               for p in outbox)


def test_recs_send_images_then_try(env, outbox, waid, monkeypatch):
    recs = [{"code": "FA-AC-01", "name_en": "Linen",
             "name_ar": "كتان", "price_usd_per_m": 95,
             "image": "data/catalog/FA-AC-01.jpg",
             "reason": "Good.", "matched": ["washable"]}]
    monkeypatch.setattr(wa, "upload_media",
                        lambda path, mime="image/jpeg": "media-1")

    def fake_chat(sid, message, image_path=None, **kwargs):
        return {"reply": "Top picks", "recommendations": recs,
                "options": [], "targets": {}, "detected_lang": "en"}

    monkeypatch.setattr(wa.consultant_mod, "chat", fake_chat)
    wa.process_message(waid, {"kind": "text", "id": "m-rec",
                              "text": "recommend"})
    images = [p for p in outbox if p.get("type") == "image"]
    assert images and images[0]["image"]["id"] == "media-1"
    assert "FA-AC-01" in images[0]["image"]["caption"]
    assert "95" in images[0]["image"]["caption"]
    tries = [p for p in outbox
             if p.get("interactive", {}).get("type") == "button"]
    assert tries
    assert tries[0]["interactive"]["action"]["buttons"][0][
        "reply"]["id"] == "try:FA-AC-01"


def test_try_runs_swap(env, outbox, waid, monkeypatch):
    import os
    monkeypatch.setattr(wa, "upload_media",
                        lambda path, mime="image/jpeg": "media-9")

    def fake_swap(room_path, code, target="sofa", **kwargs):
        assert code == "FA-AC-01"
        return {"result_url": "uploads/swap/r.jpg", "mask_url": "",
                "scores": {}, "attempts": 1}

    import app.services.swap as swap_mod
    monkeypatch.setattr(swap_mod, "swap", fake_swap)
    wa.consultant_mod.SESSIONS[wa.wa_session_id(waid)] = {
        "messages": [], "lang": "en",
        "image_path": "uploads/room.jpg",
        "chosen_targets": ["sofa"]}
    wa.process_message(waid, {"kind": "interactive", "id": "m-try",
                              "payload": "try:FA-AC-01"})
    images = [p for p in outbox if p.get("type") == "image"]
    assert images
    assert "FA-AC-01" in images[0]["image"]["caption"]


def test_try_without_photo_asks(env, outbox, waid):
    wa.consultant_mod.SESSIONS[wa.wa_session_id(waid)] = {
        "messages": [], "lang": "ar"}
    wa.process_message(waid, {"kind": "interactive", "id": "m-try2",
                              "payload": "try:FA-AC-01"})
    assert outbox and "صورة" in outbox[0]["text"]["body"]


def test_new_and_language_commands(env, outbox, waid):
    wa.consultant_mod.SESSIONS[wa.wa_session_id(waid)] = {
        "messages": [{"role": "user", "content": "hi"}]}
    wa.process_message(waid, {"kind": "text", "id": "m-new",
                              "text": "new"})
    assert wa.wa_session_id(waid) not in wa.consultant_mod.SESSIONS
    wa.process_message(waid, {"kind": "text", "id": "m-lang",
                              "text": "language"})
    assert any(p.get("type") == "interactive" for p in outbox)


def test_image_inbound(env, outbox, waid, monkeypatch):
    import shutil
    src = "data/samples/living.jpg"
    monkeypatch.setattr(wa, "fetch_media",
                        lambda mid: open(src, "rb").read())

    def fake_chat(sid, message, image_path=None, **kwargs):
        assert image_path and image_path.startswith("uploads/wa-")
        return {"reply": "Nice room", "recommendations": [],
                "options": [], "targets": {}, "detected_lang": "en"}

    monkeypatch.setattr(wa.consultant_mod, "chat", fake_chat)
    wa.process_message(waid, {"kind": "image", "id": "m-img",
                              "media_id": "mid-1", "caption": ""})
    assert any(p.get("text", {}).get("body") == "Nice room"
               for p in outbox if p.get("type") == "text")


def test_audio_inbound(env, outbox, waid, monkeypatch):
    monkeypatch.setattr(wa, "fetch_media", lambda mid: b"fake-ogg")

    def fake_transcribe(path):
        assert path.endswith(".ogg")
        return {"text": "sofa fabric please"}

    import app.services.voice as voice_mod
    monkeypatch.setattr(voice_mod, "transcribe", fake_transcribe)
    seen = []

    def fake_chat(sid, message, image_path=None, **kwargs):
        seen.append(message)
        return {"reply": "ok", "recommendations": [], "options": [],
                "targets": {}, "detected_lang": "en"}

    monkeypatch.setattr(wa.consultant_mod, "chat", fake_chat)
    wa.process_message(waid, {"kind": "audio", "id": "m-au",
                              "media_id": "aud-1"})
    assert seen == ["sofa fabric please"]


def test_summary_text(env, waid):
    wa.consultant_mod.SESSIONS[wa.wa_session_id(waid)] = {
        "messages": [], "lang": "en",
        "assignments": {"sofa": "FA-AC-01"}}
    text = wa.summary_text(waid, "en")
    assert "FA-AC-01" in text
    assert "Total" in text and "$" in text and "SAR" not in text
    assert "52" in text and "NEPD-1805-759" in text
    ar = wa.summary_text(waid, "ar")
    assert "الإجمالي" in ar and "$" in ar and "ر.س" not in ar


def test_session_persists_and_expires(env, waid):
    session = {"messages": [{"role": "user", "content": "hi"}],
               "lang": "ar", "seen_ids": ["a"]}
    wa.save_wa_session(waid, session)
    loaded = wa.load_wa_session(waid)
    assert loaded["lang"] == "ar"
    assert loaded["messages"]
    import time
    path = wa.session_path(waid)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["saved_at"] = time.time() - 25 * 3600
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    assert wa.load_wa_session(waid) == {}


def test_parse_webhook_shapes():
    body = {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": "1555"}],
        "messages": [
            {"id": "t1", "type": "text",
             "text": {"body": "hi"}},
            {"id": "i1", "type": "image",
             "image": {"id": "m1", "caption": "cap"}},
            {"id": "a1", "type": "audio",
             "audio": {"id": "m2"}},
            {"id": "b1", "type": "interactive",
             "interactive": {"type": "button_reply",
                             "button_reply": {"id": "chip:x"}}},
            {"id": "s1", "type": "sticker", "sticker": {}}]}}]}]}
    got = wa.parse_webhook(body)
    kinds = [m["kind"] for _, m in got]
    assert kinds == ["text", "image", "audio", "interactive"]
    assert got[1][1]["caption"] == "cap"
    assert got[3][1]["payload"] == "chip:x"
    assert wa.parse_webhook({}) == []
    assert wa.parse_webhook({"entry": [{"changes": []}]}) == []
