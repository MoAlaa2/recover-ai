"""Chat and upload endpoints for the ReCover consultant."""
import os
import shutil
import subprocess
import uuid

from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core.config import BASE_DIR, UPLOAD_DIR
from app.services import consultant
from app.services.voice import AUDIO_EXT, VoiceError, transcribe

router = APIRouter(prefix="/api")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = ""
    image_path: Optional[str] = None


def convert_to_jpg(src, dest):
    """Convert an uploaded image to JPEG. Returns True on success."""
    try:
        from PIL import Image
        im = Image.open(src).convert("RGB")
        im.save(dest, "JPEG", quality=90)
        return True
    except Exception:  # noqa: BLE001 - fall back to sips
        pass
    try:
        subprocess.run(["sips", "-s", "format", "jpeg", src,
                        "--out", dest],
                       check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


@router.post("/upload")
def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, "unsupported image type")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = "%s%s" % (uuid.uuid4().hex, ext)
    raw = os.path.join(UPLOAD_DIR, name)
    with open(raw, "wb") as f:
        shutil.copyfileobj(file.file, f)
    if ext in (".jpg", ".jpeg"):
        return {"image_path": os.path.join("uploads", name)}
    dest = os.path.join(UPLOAD_DIR, uuid.uuid4().hex + ".jpg")
    if not convert_to_jpg(raw, dest):
        os.remove(raw)
        raise HTTPException(400, "could not read image")
    os.remove(raw)
    return {"image_path": os.path.join(
        "uploads", os.path.basename(dest))}


@router.post("/voice")
def voice(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(400, "unsupported audio type")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    raw = os.path.join(UPLOAD_DIR, "upload-%s%s" % (uuid.uuid4().hex, ext))
    with open(raw, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        text = transcribe(raw)["text"].strip()
    except VoiceError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    finally:
        if os.path.exists(raw):
            os.remove(raw)
    if not text:
        raise HTTPException(400, "no speech detected")
    return {"text": text}


@router.post("/chat")
def chat(req: ChatRequest):
    if req.image_path:
        path = req.image_path if os.path.isabs(req.image_path) else \
            os.path.join(BASE_DIR, req.image_path)
        if not os.path.exists(path):
            raise HTTPException(400, "image not found")
    try:
        return consultant.chat(req.session_id, req.message,
                               req.image_path)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
