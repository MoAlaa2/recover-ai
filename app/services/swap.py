"""Fabric swap: SAM 3.1 segments the piece, Muse Image reupholsters it,
a feathered composite keeps the rest of the room pixel-identical, and
muse-spark-1.3 verifies color, pattern, scale and isolation (0-10 each).

Pipeline notes:
- SAM boxes localize the piece reliably; the paste mask is the dilated
  union box intersected with a dilated change map (|edit - original|),
  feathered. This pastes only what the edit actually changed near the
  piece, so surroundings the edit preserved stay pixel-identical.
- The raw merged SAM mask is saved alongside for debugging.
- Every model call has a timeout and one retry.
"""
import base64
import io
import json
import os
import time
import urllib.request
import uuid

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from app.core.config import (BASE_DIR, CHAT_URL, SPARK_MODEL, UPLOAD_DIR,
                             require_api_key)
from app.services import sam_codec
from app.services.catalog import get_fabric

SAM_URL = "https://api.meta.ai/v1/responses"
SAM_MODEL = "sam-3.1"
EDIT_URL = "https://api.meta.ai/v1/images/edits"
EDIT_MODEL = "muse-image-1.0"

TARGET_CONCEPTS = {
    "sofa": "sofa",
    "armchair": "armchair",
    "curtains": "curtains",
    "cushions": "cushions",
}

VERIFY_LABELS = ("color", "pattern", "scale", "isolation")


class SwapError(RuntimeError):
    """Swap failed (bad input, segmentation, edit or verify error)."""


def _post_json(url, payload, api_key, timeout):
    """POST JSON with one retry. Returns the parsed response body."""
    data = json.dumps(payload).encode("utf-8")
    last_err = None
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
            time.sleep(2 * (attempt + 1))
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


def segment(image_bytes, concept, api_key=None, timeout=120):
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
        resp = _post_json(SAM_URL, body, key, timeout=timeout)
    except SwapError as exc:
        raise SwapError("segmentation failed: %s" % exc)
    try:
        return sam_codec.parse_output_text(_output_text(resp))
    except sam_codec.MaskError as exc:
        raise SwapError("bad segmentation response: %s" % exc)


def sam_mask(records, size):
    """Merge record masks into one room-sized L image (0/255)."""
    width, height = size
    merged = None
    for record in records:
        try:
            raster, w, h = sam_codec.decode_record(record)
        except sam_codec.MaskError:
            continue
        arr = np.frombuffer(bytes(raster), dtype=np.uint8).reshape(h, w)
        layer = Image.frombytes(
            "L", (w, h), (arr * 255).astype(np.uint8).tobytes())
        layer = layer.resize(size, Image.BILINEAR).point(lambda v: 255
                                                         if v > 127 else 0)
        merged = layer if merged is None else Image.composite(
            Image.new("L", size, 255), merged, layer)
    if merged is None:
        raise SwapError("no usable segmentation mask")
    return merged


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
    if corrective:
        text += " Correction for this retry: %s" % corrective
    return text


def edit_room(room_bytes, swatch_bytes, fabric, piece_label,
              api_key=None, corrective=None, timeout=300):
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
        resp = _post_json(EDIT_URL, body, key, timeout=timeout)
        raw = base64.b64decode(resp["data"][0]["b64_json"])
    except (SwapError, KeyError, ValueError) as exc:
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
           timeout=120):
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
                          body, key, timeout=timeout)
        content = resp["choices"][0]["message"]["content"] or ""
        scores = json.loads(content[content.find("{"):content.rfind("}")
                                        + 1])
        return {k: max(0, min(10, int(scores.get(k, 0))))
                for k in VERIFY_LABELS}
    except (SwapError, KeyError, ValueError) as exc:
        raise SwapError("swap verification failed: %s" % exc)


def _corrective(scores, concept):
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

    step("segment")
    records = segment(room_bytes, concept, key)
    if not records:
        raise SwapError("could not find the %s in this photo" % concept)
    boxes = []
    for record in records:
        x1, y1, x2, y2 = record["box"]
        fw, fh = record["frame_size"]
        boxes.append((int(x1 / fw * width), int(y1 / fh * height),
                      int(x2 / fw * width), int(y2 / fh * height)))
    union = (min(b[0] for b in boxes), min(b[1] for b in boxes),
             max(b[2] for b in boxes), max(b[3] for b in boxes))
    raw_mask = sam_mask(records, (width, height))

    out_dir = out_dir or os.path.join(UPLOAD_DIR, "swap")
    os.makedirs(out_dir, exist_ok=True)
    tag = uuid.uuid4().hex
    raw_mask.save(os.path.join(out_dir, "mask-%s.png" % tag))

    best = None
    attempts = 0
    for round_no in range(2):
        corrective = None
        if best is not None:
            corrective = _corrective(best["scores"], concept)
            step("retry")
        step("edit")
        edited = edit_room(room_bytes, swatch_bytes, fabric, concept,
                           key, corrective).resize((width, height),
                                                   Image.BILINEAR)
        step("composite")
        mask = paste_mask(room, edited, union)
        result = room.copy()
        result.paste(edited, (0, 0), mask)
        step("verify")
        scores = verify(swatch_bytes, result, fabric, concept, key)
        attempts = round_no + 1
        cand = {"result": result, "mask": mask, "scores": scores}
        if best is None or (min(scores.values()), sum(scores.values())) > (
                min(best["scores"].values()),
                sum(best["scores"].values())):
            best = cand
        if min(scores.values()) >= 7:
            break

    result_name = "swap-%s.jpg" % tag
    mask_name = "swapmask-%s.png" % tag
    best["result"].save(os.path.join(out_dir, result_name), "JPEG",
                        quality=90)
    best["mask"].save(os.path.join(out_dir, mask_name))
    base = os.path.relpath(out_dir, BASE_DIR)
    return {"result_url": os.path.join(base, result_name),
            "mask_url": os.path.join(base, mask_name),
            "scores": best["scores"], "attempts": attempts}


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

    for job in jobs:
        img_path, mask_path, meta_path = _cache_paths(
            out_dir, rtag, job["target"], job["code"])
        if (os.path.exists(img_path) and os.path.exists(mask_path)
                and os.path.exists(meta_path)):
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
            out_dir, rtag, target, code)
        # Vision calls get a capped copy; the edit and the composite
        # always use the full-resolution original.
        seg_bytes = _small_copy(room_bytes, 1600)
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
                records = segment(seg_bytes, concept, key,
                                  timeout=call_timeout())
                if not records:
                    raise SwapError("could not find the %s in this "
                                    "photo" % concept)
                mask = sam_mask(records, (width, height))
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
                    corrective = _corrective(best["scores"], concept)
                    step("retry")
                edited = edit_room(room_bytes, swatch_bytes, fabric,
                                   concept, key, corrective,
                                   timeout=call_timeout())
                step("composite")
                base_img = Image.open(
                    io.BytesIO(room_bytes)).convert("RGB")
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
                if best is None or (
                        min(scores.values()),
                        sum(scores.values())) > (
                        min(best["scores"].values()),
                        sum(best["scores"].values())):
                    best = {"result": cand, "mask": mask,
                            "scores": scores, "area": area}
                if min(scores.values()) >= 7:
                    break
            except Exception as exc:  # noqa: BLE001 - one bad item
                last_err = str(exc)  # must become a skip, never a 500
                continue
        if best is None:
            return (None,
                    {"target": target, "code": code,
                     "reason": last_err}, None, None, -1)
        best["result"].save(img_path, "JPEG", quality=90)
        best["mask"].save(mask_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"scores": best["scores"],
                       "attempts": attempts}, f)
        base = os.path.relpath(out_dir, BASE_DIR)
        entry = {"target": target, "code": code,
                 "result_url": os.path.join(
                     base, os.path.basename(img_path)),
                 "mask_url": os.path.join(
                     base, os.path.basename(mask_path)),
                 "scores": best["scores"], "attempts": attempts,
                 "cached": False}
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
            except (ValueError, TypeError):
                scores, attempts = {}, 0
            base = os.path.relpath(out_dir, BASE_DIR)
            results.append({
                "target": job["target"], "code": job["code"],
                "result_url": os.path.join(
                    base, os.path.basename(img_path)),
                "mask_url": os.path.join(
                    base, os.path.basename(mask_path)),
                "scores": scores, "attempts": attempts,
                "cached": True})
            pieces.append((item_img, item_mask, job["area"],
                           job["target"]))
    pending = [j for j in jobs if j["cache"] is None]
    if pending:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(
                max_workers=max(1, min(4, len(pending)))) as pool:
            for entry, skip, img, mask, area in pool.map(
                    run_one, pending):
                if entry is not None:
                    results.append(entry)
                    pieces.append((img, mask, area,
                                   entry["target"]))
                else:
                    skipped.append(skip)
    if not results:
        reason = skipped[0]["reason"] if skipped else "no assignments"
        raise SwapError("multi-swap failed: %s" % reason)
    # One pass, largest first, each strictly inside its own mask.
    pieces.sort(key=lambda piece: piece[2], reverse=True)
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
