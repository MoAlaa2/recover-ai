"""ReCover FastAPI application."""
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.chat import router

app = FastAPI(title="ReCover consultant API")
app.include_router(router)
app.mount("/data/catalog", StaticFiles(
    directory=os.path.join(os.path.dirname(__file__), "..", "data", "catalog"),
    check_dir=False), name="catalog")
app.mount("/uploads", StaticFiles(
    directory=os.path.join(os.path.dirname(__file__), "..", "uploads"),
    check_dir=False), name="uploads")
app.mount("/", StaticFiles(
    directory=os.path.join(os.path.dirname(__file__), "static"),
    html=True), name="static")
