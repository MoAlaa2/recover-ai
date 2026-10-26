"""ReCover FastAPI application."""
from fastapi import FastAPI

from app.api.chat import router

app = FastAPI(title="ReCover consultant API")
app.include_router(router)
