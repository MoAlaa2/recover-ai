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

from app.core.config import BASE_DIR, SPARK_MODEL, UPLOAD_DIR
from app.services import consultant
from app.services import targets as targets_mod
from app.services.swap import EDIT_MODEL, SAM_MODEL, SwapError, swap
from app.services.voice import AUDIO_EXT, VoiceError, transcribe

# Which model powers each streamed step label. Chat tool steps run on
# the Spark agent; swap stages name their own model; local-only work
# (composite) carries no model and gets no badge.
STEP_MODELS = {
    "search": SPARK_MODEL, "claw": SPARK_MODEL, "details": SPARK_MODEL,
    "room": SPARK_MODEL, "photo": SPARK_MODEL,
    "segment": SAM_MODEL, "edit": EDIT_MODEL, "composite": None,
    "verify": SPARK_MODEL, "retry": SPARK_MODEL,
}


def step_event(label):
    """One SSE step event, with the powering model when it has one."""
    evt = {"type": "step", "label": label}
    model = STEP_MODELS.get(label)
    if model:
        evt["model"] = model
    return evt

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


def _open_photo(src):
    """Open any accepted upload, EXIF-transposed, flattened to RGB."""
    from PIL import Image, ImageOps
    try:
        import pillow_heif  # noqa: F401 - registers HEIF opener
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    im = Image.open(src)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA") or (im.mode == "P"
                                     and "transparency" in im.info):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im.convert("RGB"), mask=im.convert("RGBA").split()[3])
        im = bg
    else:
        im = im.convert("RGB")
    return im


def convert_to_jpg(src, dest):
    """Convert an uploaded image to JPEG. Returns True on success."""
    try:
        _open_photo(src).save(dest, "JPEG", quality=90)
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


class AssignmentItem(BaseModel):
    target: str = ""
    code: str = ""


class SwapMultiRequest(BaseModel):
    session_id: str = ""
    image_path: str
    assignments: list = []


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


def _wait_for_image(path, tries=4):
    """Tolerate a just-written file that is not visible yet.

    Upload/swap/mask files can lag one volume sync behind the request
    that references them (fresh container, commit in flight). The
    happy path costs nothing; only a missing file waits, 1s at a
    time, then the caller 400s as before.
    """
    import time as _time
    for _ in range(tries):
        if os.path.exists(path):
            return True
        _time.sleep(1)
    return os.path.exists(path)


IMAGE_MAX_BYTES = 20 * 1024 * 1024
SAMPLES_DIR = os.path.join(BASE_DIR, "data", "samples")


def resolve_client_image(image_path):
    """Allow-listed, size-capped resolution of a client image_path.

    Real path must sit under the uploads dir or the samples dir, and
    the file must exist within the size cap. Absolute paths, `..`
    escapes and special files (/dev/zero would OOM a naive reader)
    all fail closed with the same generic 400. Nothing is read here.
    """
    raw = (image_path or "").strip()
    if not raw:
        raise HTTPException(400, "image not found")
    joined = raw if os.path.isabs(raw) else os.path.join(BASE_DIR, raw)
    real = os.path.realpath(joined)
    allowed = (os.path.realpath(UPLOAD_DIR), os.path.realpath(SAMPLES_DIR))
    if not any(real == base or real.startswith(base + os.sep)
               for base in allowed):
        raise HTTPException(400, "image not found")
    if not _wait_for_image(real):
        raise HTTPException(400, "image not found")
    try:
        if os.path.getsize(real) > IMAGE_MAX_BYTES:
            raise HTTPException(400, "image not found")
    except OSError:
        raise HTTPException(400, "image not found")
    return real


def _check_image(image_path):
    return resolve_client_image(image_path)


def _check_assignments(raw):
    from app.services.catalog import get_fabric
    from app.services.swap import TARGET_CONCEPTS
    cleaned = []
    for item in raw or []:
        target = ((item.get("target") if isinstance(item, dict)
                   else getattr(item, "target", "")) or "").lower()
        code = ((item.get("code") if isinstance(item, dict)
                 else getattr(item, "code", "")) or "")
        if target not in TARGET_CONCEPTS:
            raise HTTPException(400, "unknown target: %s" % target)
        if not get_fabric(code):
            raise HTTPException(400, "unknown fabric code: %s" % code)
        cleaned.append({"target": target, "code": code})
    if not cleaned:
        raise HTTPException(400, "no assignments")
    return cleaned


@router.post("/swap/multi")
def swap_multi_fabrics(req: SwapMultiRequest):
    from app.services.swap import SwapError as _SwapError
    from app.services.swap import swap_multi
    _check_image(req.image_path)
    cleaned = _check_assignments(req.assignments)
    try:
        res = swap_multi(req.image_path, cleaned)
    except _SwapError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    before = req.image_path or ""
    for item in res.get("results", []):
        record_preview(req.session_id, item["code"], item, before)
        before = item.get("result_url", before)
    session = consultant.SESSIONS.setdefault(req.session_id,
                                             {"messages": []})
    session.setdefault("assignments", {}).update(
        {i["target"]: i["code"] for i in cleaned})
    return res


@router.post("/swap/multi/stream")
def swap_multi_stream(req: SwapMultiRequest):
    """Same as /api/swap/multi but streams backend progress as SSE."""
    from app.services.swap import SwapError as _SwapError
    from app.services.swap import TimeoutSwapError as _TimeoutSwapError
    from app.services.swap import swap_multi
    try:
        _check_image(req.image_path)
        cleaned = _check_assignments(req.assignments)
    except HTTPException as exc:
        def err_gen():
            yield "data: %s\n\n" % json.dumps(
                {"type": "error", "message": exc.detail},
                ensure_ascii=False)
        return StreamingResponse(err_gen(),
                                 media_type="text/event-stream")
    events = queue.Queue()

    def run():
        try:
            res = swap_multi(
                req.image_path, cleaned,
                on_step=lambda s: events.put(step_event(s)))
            before = req.image_path or ""
            for item in res.get("results", []):
                record_preview(req.session_id, item["code"], item,
                               before)
                before = item.get("result_url", before)
            session = consultant.SESSIONS.setdefault(
                req.session_id, {"messages": []})
            session.setdefault("assignments", {}).update(
                {i["target"]: i["code"] for i in cleaned})
            events.put({"type": "done", "result": res})
        except _SwapError as exc:
            events.put({"type": "error", "message": str(exc),
                        "timeout": isinstance(exc, _TimeoutSwapError)})
        except RuntimeError as exc:
            events.put({"type": "error", "message": str(exc),
                        "timeout": False})
        except Exception:  # noqa: BLE001 - never hang the stream
            events.put({"type": "error",
                        "message": "multi-swap failed",
                        "timeout": False})

    threading.Thread(target=run, daemon=True).start()

    def gen():
        while True:
            try:
                evt = events.get(timeout=15)
            except queue.Empty:
                # Heartbeat so proxies and the client stall timer see a
                # live stream while a slow model call is in flight.
                yield ": ping\n\n"
                continue
            yield "data: %s\n\n" % json.dumps(evt, ensure_ascii=False)
            if evt["type"] in ("done", "error"):
                break

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/fabrics")
def fabric_list(suitable_for: str = "", usage: str = "",
                limit: int = 12):
    """Browse fabrics, filtered for one item type (Browse-myself panel).

    suitable_for is one of sofa/cushions/curtains; usage is
    upholstery/curtains. Ranked by the same catalog search.
    """
    from app.services import catalog as catalog_mod
    flt = ([suitable_for] if suitable_for in ("sofa", "cushions",
                                              "curtains") else None)
    norm_usage = catalog_mod.normalize_usage(usage) if usage else None
    fabrics, _ = catalog_mod.search_catalog(
        usage=norm_usage, suitable_for=flt,
        limit=max(1, min(limit, 40)))
    return {"fabrics": fabrics, "suitable_for": suitable_for or "",
            "usage": norm_usage or ""}


@router.post("/session/{session_id}/assignments")
def set_assignment(session_id: str, item: AssignmentItem):
    """Pin one fabric to one item (Browse panel / outline tap)."""
    cleaned = _check_assignments([item])[0]
    session = consultant.SESSIONS.setdefault(session_id,
                                             {"messages": []})
    session.setdefault("assignments", {})[cleaned["target"]] = \
        cleaned["code"]
    chosen = session.setdefault("chosen_targets", [])
    if cleaned["target"] not in chosen:
        chosen.append(cleaned["target"])
    return {"assignments": session["assignments"]}


@router.delete("/session/{session_id}/assignments")
def clear_assignments(session_id: str):
    """Reset all item→fabric picks (Reset button)."""
    session = consultant.SESSIONS.setdefault(session_id,
                                             {"messages": []})
    session["assignments"] = {}
    return {"assignments": {}}


class ShareRequest(BaseModel):
    result_url: str = ""


@router.post("/share")
def create_share(req: ShareRequest):
    """Mint a public 14-day link for one swap result image."""
    from app.services import share as share_mod
    try:
        rel = share_mod.resolve_result(req.result_url)
    except RuntimeError:
        raise HTTPException(500, "share unavailable")
    if rel is None:
        raise HTTPException(404, "result not found")
    base = os.path.relpath(rel, UPLOAD_DIR)
    # Only swap outputs and web-upload room photos mint links: never
    # session histories, logs, caches or transient uploads.
    if not share_mod.is_public_upload(base):
        raise HTTPException(404, "result not found")
    try:
        token, exp = share_mod.create_token(base)
    except RuntimeError:
        raise HTTPException(500, "share unavailable")
    return {"token": token,
            "share_path": "/share/" + token + ".jpg",
            "expires_at": exp}


public_router = APIRouter()


@public_router.get("/share/{token}")
def serve_share(token: str):
    """One public result image. No listing, noindex, 14-day expiry."""
    from fastapi.responses import FileResponse
    from app.services import share as share_mod
    rel = share_mod.verify_token(token)
    if rel is None or not share_mod.is_public_upload(rel):
        raise HTTPException(404, "link invalid or expired")
    path = os.path.join(UPLOAD_DIR, rel)
    if not os.path.isfile(path):
        raise HTTPException(404, "result not found")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"X-Robots-Tag": "noindex, nofollow",
                                 "Cache-Control":
                                 "public, max-age=1209600"})


@router.get("/session/{session_id}/quote")
def session_quote(session_id: str):
    """Meterage + price for the session's assignments (LOOP 4)."""
    from app.services import catalog as catalog_mod
    from app.services import meterage as meterage_mod
    session = consultant.SESSIONS.get(session_id, {})
    assignments = session.get("assignments", {})
    fabrics = {}
    for code in set(assignments.values()):
        item = catalog_mod.get_fabric(code)
        if item:
            fabrics[code] = item
    res = meterage_mod.quote(assignments, fabrics,
                             session.get("curtain_dims"),
                             session.get("pillow_counts", {}))
    res["preliminary"] = True
    from app.services import impact as impact_mod
    co2, waste = impact_mod.avoided(assignments)
    res["co2"] = {"kg": co2, "waste_kg": waste,
                  "source": impact_mod.CO2_SOURCE}
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


@router.get("/session/{session_id}/targets")
def session_targets(session_id: str, image_path: str = ""):
    """Changeable items (sofa/cushions/curtains) in a room photo.

    Caches per session so the canvas can re-render without resegmenting.
    """
    session = consultant.SESSIONS.setdefault(session_id, {"messages": []})
    cached = session.get("targets")
    if cached and (not image_path
                   or cached.get("image_path") == image_path):
        return cached
    if not image_path:
        raise HTTPException(400, "image_path is required")
    resolve_client_image(image_path)
    try:
        items = targets_mod.detect_targets(image_path)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    entry = {"image_path": image_path, "targets": items}
    session["targets"] = entry
    return entry


@router.get("/fabric/{code}")
def fabric_spec(code: str):
    """One fabric's catalog spec, for landing captions and cards."""
    from app.services.catalog import get_fabric
    item = get_fabric((code or "").upper())
    if not item:
        raise HTTPException(404, "unknown fabric code")
    return item


@router.get("/landing-meta")
def landing_meta():
    """Live numbers for the landing metrics strip (never hardcoded)."""
    from app.services import catalog as catalog_mod
    total = passed = 0
    try:
        with open("data/eval_report.json", encoding="utf-8") as f:
            report = json.load(f)
        for sc in report.get("scenarios", []):
            total += 1
            if sc.get("pass"):
                passed += 1
    except (OSError, ValueError):
        pass
    return {"fabrics": len(catalog_mod.load_specs()),
            "eval_pass": passed, "eval_total": total,
            "languages": 5, "swap_min_score": 7}


@router.post("/swap/stream")
def swap_stream(req: SwapRequest):
    """Same as /api/swap but streams backend progress as SSE.

    Events: {"type": "step", "label": ..., "model": ...} per stage, then
    {"type": "done", "result": {...}} with the full /api/swap payload,
    or {"type": "error", ...} on failure.
    """
    target = _swap_target(req)
    events = queue.Queue()
    from app.services.swap import TimeoutSwapError as _TimeoutSwapError

    def run():
        try:
            res = swap(req.image_path, req.fabric_code, target,
                       on_step=lambda s: events.put(step_event(s)))
            # The result bubble shows name + price even when the swap was
            # triggered outside the recommendation list (browse panel,
            # multi-apply): the client only knows the code there.
            try:
                from app.services import catalog as catalog_mod
                fab = catalog_mod.get_fabric(req.fabric_code) or {}
                res["fabric"] = {
                    "code": req.fabric_code,
                    "name_en": fab.get("name_en", ""),
                    "name_ar": fab.get("name_ar", ""),
                    "price_sar_per_m": fab.get("price_sar_per_m"),
                    "image": fab.get("image", "")}
            except Exception:  # noqa: BLE001 - meta is best-effort
                pass
            record_preview(req.session_id, req.fabric_code, res,
                         req.image_path or "")
            events.put({"type": "done", "result": res})
        except SwapError as exc:
            events.put({"type": "error", "message": str(exc),
                        "timeout": isinstance(exc, _TimeoutSwapError)})
        except RuntimeError as exc:
            events.put({"type": "error", "message": str(exc),
                        "timeout": False})
        except Exception:  # noqa: BLE001 - never hang the stream
            events.put({"type": "error", "message": "swap failed",
                        "timeout": False})

    threading.Thread(target=run, daemon=True).start()

    def gen():
        while True:
            try:
                evt = events.get(timeout=15)
            except queue.Empty:
                # Heartbeat so proxies and the client stall timer see a
                # live stream while a slow model call is in flight.
                yield ": ping\n\n"
                continue
            yield "data: %s\n\n" % json.dumps(evt, ensure_ascii=False)
            if evt["type"] in ("done", "error"):
                break

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/chat")
def chat(req: ChatRequest):
    if req.image_path:
        resolve_client_image(req.image_path)
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
    {"type": "step", "label": ..., "model": ...} for progress, then a final
    {"type": "done", "result": {...}} with the full /api/chat payload,
    or {"type": "error", ...} on failure.
    """
    if req.image_path:
        resolve_client_image(req.image_path)
    events = queue.Queue()

    def run():
        try:
            res = consultant.chat(
                req.session_id, req.message, req.image_path,
                on_token=lambda t: events.put({"type": "token",
                                                "text": t}),
                on_step=lambda s: events.put(step_event(s)),
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
            try:
                evt = events.get(timeout=15)
            except queue.Empty:
                # Heartbeat so proxies and the client stall timer see a
                # live stream while a slow model call is in flight.
                yield ": ping\n\n"
                continue
            yield "data: %s\n\n" % json.dumps(evt, ensure_ascii=False)
            if evt["type"] in ("done", "error"):
                break

    return StreamingResponse(gen(), media_type="text/event-stream")
