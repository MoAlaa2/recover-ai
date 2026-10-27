"""Chat and upload endpoints for the ReCover consultant."""
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid

from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import BASE_DIR, UPLOAD_DIR
from app.services import consultant
from app.services.swap import SwapError, swap
from app.services.voice import AUDIO_EXT, VoiceError, transcribe

PIECE_TARGET = {"sofa": "sofa", "armchair": "armchair", "chair": "armchair",
                "curtains": "curtains", "cushions": "cushions"}
TOPIC_TARGET = {"upholstery": "sofa", "curtains": "curtains",
                "cushions": "cushions"}

router = APIRouter(prefix="/api")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = ""
    image_path: Optional[str] = None
    lang: Optional[str] = None


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


class SwapRequest(BaseModel):
    session_id: str = ""
    image_path: str
    fabric_code: str
    target: str = ""


@router.post("/swap")
def swap_fabric(req: SwapRequest):
    target = _swap_target(req)
    try:
        res = swap(req.image_path, req.fabric_code, target)
    except SwapError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    record_preview(req.session_id, req.fabric_code, res,
                         req.image_path or "")
    return res


def _swap_target(req: SwapRequest):
    target = (req.target or "").lower()
    if target not in ("sofa", "armchair", "curtains", "cushions"):
        session = consultant.SESSIONS.get(req.session_id, {})
        piece = session.get("detected_piece")
        topic = session.get("topic")
        target = (PIECE_TARGET.get(piece or "")
                  or TOPIC_TARGET.get(topic or "") or "sofa")
    return target


# Swap previews, kept per session so a refresh never loses results.
PREVIEWS = {}
MAX_PREVIEWS = 20


def record_preview(session_id, fabric_code, res, before_url=""):
    """Store one finished swap for the session. Returns the entry."""
    entry = {"fabric_code": fabric_code,
             "result_url": res.get("result_url", ""),
             "mask_url": res.get("mask_url", ""),
             "before_url": before_url or "",
             "scores": res.get("scores", {}),
             "attempts": res.get("attempts", 1),
             "created_at": time.time()}
    if session_id:
        PREVIEWS.setdefault(session_id, []).append(entry)
        del PREVIEWS[session_id][:-MAX_PREVIEWS]
    return entry


def get_previews(session_id):
    """All stored swap previews for one session, oldest first."""
    return list(PREVIEWS.get(session_id or "", []))


@router.get("/session/{session_id}/previews")
def session_previews(session_id: str):
    return {"previews": get_previews(session_id)}


@router.post("/swap/stream")
def swap_stream(req: SwapRequest):
    """Same as /api/swap but streams backend progress as SSE.

    Events: {"type": "step", "label": ...} as each stage starts, then
    {"type": "done", "result": {...}} with the full /api/swap payload,
    or {"type": "error", ...} on failure.
    """
    target = _swap_target(req)
    events = queue.Queue()

    def run():
        try:
            res = swap(req.image_path, req.fabric_code, target,
                       on_step=lambda s: events.put({"type": "step",
                                                    "label": s}))
            record_preview(req.session_id, req.fabric_code, res,
                         req.image_path or "")
            events.put({"type": "done", "result": res})
        except SwapError as exc:
            events.put({"type": "error", "message": str(exc)})
        except RuntimeError as exc:
            events.put({"type": "error", "message": str(exc)})
        except Exception:  # noqa: BLE001 - never hang the stream
            events.put({"type": "error", "message": "swap failed"})

    threading.Thread(target=run, daemon=True).start()

    def gen():
        while True:
            evt = events.get()
            yield "data: %s\n\n" % json.dumps(evt, ensure_ascii=False)
            if evt["type"] in ("done", "error"):
                break

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/chat")
def chat(req: ChatRequest):
    if req.image_path:
        path = req.image_path if os.path.isabs(req.image_path) else \
            os.path.join(BASE_DIR, req.image_path)
        if not os.path.exists(path):
            raise HTTPException(400, "image not found")
    try:
        return consultant.chat(req.session_id, req.message,
                               req.image_path, lang=req.lang)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))


@router.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Same as /api/chat but streams reply tokens as SSE.

    Events: {"type": "token", "text": ...} as text arrives,
    {"type": "step", "label": ...} for progress, then a final
    {"type": "done", "result": {...}} with the full /api/chat payload,
    or {"type": "error", ...} on failure.
    """
    if req.image_path:
        path = req.image_path if os.path.isabs(req.image_path) else \
            os.path.join(BASE_DIR, req.image_path)
        if not os.path.exists(path):
            raise HTTPException(400, "image not found")
    events = queue.Queue()

    def run():
        try:
            res = consultant.chat(
                req.session_id, req.message, req.image_path,
                on_token=lambda t: events.put({"type": "token",
                                                "text": t}),
                on_step=lambda s: events.put({"type": "step",
                                               "label": s}),
                lang=req.lang)
            events.put({"type": "done", "result": res})
        except FileNotFoundError as exc:
            events.put({"type": "error", "message": str(exc)})
        except RuntimeError as exc:
            events.put({"type": "error", "message": str(exc)})
        except Exception:  # noqa: BLE001 - never hang the stream
            events.put({"type": "error", "message": "chat failed"})

    threading.Thread(target=run, daemon=True).start()

    def gen():
        while True:
            evt = events.get()
            yield "data: %s\n\n" % json.dumps(evt, ensure_ascii=False)
            if evt["type"] in ("done", "error"):
                break

    return StreamingResponse(gen(), media_type="text/event-stream")
