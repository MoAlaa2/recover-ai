"""Precomputed analysis/targets/masks cache for the judge sample rooms.

The 5 new samples on /consult (sofa_pillows, sage_curtains, navy_living,
majlis_burgundy, mustard_armchair) are served files chatted with directly
(see useSamplePhoto in app.js), so their bytes are exactly the committed
files. Their room analysis (per language), target listing and SAM masks
are precomputed by scripts/warm_sample_cache.py into
data/samples/cache/<id>.json (+ masks under data/samples/masks/) and
served from disk here: picking a sample answers in seconds with zero
model calls. Anything uncached falls through to the live path, so user
photos and old samples behave exactly as before.
"""
import hashlib
import json
import os

from app.core.config import BASE_DIR

SAMPLE_IDS = ("sofa_pillows", "sage_curtains", "navy_living",
              "majlis_burgundy", "mustard_armchair")
SAMPLES_DIR = os.path.join(BASE_DIR, "data", "samples")
CACHE_DIR = os.path.join(SAMPLES_DIR, "cache")
MASKS_DIR = os.path.join(SAMPLES_DIR, "masks")

_INDEX = None


def _load_index():
    """{sha256: entry} for every warmed sample. Disk reads only."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    _INDEX = {}
    if not os.path.isdir(CACHE_DIR):
        return _INDEX
    for sid in SAMPLE_IDS:
        path = os.path.join(CACHE_DIR, sid + ".json")
        try:
            with open(path, encoding="utf-8") as f:
                entry = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(entry, dict) and entry.get("sha256"):
            _INDEX[entry["sha256"]] = entry
    return _INDEX


def _entry_for(image_path):
    """Cache entry when image_path is exactly a warmed sample file."""
    path = (image_path if os.path.isabs(image_path)
            else os.path.join(BASE_DIR, image_path))
    real = os.path.realpath(path)
    if os.path.dirname(real) != os.path.realpath(SAMPLES_DIR):
        return None
    if os.path.basename(real)[:-4] not in SAMPLE_IDS:
        return None
    try:
        with open(real, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None
    entry = _load_index().get(sha)
    if entry and entry.get("sample_id") != os.path.basename(real)[:-4]:
        return None
    return entry


def get_analysis(image_path, lang):
    """Precomputed room analysis for a sample, or None to go live."""
    entry = _entry_for(image_path)
    if not entry:
        return None
    key = lang if lang else "null"
    analyses = entry.get("analyses") or {}
    result = analyses.get(key)
    return dict(result) if isinstance(result, dict) else None


def get_targets(image_path):
    """Precomputed target dicts (mask_url under /data/samples/masks/)."""
    entry = _entry_for(image_path)
    if not entry:
        return None
    targets = entry.get("targets")
    if not isinstance(targets, list) or not targets:
        return None
    out = []
    for item in targets:
        if not isinstance(item, dict) or not item.get("mask_url"):
            return None
        mask_path = os.path.join(
            BASE_DIR, item["mask_url"].lstrip("/"))
        if not os.path.isfile(mask_path):
            return None
        out.append(dict(item))
    return out
