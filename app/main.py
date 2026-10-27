"""ReCover FastAPI application."""
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router

app = FastAPI(title="ReCover consultant API")
app.include_router(router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.get("/", include_in_schema=False)
def landing():
    return FileResponse(os.path.join(STATIC_DIR, "landing.html"))


@app.get("/consult", include_in_schema=False)
def consult():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
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
