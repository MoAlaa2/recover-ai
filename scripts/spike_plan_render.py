"""SPIKE (throwaway): can muse-image-1.0 turn a 2D floor plan into a
top-down photoreal furnished render with our fabrics on the right pieces?

  .venv/bin/python scripts/spike_plan_render.py

1. Draws a living-room plan (10 x 6 m) with PIL: sofa, two armchairs,
   rug, coffee table. Attempts 1-2 use black lines on white; attempt 3
   uses a dark CAD look (cyan lines) to see whether the plan style matters.
2. Muse Spark lists every fabric-able piece with a pixel bounding box.
3. Per fabric: a 2x copy of the plan with only its pieces outlined in
   magenta (an "outline map").
4. One muse-image-1.0 edit call: plan + swatch/outline pairs + prompt.
5. Saves everything under storyboard/spike/ with timings in report.json.
No app code is touched.
"""
import base64
import io
import json
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from app.core.config import CHAT_URL, SPARK_MODEL, require_api_key  # noqa: E402
from app.services import swap as sw  # noqa: E402
from app.services.catalog import get_fabric  # noqa: E402

OUT = "storyboard/spike"
PX_PER_M = 100
W_M, H_M = 10, 6
# Ground truth in metres (x0, y0, x1, y1) for the layout judgement.
PIECES = {
    "sofa": (3.0, 4.6, 6.0, 5.5),
    "armchair-1": (1.2, 2.2, 2.1, 3.1),
    "armchair-2": (6.9, 2.2, 7.8, 3.1),
    "rug": (2.2, 1.6, 6.8, 4.4),
    "coffee-table": (3.9, 2.6, 5.1, 3.4),
}
ASSIGN = {"sofa": "FA-AC-01", "armchair-1": "FA-NL-03",
          "armchair-2": "FA-NL-03"}


def m2px(box, scale=1):
    return tuple(int(v * PX_PER_M * scale) for v in box)


def font(size):
    for path in ("/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_plan(dark=False):
    """Simple architectural plan: walls, door swing, furniture outlines
    with small labels (as a real plan would carry)."""
    bg, ink = ((22, 26, 30), (120, 220, 235)) if dark else (
        (255, 255, 255), (0, 0, 0))
    pad = 60
    img = Image.new("RGB", (W_M * PX_PER_M + 2 * pad,
                            H_M * PX_PER_M + 2 * pad), bg)
    d = ImageDraw.Draw(img)
    ox, oy = pad, pad

    def rect(box, width=2, label=None):
        x0, y0, x1, y1 = m2px(box)
        d.rectangle([ox + x0, oy + y0, ox + x1, oy + y1], outline=ink,
                    width=width)
        if label:
            f = font(16)
            tw = d.textlength(label, font=f)
            d.text((ox + (x0 + x1) / 2 - tw / 2, oy + (y0 + y1) / 2 - 9),
                   label, fill=ink, font=f)

    # Walls (thick) with a door opening on the bottom wall.
    d.rectangle([ox, oy, ox + W_M * PX_PER_M, oy + H_M * PX_PER_M],
                outline=ink, width=8)
    d.rectangle([ox + 820, oy + H_M * PX_PER_M - 6, ox + 910,
                 oy + H_M * PX_PER_M + 6], fill=bg)
    d.arc([ox + 820 - 90, oy + H_M * PX_PER_M - 90, ox + 820 + 90,
           oy + H_M * PX_PER_M + 90], 270, 360, fill=ink, width=2)
    # Window ticks on the top wall.
    for x in (250, 650):
        d.rectangle([ox + x, oy - 4, ox + x + 160, oy + 4], fill=bg)
        d.line([ox + x, oy, ox + x + 160, oy], fill=ink, width=2)
    rect(PIECES["rug"], 1, "RUG")
    rect(PIECES["sofa"], 3, "SOFA")
    # Seat split lines on the sofa.
    x0, y0, x1, y1 = m2px(PIECES["sofa"])
    for k in (1, 2):
        xx = ox + x0 + (x1 - x0) * k // 3
        d.line([xx, oy + y0 + 20, xx, oy + y1], fill=ink, width=1)
    d.line([ox + x0, oy + y0 + 20, ox + x1, oy + y0 + 20], fill=ink,
           width=1)
    rect(PIECES["armchair-1"], 3, "CHAIR")
    rect(PIECES["armchair-2"], 3, "CHAIR")
    rect(PIECES["coffee-table"], 2, "TABLE")
    # Scale note.
    d.text((ox, oy + H_M * PX_PER_M + 18), "LIVING ROOM  10 x 6 m  1:50",
           fill=ink, font=font(14))
    return img


def b64(img, fmt="JPEG", q=92):
    buf = io.BytesIO()
    img.save(buf, fmt, quality=q)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def spark_pieces(plan, key):
    """Ask Spark for every fabric-able piece + pixel box (JSON only)."""
    text = ("This is a 2D architectural floor plan image of %d x %d "
            "pixels. List every piece of UPHOLSTERED furniture that could "
            "be reupholstered in fabric (sofas, armchairs, chairs with "
            "cushions, ottomans). Ignore rugs, tables, walls, doors and "
            "windows. Reply with JSON only: {\"pieces\": [{\"name\": "
            "\"sofa\"|\"armchair-1\"|..., \"box\": [x1, y1, x2, y2] in "
            "pixels of this image}]}." % plan.size)
    body = {"model": SPARK_MODEL, "messages": [{"role": "user", "content": [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + b64(plan)}}]}]}
    t0 = time.time()
    resp = sw._post_json(CHAT_URL, body, key, timeout=90, stage="spike-spark",
                         model=SPARK_MODEL)
    content = resp["choices"][0]["message"]["content"] or ""
    secs = time.time() - t0
    try:
        data = json.loads(content[content.find("{"):content.rfind("}") + 1])
        pieces = data.get("pieces", [])
    except ValueError:
        pieces = []
    return pieces, content, secs


def iou(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua else 0.0


def outline_map(plan2x, boxes, dark=False):
    """2x plan with ONLY the given pieces outlined in magenta."""
    img = plan2x.copy()
    d = ImageDraw.Draw(img)
    for box in boxes:
        d.rectangle([v * 2 for v in box], outline=(255, 0, 255), width=10)
    return img


def render(plan2x, fabric_maps, key, dark=False):
    """One muse-image-1.0 edit: plan, then (swatch, outline map) pairs."""
    names = []
    images = [{"image_url": "data:image/jpeg;base64," + b64(plan2x)}]
    for i, (fabric, pieces, omap) in enumerate(fabric_maps):
        images.append({"image_url": "data:image/jpeg;base64,"
                       + b64(Image.open(fabric["image"]).convert("RGB"))})
        images.append({"image_url": "data:image/jpeg;base64," + b64(omap)})
        names.append("Fabric %d (%s, %s, %s) goes on the %d piece(s) "
                     "outlined in magenta in image %d: %s." % (
                         i + 1, fabric["name_en"], fabric.get("material"),
                         fabric.get("primary_color"), len(pieces),
                         2 * i + 3, ", ".join(pieces)))
    prompt = (
        "Image 1 is a 2D floor plan of a living room, %s. Produce a "
        "photorealistic TOP-DOWN (bird's-eye, straight down) render of this "
        "exact room, as if photographed from the ceiling in soft daylight. "
        "Keep the plan's proportions and the position and size of every "
        "piece exactly as drawn. Furnish ONLY what is drawn: one three-seat "
        "sofa, two armchairs, one rug, one coffee table. Exact counts, no "
        "extra furniture, no plants, no people. %s Walls plain white, "
        "floor light oak, plain floor at the cropped edges. The output "
        "must contain NO lines, outlines, marks, labels or text of any "
        "kind: the magenta outlines and labels are instructions only."
        % ("drawn as dark CAD linework" if dark else "black lines on white",
           " ".join(names)))
    body = {"model": sw.EDIT_MODEL, "prompt": prompt, "images": images,
            "n": 1}
    t0 = time.time()
    resp = sw._post_json(sw.EDIT_URL, body, key, timeout=150,
                         stage="spike-edit", model=sw.EDIT_MODEL)
    raw = base64.b64decode(resp["data"][0]["b64_json"])
    return Image.open(io.BytesIO(raw)).convert("RGB"), time.time() - t0, prompt


def main():
    key = require_api_key()
    os.makedirs(OUT, exist_ok=True)
    report = {"attempts": []}
    for attempt in (1, 2, 3):
        dark = attempt == 3
        tag = "attempt%d%s" % (attempt, "-cad" if dark else "")
        plan = draw_plan(dark=dark)
        plan.save(os.path.join(OUT, "%s-plan.png" % tag))
        pieces, raw_text, t_spark = spark_pieces(plan, key)
        pad = 60
        truth = {n: tuple(v + pad for v in m2px(b)) for n, b in
                 PIECES.items() if n in ASSIGN}
        found = {}
        for p in pieces:
            try:
                box = tuple(int(v) for v in p["box"])
            except (KeyError, TypeError, ValueError):
                continue
            best = max(truth, key=lambda n: iou(box, truth[n]))
            found[str(p.get("name"))] = {"box": box, "matches": best,
                                         "iou": round(iou(box, truth[best]),
                                                      2)}
        print("[%s] Spark %.1fs pieces=%s" % (tag, t_spark, json.dumps(found)),
              flush=True)
        # Outline maps use SPARK'S boxes (the real pipeline would); fall
        # back to the truth box when Spark missed a piece, and say so.
        plan2x = plan.resize((plan.width * 2, plan.height * 2), Image.LANCZOS)
        fabric_maps = []
        fallback = []
        for code in sorted(set(ASSIGN.values())):
            fabric = get_fabric(code)
            names = [n for n, c in ASSIGN.items() if c == code]
            boxes = []
            for n in names:
                hit = next((f for f in found.values() if f["matches"] == n
                            and f["iou"] >= 0.3), None)
                if hit:
                    boxes.append(hit["box"])
                else:
                    boxes.append(truth[n])
                    fallback.append(n)
            omap = outline_map(plan2x, boxes, dark)
            omap.save(os.path.join(OUT, "%s-outline-%s.png" % (tag, code)))
            fabric_maps.append((fabric, names, omap))
        try:
            img, t_edit, prompt = render(plan2x, fabric_maps, key, dark)
            img.save(os.path.join(OUT, "%s-render.jpg" % tag), quality=92)
            print("[%s] edit %.1fs -> %s size=%s" % (tag, t_edit, tag,
                                                      img.size), flush=True)
            err = None
        except Exception as exc:  # noqa: BLE001 - spike: report, go on
            t_edit, err, prompt = None, str(exc), None
            print("[%s] edit FAILED: %s" % (tag, exc), flush=True)
        report["attempts"].append({
            "tag": tag, "dark_cad": dark, "spark_secs": round(t_spark, 1),
            "spark_raw": raw_text[:600], "pieces_found": found,
            "fallback_boxes": fallback, "edit_secs": t_edit and round(
                t_edit, 1), "error": err, "prompt": prompt})
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print("wrote %s/report.json" % OUT)


if __name__ == "__main__":
    main()
