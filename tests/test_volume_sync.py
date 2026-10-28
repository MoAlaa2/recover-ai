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


def run(path, method, chunks=(b"ok",)):
    vol = FakeVolume()
    messages = []

    async def inner(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        for i, chunk in enumerate(chunks):
            await send({"type": "http.response.body", "body": chunk,
                        "more_body": i < len(chunks) - 1})

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "path": path, "method": method,
             "headers": []}
    asyncio.run(VolumeSyncMiddleware(inner, vol)(scope, receive, send))
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
