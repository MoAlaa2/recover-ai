"""Designer mode (plan -> render) and the client proposal PDF."""
import json
import os
import queue
import shutil
import threading
import uuid
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image
from pydantic import BaseModel

from app.api.chat import resolve_client_image, step_event
from app.core.config import BASE_DIR, UPLOAD_DIR
from app.services import designer, proposal
from app.services.catalog import get_fabric

router = APIRouter(prefix="/api")

PLAN_EXT = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
PLAN_MAX_BYTES = 25 * 1024 * 1024


@router.post("/designer/plan")
def upload_plan(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in PLAN_EXT:
        raise HTTPException(400, "unsupported plan type")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    raw = os.path.join(UPLOAD_DIR, "plan-%s%s" % (uuid.uuid4().hex, ext))
    with open(raw, "wb") as f:
        shutil.copyfileobj(file.file, f, length=PLAN_MAX_BYTES + 1)
    try:
        if os.path.getsize(raw) > PLAN_MAX_BYTES:
            raise HTTPException(400, "plan too large")
        try:
            img = designer.plan_image(raw, ext)
        except designer.DesignerError as exc:
            raise HTTPException(400, str(exc))
    finally:
        if os.path.exists(raw):
            os.remove(raw)
    path = designer.save_plan(img)
    return {"image_path": path, "width": img.width, "height": img.height}


class PiecesRequest(BaseModel):
    image_path: str


@router.post("/designer/pieces")
def list_pieces(req: PiecesRequest):
    real = resolve_client_image(req.image_path)
    plan = Image.open(real).convert("RGB")
    try:
        pieces, raw, secs = designer.list_pieces(plan)
    except designer.DesignerError as exc:
        raise HTTPException(502, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    return {"pieces": pieces, "width": plan.width, "height": plan.height,
            "seconds": round(secs, 1), "raw": raw[:400]}


class RenderRequest(BaseModel):
    image_path: str
    pieces: List[dict]


@router.post("/designer/render/stream")
def render_stream(req: RenderRequest):
    """SSE: {"type":"step"} per stage, then done/error."""
    real = resolve_client_image(req.image_path)
    plan = Image.open(real).convert("RGB")
    pieces = designer.normalize_pieces(req.pieces, plan.size)
    if not any(p.get("code") for p in pieces):
        raise HTTPException(400, "assign a fabric to at least one piece")
    events = queue.Queue()

    def run():
        try:
            res = designer.render(
                plan, pieces, on_step=lambda s: events.put(step_event(s)))
            res["quote"] = designer.quote_pieces(pieces)
            res["plan_url"] = req.image_path
            events.put({"type": "done", "result": res})
        except designer.DesignerError as exc:
            events.put({"type": "error", "message": str(exc),
                        "timeout": "timed out" in str(exc)})
        except RuntimeError as exc:
            events.put({"type": "error", "message": str(exc)})
        except Exception:  # noqa: BLE001 - never hang the stream
            events.put({"type": "error", "message": "render failed"})

    threading.Thread(target=run, daemon=True).start()

    def gen():
        while True:
            try:
                evt = events.get(timeout=15)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            yield "data: %s\n\n" % json.dumps(evt, ensure_ascii=False)
            if evt["type"] in ("done", "error"):
                break

    return StreamingResponse(gen(), media_type="text/event-stream")


class ProposalItem(BaseModel):
    label: str = ""
    code: str = ""
    meters: Optional[float] = None
    line_total: Optional[float] = None


class ProposalRequest(BaseModel):
    lang: str = "en"
    mode: str = "photo"
    prepared_by: str = ""
    before_url: Optional[str] = None
    after_url: Optional[str] = None
    items: List[ProposalItem] = []
    total: Optional[float] = None
    co2: Optional[dict] = None


def _image_or_none(url):
    if not url:
        return None
    rel = str(url).split("?")[0].lstrip("/")
    try:
        real = resolve_client_image(rel)
        return Image.open(real).convert("RGB")
    except HTTPException:
        return None
    except Exception:  # noqa: BLE001 - unreadable file: leave the slot
        return None


@router.post("/proposal/pdf")
def proposal_pdf(req: ProposalRequest):
    lang = "ar" if req.lang == "ar" else "en"
    items = []
    for it in req.items[:12]:
        fabric = get_fabric(it.code) or {}
        swatch = None
        if fabric.get("image"):
            try:
                swatch = Image.open(os.path.join(
                    BASE_DIR, fabric["image"])).convert("RGB")
            except Exception:  # noqa: BLE001 - no swatch, no thumbnail
                swatch = None
        items.append({
            "label": it.label[:60], "code": it.code[:20],
            "name": (fabric.get("name_ar") if lang == "ar"
                     else fabric.get("name_en")) or it.code,
            "material": fabric.get("material", ""),
            "price_usd_per_m": fabric.get("price_usd_per_m"),
            "meters": it.meters, "line_total": it.line_total,
            "swatch": swatch})
    data = {"mode": "plan" if req.mode == "plan" else "photo",
            "prepared_by": (req.prepared_by or "")[:80],
            "before": _image_or_none(req.before_url),
            "after": _image_or_none(req.after_url),
            "items": items, "total": req.total,
            "co2": req.co2 if isinstance(req.co2, dict) else None}
    pdf = proposal.render_proposal(data, lang)
    name = "recover-proposal-%s.pdf" % lang
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition":
                             'attachment; filename="%s"' % name,
                             "Cache-Control": "no-store"})
