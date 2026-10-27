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


def segment(image_bytes, concept, api_key=None):
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
        resp = _post_json(SAM_URL, body, key, timeout=120)
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
              api_key=None, corrective=None):
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
        resp = _post_json(EDIT_URL, body, key, timeout=300)
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


def verify(swatch_bytes, result_image, fabric, piece_label, api_key=None):
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
                          body, key, timeout=120)
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
