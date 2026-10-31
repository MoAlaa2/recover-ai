"""Designer mode: 2D floor plan -> top-down concept render.

Pipeline (Meta models only):
  1. plan_image(): PNG/JPG/PDF-first-page -> capped RGB plan.
  2. list_pieces(): Muse Spark lists the fabric-able pieces with pixel
     boxes; parse_pieces() cleans, orders (reading order) and numbers
     them (max MAX_PIECES). The designer may delete or drag boxes;
     normalize_pieces() validates what comes back.
  3. render(): one muse-image-1.0 edit with the 2x plan, one magenta
     outline map per fabric and the swatches; the prompt carries the
     spike's fixes (orthographic, windows not skylights, floor to the
     walls, aspect ratio). fit_aspect() restores the plan's aspect.
  4. Per-piece colour check (swap_checks.colour_check on the box) with
     one corrective retry; the attempt with more passing pieces wins.
  5. quote_pieces(): meters / SAR / CO2 for the proposal.
"""
import base64
import io
import json
import os
import re
import time
import uuid

from PIL import Image, ImageDraw, ImageOps

from app.core.config import (BASE_DIR, CHAT_URL, SPARK_MODEL, UPLOAD_DIR,
                             require_api_key)
from app.services import impact, meterage, swap_checks
from app.services import swap as sw
from app.services.catalog import get_fabric

PLAN_MAX_SIDE = 2048
VISION_SIDE = 1600
MAX_PIECES = 12
MIN_BOX_FRAC = 0.01        # a box under 1% of a side is noise
DUP_IOU = 0.7              # two boxes this overlapped are one piece
ROW_TOL = 0.08             # reading order: same row within 8% height
OUTLINE_W_FRAC = 0.004
CHECK_INSET = 0.18         # colour check on the box's inner 64%
PDF_SCALE = 2.0            # 144 dpi first page
LAYOUT_MIN_SCORE = 7       # Spark layout fidelity below this retries
LAYOUT_SIDE = 800          # plan + render copies sent to the layout check
CHECK_CELLS = 3            # colour check grid per piece (L-shapes, round chairs)
CHECK_MIN_CELLS = 0.5      # share of cells that must carry the fabric

# Spark piece type -> yardage / CO2 piece key (meterage.YARDAGE).
PIECE_KEYS = {
    "sofa": "sofa-3-seat", "couch": "sofa-3-seat",
    "loveseat": "loveseat", "sectional": "sectional",
    "armchair": "armchair", "chair": "armchair", "wingback": "wingback",
    "ottoman": "ottoman", "bench": "ottoman", "stool": "ottoman",
    "pouf": "ottoman", "daybed": "sofa-2-seat", "sofa-2-seat": "sofa-2-seat",
}
PIECE_LABELS = {
    "sofa-3-seat": ("Sofa", "كنبة"), "loveseat": ("Loveseat", "كنبة مقعدين"),
    "sectional": ("Sectional", "كنبة زاوية"),
    "armchair": ("Armchair", "كرسي"), "wingback": ("Wingback", "كرسي بأذنين"),
    "ottoman": ("Ottoman", "مقعد صغير"), "sofa-2-seat": ("Daybed", "كنبة"),
}


class DesignerError(Exception):
    pass


# --- 1. plan import -------------------------------------------------

def plan_image(src, ext):
    """RGB plan from a PNG/JPG/PDF path. PDF: first page only."""
    ext = (ext or "").lower()
    if ext == ".pdf":
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(src)
            if len(doc) < 1:
                raise DesignerError("empty PDF")
            page = doc[0]
            img = page.render(scale=PDF_SCALE).to_pil().convert("RGB")
        except DesignerError:
            raise
        except Exception as exc:  # noqa: BLE001 - any pdfium failure
            raise DesignerError("could not read the PDF: %s" % exc)
    else:
        try:
            img = Image.open(src)
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA") or (
                    img.mode == "P" and "transparency" in img.info):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img.convert("RGB"),
                         mask=img.convert("RGBA").split()[3])
                img = bg
            else:
                img = img.convert("RGB")
        except Exception as exc:  # noqa: BLE001 - unreadable image
            raise DesignerError("could not read the plan image: %s" % exc)
    if max(img.size) > PLAN_MAX_SIDE:
        img.thumbnail((PLAN_MAX_SIDE, PLAN_MAX_SIDE), Image.LANCZOS)
    return img


def save_plan(img):
    """Store the plan as a public upload (uploads/<hex>.jpg)."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = uuid.uuid4().hex + ".jpg"
    img.save(os.path.join(UPLOAD_DIR, name), "JPEG", quality=92)
    return os.path.join("uploads", name)


# --- 2. pieces -------------------------------------------------------

def _b64_jpeg(img, q=90):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _vision_copy(img):
    small = img.copy()
    if max(small.size) > VISION_SIDE:
        small.thumbnail((VISION_SIDE, VISION_SIDE), Image.LANCZOS)
    return small


def pieces_prompt(size):
    return (
        "This is a 2D architectural floor plan image, %d x %d pixels. "
        "List every piece of UPHOLSTERED furniture that could be "
        "reupholstered in fabric: sofas, loveseats, sectionals, armchairs, "
        "chairs with cushions, ottomans, benches, stools, daybeds. Ignore "
        "rugs, tables, beds, walls, doors, windows, plants and text. At "
        "most %d pieces, in reading order (top-left to bottom-right). "
        "Reply with JSON only: {\"pieces\": [{\"name\": \"short label\", "
        "\"type\": \"sofa|loveseat|sectional|armchair|chair|wingback|"
        "ottoman|bench|stool|daybed\", \"box\": [x1, y1, x2, y2]}]} with "
        "box in pixel coordinates of this image." % (size[0], size[1],
                                                      MAX_PIECES))


def list_pieces(plan, api_key=None, timeout=90):
    """Spark lists the pieces. Returns (pieces, raw_text, seconds)."""
    key = api_key or require_api_key()
    small = _vision_copy(plan)
    body = {"model": SPARK_MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": pieces_prompt(small.size)},
        {"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + _b64_jpeg(small)}}]}]}
    t0 = time.time()
    try:
        resp = sw._post_json(CHAT_URL, body, key, timeout=timeout,
                             stage="designer-pieces", model=SPARK_MODEL)
        text = resp["choices"][0]["message"]["content"] or ""
    except (sw.SwapError, KeyError, IndexError, TypeError) as exc:
        raise DesignerError("piece listing failed: %s" % exc)
    pieces = parse_pieces(text, small.size)
    sx = plan.width / float(small.width)
    sy = plan.height / float(small.height)
    for p in pieces:
        x1, y1, x2, y2 = p["box"]
        p["box"] = [int(round(x1 * sx)), int(round(y1 * sy)),
                    int(round(x2 * sx)), int(round(y2 * sy))]
    return pieces, text, time.time() - t0


def _iou(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    ua = ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1])
          - inter)
    return inter / float(ua) if ua else 0.0


def _clean_box(raw, size):
    """Ints, corners ordered, clamped; None when degenerate."""
    try:
        vals = [float(v) for v in raw][:4]
    except (TypeError, ValueError):
        return None
    if len(vals) != 4:
        return None
    w, h = size
    x1, x2 = sorted((vals[0], vals[2]))
    y1, y2 = sorted((vals[1], vals[3]))
    x1, x2 = max(0, min(w, x1)), max(0, min(w, x2))
    y1, y2 = max(0, min(h, y1)), max(0, min(h, y2))
    if (x2 - x1) < MIN_BOX_FRAC * w or (y2 - y1) < MIN_BOX_FRAC * h:
        return None
    return [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))]


def piece_key(type_or_name):
    text = str(type_or_name or "").lower()
    for word, key in PIECE_KEYS.items():
        if re.search(r"\b%s\b" % re.escape(word), text):
            return key
    return "armchair"


def reading_order(pieces, size):
    """Sort by row band (ROW_TOL of the height) then x."""
    tol = max(1.0, ROW_TOL * size[1])

    def centre(p):
        b = p["box"]
        return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)
    rows = []
    for p in sorted(pieces, key=lambda p: centre(p)[1]):
        cy = centre(p)[1]
        for row in rows:
            if abs(row["y"] - cy) <= tol:
                row["items"].append(p)
                row["y"] = sum(centre(q)[1] for q in row["items"]) / len(
                    row["items"])
                break
        else:
            rows.append({"y": cy, "items": [p]})
    out = []
    for row in sorted(rows, key=lambda r: r["y"]):
        out.extend(sorted(row["items"], key=lambda p: centre(p)[0]))
    return out


def parse_pieces(text, size):
    """Spark text -> [{id, name, type, box}] cleaned, ordered, numbered."""
    try:
        data = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except ValueError:
        return []
    raw = data.get("pieces") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    pieces = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        box = _clean_box(item.get("box"), size)
        if box is None:
            continue
        if any(_iou(box, p["box"]) >= DUP_IOU for p in pieces):
            continue
        key = piece_key("%s %s" % (item.get("type", ""),
                                   item.get("name", "")))
        name = str(item.get("name") or item.get("type") or key).strip()
        pieces.append({"name": name[:40], "type": key, "box": box})
    pieces = reading_order(pieces, size)[:MAX_PIECES]
    for i, p in enumerate(pieces):
        p["id"] = i + 1
    return pieces


def normalize_pieces(pieces, size):
    """Validate client-edited pieces (deleted ones are simply absent).

    Keeps id/name/type/box/code; drops degenerate boxes; caps the count;
    re-reads the type from the name when it is missing."""
    out = []
    seen = set()
    for item in pieces or []:
        if not isinstance(item, dict):
            continue
        box = _clean_box(item.get("box"), size)
        if box is None:
            continue
        try:
            pid = int(item.get("id"))
        except (TypeError, ValueError):
            pid = None
        if pid is None or pid in seen:
            pid = (max(seen) + 1) if seen else 1
        seen.add(pid)
        key = item.get("type") if item.get("type") in PIECE_LABELS else \
            piece_key(item.get("name", ""))
        code = item.get("code")
        out.append({"id": pid, "name": str(item.get("name") or key)[:40],
                    "type": key, "box": box,
                    "code": str(code) if code else None})
        if len(out) >= MAX_PIECES:
            break
    return out


# --- 3. render -------------------------------------------------------

def outline_map(plan2x, boxes):
    """Copy of the 2x plan with ONLY the given (2x) boxes in magenta."""
    img = plan2x.copy()
    d = ImageDraw.Draw(img)
    width = max(4, int(max(img.size) * OUTLINE_W_FRAC))
    for box in boxes:
        d.rectangle(list(box), outline=(255, 0, 255), width=width)
    return img


def _ratio_text(size):
    import math
    g = math.gcd(size[0], size[1]) or 1
    return "%d:%d" % (size[0] // g, size[1] // g)


def build_prompt(groups, size, corrective=None):
    """groups: [(fabric, [piece names], image index of its outline map)].

    size is the 2x plan size the output must keep."""
    total = sum(len(names) for _, names, _ in groups)
    lines = []
    for i, (fabric, names, img_idx) in enumerate(groups):
        lines.append(
            "Fabric %d is image %d (%s, %s, %s): it goes ONLY on the %d "
            "piece(s) outlined in magenta in image %d: %s." % (
                i + 1, img_idx - 1, fabric["name_en"],
                fabric.get("material", "fabric"),
                fabric.get("primary_color", ""), len(names), img_idx,
                ", ".join(names)))
    text = (
        "Image 1 is a 2D architectural floor plan of a room. Produce a "
        "photorealistic, STRICTLY ORTHOGRAPHIC top-down render of this "
        "exact room, straight down like a satellite view: no perspective, "
        "no visible wall faces, walls appear only as their thin top edge. "
        "Treat image 1 as a precise template: every wall, partition, "
        "door opening, window, fixture (bed, bath, toilet, basin, kitchen "
        "units and island, tables, rug) and piece of furniture stays at "
        "exactly its drawn position, size and orientation; move nothing, "
        "mirror nothing, resize nothing. The output must keep the plan's aspect "
        "ratio: %d x %d pixels (%s). Furnish ONLY what is drawn, with "
        "exact counts: %d upholstered piece(s) in total. %s Every other "
        "drawn item (rug, tables, bed, storage) stays as drawn, in neutral "
        "oak and linen. Window marks on the walls are windows IN the "
        "walls, never skylights or openings in the floor; the ceiling is "
        "not visible. The floor fills the room to the walls with no "
        "border or margin. Soft daylight. The output must contain NO "
        "lines, outlines, marks, labels or text of any kind: the magenta "
        "outlines and labels are instructions only."
        % (size[0], size[1], _ratio_text(size), total, " ".join(lines)))
    if corrective:
        text += " Correction for this retry: %s" % corrective
    return text


def fit_aspect(img, size, tolerance=0.02):
    """Return img at the plan's size; crop to its aspect first when the
    model drifted beyond tolerance (a stretched room is not a plan)."""
    tw, th = size
    want = tw / float(th)
    have = img.width / float(img.height)
    if abs(have - want) / want > tolerance:
        if have > want:
            new_w = int(round(img.height * want))
            x0 = (img.width - new_w) // 2
            img = img.crop((x0, 0, x0 + new_w, img.height))
        else:
            new_h = int(round(img.width / want))
            y0 = (img.height - new_h) // 2
            img = img.crop((0, y0, img.width, y0 + new_h))
    if img.size != (tw, th):
        img = img.resize((tw, th), Image.LANCZOS)
    return img


def check_piece(render, box2x, swatch_bytes):
    """Colour check on a piece's (2x) box.

    The inset box is cut into CHECK_CELLS x CHECK_CELLS cells and each
    cell is matched against the swatch on its own: a sectional's box
    is mostly floor and a round chair's corners are too, so the piece
    passes when at least CHECK_MIN_CELLS of its cells carry the fabric.
    delta_e reported is the median over the passing cells (or all)."""
    x1, y1, x2, y2 = box2x
    dx, dy = (x2 - x1) * CHECK_INSET, (y2 - y1) * CHECK_INSET
    ix1, iy1, ix2, iy2 = x1 + dx, y1 + dy, x2 - dx, y2 - dy
    cw, ch = (ix2 - ix1) / CHECK_CELLS, (iy2 - iy1) / CHECK_CELLS
    results = []
    for r in range(CHECK_CELLS):
        for c in range(CHECK_CELLS):
            mask = Image.new("L", render.size, 0)
            ImageDraw.Draw(mask).rectangle(
                [ix1 + c * cw, iy1 + r * ch, ix1 + (c + 1) * cw,
                 iy1 + (r + 1) * ch], fill=255)
            results.append(swap_checks.colour_check(render, mask,
                                                    swatch_bytes))
    passing = [x for x in results if x["ok"]]
    ok = len(passing) >= CHECK_MIN_CELLS * len(results)
    pool = passing if passing else [x for x in results
                                     if x["delta_e"] is not None]
    if not pool:
        return {"delta_e": None, "delta_l": None, "ok": False, "cells": 0}
    pool = sorted(pool, key=lambda x: x["delta_e"])
    mid = pool[len(pool) // 2]
    return {"delta_e": mid["delta_e"], "delta_l": mid["delta_l"],
            "ok": ok, "cells": len(passing)}


def _edit(plan2x, groups, prompt, key, timeout):
    images = [{"image_url": "data:image/jpeg;base64," + _b64_jpeg(plan2x)}]
    for fabric, _, omap in groups:
        with open(os.path.join(BASE_DIR, fabric["image"]), "rb") as f:
            sw_b64 = base64.b64encode(f.read()).decode("ascii")
        images.append({"image_url": "data:image/jpeg;base64," + sw_b64})
        images.append({"image_url": "data:image/jpeg;base64,"
                       + _b64_jpeg(omap)})
    body = {"model": sw.EDIT_MODEL, "prompt": prompt, "images": images,
            "n": 1}
    try:
        resp = sw._post_json(sw.EDIT_URL, body, key, timeout=timeout,
                             stage="designer-render", model=sw.EDIT_MODEL)
        raw = base64.b64decode(resp["data"][0]["b64_json"])
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except (sw.SwapError, KeyError, IndexError, TypeError,
            ValueError) as exc:
        if isinstance(exc, sw.TimeoutSwapError):
            raise DesignerError("render timed out — please try again")
        raise DesignerError("render failed: %s" % exc)


def layout_prompt():
    return ("Image 1 is a 2D floor plan; image 2 is a top-down render made "
            "from it. Judge how faithfully the render keeps the plan's "
            "LAYOUT: room partitions and walls, door and window positions, "
            "and the position, size and orientation of every fixture and "
            "piece of furniture (bed, bath, toilet, basin, kitchen units, "
            "island, tables, sofas, chairs, rug). Ignore colours, materials "
            "and style. Reply with JSON only: {\"score\": 0-10 (10 = "
            "everything exactly where drawn), \"moved\": [short phrases "
            "naming each item that moved, flipped, resized, vanished or was "
            "invented, max 6]}.")


def parse_layout(text):
    """Spark text -> {score: int|None, moved: [str]}."""
    try:
        data = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except ValueError:
        return {"score": None, "moved": []}
    if not isinstance(data, dict):
        return {"score": None, "moved": []}
    try:
        score = max(0, min(10, int(data.get("score"))))
    except (TypeError, ValueError):
        score = None
    moved = data.get("moved") or []
    if not isinstance(moved, list):
        moved = []
    moved = [str(m).strip()[:80] for m in moved if str(m).strip()][:6]
    return {"score": score, "moved": moved}


def layout_check(plan, render_img, api_key=None, timeout=90):
    """Spark compares plan and render. Never raises: a failed call is
    {score: None, moved: []} (the colour checks still decide)."""
    key = api_key or require_api_key()

    def small(img):
        out = img.copy()
        out.thumbnail((LAYOUT_SIDE, LAYOUT_SIDE), Image.LANCZOS)
        return out
    body = {"model": SPARK_MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": layout_prompt()},
        {"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + _b64_jpeg(small(plan), 85)}},
        {"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64,"
            + _b64_jpeg(small(render_img), 85)}}]}]}
    try:
        resp = sw._post_json(CHAT_URL, body, key, timeout=timeout,
                             stage="designer-layout", model=SPARK_MODEL)
        return parse_layout(resp["choices"][0]["message"]["content"] or "")
    except Exception:  # noqa: BLE001 - advisory check
        return {"score": None, "moved": []}


def render(plan, pieces, api_key=None, on_step=None, out_dir=None,
           timeout=150):
    """Render the assigned pieces. Returns {render_url, size, legend,
    checks, attempts, prompt}. Pieces without a code are left as drawn."""
    key = api_key or require_api_key()

    def step(label):
        if on_step:
            on_step(label)
    assigned = [p for p in pieces if p.get("code")]
    if not assigned:
        raise DesignerError("assign a fabric to at least one piece")
    plan2x = plan.resize((plan.width * 2, plan.height * 2), Image.LANCZOS)
    by_code = {}
    for p in assigned:
        by_code.setdefault(p["code"], []).append(p)
    groups = []          # (fabric, names, outline map)
    prompt_groups = []   # (fabric, names, image index)
    idx = 2
    for code, items in by_code.items():
        fabric = get_fabric(code)
        if not fabric:
            raise DesignerError("unknown fabric code: %s" % code)
        boxes = [[v * 2 for v in p["box"]] for p in items]
        names = ["%s %d" % (p["name"], p["id"]) for p in items]
        groups.append((fabric, names, outline_map(plan2x, boxes)))
        prompt_groups.append((fabric, names, idx + 1))
        idx += 2
    swatches = {}
    for code in by_code:
        with open(os.path.join(BASE_DIR, get_fabric(code)["image"]),
                  "rb") as f:
            swatches[code] = f.read()
    best = None
    corrective = None
    attempts = 0
    prompt = ""
    for round_no in range(2):
        if round_no:
            step("retry")
        step("edit")
        prompt = build_prompt(prompt_groups, plan2x.size, corrective)
        out = fit_aspect(_edit(plan2x, groups, prompt, key, timeout),
                         plan2x.size)
        attempts += 1
        step("check")
        checks = []
        for p in assigned:
            res = check_piece(out, [v * 2 for v in p["box"]],
                              swatches[p["code"]])
            checks.append({"id": p["id"], "name": p["name"],
                           "code": p["code"], "ok": bool(res["ok"]),
                           "delta_e": res["delta_e"],
                           "delta_l": res["delta_l"]})
        n_ok = sum(1 for c in checks if c["ok"])
        layout = layout_check(plan, out, key)
        score = layout.get("score")
        layout_ok = score is None or score >= LAYOUT_MIN_SCORE
        cand = {"image": out, "checks": checks, "n_ok": n_ok,
                "layout": layout,
                "rank": (n_ok, -1 if score is None else score)}
        if best is None or cand["rank"] > best["rank"]:
            best = cand
        if n_ok == len(checks) and layout_ok:
            break
        notes = []
        failed = [c for c in checks if not c["ok"]]
        if failed:
            notes.append("the fabric colour on %s must match swatch %s "
                         "exactly (same hue and lightness, uniform across "
                         "the piece)" % (
                             ", ".join(c["name"] for c in failed),
                             ", ".join(sorted({c["code"] for c in failed}))))
        if not layout_ok:
            notes.append("the layout drifted from the plan (%s): put every "
                         "wall, door, fixture and piece back exactly where "
                         "the plan draws it, same size and orientation" % (
                             "; ".join(layout.get("moved") or
                                       ["items moved"])))
        corrective = "; ".join(notes) + ". Keep everything else as it is."
    out_dir = out_dir or os.path.join(UPLOAD_DIR, "swap")
    os.makedirs(out_dir, exist_ok=True)
    name = "plan-render-%s.jpg" % uuid.uuid4().hex
    best["image"].save(os.path.join(out_dir, name), "JPEG", quality=90)
    base = os.path.relpath(out_dir, BASE_DIR)
    legend = []
    for p in pieces:
        fabric = get_fabric(p["code"]) if p.get("code") else None
        legend.append({"id": p["id"], "name": p["name"], "type": p["type"],
                       "box": p["box"], "code": p.get("code"),
                       "name_en": fabric["name_en"] if fabric else "",
                       "name_ar": fabric["name_ar"] if fabric else "",
                       "image": fabric["image"] if fabric else "",
                       "material": (fabric or {}).get("material", ""),
                       "price_sar_per_m": (fabric or {}).get(
                           "price_sar_per_m")})
    return {"render_url": os.path.join(base, name),
            "size": list(plan2x.size), "legend": legend,
            "checks": best["checks"], "attempts": attempts,
            "layout": best["layout"],
            "ok": best["n_ok"] == len(best["checks"]), "prompt": prompt}


# --- 5. quote --------------------------------------------------------

def quote_pieces(pieces):
    """Meters / SAR / CO2 for assigned pieces (plan mode has no
    measurements: standard yardage per piece type)."""
    items = []
    total = 0.0
    co2 = waste = 0.0
    for p in pieces:
        if not p.get("code"):
            continue
        fabric = get_fabric(p["code"]) or {}
        key = p.get("type") if p.get("type") in meterage.YARDAGE \
            else "armchair"
        meters = meterage.piece_meters(key, fabric)
        price = fabric.get("price_sar_per_m")
        line = round(meters * price, 2) if price is not None else None
        if line is not None:
            total += line
        factor = impact.CO2_FACTORS.get(key, 0.0)
        co2 += impact.CO2_PER_3SEAT_KG * factor
        waste += impact.WASTE_PER_3SEAT_KG * factor
        items.append({"id": p["id"], "name": p["name"], "type": key,
                      "code": p["code"], "name_en": fabric.get("name_en"),
                      "name_ar": fabric.get("name_ar"),
                      "material": fabric.get("material", ""),
                      "image": fabric.get("image", ""),
                      "meters": meters, "price_sar_per_m": price,
                      "line_total": line})
    return {"items": items, "total": round(total, 2), "currency": "SAR",
            "preliminary": True,
            "co2": {"kg": round(co2, 1), "waste_kg": round(waste, 1),
                    "source": impact.CO2_SOURCE}}
