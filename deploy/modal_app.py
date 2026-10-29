"""Locked Modal deploy for the ReCover demo (do NOT make it public).

Serve with:  modal deploy deploy/modal_app.py

Secrets (create once, never in code or local files read by the deploy)::

    modal secret create recover-secrets \
        MODEL_API_KEY=<key> DEMO_USER=<user> DEMO_PASS=<pass>

Runtime writes (uploads, swap results) live on a persistent Volume.
The catalog, samples, specs and static UI are baked into the image.
In-memory chat sessions and previews stay alive on the warm container
(min_containers=1). Local dev is unaffected: without DEMO_LOCK the
auth middleware passes everything through, so tests are unchanged.
"""
import base64
import hmac
import os

import modal

app = modal.App("recover-ai")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("app", remote_path="/root/recover/app")
    .add_local_dir("data", remote_path="/root/recover/data")
)

vol = modal.Volume.from_name("recover-data", create_if_missing=True)


class VolumeSyncMiddleware:
    """Keep runtime files visible across requests on the demo.

    The demo is pinned to a single container (min/max_containers=1),
    so in-memory sessions and previews never split. Volume files
    (uploads, masks, swap results) still need explicit sync: commit
    after the write paths respond, reload before the read paths run,
    so a redeploy handover or a second writer can never serve a 404.
    """

    WRITE_PREFIXES = ("/api/upload", "/api/swap", "/api/session/",
                      "/webhook/whatsapp")

    def __init__(self, inner, volume):
        self.inner = inner
        self.volume = volume

    @staticmethod
    def reads_volume(path, method):
        """True when this request reads files other requests wrote."""
        if method == "GET":
            # Previews and session state are in-memory; only uploads
            # and freshly written target masks touch the volume.
            return path.startswith("/uploads/") or (
                path.startswith("/api/session/")
                and path.endswith("/targets"))
        if method == "POST" and path.startswith("/webhook/"):
            # WhatsApp sessions and media live on the volume.
            return True
        return method == "POST" and (
            path == "/api/chat" or path.startswith("/api/swap"))

    def writes_volume(self, path, method):
        if method in ("POST", "PUT", "DELETE") and any(
                path == p or path.startswith(p)
                for p in self.WRITE_PREFIXES):
            return True
        # GET /api/session/{id}/targets also persists mask files.
        return (method == "GET" and path.startswith("/api/session/")
                and path.endswith("/targets"))

    async def __call__(self, scope, receive, send):
        import asyncio
        if scope.get("type") != "http":
            await self.inner(scope, receive, send)
            return
        path = scope.get("path", "")
        method = scope.get("method", "")
        if self.reads_volume(path, method):
            await asyncio.to_thread(self.volume.reload)
        if not self.writes_volume(path, method):
            await self.inner(scope, receive, send)
            return
        committed = []

        async def send_and_commit(message):
            # Commit BEFORE the client sees the final bytes: the app
            # answers with file URLs (uploads, masks, swap results)
            # that the browser fetches immediately, so the files must
            # be visible before the response lands. Committing after
            # send raced the browser's GET and served 404s.
            if (message["type"] == "http.response.body"
                    and not message.get("more_body")
                    and not committed):
                committed.append(True)
                await asyncio.to_thread(self.volume.commit)
            await send(message)

        await self.inner(scope, receive, send_and_commit)


class DemoLockMiddleware:
    """HTTP Basic Auth on every route when DEMO_LOCK=1.

    Uses constant-time comparison and adds
    X-Robots-Tag: noindex, nofollow to every response while locked.
    The WhatsApp webhook is exempt: Meta cannot send Basic Auth, so
    GET verification is public and POST is HMAC-verified instead.
    """

    PUBLIC_PREFIXES = ("/webhook/", "/share/")

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("type") not in ("http", "websocket"):
            await self.inner(scope, receive, send)
            return
        if os.environ.get("DEMO_LOCK", "") != "1":
            await self.inner(scope, receive, send)
            return
        if scope.get("path", "").startswith(self.PUBLIC_PREFIXES):
            await self.inner(scope, receive, send)
            return
        if not self._authed(scope.get("headers", [])):
            if scope.get("type") == "websocket":
                await send({"type": "websocket.close", "code": 4401})
                return
            body = b"Authentication required"
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"text/plain"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate",
                     b'Basic realm="ReCover demo"'),
                    (b"x-robots-tag", b"noindex, nofollow"),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        async def send_locked(message):
            if message["type"] == "http.response.start":
                headers = [(k, v)
                           for k, v in message.get("headers", [])
                           if k.lower() != b"x-robots-tag"]
                headers.append((b"x-robots-tag", b"noindex, nofollow"))
                message = dict(message)
                message["headers"] = headers
            await send(message)

        await self.inner(scope, receive, send_locked)

    @staticmethod
    def _authed(headers):
        user = os.environ.get("DEMO_USER", "")
        pwd = os.environ.get("DEMO_PASS", "")
        if not user or not pwd:
            return False
        raw = b""
        for key, value in headers or []:
            if key.lower() == b"authorization":
                raw = value
                break
        try:
            scheme, _, param = raw.decode("latin1").partition(" ")
            if scheme.lower() != "basic":
                return False
            decoded = base64.b64decode(param.strip()).decode("utf-8")
            got_user, _, got_pwd = decoded.partition(":")
        except Exception:  # noqa: BLE001 - any parse failure denies
            return False
        return (hmac.compare_digest(got_user, user)
                and hmac.compare_digest(got_pwd, pwd))


@app.function(
    image=image,
    # NOTE: append modal.Secret.from_name("recover-whatsapp") here the
    # moment that secret exists (commit f67ab77 did; reverted because
    # a missing secret blocks every deploy). Then redeploy + verify.
    secrets=[modal.Secret.from_name("recover-secrets")],
    volumes={"/root/recover/uploads": vol},
    env={"DEMO_LOCK": "1"},
    min_containers=1,
    max_containers=1,
    timeout=900,
)
@modal.concurrent(max_inputs=50)
@modal.asgi_app()
def web():
    import sys
    sys.path.insert(0, "/root/recover")
    from app.main import app as fastapi_app
    return DemoLockMiddleware(VolumeSyncMiddleware(fastapi_app, vol))
