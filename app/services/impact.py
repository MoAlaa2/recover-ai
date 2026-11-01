"""Sourced impact figures (estimates are never presented as fact).

Manufacturing CO2e: EPD NEPD-1805-759 (Helland Duun 3-seater sofa,
47.7 kg product weight): 52 kg CO2e for life-cycle stages A1-A3.
Furniture waste avoided ~= product weight, rounded to 48 kg.
Other pieces scale by weight class; curtains and loose pillows have
no sourced figure and count as 0 (they are omitted, never estimated).
"""
CO2_PER_3SEAT_KG = 52.0
WASTE_PER_3SEAT_KG = 48.0
CO2_SOURCE = "EPD NEPD-1805-759 (Helland Duun 3-seater sofa)"
CO2_FACTORS = {
    "loveseat": 0.75,
    "sofa-2-seat": 0.85,
    "sofa-3-seat": 1.0,
    "sofa-6-seat": 1.4,
    "sectional": 1.4,
    "wingback": 0.35,
    "armchair": 0.35,
    "ottoman": 0.2,
    "throw-pillow": 0.0,
}

# Consultant target -> piece. Loose pillows and curtains have no
# sourced figure and count as nothing (never a whole sofa); sofa +
# cushions count one sofa.
TARGET_PIECE = {
    "sofa": "sofa-3-seat",
    "armchair": "armchair",
    "cushions": "throw-pillow",
    "curtains": None,
}


def avoided(assignments):
    """(co2_kg, waste_kg) avoided by keeping the assigned pieces."""
    pieces = {TARGET_PIECE.get(t) for t in (assignments or {})}
    pieces.discard(None)
    co2 = sum(CO2_PER_3SEAT_KG * CO2_FACTORS[p] for p in pieces)
    waste = sum(WASTE_PER_3SEAT_KG * CO2_FACTORS[p] for p in pieces)
    return round(co2, 1), round(waste, 1)
