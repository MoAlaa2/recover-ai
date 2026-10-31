"""Generate the landing hero looks on the living sample with the swap
engine; accept only results that pass the deterministic colour and
coverage checks; save static assets + caption data.

  .venv/bin/python scripts/generate_hero_looks.py [warm calm mix]

Writes app/static/landing/hero-<look>.jpg and hero-looks.json.
"""
import io
import json
import os
import shutil
import sys
import time
from collections import deque

from PIL import Image

sys.path.insert(0, os.getcwd())
from app.core.config import BASE_DIR, require_api_key  # noqa: E402
from app.services import swap as sw  # noqa: E402
from app.services import swap_checks as sc  # noqa: E402
from app.services.catalog import get_fabric  # noqa: E402

ROOM = os.path.join(BASE_DIR, "data/samples/living.jpg")
OUT = os.path.join(BASE_DIR, "app/static/landing")
WORK = os.path.join(BASE_DIR, "uploads/hero-work")
QC = os.path.join(BASE_DIR, "storyboard/hero_qc")

LOOKS = {
    "warm": {"sofa": "FA-AC-01", "cushions": "FA-AC-08"},
    "calm": {"sofa": "FA-AC-05", "cushions": "FA-AC-03"},
    # Midnight Sapphire: the chunky Sand Ceremony chenille rendered as an
    # oversized basket weave; a plain velvet lets the three pillows carry
    # the mix (geometric print, clay, oat).
    "mix": {"sofa": "FA-VL-04",
            "pillows": ["FA-AC-13", "FA-AC-04", "FA-AC-03"]},
}


def components(mask, work_side=320, min_frac=0.03):
    """Per-blob masks (largest first), tiny specks dropped."""
    w0, h0 = mask.size
    small = mask.convert("L").copy()
    small.thumbnail((work_side, work_side))
    w, h = small.size
    px = small.load()
    seen = bytearray(w * h)
    comps = []
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if seen[idx] or px[x, y] < 128:
                continue
            seen[idx] = 1
            q = deque([idx])
            members = []
            while q:
                cur = q.popleft()
                members.append(cur)
                cx, cy = cur % w, cur // w
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1),
                               (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        n = ny * w + nx
                        if not seen[n] and px[nx, ny] >= 128:
                            seen[n] = 1
                            q.append(n)
            comps.append(members)
    comps.sort(key=len, reverse=True)
    out = []
    for members in comps:
        if len(members) < min_frac * len(comps[0]):
            continue
        layer = Image.new("L", (w, h), 0)
        lp = layer.load()
        xs = [m % w for m in members]
        for m in members:
            lp[m % w, m // w] = 255
        layer = layer.resize((w0, h0), Image.NEAREST)
        full = Image.composite(mask.convert("L"), Image.new("L", (w0, h0), 0),
                               layer)
        out.append((sum(xs) / len(xs), full))
    out.sort(key=lambda t: t[0])  # left to right
    return [m for _, m in out]


def item_record(target, code, scores, checks, label_en=None,
                label_ar=None):
    f = get_fabric(code)
    return {"target": target, "code": code, "name_en": f["name_en"],
            "name_ar": f["name_ar"], "image": f["image"],
            "material": f.get("material", ""),
            "price_sar_per_m": f.get("price_sar_per_m"),
            "label_en": label_en, "label_ar": label_ar,
            "scores": scores, "delta_e": checks.get("delta_e"),
            "coverage": checks.get("coverage")}


def run_multi(assign):
    res = sw.swap_multi(ROOM, [{"target": t, "code": c}
                               for t, c in assign.items()],
                        out_dir=WORK, budget=110)
    return res


def pillows_on(base_img, codes, key, room_bytes, sofa_mask=None,
               sofa_swatch=None):
    """Each pillow its own fabric; edited ON the sofa result so the area
    behind a narrower new pillow shows the new sofa fabric; pasted
    strictly inside that pillow's component; checks per pillow with the
    residue search over sofa ∪ pillow against the ORIGINAL."""
    from app.services.targets import CONCEPT_PROMPTS
    # Segment on the sofa result only when the new sofa contrasts with
    # the old pillows (see swap.pillows_contrast); else on the original.
    seg_bytes = sw._small_copy(room_bytes, 1600)
    probe = sw.segment(seg_bytes, CONCEPT_PROMPTS.get("cushions", "cushions"),
                       key)
    if probe and sofa_swatch and sw.pillows_contrast(
            Image.open(io.BytesIO(room_bytes)).convert("RGB"),
            sw.sam_mask(probe, base_img.size), [sofa_swatch]):
        seg_buf = io.BytesIO()
        base_img.save(seg_buf, "JPEG", quality=95)
        seg_bytes = sw._small_copy(seg_buf.getvalue(), 1600)
        print("  pillows segmented on the sofa result", flush=True)
    parts = []
    for prompt in (CONCEPT_PROMPTS.get("cushions", "cushions"),
                   "cushions", "throw pillow"):
        records = sw.segment(seg_bytes, prompt, key)
        # One SAM record per pillow: place each on its own canvas.
        layers = []
        for rec in records:
            try:
                raster, w, h = sw.sam_codec.decode_record(rec)
            except sw.sam_codec.MaskError:
                continue
            layer = sw._place_record(raster, w, h, rec, base_img.size)
            cov = sw._mask_coverage(layer, base_img.size)
            if 0.001 < cov < sw.MAX_RECORD_COVERAGE:
                layers.append((layer.getbbox()[0], layer))
        layers.sort(key=lambda t: t[0])
        parts = [lyr for _, lyr in layers]
        if len(parts) < len(codes):
            merged = sw.sam_mask(records, base_img.size)
            parts = components(merged)
        print("  prompt %r -> %d pillow masks" % (prompt, len(parts)),
              flush=True)
        if len(parts) >= len(codes):
            break
    if len(parts) < len(codes):
        raise sw.SwapError("found %d pillows, need %d" % (len(parts),
                                                          len(codes)))
    original = Image.open(io.BytesIO(room_bytes)).convert("RGB")
    current = base_img.copy()
    items = []
    pillow_boxes = []
    labels = [("Left cushion", "الوسادة اليسرى"),
              ("Middle cushion", "الوسادة الوسطى"),
              ("Right cushion", "الوسادة اليمنى")]
    if len(codes) == 2:
        labels = [labels[0], labels[2]]
    for i, code in enumerate(codes):
        fabric = get_fabric(code)
        with open(os.path.join(BASE_DIR, fabric["image"]), "rb") as f:
            swatch = f.read()
        comp = parts[i]
        pillow_boxes.append(comp.getbbox())
        best = None
        corrective = None
        residue_mask = (Image.composite(comp, sofa_mask, comp)
                        if sofa_mask is not None else comp)
        for attempt in range(2):
            buf = io.BytesIO()
            current.save(buf, "JPEG", quality=95)
            edited = sw.edit_room(buf.getvalue(), swatch, fabric,
                                  sw.TARGET_CONCEPTS["cushions"], key,
                                  corrective)
            cand = sw.paste_strict(current, edited, comp)
            checks = sc.run_checks(
                original, cand, comp, swatch, base=current,
                residue_mask=residue_mask,
                extra_swatches=[sofa_swatch] if sofa_swatch else ())
            small = cand.copy()
            small.thumbnail((1024, 1024))
            scores = sw.verify(swatch, small, fabric, "cushion", key)
            print("  pillow %d %s try %d: checks=%s scores=%s" % (
                i + 1, code, attempt + 1, checks, scores), flush=True)
            cand_entry = {"result": cand, "scores": scores,
                          "checks": checks}
            if best is None or sw._rank(cand_entry) > sw._rank(best):
                best = cand_entry
            if checks["ok"] and min(scores.values()) >= 7:
                break
            corrective = sw._corrective(scores, "cushion", checks)
        if not best["checks"]["ok"]:
            raise sw.CheckFailed(best["checks"]["fail"], best["checks"],
                                 "cushions")
        current = best["result"]
        items.append(item_record("cushions", code, best["scores"],
                                 best["checks"], labels[i][0],
                                 labels[i][1]))
    return current, items, pillow_boxes


def qc_crops(look, final, pillow_boxes, sofa_box):
    """2x crops of every pillow (with sofa around it) + the sofa, for a
    human look before a hero is accepted."""
    os.makedirs(QC, exist_ok=True)
    paths = []
    W, H = final.size

    def crop2x(box, pad, name):
        x0, y0, x1, y1 = box
        bw, bh = x1 - x0, y1 - y0
        px, py = int(bw * pad), int(bh * pad)
        c = final.crop((max(0, x0 - px), max(0, y0 - py),
                        min(W, x1 + px), min(H, y1 + py)))
        c = c.resize((c.width * 2, c.height * 2), Image.LANCZOS)
        path = os.path.join(QC, "%s-%s.jpg" % (look, name))
        c.save(path, "JPEG", quality=90)
        paths.append(os.path.relpath(path, BASE_DIR))

    for i, box in enumerate(pillow_boxes):
        if box:
            crop2x(box, 0.6, "pillow-%d" % (i + 1))
    if sofa_box:
        crop2x(sofa_box, 0.08, "sofa")
    return paths


def build(look):
    key = require_api_key()
    spec = LOOKS[look]
    with open(ROOM, "rb") as f:
        room_bytes = f.read()
    t0 = time.time()
    if "pillows" in spec:
        res = run_multi({"sofa": spec["sofa"]})
    else:
        res = run_multi(spec)
    if res.get("skipped"):
        raise sw.SwapError("skipped: %s" % res["skipped"])
    items = [item_record(r["target"], r["code"], r["scores"],
                         r.get("checks") or {}) for r in res["results"]]
    for r in res["results"]:
        print("  %s %s: checks=%s scores=%s" % (
            r["target"], r["code"], r.get("checks"), r["scores"]),
            flush=True)
        if not (r.get("checks") or {}).get("ok"):
            raise sw.SwapError("%s failed checks" % r["target"])
    final = Image.open(os.path.join(BASE_DIR, res["final_url"])).convert(
        "RGB")
    masks = {r["target"]: Image.open(os.path.join(
        BASE_DIR, r["mask_url"])).convert("L") for r in res["results"]}
    pillow_boxes = []
    if "pillows" in spec:
        with open(os.path.join(BASE_DIR, get_fabric(spec["sofa"])["image"]),
                  "rb") as f:
            sofa_swatch = f.read()
        final, pillow_items, pillow_boxes = pillows_on(
            final, spec["pillows"], key, room_bytes,
            sofa_mask=masks.get("sofa"), sofa_swatch=sofa_swatch)
        items += pillow_items
    elif "cushions" in masks:
        pillow_boxes = [m.getbbox() for m in components(masks["cushions"])]
    sofa_box = masks["sofa"].getbbox() if "sofa" in masks else None
    qc = qc_crops(look, final, pillow_boxes, sofa_box)
    print("  QC crops: %s" % ", ".join(qc), flush=True)
    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, "hero-%s.jpg" % look)
    final.save(out_path, "JPEG", quality=90)
    print("%s done in %.0fs -> %s" % (look, time.time() - t0, out_path),
          flush=True)
    return {"id": look, "image": "/landing/hero-%s.jpg" % look,
            "items": items, "qc": qc}


def main(argv):
    wanted = argv or list(LOOKS)
    os.makedirs(WORK, exist_ok=True)
    json_path = os.path.join(OUT, "hero-looks.json")
    data = {"before": "/landing/hero-before.jpg", "looks": []}
    if os.path.exists(json_path):
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except ValueError:
            pass
    by_id = {lk["id"]: lk for lk in data.get("looks", [])}
    failures = 0
    for look in wanted:
        print("== %s" % look, flush=True)
        try:
            by_id[look] = build(look)
        except Exception as exc:  # noqa: BLE001 - report, keep going
            failures += 1
            print("%s FAILED: %s" % (look, exc), flush=True)
    data["looks"] = [by_id[k] for k in LOOKS if k in by_id]
    # Cache-buster: the image file names never change, so browsers kept
    # showing stale renders after a regeneration.
    data["v"] = int(time.time())
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    shutil.rmtree(WORK, ignore_errors=True)
    print("wrote %s (%d looks, %d failures)" % (json_path,
                                                 len(data["looks"]),
                                                 failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
