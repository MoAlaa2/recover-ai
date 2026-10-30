"""Minimal SAM 3.1 mask codec (one_bit payloads).

Wire grammar: docs at https://dev.meta.ai/docs/sam/reading-segmentation.
Reference decoder: @meta-sam/parser mask-codec.js (MIT-style reference).
Alphabet: printable ASCII 0x21-0x7e except " \\ , ; < > |. Payloads carry a
5-char base85 length prefix, then 5 chars per 4 bytes. one_bit raster is a
context-coded bitplane decoded here; lossless (~) is rejected (request
one_bit via metadata mask_encoding instead).
"""
import re

_EXCLUDED = set('"\\,;<>|')
ALPHABET = "".join(chr(c) for c in range(0x21, 0x7F)
                   if chr(c) not in _EXCLUDED)
_RADIX = 85
_VALUES = {c: i for i, c in enumerate(ALPHABET)}

_MASK32 = 0xFFFFFFFF
_TOP = 1 << 24
_BOTTOM = 1 << 16
_INCREMENT = 14
_COUNT_LIMIT = 4096
_CONTEXT_COUNT = 1 << 12
_PADDING = 2


class MaskError(ValueError):
    """Malformed SAM 3.1 mask payload."""


def _digit(ch):
    value = _VALUES.get(ch, -1)
    if value < 0 or value >= _RADIX:
        raise MaskError("mask payload contains an invalid character")
    return value


def unpack(payload):
    """Base85-decode a payload (without its ~ or ! marker) to bytes."""
    if len(payload) < 5:
        raise MaskError("mask payload is missing its length prefix")
    length = 0
    for ch in payload[:5]:
        length = length * _RADIX + _digit(ch)
    rem = length % 4
    expected = 5 + (length // 4) * 5 + (0 if rem == 0 else rem + 1)
    if len(payload) != expected:
        raise MaskError("mask payload length does not match its prefix")
    out = bytearray(length)
    src = 5
    dest = 0
    full = length - rem
    while dest < full:
        value = 0
        for i in range(5):
            value = value * _RADIX + _digit(payload[src + i])
        if value > _MASK32:
            raise MaskError("mask payload contains an out-of-range group")
        src += 5
        out[dest] = (value >> 24) & 0xFF
        out[dest + 1] = (value >> 16) & 0xFF
        out[dest + 2] = (value >> 8) & 0xFF
        out[dest + 3] = value & 0xFF
        dest += 4
    if rem:
        value = 0
        for i in range(5):
            add = _digit(payload[src + i]) if i < rem + 1 else _RADIX - 1
            value = value * _RADIX + add
        if value > _MASK32:
            raise MaskError("mask payload contains an out-of-range tail")
        for i in range(rem):
            out[dest + i] = (value >> (24 - i * 8)) & 0xFF
    return bytes(out)


class _RangeDecoder:
    def __init__(self, data):
        if len(data) < 4:
            raise MaskError("mask payload is missing its finalization")
        self._data = data
        self._pos = 0
        self._low = 0
        self._range = _MASK32
        self._code = 0
        self._scaled = 0
        for _ in range(4):
            self._code = ((self._code << 8) | self._read()) & _MASK32

    def _read(self):
        if self._pos >= len(self._data):
            raise MaskError("mask payload ended before decoding completed")
        byte = self._data[self._pos]
        self._pos += 1
        return byte

    def freq(self, total):
        self._scaled = self._range // total
        if self._scaled == 0:
            raise MaskError("mask payload has invalid coding state")
        value = ((self._code - self._low) & _MASK32) // self._scaled
        return total - 1 if value >= total else value

    def decode(self, cumulative, frequency):
        self._low = (self._low + self._scaled * cumulative) & _MASK32
        self._range = self._scaled * frequency
        while True:
            renorm = ((self._low ^ (self._low + self._range))
                      & _MASK32) < _TOP
            if not renorm:
                if self._range >= _BOTTOM:
                    break
                self._range = ((-self._low) & _MASK32) & (_BOTTOM - 1)
            self._code = ((self._code << 8) | self._read()) & _MASK32
            self._low = (self._low << 8) & _MASK32
            self._range = (self._range << 8) & _MASK32


def _context_at(raster, pos, prior, earlier):
    return (raster[pos - 1] | (raster[pos - 2] << 1)
            | (raster[prior - 2] << 2) | (raster[prior - 1] << 3)
            | (raster[prior] << 4) | (raster[prior + 1] << 5)
            | (raster[prior + 2] << 6) | (raster[earlier - 2] << 7)
            | (raster[earlier - 1] << 8) | (raster[earlier] << 9)
            | (raster[earlier + 1] << 10) | (raster[earlier + 2] << 11))


def _paeth(left, up, upper_left):
    est = left + up - upper_left
    dl, du, dul = abs(est - left), abs(est - up), abs(est - upper_left)
    if dl <= du and dl <= dul:
        return left
    return up if du <= dul else upper_left


def _predict_byte(buf, offset, x, y, mode, width):
    left = buf[offset - 1] if x > 0 else 0
    up = buf[offset - width] if y > 0 else 0
    if mode == 1:
        return up
    if mode == 2:
        return left
    if mode == 3:
        return (left + up) >> 1
    ul = buf[offset - width - 1] if (x > 0 and y > 0) else 0
    if mode == 0:
        return _paeth(left, up, ul)
    if ul >= max(left, up):
        return min(left, up)
    if ul <= min(left, up):
        return max(left, up)
    return left + up - ul


def _unzig(value, prediction):
    delta = -((value + 1) >> 1) if value & 1 else value >> 1
    return (prediction + delta) & 0xFF


def _zero_context(residuals, offset, x, y, width):
    left = 1 if (x == 0 or residuals[offset - 1] == 0) else 0
    up = 1 if (y == 0 or residuals[offset - width] == 0) else 0
    ul = 1 if (x == 0 or y == 0
               or residuals[offset - width - 1] == 0) else 0
    ur = 1 if (y == 0 or x >= width - 1
               or residuals[offset - width + 1] == 0) else 0
    return left | (up << 1) | (ul << 2) | (ur << 3)


_ZERO_INC = 32
_ZERO_LIMIT = 16384
_ORDER1_INC = 56
_ORDER1_LIMIT = 8192
_ORDER2_STEP = 14 * 44
_ORDER2_LIMIT = 14 * 3584
_ORDER0_STEP = 2 * 16
_ORDER0_LIMIT = 2 * 2048


def decode_lossless(payload, width, height):
    """Decode a ~-marked payload to a row-major bytes object of 0/1."""
    if not payload.startswith("~"):
        raise MaskError("lossless mask payloads must start with ~")
    packed = unpack(payload[1:])
    if len(packed) < 5:
        raise MaskError("lossless mask payload is truncated")
    selector = packed[0]
    if selector > 4:
        raise MaskError("lossless mask payload uses an invalid predictor")
    decoder = _RangeDecoder(packed[1:])
    length = width * height
    out = bytearray(length)
    residuals = bytearray(length)
    zero_counts = [1] * 32
    order_one = [1] * (256 * 256)
    order_one_totals = [256] * 256
    order_zero = [2] * 256
    order_zero_total = 512
    order_two = {}
    previous = 0
    for offset in range(length):
        x = offset % width
        y = offset // width
        zctx = _zero_context(residuals, offset, x, y, width) << 1
        zero, nonzero = zero_counts[zctx], zero_counts[zctx + 1]
        bit = 0 if decoder.freq(zero + nonzero) < zero else 1
        if bit == 0:
            decoder.decode(0, zero)
        else:
            decoder.decode(zero, nonzero)
        zero_counts[zctx + bit] += _ZERO_INC
        if zero_counts[zctx] + zero_counts[zctx + 1] >= _ZERO_LIMIT:
            zero_counts[zctx] = zero_counts[zctx] >> 1 or 1
            zero_counts[zctx + 1] = zero_counts[zctx + 1] >> 1 or 1
        symbol = 0
        if bit == 1:
            above = residuals[offset - width] if offset >= width else 0
            key = (previous << 8) | above
            second = order_two.get(key)
            if second is None:
                second = [0] * 257
                order_two[key] = second
            first = previous << 8
            excluded = second[0] + order_one[first] + order_zero[0]
            total = (second[256] + order_one_totals[previous]
                     + order_zero_total - excluded)
            target = decoder.freq(total)
            cumulative = 0
            symbol = 1
            frequency = (second[1] + order_one[first + 1]
                         + order_zero[1])
            while cumulative + frequency <= target:
                cumulative += frequency
                symbol += 1
                if symbol >= 256:
                    raise MaskError("lossless mask payload is malformed")
                frequency = (second[symbol] + order_one[first + symbol]
                             + order_zero[symbol])
            decoder.decode(cumulative, frequency)
            second[symbol] += _ORDER2_STEP
            second[256] += _ORDER2_STEP
            if second[256] >= _ORDER2_LIMIT:
                total_after = 0
                for v in range(256):
                    second[v] >>= 1
                    total_after += second[v]
                second[256] = total_after
            order_one[first + symbol] += _ORDER1_INC
            order_one_totals[previous] += _ORDER1_INC
            if order_one_totals[previous] >= _ORDER1_LIMIT:
                total_after = 0
                for v in range(256):
                    scaled = order_one[first + v] >> 1 or 1
                    order_one[first + v] = scaled
                    total_after += scaled
                order_one_totals[previous] = total_after
            order_zero[symbol] += _ORDER0_STEP
            order_zero_total += _ORDER0_STEP
            if order_zero_total >= _ORDER0_LIMIT:
                order_zero_total = 0
                for v in range(256):
                    order_zero[v] >>= 1
                    order_zero_total += order_zero[v]
        residuals[offset] = symbol
        out[offset] = _unzig(
            symbol, _predict_byte(out, offset, x, y, selector, width))
        previous = symbol
    return bytes(1 if b >= 129 else 0 for b in out)


def decode_one_bit(payload, width, height):
    """Decode a !-marked payload to a row-major bytes object of 0/1."""
    if not payload.startswith("!"):
        raise MaskError("one_bit mask payloads must start with !")
    decoder = _RangeDecoder(unpack(payload[1:]))
    counts = [1] * (_CONTEXT_COUNT * 2)
    stride = width + 2 * _PADDING
    padded = bytearray(stride * (height + _PADDING))
    out = bytearray(width * height)
    for y in range(height):
        row = (y + _PADDING) * stride + _PADDING
        base = y * width
        for x in range(width):
            pos = row + x
            ctx = _context_at(padded, pos, pos - stride, pos - 2 * stride)
            off = ctx << 1
            zero, one = counts[off], counts[off + 1]
            bit = 0 if decoder.freq(zero + one) < zero else 1
            if bit == 0:
                decoder.decode(0, zero)
            else:
                decoder.decode(zero, one)
            padded[pos] = bit
            out[base + x] = bit
            counts[off + bit] += _INCREMENT
            if counts[off] + counts[off + 1] >= _COUNT_LIMIT:
                counts[off] = counts[off] >> 1 or 1
                counts[off + 1] = counts[off + 1] >> 1 or 1
    return bytes(out)


_RECORD = re.compile(
    r"(\d+)<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)"
    r"(?:;c=([\d.]+))?\|><\|mask;x=(\d+);y=(\d+)(?:;c=([\d.]+))?;"
    r"data=(\d+),(\d+),([~!])(.*?)\|>")

FRAME = re.compile(r"<(\d+)f>")


def parse_output_text(text):
    """Parse SAM output_text into records.

    Returns a list of dicts: frame, id, box, score (mask confidence,
    else box confidence, else 1.0 when SAM emits none), mask_w,
    mask_h, mask_encoding (one_bit/lossless), mask_payload (marker).
    """
    records = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        frame = FRAME.match(line)
        frame_id = int(frame.group(1)) if frame else 0
        body = line[frame.end():] if frame else line
        for m in _RECORD.finditer(body):
            (obj_id, x1, y1, x2, y2, fw, fh, box_c, mx, my,
             mask_c, mh, mw, enc, payload) = m.groups()
            score = 1.0
            for raw in (mask_c, box_c):
                if raw is not None:
                    try:
                        score = float(raw)
                    except ValueError:
                        continue
                    break
            records.append({
                "id": int(obj_id),
                "frame": frame_id,
                "box": (int(x1), int(y1), int(x2), int(y2)),
                "frame_size": (int(fw), int(fh)),
                "score": score,
                "mask_origin": (int(mx), int(my)),
                "mask_size": (int(mh), int(mw)),
                "mask_encoding": ("lossless" if enc == "~"
                                   else "one_bit"),
                "mask_payload": enc + payload,
            })
    return records


def decode_record(record):
    """Decode one parsed record to (bytes 0/1 raster, width, height)."""
    height, width = record["mask_size"]
    if record["mask_encoding"] == "one_bit":
        raster = decode_one_bit(record["mask_payload"], width, height)
    elif record["mask_encoding"] == "lossless":
        raster = decode_lossless(record["mask_payload"], width, height)
    else:
        raise MaskError("unknown mask encoding")
    if len(raster) != width * height:
        raise MaskError("decoded mask size mismatch")
    return raster, width, height
