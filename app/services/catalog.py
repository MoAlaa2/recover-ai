"""Catalog access for the consultant tools.

Reads data/fabric_specs.json. search_catalog filters locally and reports
which constraints were relaxed so the agent can say so honestly.
"""
import json

from app.core.config import SPECS_PATH

_SPECS = None
MIN_RESULTS = 3

# Relaxed in this order until enough fabrics match: style first, then
# tone/color, then budget, functional needs (features) next, and the
# snag-safe filter last.
RELAX_ORDER = ["styles", "tone", "colors", "suitable_for",
               "plain_or_patterned", "opacity", "max_price",
               "features", "any_features", "snag_risk"]

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
    if flt.get("any_features") and \
            not set(flt["any_features"]) & set(item["features"]):
        return False
    if flt.get("suitable_for") and \
            not set(flt["suitable_for"]) & set(item["suitable_for"]):
        return False
    if flt.get("opacity") and item["opacity"] != flt["opacity"]:
        return False
    if flt.get("max_price") is not None and \
            item["price_sar_per_m"] > flt["max_price"]:
        return False
    if flt.get("snag_levels") is not None and \
            item.get("snag_risk") not in flt["snag_levels"]:
        return False
    return True


# With pets, loop and raised-pile textures trap claws and fur.
PET_UNSAFE_MATERIALS = ("boucle",)
PET_UNSAFE_PATTERNS = ("honeycomb",)

# Tight weaves first when pets are around.
PET_PREFERRED_MATERIALS = {"performance velvet": 0,
                           "performance linen": 0,
                           "cotton canvas": 1,
                           "linen print": 1}


def _pet_rank(item):
    return PET_PREFERRED_MATERIALS.get(item["material"], 2)


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
                   any_features=None, suitable_for=None, opacity=None,
                   max_price=None, limit=6, protected=(),
                   pet_safe=False, snag_levels=None):
    """Filter the catalog. Returns (summaries, relaxed_constraints).

    Filters are relaxed in RELAX_ORDER until at least MIN_RESULTS match.
    Protected features are only dropped as a last resort. relaxed lists
    only filters that actually changed, computed from the real diff.
    """
    flt = {"usage": usage, "colors": list(colors or []), "tone": tone,
           "plain_or_patterned": plain_or_patterned,
           "styles": list(styles or []), "features": list(features or []),
           "any_features": list(any_features or []),
           "suitable_for": list(suitable_for or []), "opacity": opacity,
           "max_price": max_price,
           "snag_levels": list(snag_levels) if snag_levels else None}
    original = {k: (list(v) if isinstance(v, list) else v)
                for k, v in flt.items()}
    specs = load_specs()
    if pet_safe:
        specs = [i for i in specs
                 if not any(m in i["material"]
                            for m in PET_UNSAFE_MATERIALS)
                 and i["pattern_type"] not in PET_UNSAFE_PATTERNS]
    results = [i for i in specs if _matches(i, flt)]
    for name in RELAX_ORDER:
        if len(results) >= MIN_RESULTS:
            break
        if name == "snag_risk":
            if not flt["snag_levels"]:
                continue
            if flt["snag_levels"] == ["low"]:
                flt["snag_levels"] = ["low", "medium"]
            else:
                flt["snag_levels"] = None
        elif name in ("features", "any_features"):
            keepable = [f for f in flt[name] if f in protected]
            if len(keepable) == len(flt[name]):
                continue
            flt[name] = keepable
        elif name == "max_price" and flt["max_price"] is not None:
            flt["max_price"] = None
        elif name in ("colors", "styles", "suitable_for") and flt[name]:
            flt[name] = []
        elif name in ("tone", "opacity", "plain_or_patterned") \
                and flt[name]:
            flt[name] = None
        else:
            continue
        results = [i for i in specs if _matches(i, flt)]
    if len(results) < MIN_RESULTS:
        dropped = False
        for name in ("features", "any_features"):
            if flt[name]:
                flt[name] = []
                dropped = True
        if dropped:
            results = [i for i in specs if _matches(i, flt)]
    if pet_safe:
        results = sorted(results, key=_pet_rank)
    relaxed = [k for k in flt if flt[k] != original[k]]
    return [compact(i) for i in results[:limit]], relaxed


PET_WORDS = ("pet", "dog", "cat", "كلب", "قطة", "قط", "حيوان")


def has_pets(text):
    """True if the user mentions pets."""
    t = (text or "").lower()
    return any(w in t for w in PET_WORDS)


PIECE_WORDS = {
    "sofa": ["sofa", "couch", "صوفا", "كنبة", "كنب"],
    "armchair": ["armchair", "wingback"],
    "chair": ["chair", "كرسي"],
    "curtains": ["curtain", "drape", "ستارة", "ستائر"],
    "cushions": ["cushion", "pillow", "وسادة", "وسائد", "مخدة", "مخدات"],
    "bed": ["bed", "سرير"],
}

PIECE_NAMES_AR = {"sofa": "الكنبة", "armchair": "كرسي الاسترخاء",
                  "chair": "الكرسي", "curtains": "الستائر",
                  "cushions": "الوسائد", "bed": "السرير"}

# Words that keep a turn inside the consultant's scope.
SCOPE_KEEP_WORDS = [
    "hi", "hello", "hey", "thanks", "thank", "bye", "morning", "evening",
    "welcome", "okay", "great", "nice", "perfect", "lol", "haha",
    "how are you", "who are you", "what do you do", "what can you do",
    "recommend", "suggest", "buy", "choose", "match", "swatch", "catalog",
    "sample", "texture", "fabric", "upholstery", "curtain", "sofa",
    "couch", "chair", "cushion", "pillow", "velvet", "linen", "chenille",
    "boucle", "jacquard", "cotton", "silk", "wool", "sadu", "kilim",
    "color", "colour", "pattern", "plain", "print", "clean", "wash",
    "stain", "care", "maintain", "light", "sun", "decor", "interior",
    "furniture", "room", "bedroom", "living", "majlis", "wall", "paint",
    "floor", "rug", "carpet", "style", "modern", "classic", "budget",
    "price", "cost", "meter", "martindale", "durable", "pet", "kid",
    "hotel", "office", "photo", "picture", "image", "blue", "green",
    "red", "beige", "white", "grey", "gray", "black", "ivory", "gold",
    "silver", "pink", "yellow", "brown", "navy", "teal", "terracotta",
    "olive", "mustard", "help",
    "مرحبا", "هلا", "السلام", "صباح الخير", "مساء الخير", "شكرا",
    "يعطيك العافية", "تمام", "حلو", "ممتاز", "ههه", "طيب", "من انت",
    "وش تسوي", "وش تقدر", "وش تقدم", "ساعدني", "لو سمحت", "قماش",
    "أقمشة", "تنجيد", "ستارة", "ستائر", "كنب", "كنبة", "كرسي",
    "كراسي", "وسادة", "وسائد", "مخدة", "مخمل", "كتان", "قطن",
    "حرير", "صوف", "لون", "ألوان", "نقشة", "سادة", "مشجر",
    "تنظيف", "غسيل", "بقعة", "بقع", "عناية", "إضاءة", "نور",
    "شمس", "ديكور", "أثاث", "غرفة", "غرف", "مجلس", "صالة",
    "جدار", "حائط", "أرضية", "سجاد", "ستايل", "مودرن", "كلاسيك",
    "ميزانية", "سعر", "أسعار", "متر", "متانة", "حيوان", "قطة",
    "كلب", "أطفال", "فندق", "مكتب", "صورة", "صور", "تنصح",
    "أبغى", "أبي", "ودي", "بيت", "منزل", "شقة",
]

# Regexes that mark a turn as outside the consultant's scope.
SCOPE_DECLINE_PATTERNS = [
    r"\d\s*[+\-*/×÷%^]\s*\d",
    r"calculate|equation|\bmath\b|solve for|احسب|رياضيات|معادلة",
    r"python|javascript|\bjava\b|programming|function\s*\(|def\s+\w+\s*\(|"
    r"import\s+\w+|\bbug\b|compiler|\bapi\b|software|database|برمجة|بايثون",
    r"\bnews\b|election|president|minister|\bwar\b|أخبار|انتخابات|رئيس|"
    r"حرب|وزير|حكومة",
    r"relationship|divorce|marry|marriage|health|doctor|diet|invest|"
    r"stock|salary|loan|lawyer|court|زواج|طلاق|علاقة|صحة|دكتور|طبيب|"
    r"رجيم|راتب|قرض|استثمار|محامي|محكمة|قانون",
    r"capital of|who invented|who discovered|tallest|longest|عاصمة|"
    r"من اخترع|من اكتشف|أطول|أين تقع",
    r"football|soccer|premier league|world cup|مباراة|الدوري|كأس العالم|"
    r"كرة القدم",
]


def is_in_scope(text):
    """True when the turn belongs to the consultant.

    Greetings, thanks, session small talk and anything home-related
    stay in scope. Explicit decline categories (math, coding, news,
    personal advice, general knowledge, sports) do not.
    """
    import re
    t = (text or "").lower()
    if not t.strip():
        return True
    if any(w in t for w in SCOPE_KEEP_WORDS):
        return True
    return not any(re.search(p, t) for p in SCOPE_DECLINE_PATTERNS)


def detect_piece(text):
    """Coarse furniture type mentioned in text, or None."""
    t = (text or "").lower()
    for piece, words in PIECE_WORDS.items():
        if any(w in t for w in words):
            return piece
    return None


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
