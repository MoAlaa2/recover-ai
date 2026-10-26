"""Tag every catalog swatch with a vision-based snag risk.

Sends each swatch image to muse-spark-1.3 vision and asks how easily
cat or dog claws would snag the visible surface. Writes "snag_risk"
(low/medium/high) back into data/fabric_specs.json. Resumable: tagged
fabrics are skipped unless --force is given.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS_PATH = os.path.join(BASE_DIR, "data", "fabric_specs.json")
CATALOG_DIR = os.path.join(BASE_DIR, "data", "catalog")
CHAT_URL = "https://api.meta.ai/v1/chat/completions"
MODEL = "muse-spark-1.3"
LEVELS = ("low", "medium", "high")
MAX_RETRIES = 2

PROMPT = (
    "Rate how easily cat or dog claws would snag this upholstery fabric "
    "based on its visible surface: loops, raised pile, open weave = high; "
    "textured but tight = medium; flat tight weave or short dense velvet "
    "pile = low. Reply with JSON only: "
    "{\"snag_risk\": \"low|medium|high\", \"reason\": \"short\"}.")


def load_api_key():
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


def tag_one(api_key, image_path):
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    payload = {"model": MODEL,
               "messages": [{"role": "user", "content": [
                   {"type": "text", "text": PROMPT},
                   {"type": "image_url", "image_url": {
                       "url": "data:image/jpeg;base64," + b64}}]}],
               "temperature": 0}
    last_err = None
    for _ in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                CHAT_URL, data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": "Bearer " + api_key,
                         "Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            text = body["choices"][0]["message"]["content"] or ""
            data = json.loads(text[text.find("{"):text.rfind("}") + 1])
            level = str(data["snag_risk"]).lower()
            if level in LEVELS:
                return level, str(data.get("reason", ""))
            last_err = "bad level %r" % level
        except Exception as exc:  # noqa: BLE001 - retry then report
            last_err = exc
        time.sleep(2)
    raise SystemExit("tag failed %s: %s" % (image_path, last_err))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="",
                        help="comma-separated codes")
    parser.add_argument("--force", action="store_true",
                        help="retag even if already tagged")
    args = parser.parse_args(argv)

    with open(SPECS_PATH, encoding="utf-8") as f:
        specs = json.load(f)
    if args.only:
        wanted = {c.strip() for c in args.only.split(",") if c.strip()}
        specs_subset = [i for i in specs if i["code"] in wanted]
        missing = wanted - {i["code"] for i in specs_subset}
        if missing:
            raise SystemExit("unknown codes: %s" % ", ".join(sorted(missing)))
    else:
        specs_subset = specs

    api_key = load_api_key()
    done = 0
    for n, item in enumerate(specs_subset, 1):
        if item.get("snag_risk") in LEVELS and not args.force:
            continue
        img = os.path.join(CATALOG_DIR, item["code"] + ".jpg")
        level, reason = tag_one(api_key, img)
        item["snag_risk"] = level
        done += 1
        print("(%d) %s -> %s (%s)" % (n, item["code"], level, reason))
        with open(SPECS_PATH, "w", encoding="utf-8") as f:
            json.dump(specs, f, ensure_ascii=False, indent=2)
    print("tagged %d fabrics" % done)
    return 0


if __name__ == "__main__":
    sys.exit(main())
