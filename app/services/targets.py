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

CHOICE_WORDS = {
    "sofa": ("sofa", "كنبة", "كنبه", "sofas"),
    "cushions": ("cushion", "cushions", "pillow", "pillows", "وسائد",
                 "وساده", "مخدات", "مخدة"),
    "curtains": ("curtain", "curtains", "drape", "drapes", "ستائر",
                 "ستاره", "ستارة", "sheer", "blackout"),
}
ALL_WORDS = ("all", "everything", "كل", "كلهم", "both", "الكل")
SKIP_WORDS = ("just show me", "skip", "show me", "وريني", "تخط",
              "بدون أسئلة", "no questions")


def match_targets(message, available):
    """Map a choice reply onto available targets.

    Returns (chosen list, flags). "All" expands to every available
    target; "Just show me" sets the skip flag. No match → ([], {}).
    """
    text = (message or "").lower()
    if any(w in text for w in SKIP_WORDS):
        return list(available), {"skip": True}
    if any(w in text for w in ALL_WORDS):
        return list(available), {"all": True}
    chosen = [t for t in available
              if any(w in text for w in CHOICE_WORDS.get(t, ()))]
    if chosen:
        return chosen, {}
    return [], {}


TARGETS_CACHE = {}
MAX_TARGETS_CACHE = 50


def _image_key(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def available_types(image_path, api_key=None):
    """Cached list_types: which targets are visible in this photo."""
    path = image_path if os.path.isabs(image_path) else \
        os.path.join(BASE_DIR, image_path)
    key = _image_key(path)
    if key not in TARGETS_CACHE:
        if len(TARGETS_CACHE) >= MAX_TARGETS_CACHE:
            TARGETS_CACHE.pop(next(iter(TARGETS_CACHE)))
        TARGETS_CACHE[key] = list_types(image_path)
    return TARGETS_CACHE[key]

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


def count_components(mask, min_area_frac=0.005):
    """Count connected blobs in a binary mask (4-connectivity).

    mask is a PIL image or file path (white = foreground). Tiny
    components below min_area_frac of the pixels are ignored as noise.
    Used to count throw pillows from the cushions mask.
    """
    from collections import deque
    if isinstance(mask, str):
        if not os.path.isabs(mask):
            mask = os.path.join(BASE_DIR, mask.lstrip("/"))
        mask = Image.open(mask).convert("L")
    else:
        mask = mask.convert("L")
    mask = mask.copy()
    mask.thumbnail((160, 160))
    width, height = mask.size
    px = mask.load()
    seen = bytearray(width * height)
    blobs = 0
    min_area = max(1, int(width * height * min_area_frac))
    for y in range(height):
        for x in range(width):
            idx = y * width + x
            if seen[idx] or px[x, y] < 128:
                continue
            area = 0
            queue = deque([idx])
            seen[idx] = 1
            while queue:
                cur = queue.popleft()
                area += 1
                cx, cy = cur % width, cur // width
                for nx, ny in ((cx - 1, cy), (cx + 1, cy),
                               (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        nidx = ny * width + nx
                        if not seen[nidx] and px[nx, ny] >= 128:
                            seen[nidx] = 1
                            queue.append(nidx)
            if area >= min_area:
                blobs += 1
    return blobs


# SAM text prompts for the taps/counting path. Bare words ("cushions")
# let SAM flood the whole room on slipcovered/sample photos; naming the
# object precisely segments the item instead. The swap pipeline keeps
# the raw concept (its change-map intersection already pastes only
# what the edit changed), so tap masks and swap masks may differ
# slightly by design.
CONCEPT_PROMPTS = {
    "sofa": "sofa",
    "cushions": "throw pillows on the sofa",
    "curtains": "window curtains",
}


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
        records = []
        try:
            records = segment(room_bytes,
                              CONCEPT_PROMPTS.get(target, target), key)
        except Exception:  # noqa: BLE001 - fallback below
            records = []
        if not records and CONCEPT_PROMPTS.get(target) != target:
            try:
                records = segment(room_bytes, target, key)
            except Exception:  # noqa: BLE001 - one missing item skips
                records = []
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


def _component_boxes(mask, min_area_frac=0.005, max_boxes=8):
    """Tight boxes, one per white blob, largest first.

    SAM masks often carry stray edge specks that blow a plain getbbox
    up to the full image. Blobs below min_area_frac of the pixels are
    ignored as noise; the rest become tappable regions in mask pixels.
    """
    from collections import deque
    w0, h0 = mask.size
    small = mask.convert("L").copy()
    small.thumbnail((160, 160))
    w, h = small.size
    sx, sy = w0 / w, h0 / h
    px = small.load()
    seen = bytearray(w * h)
    min_area = max(1, int(w * h * min_area_frac))
    found = []
    for y in range(h):
        row = y * w
        for x in range(w):
            idx = row + x
            if seen[idx] or px[x, y] < 128:
                continue
            area = 0
            x1, y1, x2, y2 = x, y, x, y
            queue = deque([idx])
            seen[idx] = 1
            while queue:
                cur = queue.popleft()
                cx, cy = cur % w, cur // w
                area += 1
                if cx < x1:
                    x1 = cx
                elif cx > x2:
                    x2 = cx
                if cy < y1:
                    y1 = cy
                elif cy > y2:
                    y2 = cy
                if cx > 0 and not seen[cur - 1] \
                        and px[cx - 1, cy] >= 128:
                    seen[cur - 1] = 1
                    queue.append(cur - 1)
                if cx + 1 < w and not seen[cur + 1] \
                        and px[cx + 1, cy] >= 128:
                    seen[cur + 1] = 1
                    queue.append(cur + 1)
                if cy > 0 and not seen[cur - w] \
                        and px[cx, cy - 1] >= 128:
                    seen[cur - w] = 1
                    queue.append(cur - w)
                if cy + 1 < h and not seen[cur + w] \
                        and px[cx, cy + 1] >= 128:
                    seen[cur + w] = 1
                    queue.append(cur + w)
            if area >= min_area:
                found.append((area, [int(x1 * sx), int(y1 * sy),
                                     int((x2 + 1) * sx),
                                     int((y2 + 1) * sy)]))
    found.sort(key=lambda item: item[0], reverse=True)
    return [box for _, box in found[:max_boxes]]


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
        boxes = _component_boxes(mask) or [list(box)]
        targets.append({"id": target, "type": target,
                        "label_en": label_en, "label_ar": label_ar,
                        "mask_url": os.path.join("uploads", "masks", name),
                        "box": list(box),
                        "boxes": boxes,
                        "size": [mask.size[0], mask.size[1]]})
    return targets
