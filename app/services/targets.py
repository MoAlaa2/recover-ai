"""Multi-object targets: list the changeable items in a room photo.

Spark lists which of sofa / cushions / curtains are clearly visible;
SAM 3.1 segments each one. The sofa mask has the cushions mask
subtracted so reupholstering the sofa never repaints the pillows.
Masks are saved under uploads/masks/ for the canvas overlays.
"""
import base64
import io
import json
import os
import time
import urllib.request
import uuid

from PIL import Image, ImageChops

from app.core.config import (BASE_DIR, CHAT_URL, SPARK_MODEL, UPLOAD_DIR,
                             require_api_key)
from app.services import sam_codec
from app.services.swap import sam_mask, segment

TARGET_TYPES = ("sofa", "cushions", "curtains")

TARGET_LABELS = {
    "sofa": ("Sofa", "الكنبة"),
    "cushions": ("Cushions", "الوسائد"),
    "curtains": ("Curtains", "الستائر"),
}

LIST_TIMEOUT = 60


def _call_vision(messages):
    """Low-level Spark vision call. Monkeypatch this in tests."""
    payload = {"model": SPARK_MODEL, "messages": messages}
    last_err = None
    for attempt in range(2):
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                CHAT_URL, data=data,
                headers={"Authorization": "Bearer " + require_api_key(),
                         "Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req,
                                       timeout=LIST_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - retry once, then raise
            last_err = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("target listing failed: %s" % last_err)


def list_types(image_path):
    """Which of sofa/cushions/curtains are clearly visible. Returns list."""
    from app.services.consultant import vision_jpeg_bytes
    path = image_path if os.path.isabs(image_path) else \
        os.path.join(BASE_DIR, image_path)
    b64 = base64.b64encode(vision_jpeg_bytes(path)).decode("ascii")
    ask = ("Which of these are clearly visible in this room photo: "
           "sofa, cushions (pillows on a sofa or chairs), curtains? "
           'Reply with JSON only: {"items": ["sofa", ...]}.')
    messages = [{"role": "user", "content": [
        {"type": "text", "text": ask},
        {"type": "image_url",
         "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]
    body = _call_vision(messages)
    text = body["choices"][0]["message"]["content"] or ""
    try:
        items = json.loads(text[text.find("{"):text.rfind("}") + 1])
        found = items.get("items", [])
    except (ValueError, IndexError, AttributeError):
        return []
    return [t for t in found if t in TARGET_TYPES]


def masks_for(image_path, types, api_key=None):
    """Segment each type. Returns {type: PIL mask}, sofa minus cushions."""
    key = api_key or require_api_key()
    path = image_path if os.path.isabs(image_path) else \
        os.path.join(BASE_DIR, image_path)
    with open(path, "rb") as f:
        room_bytes = f.read()
    room = Image.open(io.BytesIO(room_bytes)).convert("RGB")
    masks = {}
    for target in types:
        if target not in TARGET_TYPES:
            continue
        try:
            records = segment(room_bytes, target, key)
        except Exception:  # noqa: BLE001 - one missing item skips
            continue
        if not records:
            continue
        try:
            masks[target] = sam_mask(records, room.size)
        except sam_codec.MaskError:
            continue
    if "sofa" in masks and "cushions" in masks:
        masks["sofa"] = ImageChops.subtract(masks["sofa"],
                                            masks["cushions"])
    return masks


def detect_targets(image_path, api_key=None):
    """List + segment + persist masks. Returns target dicts for the API."""
    types = list_types(image_path)
    if not types:
        return []
    masks = masks_for(image_path, types, api_key)
    out_dir = os.path.join(UPLOAD_DIR, "masks")
    os.makedirs(out_dir, exist_ok=True)
    tag = uuid.uuid4().hex
    targets = []
    for target in types:
        mask = masks.get(target)
        if mask is None:
            continue
        name = "mask-%s-%s.png" % (tag, target)
        mask.save(os.path.join(out_dir, name))
        box = mask.getbbox() or (0, 0, mask.size[0], mask.size[1])
        label_en, label_ar = TARGET_LABELS[target]
        targets.append({"id": target, "type": target,
                        "label_en": label_en, "label_ar": label_ar,
                        "mask_url": os.path.join("uploads", "masks", name),
                        "box": list(box)})
    return targets
