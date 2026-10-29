"""Public one-file share links for swap results.

GET /share/<token>[.jpg] serves a single result image with no login,
so an upholsterer can open the preview from a forwarded message.
Tokens are HMAC-SHA256 keyed by the server API key (never leaves the
server; rotation invalidates outstanding links), carry an expiry
(14 days), and are unguessable. No listing, noindex.
"""
import base64
import hashlib
import hmac
import os
import time

from app.core.config import UPLOAD_DIR, require_api_key

SHARE_TTL_S = 14 * 24 * 3600
SHAREABLE_EXTS = (".jpg", ".jpeg", ".png")

# Only swap outputs and web-upload room photos are public. Session
# histories, logs, caches and raw/transient uploads never mint links.
_PUBLIC_UPLOAD_RE = None


def _public_re():
    import re as _re
    global _PUBLIC_UPLOAD_RE
    if _PUBLIC_UPLOAD_RE is None:
        _PUBLIC_UPLOAD_RE = _re.compile(
            r"^(?:swap/[^/\s]+|masks/[^/\s]+|[0-9a-f]{32}\.jpg|"
            r"wa-[0-9a-f]{12}\.jpg)$")
    return _PUBLIC_UPLOAD_RE


def is_public_upload(rel):
    """Uploads-relative path allowed to be served or shared, else False."""
    return bool(_public_re().match(rel or ""))


def _key():
    return require_api_key().encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def disk_path_for(result_url, base=None):
    """Map a result URL to its on-disk path, or None when unsafe.

    No existence check: the volume middleware uses this to wait a fresh
    file into visibility BEFORE the share endpoint stats it. `base`
    defaults to the app uploads dir; the middleware passes its own
    volume mount (same path in prod, different in tests).
    """
    base = os.path.normpath(base or UPLOAD_DIR)
    rel = (result_url or "").lstrip("/")
    if rel.startswith("uploads/"):
        rel = rel[len("uploads/"):]
    if os.path.splitext(rel)[1].lower() not in SHAREABLE_EXTS:
        return None
    if not rel or rel.startswith(".") or ".." in rel.split("/"):
        return None
    abs_path = os.path.normpath(os.path.join(base, rel))
    if os.path.commonpath([abs_path, base]) != base:
        return None
    return abs_path


def resolve_result(result_url):
    """Result path under the uploads dir, or None (incl. traversal)."""
    abs_path = disk_path_for(result_url)
    if abs_path is None or not os.path.isfile(abs_path):
        return None
    return abs_path


def create_token(result_rel, ttl_s=SHARE_TTL_S):
    """Mint a share token for uploads/<result_rel>. Returns (token, exp).

    The whole body is base64url so the token never contains slashes
    and always fits one path segment.
    """
    exp = int(time.time() + ttl_s)
    body = "%s.%d" % (result_rel, exp)
    mac = hmac.new(_key(), body.encode("utf-8"),
                   hashlib.sha256).digest()
    return "%s.%s" % (_b64(body.encode("utf-8")), _b64(mac)), exp


def verify_token(token):
    """Valid token -> result rel path under uploads. Else None."""
    try:
        text = (token or "")
        if text.endswith(".jpg"):
            text = text[:-4]
        body_b64, _, mac_b64 = text.rpartition(".")
        if not body_b64 or not mac_b64:
            return None
        body = _unb64(body_b64).decode("utf-8")
        rel, _, exp_s = body.rpartition(".")
        exp = int(exp_s or "x")
        if not rel or exp < time.time():
            return None
        want = hmac.new(_key(), body.encode("utf-8"),
                        hashlib.sha256).digest()
        if not hmac.compare_digest(want, _unb64(mac_b64)):
            return None
        if resolve_result(rel) is None:
            return None
        return rel
    except (ValueError, TypeError):
        return None
