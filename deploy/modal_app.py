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


class DemoLockMiddleware:
    """HTTP Basic Auth on every route when DEMO_LOCK=1.

    Uses constant-time comparison and adds
    X-Robots-Tag: noindex, nofollow to every response while locked.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("type") not in ("http", "websocket"):
            await self.inner(scope, receive, send)
            return
        if os.environ.get("DEMO_LOCK", "") != "1":
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
    secrets=[modal.Secret.from_name("recover-secrets")],
    volumes={"/root/recover/uploads": vol},
    env={"DEMO_LOCK": "1"},
    min_containers=1,
    timeout=900,
)
@modal.asgi_app()
def web():
    import sys
    sys.path.insert(0, "/root/recover")
    from app.main import app as fastapi_app
    return DemoLockMiddleware(fastapi_app)
