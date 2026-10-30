"""Tests for the Modal volume sync (pure ASGI, no network)."""
import asyncio

from deploy.modal_app import VolumeSyncMiddleware


class FakeVolume:
    def __init__(self):
        self.calls = []

    def reload(self):
        self.calls.append("reload")

    def commit(self):
        self.calls.append("commit")


def run(path, method, chunks=(b"ok",), upload_dir=None,
        sync_kwargs=None, body=b"", echo_body=False):
    vol = FakeVolume()
    messages = []

    async def inner(_scope, receive, send):
        if echo_body:
            seen = b""
            while True:
                message = await receive()
                if message.get("type") != "http.request":
                    break
                seen += message.get("body", b"")
                if not message.get("more_body"):
                    break
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": seen,
                        "more_body": False})
            return
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        for i, chunk in enumerate(chunks):
            await send({"type": "http.response.body", "body": chunk,
                        "more_body": i < len(chunks) - 1})

    sent_body = [body]

    drained = []

    async def receive():
        if drained:
            # A real ASGI server yields http.disconnect once the body
            # is consumed and the client goes away.
            return {"type": "http.disconnect"}
        drained.append(True)
        return {"type": "http.request", "body": sent_body[0],
                "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "path": path, "method": method,
             "headers": []}
    asyncio.run(VolumeSyncMiddleware(
        inner, vol, upload_dir=upload_dir,
        **(sync_kwargs or {}))(scope, receive, send))
    return vol.calls, messages


def test_upload_commits_no_reload():
    calls, out = run("/api/upload", "POST")
    assert calls == ["commit"]
    assert out[-1] == {"type": "http.response.body", "body": b"ok",
                       "more_body": False}


def test_chat_reloads_no_commit():
    calls, _ = run("/api/chat", "POST")
    assert calls == ["reload"]


def test_upload_file_get_reloads_no_commit():
    calls, _ = run("/uploads/abc.jpg", "GET")
    assert calls == ["reload"]


def test_targets_reloads_and_commits():
    calls, _ = run("/api/session/s/targets", "GET")
    assert calls == ["reload", "commit"]


def test_unrelated_paths_untouched():
    for path, method in [("/", "GET"), ("/consult", "GET"),
                         ("/api/voice", "POST"),
                         ("/api/session/s/previews", "GET")]:
        calls, _ = run(path, method)
        assert calls == [], (path, method)


def test_commit_once_for_chunked_body():
    # Swap reads the room file first, then persists the result.
    calls, _ = run("/api/swap", "POST", chunks=(b"a", b"b"))
    assert calls == ["reload", "commit"]


def test_commit_before_final_send():
    # The browser fetches file URLs the moment the response lands, so
    # the commit must precede the final body bytes (it used to run
    # after send, racing the browser's GET into 404s).
    events = []
    vol = FakeVolume()
    real_commit = vol.commit
    vol.commit = lambda: (events.append("commit"), real_commit())

    async def inner(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": []})
        await send({"type": "http.response.body", "body": b"done",
                    "more_body": False})

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        events.append("sent:%s" % message["type"])

    scope = {"type": "http", "path": "/api/upload", "method": "POST",
             "headers": []}
    asyncio.run(VolumeSyncMiddleware(inner, vol)(scope, receive, send))
    assert events.index("commit") < events.index(
        "sent:http.response.body")


def test_upload_get_present_no_extra_wait(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    calls, out = run("/uploads/a.jpg", "GET",
                     upload_dir=str(tmp_path))
    assert calls == ["reload"]
    assert out[-1]["body"] == b"ok"


def test_upload_get_missing_waits_then_passes_through():
    calls, out = run("/uploads/nope.jpg", "GET",
                     upload_dir="/nonexistent-xyz-recover",
                     sync_kwargs={"sync_tries": 3, "sync_sleep": 0.01})
    assert calls == ["reload"] + ["reload"] * 3
    assert out[-1]["body"] == b"ok"


def test_upload_get_missing_no_dir_no_wait():
    calls, _ = run("/uploads/nope.jpg", "GET")
    assert calls == ["reload"]


def test_share_bogus_token_no_wait():
    calls, _ = run("/share/bogus.jpg", "GET",
                   upload_dir="/nonexistent-xyz-recover")
    assert calls == []


def test_share_post_missing_file_waits_then_replays_body():
    import json
    payload = json.dumps({"result_url": "uploads/fresh.jpg"}).encode()
    calls, out = run("/api/share", "POST", upload_dir="/nonexistent-xyz",
                     sync_kwargs={"sync_tries": 3, "sync_sleep": 0.01},
                     body=payload, echo_body=True)
    # No initial reload (POST /api/share is not a reload path); the
    # missing fresh file serializes one reload chain, then the drained
    # body is replayed to the app untouched.
    assert calls == ["reload"] * 3
    assert out[-1] == {"type": "http.response.body", "body": payload,
                       "more_body": False}


def test_share_post_present_file_no_wait(tmp_path):
    import json
    (tmp_path / "r.jpg").write_bytes(b"x")
    payload = json.dumps({"result_url": "uploads/r.jpg"}).encode()
    calls, out = run("/api/share", "POST", upload_dir=str(tmp_path),
                     body=payload, echo_body=True)
    assert calls == []
    assert out[-1]["body"] == payload


def test_share_post_bad_body_passes_through():
    calls, out = run("/api/share", "POST", body=b"not-json{{{",
                     echo_body=True)
    assert calls == []
    assert out[-1]["body"] == b"not-json{{{"


def test_chat_stream_reloads_and_waits_for_the_referenced_upload():
    """A chat stream right after an upload must see the file: the
    volume is reloaded before the handler and the referenced uploads/
    image is waited into visibility, then the body is replayed."""
    import json
    payload = json.dumps({"session_id": "s", "message": "",
                          "image_path": "uploads/fresh.jpg"}).encode()
    calls, out = run("/api/chat/stream", "POST",
                     upload_dir="/nonexistent-xyz",
                     sync_kwargs={"sync_tries": 2, "sync_sleep": 0.01},
                     body=payload, echo_body=True)
    assert calls[0] == "reload"           # the pre-handler reload
    assert calls.count("reload") == 3     # + 2 wait tries for the file
    assert "commit" not in calls
    assert out[-1]["body"] == payload


def test_chat_stream_present_upload_no_extra_wait(tmp_path):
    import json
    (tmp_path / "ok.jpg").write_bytes(b"x")
    payload = json.dumps({"image_path": "uploads/ok.jpg"}).encode()
    calls, out = run("/api/chat/stream", "POST", upload_dir=str(tmp_path),
                     body=payload, echo_body=True)
    assert calls == ["reload"]
    assert out[-1]["body"] == payload


def test_chat_stream_sample_path_no_wait():
    import json
    payload = json.dumps({"image_path": "data/samples/living.jpg"}).encode()
    calls, out = run("/api/chat/stream", "POST", upload_dir="/nonexistent",
                     body=payload, echo_body=True)
    assert calls == ["reload"]
    assert out[-1]["body"] == payload


def test_replayed_body_is_followed_by_disconnect():
    """After the middleware replays the drained body, a streaming
    response that keeps listening on receive() (Starlette's
    listen_for_disconnect) must get http.disconnect, never a second
    http.request: the latter killed every chat stream on the demo."""
    import json
    seen = []

    async def inner(_scope, receive, send):
        first = await receive()
        second = await receive()
        seen.extend([first["type"], second["type"]])
        await send({"type": "http.response.start", "status": 200,
                    "headers": []})
        await send({"type": "http.response.body", "body": b"",
                    "more_body": False})

    drained = []

    async def receive():
        if drained:
            return {"type": "http.disconnect"}
        drained.append(True)
        return {"type": "http.request",
                "body": json.dumps({"image_path": "data/x.jpg"}).encode(),
                "more_body": False}

    async def send(_message):
        pass

    for path in ("/api/chat/stream", "/api/swap/stream", "/api/share"):
        seen.clear()
        scope = {"type": "http", "path": path, "method": "POST",
                 "headers": []}
        asyncio.run(VolumeSyncMiddleware(
            inner, FakeVolume(), upload_dir="/nonexistent")(
                scope, receive, send))
        assert seen == ["http.request", "http.disconnect"], (path, seen)


def test_streaming_response_survives_replay_with_real_starlette():
    """End-to-end through Starlette: an @app.middleware("http") layer
    (the app has one) plus a StreamingResponse that reads the JSON
    body. Starlette's base middleware keeps polling receive() while
    the stream runs; the demo crashed here with "Unexpected message
    received: http.request" until the replay deferred to the real
    channel after its single shot."""
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse
    from starlette.testclient import TestClient

    api = FastAPI()

    @api.middleware("http")
    async def passthrough(request, call_next):
        return await call_next(request)

    @api.post("/api/chat/stream")
    async def stream(request: Request):
        data = await request.json()

        async def gen():
            yield "data: %s\n\n" % data["image_path"]
            yield "data: done\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    wrapped = VolumeSyncMiddleware(api, FakeVolume(),
                                   upload_dir="/nonexistent")
    with TestClient(wrapped, raise_server_exceptions=True) as client:
        res = client.post("/api/chat/stream",
                          json={"image_path": "data/samples/living.jpg"})
    assert res.status_code == 200
    assert res.text == ("data: data/samples/living.jpg\n\n"
                        "data: done\n\n")
