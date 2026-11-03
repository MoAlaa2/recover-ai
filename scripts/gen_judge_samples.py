"""Generate the 5 judge sample rooms (3 candidates each, keep best).

For each of the 5 briefs: generate 3 candidates at 1600x1200 with
muse-image-1.0, then ask Muse Spark to rate each candidate against the
keep rules (target pieces fully visible/uncropped, nothing blocking,
plain small-weave fabrics, believable phone photo). The highest total
wins and is saved to data/samples/<id>.jpg (<=400KB).

Candidates live under uploads/candidates/ (gitignored); only the 5
winners are copied into data/samples/. The API key is read from .env
into memory only and never printed. Progress goes to stdout + a JSONL
log. Run explicitly; takes a while (15 image calls + 15 ratings).
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

IMAGE_URL = "https://api.meta.ai/v1/images/generations"
CHAT_URL = "https://api.meta.ai/v1/chat/completions"
IMAGE_MODEL = "muse-image-1.0"
SPARK_MODEL = "muse-spark-1.3"
SIZE = "1600x1200"
CAND_DIR = os.path.join(BASE_DIR, "uploads", "candidates")
SAMPLES_DIR = os.path.join(BASE_DIR, "data", "samples")
LOG_PATH = os.path.join(CAND_DIR, "gen_judge_samples.jsonl")

SAMPLES = {
    "sofa_pillows": (
        "A realistic smartphone photo of a three-seat fabric sofa in "
        "plain warm-grey linen with three throw pillows in solid "
        "mustard, cream and teal, against a plain off-white wall in a "
        "bright living room, light oak floor, a small round side table. "
        "Shot straight-on from standing height, the whole sofa and all "
        "three pillows fully visible and not cropped. Bright, even "
        "daylight, sharp, natural colours, no film grain. No people, "
        "no text, no logos."
    ),
    "sage_curtains": (
        "A realistic smartphone photo of a living-room window wall with "
        "two floor-length solid sage-green curtain panels on a simple "
        "black rod, pulled open to show a sheer white layer behind "
        "them. A plain white wall, light wooden floor, a potted plant "
        "in the corner. Shot straight-on, both curtain panels fully "
        "visible from rod to floor and not cropped. Bright daylight, "
        "sharp, no film grain. No people, no text, no logos."
    ),
    "navy_living": (
        "A realistic smartphone photo of a full modern living room: a "
        "navy velvet three-seat sofa with two cream throw pillows, a "
        "matching terracotta fabric armchair, floor-length beige "
        "curtains on the window behind, a low wooden coffee table and a "
        "rug. Shot from a standing corner view so the sofa, armchair, "
        "pillows and curtains are all fully visible and not overlapping "
        "each other. Bright natural daylight, sharp, no film grain. "
        "No people, no text, no logos."
    ),
    "majlis_burgundy": (
        "A realistic smartphone photo of a traditional Saudi majlis "
        "room: low floor seating cushions along two walls upholstered "
        "in solid deep burgundy fabric, matching back cushions and "
        "round arm bolsters, plain cream floor-length curtains on a "
        "window, a patterned carpet in the centre, a small brass coffee "
        "tray. Shot from the room entrance, all seating, back cushions "
        "and curtains fully visible. Warm, bright daylight, sharp, no "
        "film grain. No people, no text, no logos."
    ),
    "mustard_armchair": (
        "A realistic smartphone photo of a reading corner: one "
        "upholstered wingback armchair in solid mustard-yellow fabric "
        "with a matching footstool, a floor lamp and a small bookshelf, "
        "a plain light-grey wall. Shot straight-on at a slight angle, "
        "the armchair and footstool fully visible and not cropped. "
        "Bright, even daylight, sharp, no film grain. No people, no "
        "text, no logos."
    ),
}

RATE_PROMPT = """Rate this candidate room photo for a furniture-swap demo on these rules, 1-5 each (5 = perfect):
1. visible_complete: every target piece (%s) fully visible and uncropped.
2. uncluttered: nothing blocks the pieces; no stray objects on them.
3. plain_fabrics: plain or very small-weave fabrics, no big patterns.
4. photo_look: believable bright smartphone photo, sharp, natural colours, no film grain.
Reply with JSON only: {"visible_complete": N, "uncluttered": N, "plain_fabrics": N, "photo_look": N, "notes": "..."}."""

PIECES = {
    "sofa_pillows": "the grey sofa and all three throw pillows",
    "sage_curtains": "both sage-green curtain panels from rod to floor",
    "navy_living": "the navy sofa, both cream pillows, the terracotta armchair and the beige curtains",
    "majlis_burgundy": "the burgundy floor seating, back cushions, bolsters and cream curtains",
    "mustard_armchair": "the mustard wingback armchair and the footstool",
}


def load_api_key():
    env_path = os.path.join(BASE_DIR, ".env")
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("MODEL_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("MODEL_API_KEY not found in .env")


def log(obj):
    line = json.dumps(obj, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def post_json(url, payload, api_key, timeout):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def generate_one(api_key, prompt, tag):
    """One candidate image. Returns (bytes, actual_size_note)."""
    last_err = None
    for attempt in range(3):
        try:
            body = post_json(IMAGE_URL,
                             {"model": IMAGE_MODEL, "prompt": prompt,
                              "size": SIZE}, api_key, 300)
            datum = body["data"][0]
            if "b64_json" in datum:
                return base64.b64decode(datum["b64_json"]), None
            with urllib.request.urlopen(datum["url"],
                                         timeout=300) as r:
                return r.read(), None
        except Exception as exc:  # noqa: BLE001 - retry, then report
            last_err = exc
            log({"event": "gen_retry", "tag": tag, "attempt": attempt,
                 "error": str(exc)[:300]})
            time.sleep(5 * (attempt + 1))
    return None, str(last_err)[:300]


def compress(raw, limit=400 * 1024):
    from PIL import Image
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    dims = img.size
    for quality in (84, 76, 68, 60, 52):
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=True)
        if len(buf.getvalue()) <= limit or quality == 52:
            return buf.getvalue(), dims, quality
    return buf.getvalue(), dims, 52


def rate(api_key, img_bytes, pieces, tag):
    b64 = base64.b64encode(img_bytes).decode("ascii")
    messages = [{"role": "user", "content": [
        {"type": "text",
         "text": RATE_PROMPT % pieces},
        {"type": "image_url",
         "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]
    last_err = None
    for attempt in range(3):
        try:
            body = post_json(CHAT_URL,
                             {"model": SPARK_MODEL,
                              "messages": messages}, api_key, 180)
            text = body["choices"][0]["message"]["content"] or ""
            data = json.loads(text[text.find("{"):text.rfind("}") + 1])
            scores = {k: int(data[k]) for k in
                      ("visible_complete", "uncluttered",
                       "plain_fabrics", "photo_look")}
            total = sum(scores.values())
            return total, scores, str(data.get("notes", ""))[:200]
        except Exception as exc:  # noqa: BLE001 - retry, then report
            last_err = exc
            time.sleep(4 * (attempt + 1))
    return -1, {}, "rating failed: %s" % str(last_err)[:200]


def main():
    os.makedirs(CAND_DIR, exist_ok=True)
    api_key = load_api_key()
    for sid, prompt in SAMPLES.items():
        sdir = os.path.join(CAND_DIR, sid)
        os.makedirs(sdir, exist_ok=True)
        results = []
        for n in (1, 2, 3):
            tag = "%s-c%d" % (sid, n)
            raw, err = generate_one(api_key, prompt, tag)
            if raw is None:
                log({"event": "candidate_failed", "sample": sid,
                     "n": n, "error": err})
                continue
            blob, dims, q = compress(raw)
            path = os.path.join(sdir, "cand%d.jpg" % n)
            with open(path, "wb") as f:
                f.write(blob)
            total, scores, notes = rate(api_key, blob,
                                         PIECES[sid], tag)
            time.sleep(2)
            log({"event": "candidate", "sample": sid, "n": n,
                 "kb": len(blob) // 1024, "dims": dims, "q": q,
                 "total": total, "scores": scores, "notes": notes})
            results.append((total, n, path, len(blob)))
        ok = [r for r in results if r[0] >= 0]
        if not ok:
            log({"event": "sample_failed", "sample": sid})
            continue
        ok.sort(reverse=True)
        total, n, path, size = ok[0]
        dest = os.path.join(SAMPLES_DIR, sid + ".jpg")
        with open(path, "rb") as f:
            best = f.read()
        with open(dest, "wb") as f:
            f.write(best)
        log({"event": "winner", "sample": sid, "n": n,
             "total": total, "kb": size // 1024, "dest": dest})
    log({"event": "DONE"})


if __name__ == "__main__":
    main()
