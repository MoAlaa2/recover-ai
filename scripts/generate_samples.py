"""Generate 3 photoreal sample rooms for /consult?sample= and landing.

Saves data/samples/{living,majlis,armchair}.jpg (<=300KB each), then
verifies each with Spark vision: the main piece must be clearly visible,
otherwise regenerates (up to 2 retries). Run explicitly.
"""
import base64
import io
import json
import os
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
SAMPLES_DIR = os.path.join(BASE_DIR, "data", "samples")
API_URL = "https://api.meta.ai/v1/images/generations"
MODEL = "muse-image-1.0"
MAX_RETRIES = 2

SAMPLES = {
    "living": (
        "Photorealistic living room interior, three-seat beige fabric "
        "sofa centered facing camera, warm afternoon light through sheer "
        "curtains, wooden coffee table, jute rug, no people, no text, "
        "no brand logos, interior photography",
        ["sofa", "couch", "كنبة", "sofas"],
    ),
    "majlis": (
        "Photorealistic traditional Saudi majlis seating room, low floor "
        "cushions and long upholstered mattresses along the walls, warm "
        "lantern light, large carpeted floor, no people, no text, "
        "no brand logos, interior photography",
        ["majlis", "cushion", "mattress", "مجلس", "floor seating",
         "sofa"],
    ),
    "armchair": (
        "Photorealistic cozy reading corner, single wingback armchair "
        "in sage green fabric by a tall window with daylight, small "
        "wooden side table with books, no people, no text, "
        "no brand logos, interior photography",
        ["armchair", "chair", "كرسي", "wingback"],
    ),
}


def load_api_key():
    env_path = os.path.join(BASE_DIR, ".env")
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("MODEL_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("MODEL_API_KEY not found in .env")


def generate_one(api_key, prompt):
    payload = json.dumps({"model": MODEL, "prompt": prompt,
                          "size": "1024x1024"}).encode("utf-8")
    last_err = None
    for _ in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                API_URL, data=payload,
                headers={"Authorization": "Bearer " + api_key,
                         "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            datum = body["data"][0]
            if "b64_json" in datum:
                return base64.b64decode(datum["b64_json"])
            with urllib.request.urlopen(datum["url"],
                                         timeout=180) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001 - retry then report
            last_err = exc
            time.sleep(3)
    raise SystemExit("image generation failed: %s" % last_err)


def compress(path, raw, limit=300 * 1024):
    from PIL import Image
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if max(img.size) > 1024:
        img.thumbnail((1024, 1024), Image.LANCZOS)
    for quality in (82, 72, 62, 52):
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=True)
        if len(buf.getvalue()) <= limit or quality == 52:
            with open(path, "wb") as f:
                f.write(buf.getvalue())
            return len(buf.getvalue())
    return 0


def verify(path, keywords):
    from app.services.consultant import analyze_room
    try:
        info = analyze_room(path)
    except Exception as exc:  # noqa: BLE001 - treat as unverified
        return False, "vision error: %s" % exc
    blob = json.dumps(info, ensure_ascii=False).lower()
    ok = any(k.lower() in blob for k in keywords)
    return ok, (info.get("furniture") or info.get("room_type") or "?")[:80]


def main():
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    api_key = load_api_key()
    for name, (prompt, keywords) in SAMPLES.items():
        path = os.path.join(SAMPLES_DIR, name + ".jpg")
        for attempt in range(MAX_RETRIES + 1):
            raw = generate_one(api_key, prompt)
            size = compress(path, raw)
            ok, seen = verify(path, keywords)
            print("%s attempt %d: %dKB vision=%s ok=%s"
                  % (name, attempt + 1, size // 1024, seen, ok),
                  flush=True)
            if ok:
                break
        else:
            raise SystemExit("sample %s failed verification" % name)
    print("SAMPLES_DONE", flush=True)


if __name__ == "__main__":
    main()
