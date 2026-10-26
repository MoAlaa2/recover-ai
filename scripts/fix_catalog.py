"""Self-correcting loop for weak catalog swatches.

Reads data/verify_report.json. For every fabric scoring below 7 on any
metric, asks muse-spark-1.3 to rewrite its image_prompt to fix the
reported issue, regenerates the image with muse-image-1.0, and
re-verifies. Up to 2 retries per fabric; the best-scoring version is
kept. Updated prompts are saved back to data/fabric_specs.json and
every attempt is logged to data/fix_log.json.
"""
import argparse
import base64
import json
import os
import sys
import tempfile
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS_PATH = os.path.join(BASE_DIR, "data", "fabric_specs.json")
REPORT_PATH = os.path.join(BASE_DIR, "data", "verify_report.json")
LOG_PATH = os.path.join(BASE_DIR, "data", "fix_log.json")
CATALOG_DIR = os.path.join(BASE_DIR, "data", "catalog")
CHAT_URL = "https://api.meta.ai/v1/chat/completions"
IMAGE_URL = "https://api.meta.ai/v1/images/generations"
SPARK_MODEL = "muse-spark-1.3"
IMAGE_MODEL = "muse-image-1.0"
MAX_RETRIES = 2
PASS_MARK = 7


def load_api_key():
    """Read MODEL_API_KEY from the project .env file."""
    env_path = os.path.join(BASE_DIR, ".env")
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("MODEL_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    raise SystemExit("MODEL_API_KEY not found in .env")


def post_json(url, api_key, payload, timeout):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_with_retries(url, api_key, payload, timeout, label):
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return post_json(url, api_key, payload, timeout)
        except Exception as exc:  # noqa: BLE001 - retry then report
            last_err = exc
            time.sleep(2 * (attempt + 1))
    raise SystemExit("failed %s: %s" % (label, last_err))


def rewrite_prompt(api_key, item, scores):
    """Ask Spark to rewrite the image prompt to fix the reported issue."""
    hint = ""
    if item["plain_or_patterned"] == "plain":
        hint = ('The fabric is plain: the prompt must say "solid plain, '
                'absolutely no pattern, no motif".')
    elif item["pattern_type"] == "speckle":
        hint = ("The fabric is speckled: the prompt must say \"clearly "
                "visible contrasting multicolor flecks\".")
    prompt = (
        "You write prompts for a fabric swatch image generator. Rewrite the "
        "image prompt below so the render fixes this weakness: "
        "color_match=%d/10, pattern_match=%d/10, material_look=%d/10. "
        "Issue: %s. Spec: material=%s, primary_color=%s, pattern_type=%s, "
        "plain_or_patterned=%s. %s Keep the exact opening \"Flat seamless "
        "fabric swatch, top-down view\" and keep square format, soft even "
        "studio lighting, no folds, no shadows, no objects, no text. For a "
        "patterned fabric keep the seamless repeating pattern clause. "
        "Reply with JSON only: {\"image_prompt\": \"...\"}."
        % (scores["color_match"], scores["pattern_match"],
           scores["material_look"], scores["issues"], item["material"],
           item["primary_color"], item["pattern_type"],
           item["plain_or_patterned"], hint)
    )
    body = call_with_retries(
        CHAT_URL, api_key,
        {"model": SPARK_MODEL,
         "messages": [{"role": "user", "content": prompt}],
         "temperature": 0.2},
        120, "rewrite " + item["code"])
    text = body["choices"][0]["message"]["content"]
    data = json.loads(text[text.find("{"):text.rfind("}") + 1])
    return data["image_prompt"].strip()


def generate_bytes(api_key, prompt, label):
    body = call_with_retries(
        IMAGE_URL, api_key,
        {"model": IMAGE_MODEL, "prompt": prompt, "size": "1024x1024"},
        180, "generate " + label)
    datum = body["data"][0]
    if "b64_json" in datum:
        return base64.b64decode(datum["b64_json"])
    with urllib.request.urlopen(datum["url"], timeout=180) as r:
        return r.read()


def score_bytes(api_key, img, item):
    b64 = base64.b64encode(img).decode("ascii")
    body = call_with_retries(
        CHAT_URL, api_key,
        {"model": SPARK_MODEL,
         "messages": [{
             "role": "user",
             "content": [
                 {"type": "text", "text": (
                     "You are a textile quality checker. Compare this swatch "
                     "image with spec material=%s, primary_color=%s, "
                     "pattern_type=%s, plain_or_patterned=%s. Reply with "
                     "JSON only: {\"color_match\": 0-10, "
                     "\"pattern_match\": 0-10, \"material_look\": 0-10, "
                     "\"issues\": \"short text\"}."
                     % (item["material"], item["primary_color"],
                        item["pattern_type"], item["plain_or_patterned"]))},
                 {"type": "image_url", "image_url": {
                     "url": "data:image/jpeg;base64," + b64}},
             ]}],
         "temperature": 0},
        180, "verify " + item["code"])
    text = body["choices"][0]["message"]["content"]
    data = json.loads(text[text.find("{"):text.rfind("}") + 1])
    return {
        "color_match": int(data["color_match"]),
        "pattern_match": int(data["pattern_match"]),
        "material_look": int(data["material_look"]),
        "issues": str(data.get("issues", "")),
    }


def normalize(path):
    """Convert an image to 1024x1024 JPEG under 300KB.

    Uses Pillow when it can read the file, otherwise falls back to sips.
    """
    import subprocess
    from PIL import Image
    try:
        im = Image.open(path).convert("RGB")
    except Exception:  # noqa: BLE001 - Pillow cannot read it, use sips
        subprocess.run(["sips", "-z", "1024", "1024", "-s", "format",
                        "jpeg", "-s", "formatOptions", "85", path],
                       check=True)
        im = Image.open(path).convert("RGB")
    if im.size != (1024, 1024):
        im = im.resize((1024, 1024), Image.LANCZOS)
    for q in (85, 70, 60, 50, 40, 30):
        im.save(path, "JPEG", quality=q, optimize=True)
        if os.path.getsize(path) <= 300 * 1024:
            return


def total_of(scores):
    return min(scores["color_match"], scores["pattern_match"],
               scores["material_look"])


def fix_one(api_key, item, base_scores):
    """Try up to 2 rewrites; return (best_prompt, best_scores, attempts)."""
    dest = os.path.join(CATALOG_DIR, item["code"] + ".jpg")
    with open(dest, "rb") as f:
        best_img = f.read()
    best_prompt = item["image_prompt"]
    best_scores = dict(base_scores)
    attempts = []
    current_prompt = item["image_prompt"]
    for n in range(1, MAX_RETRIES + 1):
        new_prompt = rewrite_prompt(api_key, item, best_scores)
        candidate = generate_bytes(api_key, new_prompt,
                                   "%s try%d" % (item["code"], n))
        new_scores = score_bytes(api_key, candidate, item)
        kept = total_of(new_scores) > total_of(best_scores)
        attempts.append({
            "code": item["code"], "attempt": n,
            "old_score": {k: best_scores[k] for k in
                          ("color_match", "pattern_match", "material_look")},
            "new_score": {k: new_scores[k] for k in
                          ("color_match", "pattern_match", "material_look")},
            "old_prompt": current_prompt, "new_prompt": new_prompt,
            "issues": new_scores["issues"],
            "kept": kept,
        })
        print("%s try%d: %d -> %d %s" % (
            item["code"], n, total_of(best_scores),
            total_of(new_scores), "kept" if kept else "dropped"))
        if kept:
            best_img, best_prompt, best_scores = (
                candidate, new_prompt, new_scores)
            current_prompt = new_prompt
        if total_of(best_scores) >= PASS_MARK:
            break
    with open(dest, "wb") as f:
        f.write(best_img)
    normalize(dest)
    return best_prompt, best_scores, attempts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="",
                        help="comma-separated codes to consider")
    args = parser.parse_args(argv)

    with open(SPECS_PATH, encoding="utf-8") as f:
        specs = json.load(f)
    with open(REPORT_PATH, encoding="utf-8") as f:
        report = {r["code"]: r for r in json.load(f)}
    by_code = {i["code"]: i for i in specs}

    weak = [c for c, r in report.items()
            if total_of(r) < PASS_MARK and c in by_code]
    if args.only:
        wanted = {c.strip() for c in args.only.split(",") if c.strip()}
        weak = [c for c in weak if c in wanted]

    api_key = load_api_key() if weak else None
    log = {"fixed": [], "still_weak": [], "attempts": []}
    for code in weak:
        item = by_code[code]
        prompt, scores, attempts = fix_one(api_key, item, report[code])
        log["attempts"].extend(attempts)
        if prompt != item["image_prompt"]:
            item["image_prompt"] = prompt
        report[code] = dict(scores, code=code)
        (log["fixed"] if total_of(scores) >= PASS_MARK
         else log["still_weak"]).append(code)

    if weak:
        with open(SPECS_PATH, "w", encoding="utf-8") as f:
            json.dump(specs, f, ensure_ascii=False, indent=2)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump([dict(report[c], code=c) for c in
                       sorted(report)], f, ensure_ascii=False, indent=2)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print("fixed: %s" % (log["fixed"] or "none"))
    print("still weak: %s" % (log["still_weak"] or "none"))
    print("wrote %s with %d attempts" % (LOG_PATH, len(log["attempts"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
