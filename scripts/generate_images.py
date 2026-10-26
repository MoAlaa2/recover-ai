"""Generate swatch images for the ReCover fabric catalog.

Reads data/fabric_specs.json and calls the image model to render one
square swatch per fabric. The API key is read from .env only.
Images are saved to data/catalog/[code].jpg. No images are generated
at import time; run this script explicitly.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS_PATH = os.path.join(BASE_DIR, "data", "fabric_specs.json")
CATALOG_DIR = os.path.join(BASE_DIR, "data", "catalog")
API_URL = "https://api.meta.ai/v1/images/generations"
MODEL = "muse-image-1.0"
MAX_RETRIES = 2


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


def load_specs():
    with open(SPECS_PATH, encoding="utf-8") as f:
        return json.load(f)


def pick_test_set(specs):
    """First plain + first patterned fabric of each collection (10)."""
    seen = {}
    for item in specs:
        key = (item["collection"], item["plain_or_patterned"])
        if key not in seen:
            seen[key] = item
    return [seen[k] for k in sorted(seen)]


def generate_one(api_key, item):
    """Request one square swatch image, with two retries."""
    payload = json.dumps({
        "model": MODEL,
        "prompt": item["image_prompt"],
        "size": "1024x1024",
    }).encode("utf-8")
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                API_URL,
                data=payload,
                headers={
                    "Authorization": "Bearer " + api_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            # Accept common response shapes: {"data": [{"url"|"b64_json"}]}
            datum = body["data"][0]
            if "b64_json" in datum:
                import base64
                return base64.b64decode(datum["b64_json"])
            url = datum.get("url")
            if url:
                with urllib.request.urlopen(url, timeout=120) as r:
                    return r.read()
            raise ValueError("unexpected response shape: %r" % (body,))
        except Exception as exc:  # noqa: BLE001 - retry then report
            last_err = exc
            time.sleep(2 * (attempt + 1))
    raise SystemExit("failed %s: %s" % (item["code"], last_err))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true",
                        help="generate 10 images only")
    parser.add_argument("--only", default="",
                        help="comma-separated codes, e.g. FA-VL-01,FA-NL-03")
    parser.add_argument("--force", action="store_true",
                        help="regenerate even if the file exists")
    args = parser.parse_args(argv)

    api_key = load_api_key()
    specs = load_specs()
    if args.test:
        specs = pick_test_set(specs)
    if args.only:
        wanted = {c.strip() for c in args.only.split(",") if c.strip()}
        specs = [i for i in load_specs() if i["code"] in wanted]
        missing = wanted - {i["code"] for i in specs}
        if missing:
            raise SystemExit("unknown codes: %s" % ", ".join(sorted(missing)))
    os.makedirs(CATALOG_DIR, exist_ok=True)

    total = len(specs)
    for n, item in enumerate(specs, 1):
        dest = os.path.join(CATALOG_DIR, item["code"] + ".jpg")
        if os.path.exists(dest) and not args.force:
            print("(%d/%d) %s exists, skipped" % (n, total, item["code"]))
            continue
        blob = generate_one(api_key, item)
        with open(dest, "wb") as f:
            f.write(blob)
        print("(%d/%d) %s saved" % (n, total, item["code"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
