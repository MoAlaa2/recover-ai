"""Catalog access for the consultant tools.

Reads data/fabric_specs.json. search_catalog filters locally and reports
which constraints were relaxed so the agent can say so honestly.
"""
import json

from app.core.config import SPECS_PATH

_SPECS = None
MIN_RESULTS = 3

# Relaxed in this order until enough fabrics match.
RELAX_ORDER = ["max_price", "features", "opacity", "colors", "tone",
               "suitable_for", "styles", "plain_or_patterned"]

USAGE_SYNONYMS = {
    "sofa": "upholstery", "couch": "upholstery", "chair": "upholstery",
    "seating": "upholstery", "كنب": "upholstery", "كنبة": "upholstery",
    "مجلس": "upholstery", "كرسي": "upholstery", "كراسي": "upholstery",
    "curtain": "curtains", "curtains": "curtains", "drape": "curtains",
    "ستارة": "curtains", "ستائر": "curtains",
    "cushion": "cushions", "pillow": "cushions", "وسادة": "cushions",
    "وسائد": "cushions", "مخدة": "cushions", "مخدات": "cushions",
}

# Words that mark Egyptian dialect (never use in Saudi-dialect replies).
EGYPTIAN_MARKERS = ["عايز", "عايزة", "عاوز", "عاوزة", "ازيك", "ازاي",
                    "علشان", "دلوقتي", "كده", "فين", "ليه", "برضه",
                    "برضو", "امال"]


def load_specs():
    global _SPECS
    if _SPECS is None:
        with open(SPECS_PATH, encoding="utf-8") as f:
            _SPECS = json.load(f)
    return _SPECS


def get_fabric(code):
    """Return the full spec for a fabric code, or None."""
    for item in load_specs():
        if item["code"] == code:
            return item
    return None


def normalize_usage(value):
    if not value:
        return None
    v = value.strip().lower()
    if v in ("upholstery", "curtains", "cushions"):
        return v
    for key, usage in USAGE_SYNONYMS.items():
        if key in v:
            return usage
    return None


def _matches(item, flt):
    if flt.get("usage"):
        norm = normalize_usage(flt["usage"])
        if norm and item["usage"] != norm:
            return False
    if flt.get("colors"):
        blob = " ".join([item["primary_color"]] +
                        item.get("secondary_colors", [])).lower()
        if not any(c.lower() in blob for c in flt["colors"]):
            return False
    if flt.get("tone") and item["tone"] != flt["tone"]:
        return False
    if flt.get("plain_or_patterned") and \
            item["plain_or_patterned"] != flt["plain_or_patterned"]:
        return False
    if flt.get("styles") and not set(flt["styles"]) & set(item["styles"]):
        return False
    if flt.get("features") and \
            not set(flt["features"]) <= set(item["features"]):
        return False
    if flt.get("suitable_for") and \
            not set(flt["suitable_for"]) & set(item["suitable_for"]):
        return False
    if flt.get("opacity") and item["opacity"] != flt["opacity"]:
        return False
    if flt.get("max_price") is not None and \
            item["price_sar_per_m"] > flt["max_price"]:
        return False
    return True


def compact(item):
    return {
        "code": item["code"],
        "name_en": item["name_en"],
        "name_ar": item["name_ar"],
        "material": item["material"],
        "primary_color": item["primary_color"],
        "pattern_type": item["pattern_type"],
        "price_sar_per_m": item["price_sar_per_m"],
        "image": item.get("image", ""),
        "usage": item["usage"],
        "tone": item["tone"],
    }


def search_catalog(usage=None, colors=None, tone=None,
                   plain_or_patterned=None, styles=None, features=None,
                   suitable_for=None, opacity=None, max_price=None,
                   limit=6):
    """Filter the catalog. Returns (summaries, relaxed_constraints).

    Filters are relaxed in RELAX_ORDER until at least MIN_RESULTS match.
    """
    flt = {"usage": usage, "colors": list(colors or []), "tone": tone,
           "plain_or_patterned": plain_or_patterned,
           "styles": list(styles or []), "features": list(features or []),
           "suitable_for": list(suitable_for or []), "opacity": opacity,
           "max_price": max_price}
    specs = load_specs()
    relaxed = []
    results = [i for i in specs if _matches(i, flt)]
    for name in RELAX_ORDER:
        if len(results) >= MIN_RESULTS:
            break
        if name == "max_price" and flt["max_price"] is not None:
            flt["max_price"] = None
            relaxed.append(name)
        elif name in ("colors", "styles", "features", "suitable_for") \
                and flt[name]:
            flt[name] = []
            relaxed.append(name)
        elif name in ("tone", "opacity", "plain_or_patterned") \
                and flt[name]:
            flt[name] = None
            relaxed.append(name)
        else:
            continue
        results = [i for i in specs if _matches(i, flt)]
    return [compact(i) for i in results[:limit]], relaxed


def map_needs_to_features(text):
    """Map user needs to catalog features. Returns a sorted list."""
    t = (text or "").lower()
    found = set()
    if any(w in t for w in
           ["pet", "dog", "cat", "كلب", "قطة", "قط", "حيوان"]):
        found.update(["pet-friendly", "scratch-resistant"])
    if any(w in t for w in
           ["kid", "child", "baby", "toddler", "طفل", "أطفال", "عيال",
            "رضيع"]):
        found.update(["easy-clean", "stain-resistant", "antibacterial"])
    if any(w in t for w in
           ["hotel", "restaurant", "فندق", "مطعم", "hospitality", "ضيافة"]):
        found.add("fire-resistant")
    bedroom = any(w in t for w in ["bedroom", "غرفة نوم", "غرف نوم"])
    curtain = any(w in t for w in ["curtain", "ستارة", "ستائر"])
    if bedroom and curtain:
        found.add("blackout")
    return sorted(found)


def contains_egyptian(text):
    """True if the text contains Egyptian-dialect markers."""
    t = text or ""
    return any(m in t for m in EGYPTIAN_MARKERS)


def is_arabic(text):
    return any("؀" <= ch <= "ۿ" for ch in (text or ""))
