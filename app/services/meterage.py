"""Meterage and quote estimates for reupholstery picks.

One config module: base yardage assumes 137 cm fabric width. Patterned
fabrics (pattern/repeat) take a +15% uplift. Every result rounds UP to
the nearest 0.5 m. Curtains need the window width x height (asked once);
without them the item reports "needs measurements".
"""
import math

FABRIC_WIDTH_M = 1.37
PATTERN_UPLIFT = 1.15

# Base meters per piece at 137 cm width, before pattern uplift.
YARDAGE = {
    "loveseat": 12.0,
    "sofa-2-seat": 14.5,
    "sofa-3-seat": 16.5,
    "sofa-6-seat": 20.0,
    "sectional": 20.0,
    "wingback": 9.0,
    "armchair": 5.5,
    "ottoman": 3.2,
    "throw-pillow": 0.5,
}

# Consultant target -> yardage key. "cushions" means the seat cushions
# only: 40% of a 3-seat sofa piece. "body" is the same piece minus the
# pillows, kept for the upholsterer summary.
TARGET_PIECE = {
    "sofa": "sofa-3-seat",
    "armchair": "armchair",
    "cushions": "sofa-3-seat",
    "curtains": "curtains",
}
CUSHIONS_FRACTION = 0.4
CURTAIN_FULLNESS = 2.2
CURTAIN_HEM_M = 1.0
CURTAIN_DROPS_DEFAULT = 2


def round_up_half(meters):
    """Round UP to the nearest 0.5 m."""
    return math.ceil(float(meters) * 2) / 2


def is_patterned(fabric):
    """Pattern/repeat from the catalog spec (never guessed)."""
    if not fabric:
        return False
    if (fabric.get("plain_or_patterned") or "").lower() == "patterned":
        return True
    return bool((fabric.get("pattern_type") or "").lower() not in
                ("", "solid", "plain"))


def piece_meters(piece_key, fabric=None, count=1):
    """Base meters for a yardage key (throw-pillow uses count)."""
    if piece_key == "throw-pillow":
        base = YARDAGE["throw-pillow"] * max(1, int(count or 1))
    else:
        base = YARDAGE[piece_key]
    if is_patterned(fabric):
        base *= PATTERN_UPLIFT
    return round_up_half(base)


def curtain_meters(width_m, height_m, fabric=None, drops=None):
    """Curtain meters; height is recorded for the summary.

    Formula: ((width x 2.2 fullness / 1.37) + 1 hem) x drops.
    Returns None when the window size is unknown.
    """
    if not width_m or not height_m:
        return None
    drops = drops or CURTAIN_DROPS_DEFAULT
    base = ((float(width_m) * CURTAIN_FULLNESS / FABRIC_WIDTH_M)
            + CURTAIN_HEM_M) * drops
    if is_patterned(fabric):
        base *= PATTERN_UPLIFT
    return round_up_half(base)


def estimate_item(target, fabric, curtain_dims=None, pillow_count=0):
    """Meters for one assigned item. Returns (meters, note).

    meters is None when measurements are still missing (curtains).
    """
    target = (target or "").lower()
    if target == "curtains":
        dims = curtain_dims or {}
        meters = curtain_meters(dims.get("width_m"), dims.get("height_m"),
                                fabric, dims.get("drops"))
        if meters is None:
            return None, "needs measurements"
        return meters, ""
    if target == "cushions":
        base = YARDAGE["sofa-3-seat"] * CUSHIONS_FRACTION
        if pillow_count:
            base += YARDAGE["throw-pillow"] * max(0, int(pillow_count))
        if is_patterned(fabric):
            base *= PATTERN_UPLIFT
        note = "seat cushions only"
        if pillow_count:
            note += " + %d throw pillow(s)" % pillow_count
        return round_up_half(base), note
    piece = TARGET_PIECE.get(target)
    if piece is None:
        return None, "unknown piece"
    return piece_meters(piece, fabric), ""


def quote(assignments, fabrics, curtain_dims=None, extras=None):
    """Quote a {target: code} map.

    fabrics maps code -> catalog spec, extras maps target ->
    throw-pillow count. Returns {"items": [...], "total", "missing":
    [...]} where missing lists targets that still need measurements.
    """
    items = []
    missing = []
    total = 0.0
    for target, code in (assignments or {}).items():
        fabric = (fabrics or {}).get(code, {})
        pillows = ((extras or {}).get(target) or 0)
        meters, note = estimate_item(target, fabric, curtain_dims,
                                     pillow_count=pillows)
        price = fabric.get("price_sar_per_m")
        line = None
        if meters is not None and price is not None:
            line = round(meters * price, 2)
            total += line
        else:
            missing.append(target)
        items.append({"target": target, "code": code,
                      "fabric_name_en": fabric.get("name_en", ""),
                      "fabric_name_ar": fabric.get("name_ar", ""),
                      "meters": meters, "price_sar_per_m": price,
                      "line_total": line, "note": note})
    return {"items": items, "total": round(total, 2), "missing": missing,
            "currency": "SAR"}
