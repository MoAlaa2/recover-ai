"""ReCover FastAPI application."""
import os
import time

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.api.chat import public_router, router
from app.api.whatsapp import router as whatsapp_router

app = FastAPI(title="ReCover consultant API")
app.include_router(router)
from app.api.designer import router as designer_router  # noqa: E402
app.include_router(designer_router)
app.include_router(public_router)
app.include_router(whatsapp_router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")



def _build_version():
    """Commit hash of the running code, so asset URLs change exactly
    when the code does. RC_BUILD is set by the Modal deploy (the image
    has no .git); local runs read git; anything else falls back to
    the process start time."""
    env = os.environ.get("RC_BUILD", "").strip()
    if env:
        return env
    try:
        import subprocess
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True,
            text=True, timeout=5,
            cwd=os.path.dirname(os.path.dirname(__file__)))
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:  # noqa: BLE001 - no git, no problem
        pass
    return str(int(time.time()))


# Static asset URLs carry the build version as a query string, so a
# phone never runs a stale cached bundle, while the HTML shell itself
# is never cached.
VERSION = _build_version()

VERSIONED_ASSETS = ("common.js", "app.js", "landing.js", "switcher.js",
                    "strings.js", "designer.js", "styles.css",
                    "landing.css", "switcher.css", "designer.css",
                    "brand/brand.css")

# A week, immutable: versioned assets change URL when they change.
ASSET_CACHE = "public, max-age=604800, immutable"
# Sample rooms, their masks and catalog swatches keep their URLs when
# they are regenerated, so they revalidate (ETag) instead of pinning a
# stale file in the browser for a week.
DATA_CACHE = "public, max-age=300, must-revalidate"
ASSET_EXTS = (".js", ".css", ".svg", ".jpg", ".jpeg", ".png", ".webp",
              ".json", ".woff", ".woff2", ".ico")
# Uploads, share links and APIs are never cached by this rule.
NO_ASSET_CACHE_PREFIXES = ("/api/", "/uploads/", "/share/", "/webhook/")


def current_version():
    """The deploy serves one hash per build. A local server has edits
    the hash does not know about, so it adds the newest asset mtime:
    an immutable week-long cache must never hide an unsaved change."""
    if os.environ.get("RC_BUILD", "").strip():
        return VERSION
    latest = 0
    for asset in VERSIONED_ASSETS:
        try:
            latest = max(latest, os.stat(
                os.path.join(STATIC_DIR, asset)).st_mtime)
        except OSError:
            pass
    return "%s-%x" % (VERSION, int(latest))


def _versioned_html(name):
    with open(os.path.join(STATIC_DIR, name), encoding="utf-8") as f:
        html = f.read()
    version = current_version()
    for asset in VERSIONED_ASSETS:
        html = html.replace('"/%s"' % asset,
                            '"/%s?v=%s"' % (asset, version))
    return html


def _page(name):
    return Response(_versioned_html(name), media_type="text/html",
                    headers={"Cache-Control": "no-store"})


@app.get("/", include_in_schema=False)
def landing():
    return _page("landing.html")


@app.get("/consult", include_in_schema=False)
def consult():
    return _page("index.html")


@app.get("/designer", include_in_schema=False)
def designer_page():
    return _page("designer.html")
def _is_public_upload_path(path):
    """Allow-list for the served /uploads mount.

    Only swap outputs and web-upload room photos are fetchable.
    Session histories, logs, caches and transient uploads 404 even
    if present on disk (defense in depth with the private/ move).
    """
    from app.services.share import is_public_upload
    if not path.startswith("/uploads/"):
        return True
    return is_public_upload(path[len("/uploads/"):].split("?")[0])


@app.middleware("http")
async def uploads_allowlist(request, call_next):
    if not _is_public_upload_path(request.url.path):
        return Response("not found", status_code=404)
    return await call_next(request)


def _is_cacheable_asset(path):
    if path.startswith(NO_ASSET_CACHE_PREFIXES):
        return False
    return path.lower().endswith(ASSET_EXTS)


@app.middleware("http")
async def asset_cache_headers(request, call_next):
    response = await call_next(request)
    if (request.method in ("GET", "HEAD") and response.status_code == 200
            and _is_cacheable_asset(request.url.path)
            and "cache-control" not in response.headers):
        response.headers["Cache-Control"] = (
            DATA_CACHE if request.url.path.startswith("/data/")
            else ASSET_CACHE)
    return response


app.mount("/data/catalog", StaticFiles(
    directory=os.path.join(os.path.dirname(__file__), "..", "data", "catalog"),
    check_dir=False), name="catalog")
app.mount("/uploads", StaticFiles(
    directory=os.path.join(os.path.dirname(__file__), "..", "uploads"),
    check_dir=False), name="uploads")
app.mount("/data/samples", StaticFiles(
    directory=os.path.join(os.path.dirname(__file__), "..", "data", "samples"),
    check_dir=False), name="samples")
app.mount("/", StaticFiles(
    directory=os.path.join(os.path.dirname(__file__), "static"),
    html=True), name="static")
