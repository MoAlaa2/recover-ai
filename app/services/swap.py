"""Fabric swap: SAM 3.1 segments the piece, Muse Image reupholsters it,
a feathered composite keeps the rest of the room pixel-identical, and
muse-spark-1.3 verifies color, pattern, scale and isolation (0-10 each).

Pipeline notes:
- SAM boxes localize the piece reliably; the paste mask is the dilated
  union box intersected with a dilated change map (|edit - original|),
  feathered. This pastes only what the edit actually changed near the
  piece, so surroundings the edit preserved stay pixel-identical.
- The raw merged SAM mask is saved alongside for debugging.
- Every model call is capped at 75s with one silent retry; a single
  swap has a 105s overall budget and raises TimeoutSwapError past it.
"""
import base64
import io
import json
import os
import time
import urllib.request
import uuid

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app.services import swap_checks

from app.core.config import (BASE_DIR, CHAT_URL, SPARK_MODEL, UPLOAD_DIR,
                             require_api_key)
from app.services import sam_codec
from app.services.catalog import get_fabric

SAM_URL = "https://api.meta.ai/v1/responses"
SAM_MODEL = "sam-3.1"
EDIT_URL = "https://api.meta.ai/v1/images/edits"
EDIT_MODEL = "muse-image-1.0"

# The swap concept must match the tap/outline concept (targets.
# CONCEPT_PROMPTS): a bare "cushions" also segments the seat and back
# cushions, so a "cushions" swap recoloured the whole sofa seat while
# the picker thumbnail showed the throw pillows.
TARGET_CONCEPTS = {
    "sofa": "sofa",
    "armchair": "armchair",
    "curtains": "window curtains",
    "cushions": "throw pillows on the sofa",
}

VERIFY_LABELS = ("color", "pattern", "scale", "isolation")

# A second edit costs ~25s. Only the scores the deterministic checks
# cannot judge (motif and weave scale) may trigger it: colour has the
# ΔE gate and isolation is guaranteed by compositing inside the mask.
RETRY_SCORES = ("pattern", "scale")
# A patterned fabric must visibly change at least this share of the
# mask (a full gingham on an off-white sofa changes ~0.84; the model's
# "patches" edit changed a third). Plain fabrics are exempt: a
# like-for-like colour legitimately changes little.
PATTERN_MIN_CHANGED = 0.4


def min_changed_for(fabric):
    return PATTERN_MIN_CHANGED if (fabric or {}).get(
        "plain_or_patterned") == "patterned" else 0.0
RETRY_MIN_SCORE = 6

# Hard per-model-call cap (seconds). No single network call may hang
# longer than this; the client enforces the overall 2-minute budget.
MODEL_TIMEOUT = 75
# Overall wall budget for one single swap incl. the corrective retry.
# Together with the client watchdog this guarantees no spinner
# survives past ~2 minutes.
SWAP_BUDGET_S = 105

# Overridden with a tmp path in unit tests; None means the
# Volume-backed runtime logs dir.
TIMEOUT_LOG = None


class SwapError(RuntimeError):
    """Swap failed (bad input, segmentation, edit or verify error)."""


class CheckFailed(SwapError):
    """A deterministic check failed twice: the item is not applied."""

    def __init__(self, reason, checks=None, target=""):
        super().__init__("%s — not applied" % reason)
        self.reason = reason
        self.checks = checks or {}
        self.target = target


class TimeoutSwapError(SwapError):
    """A swap stage timed out (client retries once, then Try again)."""


def _is_timeout(exc):
    """True for socket/URL timeouts (the only errors that fail over)."""
    import socket
    if isinstance(exc, TimeoutError):
        return True
    return isinstance(getattr(exc, "reason", None),
                      (TimeoutError, socket.timeout))


def _timeout_log_path():
    if TIMEOUT_LOG:
        return TIMEOUT_LOG
    from app.core.config import runtime_logs_dir
    return os.path.join(runtime_logs_dir(), "swap_timeouts.jsonl")


def _log_timeout(stage, model, timeout_s, seconds, error):
    """One JSON line per timed-out model call: stage + model + budget."""
    entry = {"ts": time.time(), "stage": stage, "model": model,
             "timeout_s": timeout_s, "seconds": round(seconds, 2),
             "error": str(error)[:200]}
    try:
        dest = _timeout_log_path()
        with open(dest, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _post_json(url, payload, api_key, timeout, stage="", model=""):
    """POST JSON with one silent retry on a fresh request.

    Returns the parsed response body. Timeouts are logged with
    stage + model and raised as TimeoutSwapError (after the retry);
    every other failure stays a plain SwapError.
    """
    data = json.dumps(payload).encode("utf-8")
    last_err = None
    t0 = time.time()
    for attempt in range(2):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Authorization": "Bearer " + api_key,
                         "Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - retry once, then raise
            last_err = exc
            if _is_timeout(exc):
                _log_timeout(stage, model, timeout,
                             time.time() - t0, exc)
            if attempt == 0:
                time.sleep(2)
    if _is_timeout(last_err):
        raise TimeoutSwapError(
            "swap timed out in %s — please try again"
            % (stage or "model call"))
    raise SwapError("request failed: %s" % last_err)


def _b64_image(image):
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _small_copy(image_bytes, max_side=1600):
    """Downscaled JPEG copy for vision calls (segment/verify).

    Masks are always rebuilt at full room resolution, so this only
    shrinks the transmitted payload, never the composite.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=75)
    return buf.getvalue()


def _output_text(body):
    texts = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "output_text" and node.get("text"):
                texts.append(node["text"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(body)
    return "\n".join(texts)


def segment(image_bytes, concept, api_key=None, timeout=MODEL_TIMEOUT):
    """Run SAM 3.1 on room bytes. Returns parsed records (may be empty)."""
    key = api_key or require_api_key()
    room = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    body = {"model": SAM_MODEL,
            "input": [{"type": "message", "role": "user",
                       "content": [
                           {"type": "input_text", "text": concept},
                           {"type": "input_image",
                            "image_url": "data:image/jpeg;base64,"
                            + _b64_image(room)}]}],
            "metadata": {"mask_encoding": "one_bit"}}
    try:
        resp = _post_json(SAM_URL, body, key, timeout=timeout,
                          stage="segment", model=SAM_MODEL)
    except SwapError as exc:
        if isinstance(exc, TimeoutSwapError):
            raise
        raise SwapError("segmentation failed: %s" % exc)
    try:
        return sam_codec.parse_output_text(_output_text(resp))
    except sam_codec.MaskError as exc:
        raise SwapError("bad segmentation response: %s" % exc)


MIN_RECORD_SCORE = 0.5
MAX_RECORD_COVERAGE = 0.60
MAX_MERGED_COVERAGE = 0.60


def _mask_coverage(layer, size):
    white = sum(layer.histogram()[128:])
    return white / (size[0] * size[1])


def _place_record(raster, w, h, record, size):
    """Place one decoded SAM raster on an empty room-sized canvas.

    SAM 3.1 masks are cropped to the record's box (inclusive, so the
    raster is box w+1 by h+1) and mask x,y is an offset from the box's
    top-left corner, not a frame position. Scale frame coords to room
    coords and paste there; never stretch the crop over the frame.
    """
    width, height = size
    arr = np.frombuffer(bytes(raster), dtype=np.uint8).reshape(h, w)
    layer = Image.frombytes(
        "L", (w, h), (arr * 255).astype(np.uint8).tobytes())
    try:
        fw, fh = record["frame_size"]
        x1, y1 = record["box"][:2]
        ox, oy = record.get("mask_origin") or (0, 0)
        sx, sy = width / float(fw), height / float(fh)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        # No geometry at all: the raster is the whole frame.
        return layer.resize(size, Image.BILINEAR).point(
            lambda v: 255 if v > 127 else 0)
    tw = max(1, int(round(w * sx)))
    th = max(1, int(round(h * sy)))
    layer = layer.resize((tw, th), Image.BILINEAR).point(
        lambda v: 255 if v > 127 else 0)
    canvas = Image.new("L", size, 0)
    canvas.paste(layer, (int(round((x1 + ox) * sx)),
                         int(round((y1 + oy) * sy))))
    return canvas


def sam_mask(records, size):
    """Merge record masks into one room-sized L image (0/255).

    Each record's cropped mask is pasted at its scaled box position.
    Low-confidence records and any record covering most of the frame
    are dropped: a full-frame "mask" is a failed detection, not a
    segmentation. A merged mask still covering most of the frame
    raises instead of tinting the whole photo.
    """
    merged = None
    for record in records:
        try:
            score = float((record or {}).get("score", 1.0))
        except (TypeError, ValueError):
            score = 1.0
        if score < MIN_RECORD_SCORE:
            continue
        try:
            raster, w, h = sam_codec.decode_record(record)
        except sam_codec.MaskError:
            continue
        layer = _place_record(raster, w, h, record, size)
        if _mask_coverage(layer, size) > MAX_RECORD_COVERAGE:
            continue
        merged = layer if merged is None else Image.composite(
            Image.new("L", size, 255), merged, layer)
    if merged is None:
        raise SwapError("no usable segmentation mask")
    if _mask_coverage(merged, size) > MAX_MERGED_COVERAGE:
        raise SwapError("target covers the whole photo, not detected")
    return drop_small_components(merged)


def record_masks(records, size):
    """One room-sized mask per usable segmenter record (per object)."""
    out = []
    for record in records:
        try:
            out.append(sam_mask([record], size))
        except SwapError:
            continue
    return out


MIN_COMPONENT_FRAC = 0.03


def drop_small_components(mask, frac=MIN_COMPONENT_FRAC, work_side=320):
    """Erase blobs smaller than frac of the mask's largest blob.

    SAM leaves stray specks (a curtains mask with a blob over a
    cushion); those would be tinted and re-fabricked with the item.
    Components are found on a downscaled copy (4-connectivity) and the
    keep-map is scaled back with nearest sampling.
    """
    from collections import deque
    mask = mask.convert("L")
    w0, h0 = mask.size
    small = mask.copy()
    small.thumbnail((work_side, work_side))
    w, h = small.size
    px = small.load()
    seen = bytearray(w * h)
    comps = []
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if seen[idx] or px[x, y] < 128:
                continue
            seen[idx] = 1
            queue = deque([idx])
            members = []
            while queue:
                cur = queue.popleft()
                members.append(cur)
                cx, cy = cur % w, cur // w
                for nx, ny in ((cx - 1, cy), (cx + 1, cy),
                               (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        nidx = ny * w + nx
                        if not seen[nidx] and px[nx, ny] >= 128:
                            seen[nidx] = 1
                            queue.append(nidx)
            comps.append(members)
    if len(comps) < 2:
        return mask
    largest = max(len(c) for c in comps)
    drop = [c for c in comps if len(c) < frac * largest]
    if not drop:
        return mask
    keep = Image.new("L", (w, h), 255)
    kp = keep.load()
    for members in drop:
        for cur in members:
            kp[cur % w, cur // w] = 0
    keep = keep.resize((w0, h0), Image.NEAREST)
    return ImageChops.multiply(mask, keep)


def edit_prompt(fabric, piece_label, corrective=None):
    pattern = fabric.get("pattern_type") or "plain"
    text = ("Reupholster ONLY the %s in this exact fabric: %s, %s, "
            "primary color %s, pattern %s. "
            "The second image is the exact fabric swatch: copy its color, "
            "weave texture and pattern faithfully at a realistic furniture "
            "scale. Keep the %s's exact shape, cushions, folds, shadows "
            "and the room lighting. Do not change anything else in the "
            "room. Do not invent a new pattern." % (
                piece_label, fabric["name_en"],
                fabric.get("material", "fabric"),
                fabric.get("primary_color", ""),
                pattern, piece_label))
    if "pillow" not in piece_label and "cushion" not in piece_label:
        text += (" Keep any wooden frame, base, legs and trim exactly as "
                 "they are: only the fabric changes.")
    if "pillow" in piece_label or "cushion" in piece_label:
        text += (" Replace each existing pillow with exactly ONE pillow of "
                 "the same size, shape and position. Do not add, duplicate "
                 "or remove pillows.")
    if corrective:
        text += " Correction for this retry: %s" % corrective
    return text


def edit_room(room_bytes, swatch_bytes, fabric, piece_label,
              api_key=None, corrective=None, timeout=MODEL_TIMEOUT):
    """Reupholster via Muse Image edit. Returns the edited PIL image."""
    key = api_key or require_api_key()
    room_b64 = base64.b64encode(room_bytes).decode("ascii")
    swatch_b64 = base64.b64encode(swatch_bytes).decode("ascii")
    body = {"model": EDIT_MODEL,
            "prompt": edit_prompt(fabric, piece_label, corrective),
            "images": [{"image_url": "data:image/jpeg;base64," + room_b64},
                       {"image_url": "data:image/jpeg;base64,"
                        + swatch_b64}],
            "n": 1}
    try:
        resp = _post_json(EDIT_URL, body, key, timeout=timeout,
                          stage="edit", model=EDIT_MODEL)
        raw = base64.b64decode(resp["data"][0]["b64_json"])
    except (SwapError, KeyError, ValueError) as exc:
        if isinstance(exc, TimeoutSwapError):
            raise
        raise SwapError("fabric edit failed: %s" % exc)
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - corrupt image bytes
        raise SwapError("fabric edit returned unreadable bytes: %s" % exc)


def paste_mask(original, edited, box, margin=0.04, feather=6):
    """Feathered mask of changed pixels inside the dilated box.

    original/edited are same-size RGB images; box is (x1, y1, x2, y2).
    """
    width, height = original.size
    pad = int(max(width, height) * margin)
    x1 = max(0, box[0] - pad)
    y1 = max(0, box[1] - pad)
    x2 = min(width, box[2] + pad)
    y2 = min(height, box[3] + pad)
    box_layer = Image.new("L", (width, height), 0)
    ImageDraw.Draw(box_layer).rectangle([x1, y1, x2, y2], fill=255)
    diff = np.abs(np.asarray(original).astype(int)
                  - np.asarray(edited).astype(int)).max(axis=2)
    changed = Image.fromarray((diff > 14).astype(np.uint8) * 255)
    changed = changed.filter(ImageFilter.MaxFilter(31))
    mask = Image.composite(Image.new("L", (width, height), 255),
                           Image.new("L", (width, height), 0),
                           Image.composite(box_layer, Image.new(
                               "L", (width, height), 0), changed))
    return mask.filter(ImageFilter.GaussianBlur(feather))


# ---- hidden-sliver refinement ------------------------------------------
# SAM's seat mask stops at whatever sits in front of the seat (a throw,
# a side table, pillows), so the strips of seat visible just past those
# objects kept the OLD fabric after a strict composite. A second, aimed
# edit recolours only those strips.
SEAT_CONCEPTS = ("sofa", "armchair")
OCCLUDER_CONCEPTS = ("throw blanket", "side table", "coffee table",
                     "throw pillows")
REFINE_CLOSE_FRAC = 0.06   # closing kernel, share of the longer side
REFINE_RING_FRAC = 0.008   # hairline past the mask edge (SAM erosion)
REFINE_MIN_GAP = 0.01      # refine only when the gap is >= 1% of the seat
REFINE_MIN_BUDGET_S = 30   # seconds left in the swap budget to try it
REFINE_EDIT_TIMEOUT = 40   # the aimed edit is capped tighter than a pass
REFINE_WORK_SIDE = 800     # morphology works on a copy this big
REFINE_TEXT = ("the %s is already reupholstered in the new fabric except "
               "small leftover patches of its OLD fabric: the strips just "
               "past the objects in front of it (a throw, a table, "
               "pillows) and along its lower edge. Recolour ONLY those "
               "leftover patches in the same new fabric so the whole %s "
               "matches; keep the throw, the table, the pillows, the "
               "floor and everything else exactly as they are")


def occluder_mask(seg_bytes, size, key, timeout=MODEL_TIMEOUT):
    """Union of the masks of things usually in front of a seat.

    The concepts are segmented in parallel; a missing one, a failed
    call or a mask over half the photo (a mis-segmentation) is skipped.
    """
    from concurrent.futures import ThreadPoolExecutor

    def one(concept):
        try:
            records = segment(seg_bytes, concept, key, timeout=timeout)
            if not records:
                return None
            mask = sam_mask(records, size)
            if sum(mask.histogram()[128:]) > 0.5 * size[0] * size[1]:
                return None
            return mask
        except Exception:  # noqa: BLE001 - best effort
            return None
    out = Image.new("L", size, 0)
    with ThreadPoolExecutor(max_workers=len(OCCLUDER_CONCEPTS)) as pool:
        for mask in pool.map(one, OCCLUDER_CONCEPTS):
            if mask is not None:
                out = ImageChops.lighter(out, mask)
    return out


def gap_mask(mask, occluders, close_frac=None, ring_frac=None):
    """Candidate hidden slivers: the seat's concavities and a thin ring
    past its edge, minus the occluders themselves."""
    if close_frac is None:
        close_frac = REFINE_CLOSE_FRAC
    if ring_frac is None:
        ring_frac = REFINE_RING_FRAC
    full = mask.convert("L")
    # Morphology runs on a small copy: a closing kernel of 6% of a
    # 2700px photo is 165px wide and takes minutes at full size.
    mask = full.copy()
    mask.thumbnail((REFINE_WORK_SIDE, REFINE_WORK_SIDE), Image.BILINEAR)
    mask = mask.point(lambda v: 255 if v >= 128 else 0)
    width, height = mask.size
    close_k = max(3, int(max(width, height) * close_frac) | 1)
    ring_k = int(max(width, height) * ring_frac) | 1
    closed = mask.filter(ImageFilter.MaxFilter(close_k)).filter(
        ImageFilter.MinFilter(close_k))
    ring = mask.filter(ImageFilter.MaxFilter(ring_k)) if ring_k > 1 else mask
    gap = ImageChops.subtract(ImageChops.lighter(closed, ring), mask)
    if occluders is not None:
        occ = occluders.convert("L").resize(mask.size, Image.BILINEAR)
        occ = occ.point(lambda v: 255 if v >= 128 else 0)
        gap = ImageChops.subtract(gap, occ.filter(ImageFilter.MaxFilter(3)))
    gap = gap.resize(full.size, Image.BILINEAR).point(
        lambda v: 255 if v >= 128 else 0)
    # Drop single-pixel specks at full size (the slivers between a
    # stool's legs are only a few pixels wide, so no coarser opening).
    return gap.filter(ImageFilter.MinFilter(3)).filter(
        ImageFilter.MaxFilter(3))


def mask_share(part, whole):
    """Area of part as a share of whole (both L masks)."""
    base = sum(whole.histogram()[128:]) or 1
    return sum(part.histogram()[128:]) / float(base)


def refine_slivers(result, gap, swatch_bytes, fabric, concept, key,
                   timeout=MODEL_TIMEOUT):
    """Second aimed edit on the composite; pasted only inside gap where
    the model actually changed something. Returns (image, pasted mask)
    or None when the model changed nothing there."""
    width, height = result.size
    small = result.copy()
    small.thumbnail((1600, 1600), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=92)
    edited = edit_room(buf.getvalue(), swatch_bytes, fabric, concept, key,
                       REFINE_TEXT % (concept, concept),
                       timeout=timeout).resize((width, height),
                                               Image.BILINEAR)
    diff = np.abs(np.asarray(result).astype(int)
                  - np.asarray(edited).astype(int)).max(axis=2)
    changed = Image.fromarray((diff > 20).astype(np.uint8) * 255)
    changed = changed.filter(ImageFilter.MinFilter(3)).filter(
        ImageFilter.MaxFilter(3))
    pasted = ImageChops.multiply(gap.convert("L"), changed)
    if sum(pasted.histogram()[128:]) < 0.1 * (sum(gap.histogram()[128:]) or 1):
        return None
    # The aimed edit redraws the pillows too; its overhang must stay
    # out of the ring around them (the ghost second pillow).
    pasted = pillow_guard(edited, pasted, key, timeout, (width, height))
    return paste_strict(result, edited, pasted, feather=3), pasted


PIECES_TEXT = ("recolour the %s that still show their old fabric in the "
               "new fabric: every pillow, on the seat and on the floor "
               "too, must be in the new fabric; change nothing else")


def refine_pieces(best, room, pieces, swatch_bytes, fabric, concept, key,
                  remaining_s, timeout):
    """Aimed edit on the composite for the pillows the first edit left
    in the old fabric. Pasted strictly inside those pillows, kept only
    where they now pass the coverage check. Never raises."""
    if not pieces or remaining_s < REFINE_MIN_BUDGET_S:
        return best
    try:
        result = best["result"]
        width, height = result.size
        todo = [c for c in pieces
                if not swap_checks.coverage_check(result, c, swatch_bytes)["ok"]]
        if not todo:
            return best
        gap = todo[0].convert("L")
        for c in todo[1:]:
            gap = ImageChops.lighter(gap, c.convert("L"))
        small = result.copy()
        small.thumbnail((1600, 1600), Image.LANCZOS)
        buf = io.BytesIO()
        small.save(buf, "JPEG", quality=92)
        edited = edit_room(buf.getvalue(), swatch_bytes, fabric, concept, key,
                           PIECES_TEXT % concept,
                           timeout=min(REFINE_EDIT_TIMEOUT, timeout)).resize(
                               (width, height), Image.BILINEAR)
        image2 = paste_strict(result, edited, gap, feather=3)
        done = [c for c in todo
                if swap_checks.coverage_check(image2, c, swatch_bytes)["ok"]]
        if not done:
            best["checks"]["refine_pieces"] = 0
            return best
        kept = done[0].convert("L")
        for c in done[1:]:
            kept = ImageChops.lighter(kept, c.convert("L"))
        image3 = paste_strict(result, edited, kept, feather=3)
        checks = dict(best["checks"])
        pcs = dict(checks.get("pieces") or {})
        pcs["covered"] = int(pcs.get("covered", 0)) + len(done)
        checks["pieces"] = pcs
        checks["refine_pieces"] = len(done)
        return dict(best, result=image3, checks=checks,
                    mask=ImageChops.lighter(best["mask"].convert("L"), kept))
    except Exception as exc:  # noqa: BLE001 - never fails a swap
        best["checks"]["refine_error"] = str(exc)[:160]
        return best


def refine_seat(best, room, raw_mask, seg_bytes, swatch_bytes, fabric,
                concept, key, remaining_s, timeout, check_kwargs=None):
    """Apply the hidden-sliver pass to a passing seat candidate.

    Returns the (possibly) updated candidate dict. Never raises: a
    failure is recorded under checks["refine_error"] and the first
    composite is kept, as it is when the refined one fails the checks
    or the budget is short.
    """
    if concept not in SEAT_CONCEPTS or remaining_s < REFINE_MIN_BUDGET_S:
        return best
    try:
        size = room.size
        occluders = occluder_mask(seg_bytes, size, key, timeout=timeout)
        gap = gap_mask(raw_mask, occluders)
        if mask_share(gap, raw_mask) < REFINE_MIN_GAP:
            return best
        refined = refine_slivers(best["result"], gap, swatch_bytes, fabric,
                                 concept, key,
                                 timeout=min(REFINE_EDIT_TIMEOUT, timeout))
        if refined is None:
            return best
        image2, pasted = refined
        checks2 = swap_checks.run_checks(room, image2, raw_mask,
                                         swatch_bytes, pieces=False,
                                         **(check_kwargs or {}))
        checks2.pop("_mask", None)
        if not checks2.get("ok"):
            return best
        checks2["refined"] = round(mask_share(pasted, raw_mask), 4)
        return dict(best, result=image2, checks=checks2,
                    mask=ImageChops.lighter(best["mask"].convert("L"),
                                            pasted))
    except Exception as exc:  # noqa: BLE001 - never fails a swap
        best["checks"]["refine_error"] = str(exc)[:160]
        return best


# Throw pillows on the EDITED image are kept out of a seat paste. The
# edit model redraws a pillow a little bigger or shifted; pasting the
# seat strictly around the photo's own pillow then shows the redrawn
# pillow's overhang beside it (a ghost second pillow). Dilation covers
# the soft edge of the redrawn pillow.
PILLOW_GUARD_DILATE = 0.006
PILLOW_GUARD_MAX_SHARE = 0.6


def _dilate(mask, frac, work_side=800):
    """MaxFilter by frac of the long side, computed on a small copy."""
    w, h = mask.size
    scale = min(1.0, work_side / float(max(w, h)))
    small = mask.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                        Image.BILINEAR) if scale < 1.0 else mask
    k = max(3, int(max(small.size) * frac) | 1)
    small = small.filter(ImageFilter.MaxFilter(k))
    return small.resize((w, h), Image.BILINEAR) if scale < 1.0 else small


def pillow_guard(edited, mask, key, timeout, size):
    """Seat mask minus the pillows SAM finds on the edited image.

    Best effort: no pillows found, a SAM error, or a pillow mask that is
    most of the seat (SAM grabbed the cushions) leave the mask as is.
    The few pixels of overhang then keep the photo's own fabric, which
    reads as the pillow's shadow rather than a ghost pillow.
    """
    buf = io.BytesIO()
    edited.save(buf, "JPEG", quality=88)
    try:
        recs = segment(_small_copy(buf.getvalue(), 1600),
                       TARGET_CONCEPTS["cushions"], key, timeout=timeout)
    except SwapError:
        return mask
    if not recs:
        return mask
    try:
        pillows = sam_mask(recs, size)
    except (SwapError, sam_codec.MaskError):
        return mask
    seat = _mask_coverage(mask, size)
    if seat <= 0 or _mask_coverage(pillows, size) / seat > PILLOW_GUARD_MAX_SHARE:
        return mask
    pillows = _dilate(pillows, PILLOW_GUARD_DILATE)
    return ImageChops.subtract(mask.convert("L"), pillows.convert("L"))


def paste_strict(original, edited, mask, feather=6):
    """Composite edited onto original strictly inside mask (feathered).

    Unlike paste_mask there is no change-map intersection: the caller
    guarantees edited differs from original only where intended. Used
    by the parallel multi engine for the one-pass composite.
    """
    if edited.size != original.size:
        edited = edited.resize(original.size, Image.LANCZOS)
    if mask.size != original.size:
        mask = mask.resize(original.size, Image.LANCZOS)
    soft = mask.filter(ImageFilter.GaussianBlur(feather))
    out = original.copy()
    out.paste(edited, (0, 0), soft)
    return out


def verify(swatch_bytes, result_image, fabric, piece_label, api_key=None,
           timeout=MODEL_TIMEOUT):
    """Score the swap with muse-spark-1.3 vision. Returns dict of 0-10."""
    key = api_key or require_api_key()
    buf = io.BytesIO()
    result_image.save(buf, "JPEG", quality=88)
    if fabric.get("plain_or_patterned") == "patterned":
        pattern_ask = ("pattern match of the %s motif versus the swatch "
                       "(0 if the motif was invented or changed)" % piece_label)
    else:
        pattern_ask = ("10 when the %s fabric is plain like the swatch, "
                       "else 0" % piece_label)
    text = ("Two images: first the fabric swatch, second the room photo "
            "after reupholstering the %s in that fabric. Reply with JSON "
            "only: {\"color\": 0-10 match of the fabric color on the %s "
            "versus the swatch, \"pattern\": %s, \"scale\": 0-10 realism "
            "of the pattern/weave scale on furniture, \"isolation\": 0-10 "
            "where 10 means ONLY the %s changed and the rest of the room "
            "is untouched}." % (piece_label, piece_label, pattern_ask,
                                piece_label))
    body = {"model": SPARK_MODEL, "messages": [{
        "role": "user", "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64,"
                + base64.b64encode(swatch_bytes).decode("ascii")}},
            {"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64,"
                + base64.b64encode(buf.getvalue()).decode("ascii")}}]}]}
    try:
        resp = _post_json("https://api.meta.ai/v1/chat/completions",
                          body, key, timeout=timeout,
                          stage="verify", model=SPARK_MODEL)
        content = resp["choices"][0]["message"]["content"] or ""
        scores = json.loads(content[content.find("{"):content.rfind("}")
                                        + 1])
        return {k: max(0, min(10, int(scores.get(k, 0))))
                for k in VERIFY_LABELS}
    except (SwapError, KeyError, ValueError) as exc:
        if isinstance(exc, TimeoutSwapError):
            raise
        raise SwapError("swap verification failed: %s" % exc)


def _corrective(scores, concept, checks=None):
    if checks and not checks.get("ok"):
        return swap_checks.corrective_for(checks.get("fail"), concept)
    if checks and pieces_missing(checks):
        pcs = checks["pieces"]
        return ("recolour EVERY pillow in the new fabric: all %d of "
                "them, the ones on the back of the sofa, on the seat "
                "and on the floor alike; %d still show their old fabric "
                "and must not" % (pcs["total"], pieces_missing(checks)))
    worst = min(scores, key=scores.get)
    hints = {
        "color": ("match the swatch color exactly on every cushion and "
                  "fold, keep the hue uniform"),
        "pattern": ("copy the swatch motif exactly, same shapes and "
                    "spacing, never invent or drop pattern elements"),
        "scale": ("make the weave/pattern scale realistic for furniture: "
                  "neither giant nor miniature motifs"),
        "isolation": ("change ONLY the %s; leave walls, floor, furniture "
                      "and decor exactly as in the original photo" % concept),
    }
    return hints[worst]


def swap(room_path, fabric_code, target="sofa", api_key=None,
         out_dir=None, on_step=None):
    """Run the full swap. Returns result_url, mask_url, scores, attempts.

    on_step (optional) receives progress labels as each stage starts:
    segment, edit, composite, verify, retry.
    """
    def step(label):
        if on_step:
            on_step(label)
    key = api_key or require_api_key()
    concept = TARGET_CONCEPTS.get((target or "sofa").lower(), "sofa")
    fabric = get_fabric(fabric_code)
    if not fabric:
        raise SwapError("unknown fabric code: %s" % fabric_code)
    path = room_path if os.path.isabs(room_path) else os.path.join(
        BASE_DIR, room_path)
    with open(path, "rb") as f:
        room_bytes = f.read()
    room = Image.open(io.BytesIO(room_bytes)).convert("RGB")
    width, height = room.size
    swatch_path = os.path.join(BASE_DIR, fabric.get("image", ""))
    with open(swatch_path, "rb") as f:
        swatch_bytes = f.read()

    t_end = time.monotonic() + SWAP_BUDGET_S

    def call_timeout():
        """Per-call cap shrunk to fit the overall swap budget."""
        return max(5.0, min(MODEL_TIMEOUT, t_end - time.monotonic()))

    def need_budget(stage):
        if t_end - time.monotonic() < 10:
            raise TimeoutSwapError(
                "swap timed out in %s — please try again" % stage)

    step("segment")
    need_budget("segment")
    # Vision and edit calls get a capped copy (a 12 MP phone photo is
    # 4-5 MB of base64 per call); masks and the composite stay at full
    # room resolution.
    seg_bytes = _small_copy(room_bytes, 1600)
    if concept == TARGET_CONCEPTS["sofa"]:
        records, full_mask = sofa_full_mask(
            seg_bytes, (width, height), key, call_timeout())
    else:
        full_mask = None
        records = segment_with_fallback(seg_bytes, concept, target, key,
                                        call_timeout())
    if not records:
        raise SwapError("could not find the %s in this photo" % concept)
    raw_mask = full_mask if full_mask is not None else sam_mask(
        records, (width, height))
    if concept == TARGET_CONCEPTS["armchair"]:
        try:
            sofa_recs = segment(seg_bytes, TARGET_CONCEPTS["sofa"], key,
                                timeout=call_timeout())
        except SwapError:
            sofa_recs = None
        raw_mask = separate_seats(raw_mask, sofa_recs, (width, height))
    # Pillows are judged per piece (see swap_checks.run_checks).
    pieces = record_masks(records, (width, height)) \
        if target == "cushions" else False

    out_dir = out_dir or os.path.join(UPLOAD_DIR, "swap")
    os.makedirs(out_dir, exist_ok=True)
    tag = uuid.uuid4().hex
    raw_mask.save(os.path.join(out_dir, "mask-%s.png" % tag))

    best = None
    attempts = 0
    for round_no in range(2):
        corrective = None
        if best is not None:
            corrective = _corrective(best["scores"], concept,
                                     best.get("checks"))
            step("retry")
        step("edit")
        need_budget("edit")
        edited = edit_room(seg_bytes, swatch_bytes, fabric, concept,
                           key, corrective,
                           timeout=call_timeout()).resize(
                               (width, height), Image.BILINEAR)
        step("composite")
        # Composite strictly inside the segmentation mask: whatever the
        # model re-rendered around the item (the wooden base, the wall)
        # keeps the photo's own pixels.
        mask = raw_mask
        if full_mask is not None:
            mask = pillow_guard(edited, mask, key, call_timeout(),
                                (width, height))
        result = paste_strict(room, edited, mask)
        step("verify")
        need_budget("verify")
        small_result = result
        if max(small_result.size) > 1024:
            small_result = result.copy()
            small_result.thumbnail((1024, 1024), Image.LANCZOS)
        scores = verify(swatch_bytes, small_result, fabric, concept, key,
                        timeout=call_timeout())
        attempts = round_no + 1
        checks = swap_checks.run_checks(room, result, mask,
                                        swatch_bytes, pieces=pieces,
                                        min_changed=min_changed_for(fabric))
        kept = checks.pop("_mask", None)
        if kept is not None:
            # Only the recoloured pillows change; untouched ones keep
            # the photo's own pixels, not the model's re-render.
            mask = ImageChops.multiply(mask.convert("L"), kept.convert("L"))
            result = paste_strict(room, edited, mask)
        cand = {"result": result, "mask": mask, "scores": scores,
                "checks": checks}
        if best is None or _rank(cand) > _rank(best):
            best = cand
        if not needs_retry(checks, scores, fabric):
            break
    if not best["checks"]["ok"]:
        raise CheckFailed(best["checks"]["fail"], best["checks"], target)

    # Pillows the model skipped get an aimed pass of their own.
    if target == "cushions" and pieces_missing(best["checks"]):
        step("retry")
        best = refine_pieces(best, room, pieces, swatch_bytes, fabric,
                             concept, key, t_end - time.monotonic(),
                             call_timeout())

    # Seats: recolour the slivers hidden past a throw, a table or the
    # pillows that the strict mask left in the old fabric (best effort,
    # inside the remaining budget, must still pass the checks).
    if concept in SEAT_CONCEPTS:
        step("retry")
        best = refine_seat(best, room, raw_mask, seg_bytes, swatch_bytes,
                           fabric, concept, key,
                           t_end - time.monotonic(), call_timeout())

    best["scores"]["match"] = match_score(best["scores"], fabric)
    result_name = "swap-%s.jpg" % tag
    mask_name = "swapmask-%s.png" % tag
    best["result"].save(os.path.join(out_dir, result_name), "JPEG",
                        quality=90)
    best["mask"].save(os.path.join(out_dir, mask_name))
    base = os.path.relpath(out_dir, BASE_DIR)
    return {"result_url": os.path.join(base, result_name),
            "mask_url": os.path.join(base, mask_name),
            "scores": best["scores"], "attempts": attempts,
            "checks": best["checks"], "target": target}


def match_score(scores, fabric=None):
    """The badge number: the lowest Spark score that applies.

    For a plain fabric the "pattern" score asks "is it plain?" and
    Spark answers 0 when a patterned pillow or rug is in view, so it
    is left out (the ΔE gate already proved the colour).
    """
    keys = ["color", "pattern", "scale", "isolation"]
    if fabric is not None and fabric.get("plain_or_patterned") != "patterned":
        keys.remove("pattern")
    vals = [int(scores.get(k) or 0) for k in keys]
    return min(vals) if vals else 0


def needs_retry(checks, scores, fabric=None):
    """Second edit only when a deterministic check failed or Spark
    rated the motif/scale below RETRY_MIN_SCORE (see RETRY_SCORES).

    For a plain fabric the "pattern" score asks "is it plain?", and
    Spark answers 0 when patterned pillows or a rug are still in view
    (majlis). The ΔE gate already proves a plain colour, so the score
    is skipped there."""
    if not checks.get("ok"):
        return True
    if pieces_missing(checks):
        return True
    keys = RETRY_SCORES
    if fabric is not None and fabric.get("plain_or_patterned") != "patterned":
        keys = tuple(k for k in keys if k != "pattern")
    return min(int(scores.get(k, 0)) for k in keys) < RETRY_MIN_SCORE


def pieces_missing(checks):
    """Pillows the edit left in the old fabric (0 when not per-piece)."""
    pcs = (checks or {}).get("pieces") or {}
    return max(0, int(pcs.get("total", 0)) - int(pcs.get("covered", 0)))


def _pieces_share(checks):
    pcs = (checks or {}).get("pieces") or {}
    total = int(pcs.get("total", 0))
    return (int(pcs.get("covered", 0)) / float(total)) if total else 1.0


def _rank(cand):
    """Passing checks first, then the share of pillows actually
    recoloured, then the Spark minimum and sum."""
    scores = cand["scores"]
    checks = cand.get("checks", {})
    return (bool(checks.get("ok")), _pieces_share(checks),
            min(scores.values()), sum(scores.values()))


SOFA_CUSHIONS_CONCEPT = "cushions"
# Another seat's mask is cut out of this seat's mask only when it is
# clearly a different piece: at most this share of the seat's area.
OTHER_SEAT_MAX_SHARE = 0.6


def separate_seats(mask, other_records, size):
    """mask minus the other seat (records or a mask), when that other
    seat is a distinct, smaller piece. Never erases the seat itself."""
    if other_records is None or isinstance(other_records, Exception):
        return mask
    try:
        other = other_records if isinstance(other_records, Image.Image) \
            else (sam_mask(other_records, size) if other_records else None)
    except (SwapError, sam_codec.MaskError):
        return mask
    if other is None:
        return mask
    seat = _mask_coverage(mask, size)
    share = _mask_coverage(ImageChops.multiply(mask.convert("L"), other.convert("L")), size) / max(1e-6, seat)
    if share <= 0 or share > OTHER_SEAT_MAX_SHARE:
        return mask
    cut = ImageChops.subtract(mask.convert("L"), other.convert("L"))
    if _mask_coverage(cut, size) < 0.3 * seat:
        return mask
    return cut
SOFA_ARM_CONCEPT = "armrest"
SOFA_LEGS_CONCEPT = "sofa legs"
# Opening kernel as a share of the long side (on an 800 px copy):
# removes slivers thinner than ~1.4% of the photo, keeps arms (~3%).
OPEN_FRAC = 0.014


def open_mask(mask, frac=OPEN_FRAC, work_side=800):
    """Morphological opening (erode then dilate) on a small copy: drops
    hairlines and slivers narrower than the kernel, keeps the body."""
    w, h = mask.size
    scale = min(1.0, work_side / float(max(w, h)))
    small = mask.convert("L")
    if scale < 1.0:
        small = small.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                             Image.BILINEAR)
    small = small.point(lambda v: 255 if v > 127 else 0)
    k = max(3, int(max(small.size) * frac) | 1)
    opened = small.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
    if scale < 1.0:
        opened = opened.resize((w, h), Image.BILINEAR)
    opened = opened.point(lambda v: 255 if v > 127 else 0)
    # Never grow past the input: the dilation back stays inside it.
    return ImageChops.multiply(mask.convert("L"), opened)
SOFA_BACK_CONCEPT = "sofa backrest"
# Enclosed gaps up to this share of the mask are filled (a shadow patch
# on a back cushion); anything larger is a real opening.
FILL_HOLE_MAX_SHARE = 0.08


def _box_touches(record, records, margin=0.05):
    """True when the record's box overlaps any of the records' boxes
    widened by margin of their size."""
    try:
        x0, y0, x1, y1 = (float(v) for v in record.get("box"))
    except (TypeError, ValueError):
        return False
    for other in records or []:
        try:
            ox0, oy0, ox1, oy1 = (float(v) for v in other.get("box"))
        except (TypeError, ValueError):
            continue
        mx = (ox1 - ox0) * margin
        my = (oy1 - oy0) * margin
        if (x0 <= ox1 + mx and x1 >= ox0 - mx
                and y0 <= oy1 + my and y1 >= oy0 - my):
            return True
    return False


def fill_holes(mask, max_share=FILL_HOLE_MAX_SHARE, work_side=800):
    """Fill background regions not connected to the image border, each
    at most max_share of the mask's area. Computed on a small copy."""
    from PIL import ImageDraw
    w, h = mask.size
    scale = min(1.0, work_side / float(max(w, h)))
    small = mask.convert("L")
    if scale < 1.0:
        small = small.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                             Image.BILINEAR)
    binary = small.point(lambda v: 255 if v > 127 else 0)
    padded = Image.new("L", (binary.size[0] + 2, binary.size[1] + 2), 0)
    padded.paste(binary, (1, 1))
    # Flood the outside with a marker; what stays 0 is enclosed.
    ImageDraw.floodfill(padded, (0, 0), 128)
    arr = np.asarray(padded)
    enclosed = (arr == 0)
    if not enclosed.any():
        return mask
    mask_area = max(1, int((arr == 255).sum()))
    # Label each enclosed blob by flood-filling it; skip ones too big.
    holes = np.zeros_like(enclosed)
    work = padded.copy()
    ys, xs = np.nonzero(enclosed)
    for y, x in zip(ys, xs):
        if work.getpixel((int(x), int(y))) != 0:
            continue
        before = np.asarray(work).copy()
        ImageDraw.floodfill(work, (int(x), int(y)), 64)
        blob = (np.asarray(work) == 64) & (before == 0)
        if blob.sum() <= max_share * mask_area:
            holes |= blob
        # Mark visited either way so the loop moves on.
        work = Image.fromarray(np.where(blob, 32, np.asarray(work)).astype(np.uint8))
    filled = np.where(holes[1:-1, 1:-1], 255, np.asarray(binary)).astype(np.uint8)
    out = Image.fromarray(filled)
    if scale < 1.0:
        out = out.resize((w, h), Image.BILINEAR)
    return ImageChops.lighter(mask.convert("L"), out)
# SAM's "sofa" record includes an exposed wooden plinth/frame; a sofa
# swap must leave the wood alone, so it is segmented and cut out.
SOFA_WOOD_CONCEPT = "wooden base of the sofa"
# A wood mask this large relative to the sofa is a mis-segmentation
# (the whole sofa), not a frame: ignore it rather than erase the sofa.
WOOD_MAX_SHARE = 0.5


def segment_with_fallback(seg_bytes, concept, target, key, timeout):
    """SAM records for the concept, else for the target's fallback
    prompts (a bed pillow for cushions, a bench seat for sofa)."""
    records = segment(seg_bytes, concept, key, timeout=timeout)
    if records:
        return records
    from app.services.targets import FALLBACK_PROMPTS
    for alt in FALLBACK_PROMPTS.get(target, ()):
        try:
            records = segment(seg_bytes, alt, key, timeout=timeout)
        except SwapError:
            records = []
        if records:
            return records
    return []


def sofa_full_mask(seg_bytes, size, key, timeout, keep_pillows=True):
    """Sofa mask including its seat and back cushions.

    SAM's "sofa" record leaves the loose back cushions out, so a sofa
    swap left them in the old fabric. The bare "cushions" concept
    segments every cushion (seat, back and throw pillows); the union is
    the upholstered sofa. With keep_pillows the throw pillows are cut
    back out so the sofa swap leaves them alone. A chained sofa +
    pillows swap keeps them out too: on a sofa result that repainted
    the pillows in the sofa fabric SAM cannot tell a pillow from the
    back cushion behind it, and the pillow mask swallows the cushion
    corner (a ghost second pillow). The old pillow's fringe is covered
    by dilating the pillow mask a little before the pillow edit.
    """
    from concurrent.futures import ThreadPoolExecutor
    concepts = [TARGET_CONCEPTS["sofa"], SOFA_CUSHIONS_CONCEPT,
                SOFA_WOOD_CONCEPT, SOFA_ARM_CONCEPT, SOFA_BACK_CONCEPT,
                TARGET_CONCEPTS["armchair"], SOFA_LEGS_CONCEPT]
    if keep_pillows:
        concepts.append(TARGET_CONCEPTS["cushions"])

    def one(concept):
        try:
            return segment(seg_bytes, concept, key, timeout=timeout)
        except SwapError as exc:
            if concept == TARGET_CONCEPTS["sofa"]:
                raise
            return exc

    # The SAM calls are independent: run them side by side (one
    # call's latency instead of three or four).
    with ThreadPoolExecutor(max_workers=len(concepts)) as pool:
        outs = list(pool.map(one, concepts))
    records = outs[0]
    if not records:
        # No "sofa" as such: a bench seat, settee or window seat still
        # has an upholstered cushion SAM can name.
        from app.services.targets import FALLBACK_PROMPTS
        for alt in FALLBACK_PROMPTS["sofa"]:
            try:
                records = segment(seg_bytes, alt, key, timeout=timeout)
            except SwapError:
                records = []
            if records:
                break
    if not records:
        raise SwapError("could not find the sofa in this photo")
    mask = sam_mask(records, size)
    extra = outs[1]
    if extra and not isinstance(extra, Exception):
        try:
            mask = ImageChops.lighter(mask, sam_mask(extra, size))
        except (SwapError, sam_codec.MaskError):
            pass
    # The arm panels: SAM's "sofa" record drops an outer arm face that
    # is lit or worn differently (the whole right arm stayed in the old
    # fabric). Only arms that touch the sofa's own box count, so a
    # chair's arm elsewhere in the room is left alone.
    # Likewise the backrest: a shadow or stain on a back cushion makes
    # SAM's "sofa" and "cushions" records stop short of it, and the
    # patch stayed in the old fabric. "sofa backrest" names the whole
    # back cushion, stain included.
    for part in (outs[3], outs[4]):
        if not part or isinstance(part, Exception):
            continue
        near = [r for r in part if _box_touches(r, records)]
        if near:
            try:
                mask = ImageChops.lighter(mask, sam_mask(near, size))
            except (SwapError, sam_codec.MaskError):
                pass
    # A shadow or stain on a cushion comes back as a hole in the
    # union; anything fully enclosed by upholstery is upholstery.
    mask = fill_holes(mask, FILL_HOLE_MAX_SHARE)
    wood = outs[2]
    if wood and not isinstance(wood, Exception):
        try:
            wood_mask = sam_mask(wood, size)
            share = _mask_coverage(wood_mask, size) / max(
                1e-6, _mask_coverage(mask, size))
            if share <= WOOD_MAX_SHARE:
                mask = ImageChops.subtract(mask, wood_mask)
        except (SwapError, sam_codec.MaskError):
            pass
    # A sofa and an armchair in one room: SAM's "sofa" record often
    # swallows the armchair, the edit then recolours only the sofa and
    # the coverage check fails. The armchair is cut back out when it is
    # a separate piece (well under the sofa's own area).
    mask = separate_seats(mask, outs[5], size)
    # The legs are wood too: the "wooden base" record is the rail only,
    # and a leg sliver stayed attached to the body (it showed in the
    # judge outline). Cut the leg records out, then an opening drops any
    # hairline left along a leg or a frame edge.
    legs = outs[6]
    if legs and not isinstance(legs, Exception):
        try:
            leg_mask = sam_mask(legs, size)
            if _mask_coverage(leg_mask, size) <= WOOD_MAX_SHARE * max(
                    1e-6, _mask_coverage(mask, size)):
                mask = ImageChops.subtract(mask, leg_mask)
        except (SwapError, sam_codec.MaskError):
            pass
    mask = open_mask(mask, OPEN_FRAC)
    if keep_pillows:
        pillows = outs[7]
        if pillows and not isinstance(pillows, Exception):
            try:
                mask = ImageChops.subtract(mask, sam_mask(pillows, size))
            except (SwapError, sam_codec.MaskError):
                pass
    return records, mask


def pillows_contrast(room, pillow_mask, sofa_swatches):
    """True when the new sofa fabric clearly contrasts with the old
    pillows (hue/chroma ΔE > 12 or |ΔL| > 20), i.e. when segmenting
    the pillows on the sofa result would be unambiguous."""
    if not sofa_swatches:
        return False
    old = swap_checks.mean_lab(swap_checks._small(room, "RGB"),
                               pillow_mask.convert("L").resize(
                                   swap_checks._small(room, "RGB").size,
                                   Image.NEAREST))
    if old is None:
        return False
    for raw in sofa_swatches:
        want = swap_checks.swatch_lab(raw)
        if want is None:
            continue
        de, dl, _ = swap_checks.colour_match(old, want)
        if de > 12 or abs(dl) > 20:
            return True
    return False


def _room_tag(room_bytes):
    import hashlib
    return hashlib.md5(room_bytes).hexdigest()[:12]


def _cache_paths(out_dir, tag, target, code):
    base = "swapmulti-%s-%s-%s" % (tag, target, code)
    return (os.path.join(out_dir, base + ".jpg"),
            os.path.join(out_dir, base + "-mask.png"),
            os.path.join(out_dir, base + ".json"))


def _union_of(records, size):
    width, height = size
    boxes = []
    for record in records:
        x1, y1, x2, y2 = record["box"]
        fw, fh = record["frame_size"]
        boxes.append((int(x1 / fw * width), int(y1 / fh * height),
                      int(x2 / fw * width), int(y2 / fh * height)))
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


# Bump when mask semantics change: stale on-disk items (garbage
# full-frame masks) must be recomputed, never composited again.
MASK_CACHE_VERSION = 5


def swap_multi(room_path, assignments, api_key=None, out_dir=None,
               on_step=None, budget=60, _now=None):
    """Swap several items in one photo, largest item first.

    assignments is a list of {"target": ..., "code": ...}. Every item
    is edited from the ORIGINAL photo in a worker thread (segment,
    edit, verify — one corrective retry) inside its own wall budget
    (default 60s per item; an item that cannot finish in budget
    becomes a skip, never a hang). Verified items composite onto the
    original in one pass, largest first, each strictly inside its
    own mask. Failures become skips (reported, never fatal unless
    everything fails).

    Results are cached on disk per (image, target, code): a repeat run
    pastes the cached item through its own mask without model calls.
    Returns {"results": [{target, code, result_url, mask_url, scores,
    attempts, cached}], "skipped": [...], "final_url": ...}.
    """
    def step(label):
        if on_step:
            on_step(label)
    key = api_key or require_api_key()
    if not assignments:
        raise SwapError("no assignments")
    jobs = []
    for item in assignments:
        target = ((item or {}).get("target") or "").lower()
        code = (item or {}).get("code", "")
        if target not in TARGET_CONCEPTS:
            raise SwapError("unknown target: %s" % target)
        fabric = get_fabric(code)
        if not fabric:
            raise SwapError("unknown fabric code: %s" % code)
        jobs.append({"target": target, "code": code, "fabric": fabric,
                       "budget": budget, "_now": _now})
    path = room_path if os.path.isabs(room_path) else os.path.join(
        BASE_DIR, room_path)
    with open(path, "rb") as f:
        room_bytes = f.read()
    room = Image.open(io.BytesIO(room_bytes)).convert("RGB")
    width, height = room.size
    rtag = _room_tag(room_bytes)

    out_dir = out_dir or os.path.join(UPLOAD_DIR, "swap")
    os.makedirs(out_dir, exist_ok=True)

    # Layering: when the sofa and the pillows are both assigned, the
    # pillows are edited ON the sofa result (not the original), so any
    # old-pillow pixel the new pillow does not cover shows the new sofa
    # fabric, never the old one. The pillow cache key carries the sofa
    # code for that reason.
    by_target = {j["target"]: j for j in jobs}
    chained = "sofa" in by_target and "cushions" in by_target
    for job in jobs:
        job["ctag"] = rtag
        job["chained"] = chained
        if chained and job["target"] == "cushions":
            job["ctag"] = "%s-on-%s" % (rtag, by_target["sofa"]["code"])
        elif chained and job["target"] == "sofa":
            # v2: the sofa stage keeps the pillows out of its mask.
            job["ctag"] = "%s-under-pillows2" % rtag
    for job in jobs:
        img_path, mask_path, meta_path = _cache_paths(
            out_dir, job["ctag"], job["target"], job["code"])
        if (os.path.exists(img_path) and os.path.exists(mask_path)
                and os.path.exists(meta_path)):
            try:
                with open(meta_path, encoding="utf-8") as _mf:
                    _meta_v = json.load(_mf).get("v", 1)
            except (ValueError, OSError):
                _meta_v = 0
            if _meta_v != MASK_CACHE_VERSION:
                job["cache"] = None
                continue
            box = Image.open(mask_path).convert("L").getbbox() or (
                0, 0, width, height)
            job["area"] = max(0, box[2] - box[0]) * max(
                0, box[3] - box[1])
            job["cache"] = (img_path, mask_path, meta_path)
        else:
            job["cache"] = None

    def run_one(job):
        """One item end to end from the ORIGINAL photo (retried once).

        Returns (entry, skip, img, mask, area); entry is None on skip.
        Each network call is bounded to 60s; failures become skips.
        """
        target, fabric, code = (job["target"], job["fabric"],
                                job["code"])
        concept = TARGET_CONCEPTS[target]
        swatch_path = os.path.join(BASE_DIR, fabric.get("image", ""))
        with open(swatch_path, "rb") as f:
            swatch_bytes = f.read()
        img_path, mask_path, meta_path = _cache_paths(
            out_dir, job["ctag"], target, code)
        # The edit input: the original photo, or (pillows after the
        # sofa) the sofa result. Vision calls get a capped copy of the
        # ORIGINAL; the edit and the composite use the base.
        base_bytes = job.get("base_bytes") or room_bytes
        union_mask = job.get("union_mask")
        seg_bytes = _small_copy(room_bytes, 1600)
        seg_base_bytes = _small_copy(base_bytes, 1600) \
            if base_bytes is not room_bytes else None
        clock = job.get("_now") or time.monotonic
        item_budget = float(job.get("budget", 60))
        t_end = clock() + item_budget
        best = None
        attempts = 0
        last_err = "unknown error"

        def call_timeout():
            return max(5.0, min(60.0, t_end - clock()))

        for _ in range(2):
            if t_end - clock() < 10:
                last_err = ("item timed out after %ds" %
                            int(item_budget))
                break
            try:
                step("segment")
                if target == "sofa":
                    # Always leave the throw pillows out, chained or
                    # not: a sofa result that repaints the pillows in the
                    # sofa fabric gives SAM nothing to separate them from
                    # the back cushions, and the pillow mask then swallows
                    # a cushion corner (the ghost second pillow).
                    records, mask = sofa_full_mask(
                        seg_bytes, (width, height), key, call_timeout(),
                        keep_pillows=True)
                else:
                    records = segment_with_fallback(
                        seg_bytes, concept, target, key, call_timeout())
                    if not records:
                        raise SwapError("could not find the %s in this "
                                        "photo" % concept)
                    mask = sam_mask(records, (width, height))
                    if seg_base_bytes is not None and pillows_contrast(
                            room, mask, job.get("extra_swatches")):
                        # Chained pillows on a contrasting new sofa are
                        # re-segmented on the SOFA RESULT: on the
                        # all-one-fabric original SAM folds the sofa's
                        # back-cushion corner into the pillow and it
                        # gets the pillow fabric too (a ghost second
                        # pillow). On a same-tone sofa the original
                        # segmentation stays (no contrast to gain).
                        try:
                            rec2 = segment(seg_base_bytes, concept, key,
                                           timeout=call_timeout())
                            mask2 = sam_mask(rec2, (width, height)) \
                                if rec2 else None
                        except (SwapError, sam_codec.MaskError):
                            mask2 = None
                        if mask2 is not None and mask2.getbbox():
                            # The old pillow keeps its photo pixels on the
                            # sofa result; a little dilation lets the edit
                            # cover its fringe too.
                            k = max(3, int(max(width, height) * 0.008) | 1)
                            mask2 = mask2.filter(ImageFilter.MaxFilter(k))
                            records, mask = rec2, mask2
                if job.get("sofa_mask") is not None:
                    union_mask = ImageChops.lighter(job["sofa_mask"], mask)
                area = 0
                for rec in records:
                    try:
                        bx0, by0, bx1, by1 = (rec or {}).get(
                            "box", (0, 0, 0, 0))
                        area = max(area, max(0, bx1 - bx0) * max(
                            0, by1 - by0))
                    except (TypeError, ValueError):
                        continue
                step("edit")
                corrective = None
                if best is not None:
                    corrective = _corrective(best["scores"], concept,
                                             best.get("checks"))
                    step("retry")
                edited = edit_room(_small_copy(base_bytes, 1600),
                                   swatch_bytes, fabric, concept, key,
                                   corrective, timeout=call_timeout())
                step("composite")
                base_img = Image.open(
                    io.BytesIO(base_bytes)).convert("RGB")
                if target == "sofa":
                    mask = pillow_guard(edited, mask, key, call_timeout(),
                                        (width, height))
                cand = paste_strict(base_img, edited, mask)
                step("verify")
                small_cand = cand
                if max(small_cand.size) > 1024:
                    small_cand = cand.copy()
                    small_cand.thumbnail((1024, 1024),
                                         Image.LANCZOS)
                scores = verify(swatch_bytes, small_cand, fabric,
                                concept, key,
                                timeout=call_timeout())
                attempts += 1
                checks = swap_checks.run_checks(
                    room, cand, mask, swatch_bytes, base=base_img,
                    residue_mask=union_mask,
                    extra_swatches=job.get("extra_swatches") or (),
                    pieces=(record_masks(records, (width, height))
                            if target == "cushions" else False),
                    min_changed=min_changed_for(fabric))
                kept = checks.pop("_mask", None)
                if kept is not None:
                    mask = ImageChops.multiply(mask.convert("L"),
                                               kept.convert("L"))
                    cand = paste_strict(base_img, edited, mask)
                cand_entry = {"result": cand, "mask": mask,
                              "scores": scores, "area": area,
                              "checks": checks}
                if best is None or _rank(cand_entry) > _rank(best):
                    best = cand_entry
                if not needs_retry(checks, scores, fabric):
                    break
            except Exception as exc:  # noqa: BLE001 - one bad item
                last_err = str(exc)  # must become a skip, never a 500
                continue
        if best is not None and not best["checks"]["ok"]:
            # Deterministic check failed twice: honest skip with the
            # reason, never composited as if it worked.
            return (None,
                    {"target": target, "code": code,
                     "reason": best["checks"]["fail"],
                     "checks": best["checks"],
                     "scores": best["scores"], "attempts": attempts},
                    None, None, -1)
        if best is None:
            return (None,
                    {"target": target, "code": code,
                     "reason": last_err}, None, None, -1)
        if concept in SEAT_CONCEPTS:
            step("retry")
            best = refine_seat(
                best, room, best["mask"], seg_bytes, swatch_bytes, fabric,
                concept, key, t_end - clock(), call_timeout(),
                check_kwargs={"base": Image.open(io.BytesIO(
                    base_bytes)).convert("RGB"),
                              "residue_mask": union_mask,
                              "extra_swatches": job.get(
                                  "extra_swatches") or ()})
        best["scores"]["match"] = match_score(best["scores"], fabric)
        best["result"].save(img_path, "JPEG", quality=90)
        best["mask"].save(mask_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"scores": best["scores"],
                       "attempts": attempts,
                       "checks": best["checks"],
                       "v": MASK_CACHE_VERSION}, f)
        base = os.path.relpath(out_dir, BASE_DIR)
        entry = {"target": target, "code": code,
                 "result_url": os.path.join(
                     base, os.path.basename(img_path)),
                 "mask_url": os.path.join(
                     base, os.path.basename(mask_path)),
                 "scores": best["scores"], "attempts": attempts,
                 "checks": best["checks"], "cached": False}
        return entry, None, best["result"], best["mask"], best["area"]

    # One failing item must not kill the whole room: segmentation or
    # edit failures are collected as skips; the rest still swap.
    results = []
    skipped = []
    pieces = []
    for job in jobs:
        if job["cache"] is not None:
            img_path, mask_path, meta_path = job["cache"]
            item_img = Image.open(img_path).convert("RGB")
            item_mask = Image.open(mask_path).convert("L")
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                scores = meta.get("scores", {})
                attempts = int(meta.get("attempts", 0))
                checks = meta.get("checks") or {}
            except (ValueError, TypeError):
                scores, attempts, checks = {}, 0, {}
            base = os.path.relpath(out_dir, BASE_DIR)
            results.append({
                "target": job["target"], "code": job["code"],
                "result_url": os.path.join(
                    base, os.path.basename(img_path)),
                "mask_url": os.path.join(
                    base, os.path.basename(mask_path)),
                "scores": scores, "attempts": attempts,
                "checks": checks, "cached": True})
            pieces.append((item_img, item_mask, job["area"],
                           job["target"]))
    pending = [j for j in jobs if j["cache"] is None]

    def collect(outcomes):
        for entry, skip, img, mask, area in outcomes:
            if entry is not None:
                results.append(entry)
                pieces.append((img, mask, area, entry["target"]))
            else:
                skipped.append(skip)

    if chained:
        # Stage 1: everything but the pillows (sofa included) from the
        # original. Stage 2: pillows on the sofa result, with the
        # residue check over sofa ∪ pillows against the ORIGINAL.
        first = [j for j in pending if j["target"] != "cushions"]
        later = [j for j in pending if j["target"] == "cushions"]
        if first:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(
                    max_workers=max(1, min(4, len(first)))) as pool:
                collect(list(pool.map(run_one, first)))
        sofa_piece = next((p for p in pieces if p[3] == "sofa"), None)
        if later and sofa_piece is None:
            # Sofa skipped: pillows fall back to the original photo.
            collect([run_one(j) for j in later])
        elif later:
            sofa_img, sofa_mask = sofa_piece[0], sofa_piece[1]
            buf = io.BytesIO()
            sofa_img.save(buf, "JPEG", quality=95)
            sofa_fabric = by_target["sofa"]["fabric"]
            with open(os.path.join(BASE_DIR, sofa_fabric.get("image", "")),
                      "rb") as f:
                sofa_swatch = f.read()
            for j in later:
                j["base_bytes"] = buf.getvalue()
                j["sofa_mask"] = sofa_mask
                j["extra_swatches"] = [sofa_swatch]
            collect([run_one(j) for j in later])
    elif pending:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(
                max_workers=max(1, min(4, len(pending)))) as pool:
            collect(list(pool.map(run_one, pending)))
    if not results:
        reason = skipped[0]["reason"] if skipped else "no assignments"
        raise SwapError("multi-swap failed: %s" % reason)
    # One pass, largest first, each strictly inside its own mask.
    pieces.sort(key=lambda piece: piece[2], reverse=True)
    if chained:
        # Sofa (edited from the original) first, pillows (edited on the
        # sofa result) last: never let a cached sofa paste over them.
        pieces.sort(key=lambda piece: 1 if piece[3] == "cushions" else 0)
    final = room.copy()
    for img, mask, _, _ in pieces:
        final = paste_strict(final, img, mask)
    final_name = "swapmulti-%s-final.jpg" % uuid.uuid4().hex
    final.save(os.path.join(out_dir, final_name), "JPEG", quality=90)
    base = os.path.relpath(out_dir, BASE_DIR)
    areas = {}
    for _, _, area, target in pieces:
        areas.setdefault(target, area)
    results.sort(key=lambda r: areas.get(r["target"], 0),
                 reverse=True)
    return {"results": results, "skipped": skipped,
            "final_url": os.path.join(base, final_name)}
