"""Verify catalog swatches against their specs with Muse Spark.

For each fabric, sends the swatch image plus its spec (material,
primary_color, pattern_type, plain_or_patterned) to muse-spark-1.3
and asks for match scores as JSON. Results go to data/verify_report.json
and fabrics scoring below 7 on anything are printed.
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
REPORT_PATH = os.path.join(BASE_DIR, "data", "verify_report.json")
API_URL = "https://api.meta.ai/v1/chat/completions"
MODEL = "muse-spark-1.3"
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


def load_specs():
    with open(SPECS_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_prompt(item):
    return (
        "You are a textile quality checker. Look at this fabric swatch image "
        "and compare it with the spec below.\n"
        "Spec: material=%s, primary_color=%s, pattern_type=%s, "
        "plain_or_patterned=%s.\n"
        "Reply with JSON only, no other text: "
        '{"color_match": 0-10, "pattern_match": 0-10, '
        '"material_look": 0-10, "issues": "short text"}.'
        % (item["material"], item["primary_color"],
           item["pattern_type"], item["plain_or_patterned"])
    )


def parse_scores(text):
    """Extract the score JSON from a model reply."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON in reply: %r" % text[:200])
    data = json.loads(text[start:end + 1])
    return {
        "color_match": int(data["color_match"]),
        "pattern_match": int(data["pattern_match"]),
        "material_look": int(data["material_look"]),
        "issues": str(data.get("issues", "")),
    }


def verify_one(api_key, item):
    """Score one fabric image, with two retries."""
    img_path = os.path.join(BASE_DIR, item["image"])
    if not os.path.exists(img_path):
        raise SystemExit("missing image: %s" % item["image"])
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    payload = json.dumps({
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": build_prompt(item)},
                {"type": "image_url", "image_url": {
                    "url": "data:image/jpeg;base64," + b64}},
            ],
        }],
        "temperature": 0,
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
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            text = body["choices"][0]["message"]["content"]
            result = parse_scores(text)
            result["code"] = item["code"]
            return result
        except Exception as exc:  # noqa: BLE001 - retry then report
            last_err = exc
            time.sleep(2 * (attempt + 1))
    raise SystemExit("failed %s: %s" % (item["code"], last_err))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="",
                        help="comma-separated codes, e.g. FA-VL-01,FA-NL-03")
    args = parser.parse_args(argv)

    specs = load_specs()
    if args.only:
        wanted = {c.strip() for c in args.only.split(",") if c.strip()}
        specs = [i for i in specs if i["code"] in wanted]
        missing = wanted - {i["code"] for i in specs}
        if missing:
            raise SystemExit("unknown codes: %s" % ", ".join(sorted(missing)))

    api_key = load_api_key()
    results = []
    total = len(specs)
    for n, item in enumerate(specs, 1):
        results.append(verify_one(api_key, item))
        print("(%d/%d) %s scored" % (n, total, item["code"]))

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("wrote %s with %d results" % (REPORT_PATH, len(results)))

    weak = [r for r in results if min(r["color_match"], r["pattern_match"],
                                      r["material_look"]) < PASS_MARK]
    if weak:
        print("CODE | COLOR PATT MAT | ISSUES")
        for r in weak:
            print("%s | %d %d %d | %s" % (
                r["code"], r["color_match"], r["pattern_match"],
                r["material_look"], r["issues"]))
    else:
        print("all fabrics scored %d or above" % PASS_MARK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
