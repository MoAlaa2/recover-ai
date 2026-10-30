"""Deterministic swap checks (no model in the loop).

Two guards run on every swap candidate, single and multi, after the
Spark verify score and regardless of it:

* colour: mean CIE Lab of the result inside the item's mask versus the
  mean Lab of the fabric swatch. Room lighting shifts lightness a lot
  (a correct saffron sofa measured ΔL −27 against its flat swatch), so
  ΔE2000 is taken with the result's L set to the swatch's L (hue +
  chroma), above COLOUR_MAX_DE fails, and a separate lightness guard
  (|ΔL| above LIGHTNESS_MAX_DL, e.g. navy on a beige order) also fails.
* coverage: the item's mask is split into a grid of cells; a cell is
  covered when its mean colour passes the same colour rule against the
  swatch. The covered share must reach COVERAGE_MIN. (A plain
  changed-pixel share fails honest like-for-like swaps: oat pillows on
  beige pillows change only ~66% of pixels while being correct.)

A failing candidate is retried once with a corrective hint; a second
failure means the item is reported as "not applied" with the reason,
never shown as the headline fabric. Numbers ride along in the result
("checks") so the Under-the-hood trace can show them.
"""
import io
import math

import numpy as np
from PIL import Image

COLOUR_MAX_DE = 20.0
LIGHTNESS_MAX_DL = 45.0
COVERAGE_MIN = 0.85
COVERAGE_CELLS = 24
CHANGE_THRESHOLD = 14
CHECK_SIDE = 512

RESIDUE_MAX_DE = 8.0
RESIDUE_MAX_FRAC = 0.003
RESIDUE_NEW_DE = 12.0

REASON_COLOUR = "colour mismatch"
REASON_COVERAGE = "low coverage"
REASON_RESIDUE = "old fabric left"


def _srgb_to_lab(rgb):
    """rgb: float array (..., 3) in 0..1 -> Lab (..., 3), D65."""
    c = np.clip(rgb, 0.0, 1.0)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    # einsum, not BLAS matmul: Accelerate warns on large (N,3) inputs.
    xyz = np.einsum("...i,ji->...j", lin, m)
    white = np.array([0.95047, 1.0, 1.08883])
    t = xyz / white
    eps, kappa = 216.0 / 24389.0, 24389.0 / 27.0
    f = np.where(t > eps, np.cbrt(t), (kappa * t + 16.0) / 116.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def mean_lab(image, mask=None):
    """Mean Lab of an RGB image, optionally inside a binary L mask."""
    arr = np.asarray(image.convert("RGB")).astype(np.float64) / 255.0
    if mask is not None:
        sel = np.asarray(mask.convert("L")) > 127
        if not sel.any():
            return None
        arr = arr[sel]
    else:
        arr = arr.reshape(-1, 3)
    return _srgb_to_lab(arr.mean(axis=0))


def delta_e2000(lab1, lab2):
    """CIEDE2000 colour difference between two Lab triples."""
    L1, a1, b1 = [float(v) for v in lab1]
    L2, a2, b2 = [float(v) for v in lab2]
    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    cbar = (c1 + c2) / 2.0
    g = 0.5 * (1 - math.sqrt(cbar ** 7 / (cbar ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)

    def hp(a, b):
        if a == 0 and b == 0:
            return 0.0
        h = math.degrees(math.atan2(b, a))
        return h + 360.0 if h < 0 else h

    h1p, h2p = hp(a1p, b1), hp(a2p, b2)
    dL = L2 - L1
    dC = c2p - c1p
    if c1p * c2p == 0:
        dh = 0.0
    else:
        dh = h2p - h1p
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360
    dH = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2.0))
    Lbar = (L1 + L2) / 2.0
    Cbar = (c1p + c2p) / 2.0
    if c1p * c2p == 0:
        hbar = h1p + h2p
    else:
        hsum = h1p + h2p
        if abs(h1p - h2p) <= 180:
            hbar = hsum / 2.0
        elif hsum < 360:
            hbar = (hsum + 360) / 2.0
        else:
            hbar = (hsum - 360) / 2.0
    T = (1 - 0.17 * math.cos(math.radians(hbar - 30))
         + 0.24 * math.cos(math.radians(2 * hbar))
         + 0.32 * math.cos(math.radians(3 * hbar + 6))
         - 0.20 * math.cos(math.radians(4 * hbar - 63)))
    dtheta = 30 * math.exp(-((hbar - 275) / 25.0) ** 2)
    rc = 2 * math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7))
    sl = 1 + 0.015 * (Lbar - 50) ** 2 / math.sqrt(20 + (Lbar - 50) ** 2)
    sc = 1 + 0.045 * Cbar
    sh = 1 + 0.015 * Cbar * T
    rt = -math.sin(math.radians(2 * dtheta)) * rc
    return math.sqrt((dL / sl) ** 2 + (dC / sc) ** 2 + (dH / sh) ** 2
                     + rt * (dC / sc) * (dH / sh))


def _de2000_array(lab, ref):
    """CIEDE2000 of every row of lab (N,3) against one Lab triple."""
    L1, a1, b1 = lab[:, 0], lab[:, 1], lab[:, 2]
    L2, a2, b2 = [float(v) for v in ref]
    c1 = np.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    cbar = (c1 + c2) / 2.0
    g = 0.5 * (1 - np.sqrt(cbar ** 7 / (cbar ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360.0
    h1p = np.where((a1p == 0) & (b1 == 0), 0.0, h1p)
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360.0
    h2p = np.where((a2p == 0) & (b2 == 0), 0.0, h2p)
    dL = L2 - L1
    dC = c2p - c1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(c1p * c2p == 0, 0.0, dh)
    dH = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh / 2.0))
    Lbar = (L1 + L2) / 2.0
    Cbar = (c1p + c2p) / 2.0
    hsum = h1p + h2p
    hbar = np.where(np.abs(h1p - h2p) <= 180, hsum / 2.0,
                    np.where(hsum < 360, (hsum + 360) / 2.0,
                             (hsum - 360) / 2.0))
    hbar = np.where(c1p * c2p == 0, hsum, hbar)
    T = (1 - 0.17 * np.cos(np.radians(hbar - 30))
         + 0.24 * np.cos(np.radians(2 * hbar))
         + 0.32 * np.cos(np.radians(3 * hbar + 6))
         - 0.20 * np.cos(np.radians(4 * hbar - 63)))
    dtheta = 30 * np.exp(-((hbar - 275) / 25.0) ** 2)
    rc = 2 * np.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7))
    sl = 1 + 0.015 * (Lbar - 50) ** 2 / np.sqrt(20 + (Lbar - 50) ** 2)
    sc = 1 + 0.045 * Cbar
    sh = 1 + 0.015 * Cbar * T
    rt = -np.sin(np.radians(2 * dtheta)) * rc
    return np.sqrt((dL / sl) ** 2 + (dC / sc) ** 2 + (dH / sh) ** 2
                   + rt * (dC / sc) * (dH / sh))


def _largest_component_frac(flags):
    """Largest 4-connected True region of a 2-D bool array, as a
    fraction of the whole array."""
    from collections import deque
    h, w = flags.shape
    seen = np.zeros_like(flags, dtype=bool)
    best = 0
    ys, xs = np.where(flags)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if seen[y0, x0]:
            continue
        seen[y0, x0] = True
        q = deque([(y0, x0)])
        n = 0
        while q:
            y, x = q.popleft()
            n += 1
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and flags[ny, nx] \
                        and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        best = max(best, n)
    return best / float(h * w)


def residue_check(original, result_image, mask, swatch_bytes,
                  extra_swatches=()):
    """Old fabric left inside the mask after the swap.

    A result pixel (inside mask) is residue when it sits within
    RESIDUE_MAX_DE of the ORIGINAL fabric's mean colour AND does not
    look like any of the new fabrics (this item's swatch plus
    extra_swatches, e.g. the sofa's when the mask is sofa ∪ pillows;
    hue/chroma ΔE under RESIDUE_NEW_DE). A connected residue region
    above RESIDUE_MAX_FRAC of the image fails. Where a new fabric is
    like-for-like with the old one the test cannot tell them apart,
    and those pixels count as covered (skipped=True when nothing
    could be judged).
    """
    from PIL import ImageFilter
    small_o = _small(original, "RGB")
    m_img = mask.convert("L").resize(small_o.size, Image.NEAREST)
    m = np.asarray(m_img) > 127
    if not m.any():
        return {"residue": None, "ok": True, "skipped": True}
    orig_mean = mean_lab(small_o, m_img)
    news = [swatch_lab(b) for b in (swatch_bytes,) + tuple(extra_swatches)]
    news = [n for n in news if n is not None]
    if orig_mean is None or not news:
        return {"residue": None, "ok": True, "skipped": True}
    if all(colour_match(orig_mean, n)[0] < RESIDUE_NEW_DE for n in news):
        return {"residue": None, "ok": True, "skipped": True}
    small_r = result_image.convert("RGB").resize(small_o.size,
                                                 Image.BILINEAR)
    small_r = small_r.filter(ImageFilter.BoxBlur(1))
    arr = np.asarray(small_r).astype(np.float64) / 255.0
    lab = _srgb_to_lab(arr.reshape(-1, 3))
    old = _de2000_array(lab, orig_mean) < RESIDUE_MAX_DE
    like_new = np.zeros(lab.shape[0], dtype=bool)
    for want in news:
        eq = lab.copy()
        eq[:, 0] = want[0]
        like_new |= _de2000_array(eq, want) < RESIDUE_NEW_DE
    flags = (old & ~like_new).reshape(m.shape) & m
    frac = _largest_component_frac(flags) if flags.any() else 0.0
    return {"residue": round(frac, 4), "ok": frac <= RESIDUE_MAX_FRAC,
            "skipped": False}


def _small(img, mode):
    out = img.convert(mode)
    if max(out.size) > CHECK_SIDE:
        out = out.copy()
        out.thumbnail((CHECK_SIDE, CHECK_SIDE), Image.BILINEAR)
    return out


def swatch_lab(swatch_bytes):
    return mean_lab(_small(Image.open(io.BytesIO(swatch_bytes)), "RGB"))


def colour_match(got, want):
    """(ΔE2000 with lightness equalised, ΔL, ok) for two Lab means."""
    eq = np.array(got, dtype=float).copy()
    eq[0] = want[0]
    de = delta_e2000(eq, want)
    dl = float(got[0] - want[0])
    return de, dl, (de <= COLOUR_MAX_DE and abs(dl) <= LIGHTNESS_MAX_DL)


def colour_check(result_image, mask, swatch_bytes):
    """Hue/chroma ΔE2000 + lightness guard, masked result vs swatch."""
    small = _small(result_image, "RGB")
    m = mask.convert("L").resize(small.size, Image.NEAREST)
    got = mean_lab(small, m)
    want = swatch_lab(swatch_bytes)
    if got is None or want is None:
        return {"delta_e": None, "delta_l": None, "ok": False}
    de, dl, ok = colour_match(got, want)
    return {"delta_e": round(de, 1), "delta_l": round(dl, 1), "ok": ok}


def changed_share(original, result_image, mask,
                  threshold=CHANGE_THRESHOLD):
    """Share of mask pixels that differ from the original (trace info)."""
    small_o = _small(original, "RGB")
    small_r = result_image.convert("RGB").resize(small_o.size,
                                                 Image.BILINEAR)
    m = np.asarray(mask.convert("L").resize(small_o.size,
                                            Image.NEAREST)) > 127
    if not m.any():
        return 0.0
    diff = np.abs(np.asarray(small_o).astype(int)
                  - np.asarray(small_r).astype(int)).max(axis=2)
    return round(float(((diff > threshold) & m).sum()) / float(m.sum()), 3)


def coverage_check(result_image, mask, swatch_bytes, cells=COVERAGE_CELLS):
    """Share of the item's mask (by grid cell) that looks like the fabric.

    Each cell of a cells×cells grid over the mask's bounding box counts
    when at least half of it is inside the mask; it is covered when its
    mean colour passes colour_match against the swatch. Unpainted
    regions (old fabric left over) fail their cells.
    """
    small = _small(result_image, "RGB")
    arr = np.asarray(small).astype(np.float64) / 255.0
    m = np.asarray(mask.convert("L").resize(small.size,
                                            Image.NEAREST)) > 127
    want = swatch_lab(swatch_bytes)
    if not m.any() or want is None:
        return {"coverage": 0.0, "ok": False}
    ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    ch = max(1, (y1 - y0) // cells)
    cw = max(1, (x1 - x0) // cells)
    covered = total = 0
    for y in range(y0, y1, ch):
        for x in range(x0, x1, cw):
            sel = m[y:y + ch, x:x + cw]
            if sel.size == 0 or sel.sum() < 0.5 * sel.size:
                continue
            got = _srgb_to_lab(arr[y:y + ch, x:x + cw][sel].mean(axis=0))
            total += 1
            if colour_match(got, want)[2]:
                covered += 1
    cov = covered / float(total) if total else 0.0
    return {"coverage": round(cov, 3), "ok": cov >= COVERAGE_MIN}


def run_checks(original, result_image, mask, swatch_bytes, base=None,
               residue_mask=None, extra_swatches=()):
    """All checks. original is the untouched room photo; base is the
    image the edit was made on (the sofa result for chained pillows);
    residue_mask widens the residue search (sofa ∪ pillows).

    Returns {delta_e, delta_l, coverage, changed, residue, ok, fail}."""
    colour = colour_check(result_image, mask, swatch_bytes)
    cover = coverage_check(result_image, mask, swatch_bytes)
    changed = changed_share(base or original, result_image, mask)
    residue = residue_check(original, result_image,
                            residue_mask or mask, swatch_bytes,
                            extra_swatches)
    fail = None
    if not colour["ok"]:
        fail = REASON_COLOUR
    elif not cover["ok"]:
        fail = REASON_COVERAGE
    elif not residue["ok"]:
        fail = REASON_RESIDUE
    return {"delta_e": colour["delta_e"], "delta_l": colour["delta_l"],
            "coverage": cover["coverage"], "changed": changed,
            "residue": residue["residue"],
            "ok": fail is None, "fail": fail}


def corrective_for(fail, concept):
    """Edit-prompt hint for the retry after a failed check."""
    if fail == REASON_RESIDUE:
        return ("no part of the old %s fabric may remain visible: "
                "cover every surface and the area behind and around "
                "each pillow completely with the new fabric" % concept)
    if fail == REASON_COLOUR:
        return ("the fabric colour on the %s must match the swatch "
                "exactly: same hue, same saturation, same lightness, "
                "uniform across every surface and fold" % concept)
    return ("cover the ENTIRE %s with the new fabric: every surface, "
            "seat, back, arms and sides, leave no part in the old "
            "fabric" % concept)
