"""ReCover FastAPI application."""
import os
import time

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.api.chat import router

app = FastAPI(title="ReCover consultant API")
app.include_router(router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Bumped once per process start (= per deploy): static asset URLs carry
# it as a query string so phones never run a stale cached bundle, while
# the HTML shell itself is never cached.
VERSION = str(int(time.time()))

VERSIONED_ASSETS = ("app.js", "landing.js", "switcher.js", "strings.js",
                    "styles.css", "landing.css", "switcher.css",
                    "brand/brand.css")


def _versioned_html(name):
    with open(os.path.join(STATIC_DIR, name), encoding="utf-8") as f:
        html = f.read()
    for asset in VERSIONED_ASSETS:
        html = html.replace('"/%s"' % asset,
                            '"/%s?v=%s"' % (asset, VERSION))
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
