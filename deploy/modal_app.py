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


def _build_hash():
    """Short commit hash at deploy time, baked into the asset URLs."""
    try:
        import subprocess
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5,
                             cwd=os.path.dirname(os.path.dirname(
                                 os.path.abspath(__file__))))
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:  # noqa: BLE001 - fall back to a timestamp
        pass
    import time
    return str(int(time.time()))


BUILD = _build_hash()

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
                      "/api/designer", "/webhook/whatsapp")

    def __init__(self, inner, volume, upload_dir=None, sync_tries=12,
                 sync_sleep=1.0):
        self.inner = inner
        self.volume = volume
        self.upload_dir = upload_dir
        self.sync_tries = sync_tries
        self.sync_sleep = sync_sleep
        self._sync_lock = None

    def _disk_path(self, path):
        """Map a file-serving GET path to its on-disk file, or None."""
        if self.upload_dir and path.startswith("/uploads/"):
            rel = path[len("/uploads/"):].split("?")[0].split("#")[0]
            if not rel or rel.startswith(".") or ".." in rel.split("/"):
                return None
            return os.path.join(self.upload_dir, rel)
        if path.startswith("/share/"):
            try:
                from app.services import share as share_mod
            except Exception:  # noqa: BLE001 - fail open to the 404
                return None
            token = path[len("/share/"):].split("?")[0].split("#")[0]
            try:
                rel = share_mod.verify_token(token)
            except Exception:  # noqa: BLE001 - bad key/env, fast 404
                return None
            if not rel:
                return None
            return os.path.join(self.upload_dir, rel) \
                if self.upload_dir else None
        return None

    IMAGE_BODY_PATHS = ("/api/chat", "/api/chat/stream", "/api/swap",
                        "/api/swap/stream", "/api/swap/multi",
                        "/api/swap/multi/stream", "/api/designer/pieces",
                        "/api/designer/render/stream")

    def _image_disk_path(self, body):
        """Disk path of the uploads/ image a JSON body refers to."""
        if not self.upload_dir:
            return None
        try:
            import json
            data = json.loads(body.decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001 - the app validates the body
            return None
        raw = (data or {}).get("image_path") if isinstance(data, dict) \
            else None
        if not isinstance(raw, str) or not raw.startswith("uploads/"):
            return None
        rel = raw[len("uploads/"):]
        if not rel or rel.startswith(".") or ".." in rel.split("/"):
            return None
        return os.path.join(self.upload_dir, rel)

    async def _ensure_visible(self, disk_path):
        """Wait until a just-written file is servable.

        Volume commit/flush is eventually consistent: a burst of GETs
        the millisecond after an upload 404s (measured 9/10 on one
        probe, and 2/10 still missed with a 4s budget). The happy
        path costs one stat call; only a missing file reloads and
        waits. Concurrent waiters serialize on a lock so a burst
        issues one reload chain, not N overlapping ones.
        """
        import asyncio
        if disk_path and os.path.exists(disk_path):
            return
        if self._sync_lock is None:
            self._sync_lock = asyncio.Lock()
        async with self._sync_lock:
            for _ in range(self.sync_tries):
                if disk_path and os.path.exists(disk_path):
                    return
                await asyncio.to_thread(self.volume.reload)
                await asyncio.sleep(self.sync_sleep)

    @staticmethod
    def reads_volume(path, method):
        """True when this request reads files other requests wrote."""
        if method == "GET":
            # Previews and session state are in-memory; only uploads
            # and freshly written target masks touch the volume.
            return path.startswith("/uploads/") or (
                path.startswith("/api/session/")
                and path.endswith("/targets"))
        if method == "POST" and path == "/api/proposal/pdf":
            # The proposal pastes uploads (photo, swap, plan, render)
            # that other requests wrote.
            return True
        if method == "POST" and path.startswith("/webhook/"):
            # WhatsApp sessions and media live on the volume.
            return True
        return method == "POST" and (
            path in ("/api/chat", "/api/chat/stream")
            or path.startswith("/api/swap"))

    def writes_volume(self, path, method):
        if method in ("POST", "PUT", "DELETE") and any(
                path == p or path.startswith(p)
                for p in self.WRITE_PREFIXES):
            return True
        # GET /api/session/{id}/targets also persists mask files.
        return (method == "GET" and path.startswith("/api/session/")
                and path.endswith("/targets"))

    @staticmethod
    def _replay(body, receive):
        """A receive() that hands the drained body to the app ONCE,
        then defers to the real channel.

        Starlette's StreamingResponse keeps calling receive() while it
        streams, waiting for http.disconnect; a replay that returned
        the same http.request forever made the base middleware raise
        "Unexpected message received: http.request" mid-stream, so
        every chat/swap stream on the demo died after the first bytes.
        """
        played = []

        async def replay():
            if not played:
                played.append(True)
                return {"type": "http.request", "body": body,
                        "more_body": False}
            return await receive()

        return replay

    async def __call__(self, scope, receive, send):
        import asyncio
        if scope.get("type") != "http":
            await self.inner(scope, receive, send)
            return
        path = scope.get("path", "")
        method = scope.get("method", "")
        if self.reads_volume(path, method):
            await asyncio.to_thread(self.volume.reload)
        if method == "POST" and path in self.IMAGE_BODY_PATHS:
            # A chat / swap right after an upload references a file
            # this container committed a moment ago; the committed view
            # can lag, and the turn then fails with "image not found"
            # (measured: a 52-85 ms chat stream right after a phone
            # upload). Wait the referenced upload into visibility.
            body = b""
            while True:
                message = await receive()
                if message.get("type") != "http.request":
                    break
                body += message.get("body", b"")
                if not message.get("more_body"):
                    break
            disk = self._image_disk_path(body)
            if disk is not None:
                await self._ensure_visible(disk)

            receive = self._replay(body, receive)
        if method == "POST" and path == "/api/share":
            # Minting a link stats a file another request just wrote
            # (multi composite): wait it into visibility first, or the
            # endpoint 404s and the summary ships a link-less wa.me.
            body = b""
            while True:
                message = await receive()
                if message.get("type") != "http.request":
                    break
                body += message.get("body", b"")
                if not message.get("more_body"):
                    break
            disk = None
            try:
                import json
                from app.services import share as share_mod
                data = json.loads(body.decode("utf-8") or "{}")
                disk = share_mod.disk_path_for(
                    (data or {}).get("result_url", ""),
                    self.upload_dir or None)
            except Exception:  # noqa: BLE001 - fail open to the 404
                disk = None
            if disk is not None:
                await self._ensure_visible(disk)

            await self.inner(scope, self._replay(body, receive), send)
            return
        if method == "GET":
            disk = self._disk_path(path)
            if disk is not None:
                await self._ensure_visible(disk)
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
    secrets=[modal.Secret.from_name("recover-secrets"),
             modal.Secret.from_name("recover-baseten"),
             modal.Secret.from_name("recover-whatsapp")],
    volumes={"/root/recover/uploads": vol},
    env={"DEMO_LOCK": "1", "SPARK_OPEN_FALLBACK": "1", "RC_BUILD": BUILD},
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
    return DemoLockMiddleware(VolumeSyncMiddleware(
        fastapi_app, vol, upload_dir="/root/recover/uploads"))
