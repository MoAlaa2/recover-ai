"""ReCover consultant: a multi-turn fabric agent on muse-spark-1.3.

The model never sees the full catalog. It works through three tools
(search_catalog, get_fabric, analyze_room) and returns recommendations
as structured JSON alongside its reply. Session history is kept in an
in-memory dict keyed by session_id.
"""
import base64
import json
import os
import re
import threading
import time
import urllib.request
import uuid

from app.core.config import (BASE_DIR, CHAT_URL, SPARK_MODEL,
                             require_api_key)
from app.services.catalog import (LANG_NAMES, PIECE_NAMES_AR,
                                  contains_egyptian, detect_piece,
                                  detect_user_lang, get_fabric, has_kids,
                                  has_pets, is_arabic, is_in_scope,
                                  is_light_unprotected,
                                  map_needs_to_features, needs_durable,
                                  search_catalog)

SESSIONS = {}
MAX_TOOL_ROUNDS = 4
MAX_RETRIES = 1
CHAT_TIMEOUT = 60

# Muse Spark reasoning + output caps (Chat Completions: top-level
# reasoning_effort minimal..max, none 400s; max_tokens caps reasoning
# tokens + visible output COMBINED, so the base cap keeps ~3x headroom
# over the worst observed rec turn and length finish_reason retries
# once at the high cap instead of truncating a reply mid-block).
REASONING_EFFORT = "low"
CHAT_MAX_TOKENS = 12000
CHAT_MAX_TOKENS_RETRY = 24000

# Temporary latency instrumentation. Active only with CHAT_PERF=1 in the
# environment; one JSON line per model/tool/turn event, under the
# Volume-backed runtime logs dir (survives redeploys on Modal).
PERF = os.environ.get("CHAT_PERF") == "1"


def _perf(event):
    if not PERF:
        return
    event = dict(event)
    event["ts"] = time.time()
    try:
        from app.core.config import runtime_logs_dir
        with open(os.path.join(runtime_logs_dir(),
                               "chat_perf.jsonl"), "a") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass

SYSTEM_PROMPT = """You are the ReCover consultant, a luxury fabric and \
upholstery advisor for a premium Saudi showroom.
Voice: warm, premium, concise. No emoji spam (at most one emoji, or none).

LANGUAGE: reply in the user's language and script: Hindi in Devanagari, \
Arabic in Arabic script, French in French, Spanish in Spanish, English in \
English. Arabic means refined white Saudi dialect only (use: أبغى، أبي، \
ودي، الحين، مره، زين، مجلس، صالة). Never use Egyptian words such as: عايز، \
ازيك، كده، علشان، دلوقتي، فين، ليه. English means warm, premium, concise.

OPENING (first message only): introduce yourself in exactly 2 short lines \
(who you are, what you can do: recommend fabrics, analyze a room photo, \
show your own furniture in a new fabric). Then add this invitation on its \
own line, in the user's language: English: "Talk to me in any language, \
by text or voice." Arabic: "كلمني بأي لغة، كتابة أو صوت." Other \
languages: translate the meaning naturally. Then ask exactly one question.

DISCOVERY: first learn the use: upholstery, curtains, cushions, or a mix \
(list each use exactly once, never repeating a word). \
Then gather naturally, one question at a time, only what is still missing: \
room colors or a room photo, mood (warm/cool/neutral), style, who uses the \
space (kids, pets, hotel, office), opacity for curtains, budget per meter.

TOOLS: you never see the full catalog. Always call search_catalog before \
recommending anything, and get_fabric for details you quote. The server \
analyzes every room photo automatically, so never ask for an image path. \
Never invent fabric codes: every \
recommended code must come from a tool result in this conversation.

NEEDS MAPPING: pets -> pet-friendly and scratch-resistant; kids -> \
easy-clean, stain-resistant and antibacterial; hotel or restaurant -> \
fire-resistant; bedroom curtains -> blackout.

PREVIEW: when the user asks to see, try or preview a fabric on \
their photo, call preview_fabric with a real code from your tool results \
— never describe an imaginary preview. If no photo has been shared yet, \
ask for one and mention the sample rooms.

MULTI-ITEM: when a photo turn lists several changeable items (sofa, \
cushions, curtains), ask once right after the photo is analyzed which \
to change — "I can see a sofa, cushions and curtains — what would you \
like to change?" — with one option per item plus All and Just show me. \
Never repeat that question on later turns or recommendation turns. A \
tap, a chip and a voice answer mean the same thing. Once an item is \
chosen, ask at most ONE more question (the single most useful missing \
need), always offering "Just show me" among its options, then recommend \
on the very next turn; if they say Just show me, skip the questions and \
recommend immediately. When the user picks \
curtains, search with usage curtains so every pick is curtain-suitable. \
After 3 recommendations for a chosen target, the top pick is applied \
automatically; record every pick with assign_fabric. When fabrics are \
assigned to two or more items, offer once to coordinate them.
COST: when the user asks how many meters, how much fabric or how \
much it will cost, call estimate_cost — never guess meters or \
prices. For curtains with no window size yet, ask once for the \
width and height in meters, then call estimate_cost with them. \
Every quote is preliminary: label it "Preliminary estimate — your \
upholsterer will measure." ("تقدير مبدئي — المقاس النهائي من المنجّد.") \
in the user's language. For cushions the tool counts the throw \
pillows it can see: state that number and let the user correct it.

RECOMMENDATIONS: only when you have gathered enough and are ready to \
recommend, reply normally and end with one fenced block on its own lines:
```recommendations
[{"code": "FA-VL-01", "reason": "why in the user's language"}]
```
Exactly 3 items, codes only from tool results. On turns where you are still \
asking questions, do NOT include the block and give NO tip. If you are told \
a code was rejected, fix it with a real code from your tool results. \
When you mention why a fabric fits (features, pets, kids, budget), name \
only needs the user actually stated in this conversation — never invent \
unstated ones (no pets, kids, antibacterial or other features unless the \
user mentioned them).

RELAXED CONSTRAINTS: if a tool result says constraints were relaxed and \
you are NOT showing recommendations on this turn, state plainly in your \
reply which constraint was relaxed (for example budget). On \
recommendation turns the card already carries the one-line receipt, so \
do not restate it in prose.

TIP: include one short professional tip (martindale for heavy use, \
fade-resistant for sunny rooms, washable for kids) only on turns where you \
give recommendations, never otherwise.

OPTIONS: when you ask a question that has a small set of typical answers, \
end your reply with one fenced block on its own lines:
```options
["answer 1", "answer 2", "answer 3"]
```
2 to 4 short options in the user's language. Only when genuinely offering \
choices; omit the block otherwise.

PROSE FIRST: every reply must open with at least one full sentence of \
visible prose in the user's language before any fenced block. Never send \
a reply that is only a fenced block. If the user sends a confused message \
like "??", do not start over: simply rephrase your last open question in \
short, plain words.

ROOM PHOTOS: describe what you see with the word "looks", never "sounds". \
In Arabic use تبدو / شكلها, never any hearing word. If the user's \
described color or material clearly contradicts what is visible in the \
photo, mention it once and ask which is right before recommending.

OFF-TOPIC: if the user greets, asks what you do, or drifts off-topic, \
answer naturally in one or two lines and steer back to fabrics with a \
question."""


# Muse Spark Open on Baseten: optional fallback + scope classifier.
# Behind SPARK_OPEN_FALLBACK=1 (off by default) and only when
# BASETEN_API_KEY exists. Never logged, never committed.
BASEN_CHAT_URL = "https://inference.baseten.co/v1/chat/completions"
BASEN_MODEL = "meta-models/muse-spark-open-1026"


def _spark_open_enabled():
    """True only when the flag is on AND a key exists."""
    return os.environ.get("SPARK_OPEN_FALLBACK", "") == "1" and bool(
        os.environ.get("BASETEN_API_KEY", ""))


def _baseten_key():
    return os.environ.get("BASETEN_API_KEY", "")


def _is_timeout(exc):
    """True for socket/URL timeouts (the only errors that fail over)."""
    import socket
    if isinstance(exc, TimeoutError):
        return True
    return isinstance(getattr(exc, "reason", None),
                      (TimeoutError, socket.timeout))


def _post_baseten(payload):
    """One non-streaming Baseten attempt. Returns the response body."""
    body = dict(payload)
    body["model"] = BASEN_MODEL
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASEN_CHAT_URL, data=data,
        headers={"Authorization": "Bearer " + _baseten_key(),
                 "Content-Type": "application/json"},
        method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    _perf({"kind": "model", "via": "baseten",
           "seconds": round(time.time() - t0, 2)})
    return out


def baseten_scope_allows(text):
    """Second opinion on scope via Spark Open. Fail closed.

    Only consulted when the flag is on; any failure means declined.
    """
    if not _spark_open_enabled() or not (text or "").strip():
        return False
    prompt = ("You guard scope for ReCover, a home-furnishing fabric "
              "consultant. Reply with exactly one word, yes or no: is "
              "the user's message about home interiors, furniture, "
              "fabrics, curtains, upholstery, room photos, or ordinary "
              "session small talk (greetings, thanks, language "
              "questions)? Answer no for math, coding, news, personal "
              "advice, general knowledge, or sports. Message: %s"
              % (text or "")[:500])
    try:
        out = _post_baseten({"messages": [{"role": "user",
                                           "content": prompt}]})
        ans = out["choices"][0]["message"]["content"] or ""
        return ans.strip().lower().startswith("yes")
    except Exception:  # noqa: BLE001 - fail closed, regex decides
        return False


def _chat_payload(messages, tools=None, cap=CHAT_MAX_TOKENS):
    """Chat payload with reasoning effort + combined output cap."""
    payload = {"model": SPARK_MODEL, "messages": messages,
               "reasoning_effort": REASONING_EFFORT,
               "max_tokens": cap}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return payload


def _finish_reason(body):
    try:
        return (body.get("choices") or [{}])[0].get("finish_reason")
    except (AttributeError, IndexError, TypeError):
        return None


def _post_chat(payload, messages, tools, attempt):
    """One HTTP chat round with perf logging. Returns the body."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        CHAT_URL, data=data,
        headers={"Authorization": "Bearer " + require_api_key(),
                 "Content-Type": "application/json"},
        method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    usage = (body.get("usage") or {}) if isinstance(body, dict) \
        else {}
    chars = 0
    for m in messages:
        c = m.get("content", "")
        chars += len(c) if isinstance(c, str) else len(
            json.dumps(c, ensure_ascii=False))
    _perf({"kind": "model", "seconds": round(time.time() - t0, 2),
           "prompt_tokens": usage.get("prompt_tokens"),
           "completion_tokens": usage.get("completion_tokens"),
           "n_messages": len(messages), "prompt_chars": chars,
           "with_tools": bool(tools),
           "attempt": attempt})
    return body


def _call_chat(messages, tools=None):
    """Low-level chat call. Monkeypatch this in tests."""
    payload = _chat_payload(messages, tools)
    last_err = None
    timeouts = 0
    for attempt in range(MAX_RETRIES + 1):
        try:
            body = _post_chat(payload, messages, tools, attempt)
            if _finish_reason(body) == "length" and payload.get(
                    "max_tokens", 0) < CHAT_MAX_TOKENS_RETRY:
                # Truncated mid-reply (maybe mid-rec-block): one silent
                # re-post at the high cap instead of parsing a stub.
                payload = _chat_payload(messages, tools,
                                        CHAT_MAX_TOKENS_RETRY)
                body = _post_chat(payload, messages, tools, attempt)
            return body
        except Exception as exc:  # noqa: BLE001 - retry then raise
            last_err = exc
            if _is_timeout(exc):
                timeouts += 1
            time.sleep(2 * (attempt + 1))
    if timeouts > MAX_RETRIES and _spark_open_enabled():
        try:
            return _post_baseten(payload)
        except Exception as bexc:  # noqa: BLE001 - report both legs
            raise RuntimeError(
                "chat call failed: %s; baseten fallback failed: %s"
                % (last_err, bexc))
    raise RuntimeError("chat call failed: %s" % last_err)


class FenceFilter:
    """Hide fenced blocks from streamed display text.

    The model's ```recommendations / ```options blocks are machine
    payload, never user text. feed() returns safe outside text
    immediately; only a trailing run of 1-2 backticks (a possibly
    split fence marker) is held for the next chunk. flush() releases
    the hold. The full unfiltered text is still returned to the
    caller for parsing.
    """

    def __init__(self):
        self.carry = ""
        self.open = False

    def feed(self, chunk):
        text = self.carry + chunk
        self.carry = ""
        tail = ""
        run = re.search(r"`+$", text)
        if run and len(run.group(0)) < 3:
            tail = run.group(0)
            text = text[:-len(tail)]
        out = []
        for part in re.split(r"(```+)", text):
            if not part:
                continue
            if set(part) == {"`"}:
                self.open = not self.open
            elif not self.open:
                out.append(part)
        self.carry = tail
        return "".join(out)

    def flush(self):
        tail, self.carry = self.carry, ""
        if self.open:
            return ""
        return tail


def _stream_once(url, api_key, model, messages, tools, on_token,
                 cap=CHAT_MAX_TOKENS, _retried=False):
    """One streaming attempt. Returns (full_text, tool_calls, usage).

    On the Meta endpoint the call carries reasoning_effort + max_tokens
    (the Baseten fallback keeps its own gateway behavior). A length
    finish is re-fetched once, silently, at the high cap so the caller
    parses a whole reply instead of a cut-off stub.
    """
    payload = {"model": model, "messages": messages, "stream": True}
    tuned = url == CHAT_URL
    if tuned:
        payload["reasoning_effort"] = REASONING_EFFORT
        payload["max_tokens"] = cap
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"},
        method="POST")
    t0 = time.time()
    parts = []
    calls = {}
    usage = {}
    finish = None
    with urllib.request.urlopen(req,
                                timeout=CHAT_TIMEOUT) as resp:
        buf = b""
        for chunk in resp:
            buf += chunk
            while b"\n\n" in buf:
                raw, buf = buf.split(b"\n\n", 1)
                for line in raw.decode("utf-8",
                                       "ignore").splitlines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_s = line[5:].strip()
                    if data_s == "[DONE]":
                        break
                    try:
                        evt = json.loads(data_s)
                    except ValueError:
                        continue
                    if "usage" in evt and isinstance(
                            evt["usage"], dict):
                        usage = evt["usage"]
                    for choice in evt.get("choices", []):
                        finish = choice.get("finish_reason") or finish
                        delta = choice.get("delta", {})
                        text = delta.get("content")
                        if text:
                            parts.append(text)
                            on_token(text)
                        for tc in delta.get("tool_calls",
                                            []) or []:
                            idx = tc.get("index", 0)
                            slot = calls.setdefault(
                                idx, {"id": "", "name": "",
                                      "args": ""})
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                slot["name"] = fn["name"]
                            if fn.get("arguments"):
                                slot["args"] += fn["arguments"]
    tool_calls = []
    for idx in sorted(calls):
        slot = calls[idx]
        try:
            args = json.loads(slot["args"] or "{}")
        except ValueError:
            args = {}
        tool_calls.append(
            {"id": slot["id"] or "call-%d" % idx,
             "type": "function",
             "function": {"name": slot["name"],
                          "arguments": json.dumps(args)}})
    chars = 0
    for m in messages:
        c = m.get("content", "")
        chars += len(c) if isinstance(c, str) else len(
            json.dumps(c, ensure_ascii=False))
    _perf({"kind": "model", "stream": True,
           "seconds": round(time.time() - t0, 2),
           "prompt_tokens": (usage or {}).get("prompt_tokens"),
           "completion_tokens": (usage or {}).get(
               "completion_tokens"),
           "n_messages": len(messages), "prompt_chars": chars,
           "with_tools": bool(tools), "via": url})
    if finish == "length" and tuned and not _retried and cap < (
            CHAT_MAX_TOKENS_RETRY):
        return _stream_once(url, api_key, model, messages, tools,
                            lambda t: None, CHAT_MAX_TOKENS_RETRY,
                            True)
    return "".join(parts), tool_calls, usage


def _call_chat_stream(messages, tools, on_token):
    """Streaming chat call. Yields content live via on_token.

    Returns (full_text, tool_calls, usage). tool_calls has the same
    shape as a non-streaming reply's message["tool_calls"].
    """
    last_err = None
    timeouts = 0
    for attempt in range(MAX_RETRIES + 1):
        try:
            return _stream_once(CHAT_URL, require_api_key(),
                                SPARK_MODEL, messages, tools, on_token)
        except Exception as exc:  # noqa: BLE001 - retry then raise
            last_err = exc
            if _is_timeout(exc):
                timeouts += 1
            time.sleep(2 * (attempt + 1))
    if timeouts > MAX_RETRIES and _spark_open_enabled():
        try:
            return _stream_once(BASEN_CHAT_URL, _baseten_key(),
                                BASEN_MODEL, messages, tools, on_token)
        except Exception as bexc:  # noqa: BLE001 - report both legs
            raise RuntimeError(
                "chat call failed: %s; baseten fallback failed: %s"
                % (last_err, bexc))
    raise RuntimeError("chat call failed: %s" % last_err)


TOOLS = [
    {"type": "function", "function": {
        "name": "search_catalog",
        "description": "Search the fabric catalog with optional filters. "
                       "Returns compact summaries and relaxed constraints.",
        "parameters": {"type": "object", "properties": {
            "usage": {"type": "string",
                      "description": "upholstery, curtains or cushions"},
            "colors": {"type": "array", "items": {"type": "string"}},
            "tone": {"type": "string",
                     "description": "warm, cool or neutral"},
            "plain_or_patterned": {"type": "string",
                                   "description": "plain or patterned"},
            "styles": {"type": "array", "items": {"type": "string"}},
            "features": {"type": "array", "items": {"type": "string"},
                         "description": "ALL of these must match"},
            "any_features": {"type": "array", "items": {"type": "string"},
                             "description": "AT LEAST ONE must match; use "
                                            "for pet-friendly OR "
                                            "scratch-resistant"},
            "snag_levels": {"type": "array", "items": {"type": "string"},
                            "description": "allowed snag_risk values "
                                           "(low, medium, high)"},
            "min_martindale": {"type": "integer",
                               "description": "minimum rub cycles for "
                                              "heavy use"},
            "suitable_for": {"type": "array", "items": {"type": "string"}},
            "opacity": {"type": "string"},
            "max_price": {"type": "number"},
            "limit": {"type": "integer"}},
        "required": []}}},
    {"type": "function", "function": {
        "name": "get_fabric",
        "description": "Full details for one fabric code.",
        "parameters": {"type": "object",
                       "properties": {"code": {"type": "string"}},
                       "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "preview_fabric",
        "description": "Run a real fabric preview (swap) for one fabric "
                       "code on the user's photo. Call this when the user "
                       "asks to see, try or preview a fabric — never "
                       "describe an imaginary preview.",
        "parameters": {"type": "object",
                       "properties": {"code": {"type": "string"},
                                      "target": {"type": "string"}},
                       "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "assign_fabric",
        "description": "Record which fabric goes on which item "
                       "(sofa, cushions or curtains). Call it for every "
                       "pick the user confirms.",
        "parameters": {"type": "object",
                       "properties": {"target": {"type": "string"},
                                      "code": {"type": "string"}},
                       "required": ["target", "code"]}}},
    {"type": "function", "function": {
        "name": "estimate_cost",
        "description": "Meters and price for an assigned fabric. Call "
                       "this whenever the user asks how many meters, how "
                       "much fabric, or how much it will cost — never "
                       "guess meters or prices. For curtains, pass width_m "
                       "and height_m when the user gives them.",
        "parameters": {"type": "object",
                       "properties": {
                           "target": {"type": "string"},
                           "code": {"type": "string"},
                           "width_m": {"type": "number"},
                           "height_m": {"type": "number"},
                           "drops": {"type": "integer"},
                           "pillows": {"type": "integer"}},
                       "required": []}}},
]


def similar_reply(a, b):
    """Rough identity (0-1) of two replies. Guards repeated questions."""
    import difflib
    na = re.sub(r"\s+", " ", (a or "").lower()).strip()
    nb = re.sub(r"\s+", " ", (b or "").lower()).strip()
    if not na or not nb or len(na) < 20 or len(nb) < 20:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


PET_OR_FEATURES = ("pet-friendly", "scratch-resistant")

SNAG_ORDER = {"low": 0, "medium": 1, "high": 2}


def rank_key(summary, required, wanted_styles, wanted_tone, max_price,
             has_kids_flag):
    """Functional fit first, then snag, kids-safe color, budget, style."""
    item = get_fabric(summary["code"])
    feats = set(item.get("features", []))
    fit = len([f for f in required if f in feats])
    snag = SNAG_ORDER.get(item.get("snag_risk"), 3)
    light = 1 if (has_kids_flag and is_light_unprotected(item)) else 0
    over = 1 if (max_price is not None
                 and item["price_usd_per_m"] > max_price) else 0
    style_hit = len(set(wanted_styles) & set(item.get("styles", [])))
    if wanted_tone and item.get("tone") == wanted_tone:
        style_hit += 1
    return (-fit, snag, light, over, -style_hit,
            item["price_usd_per_m"])


# Safety requirements are never relaxed to fill the shortlist: a hotel
# that needs fire-resistant fabric gets fewer/costlier/lower-martindale
# options before it gets a non-compliant one.
SAFETY_FEATURES = {"fire-resistant"}


def run_search(args, turn):
    args = args or {}
    # Expert rules merged in: pet needs are OR-filters, always enforced.
    model_any = [f for f in _as_list(args.get("any_features"))]
    model_all = [f for f in _as_list(args.get("features"))]
    needs_any = [f for f in turn.get("needs_any", [])
                 if f not in model_any]
    needs_all = [f for f in turn.get("needs_all", [])
                 if f not in model_all]
    snag = _as_list(args.get("snag_levels"))
    if turn.get("pet_safe") and not snag:
        snag = ["low"]
    mart = args.get("min_martindale")
    if turn.get("min_martindale") and not mart:
        mart = turn["min_martindale"]
    if args.get("max_price") is not None:
        turn.setdefault("budgets", [])
        if args["max_price"] not in turn["budgets"]:
            turn["budgets"].append(args["max_price"])
    if args.get("tone"):
        turn.setdefault("tones", [])
        if args["tone"] not in turn["tones"]:
            turn["tones"].append(args["tone"])
    wanted = min(args.get("limit", 6) or 6, 12)
    summaries, relaxed = search_catalog(
        usage=args.get("usage"), colors=_as_list(args.get("colors")),
        tone=args.get("tone"),
        plain_or_patterned=args.get("plain_or_patterned"),
        styles=_as_list(args.get("styles")),
        features=model_all + needs_all,
        any_features=model_any + needs_any,
        suitable_for=_as_list(args.get("suitable_for")),
        opacity=args.get("opacity"), max_price=args.get("max_price"),
        limit=50,
        protected=tuple(set(turn.get("protected", ())) | {
            f for f in model_all + needs_all + model_any + needs_any
            if f in SAFETY_FEATURES}),
        pet_safe=turn.get("pet_safe", False),
        snag_levels=snag or None,
        min_martindale=mart)
    required = model_all + needs_all + model_any + needs_any
    summaries.sort(key=lambda s: rank_key(
        s, required, _as_list(args.get("styles")), args.get("tone"),
        args.get("max_price"), turn.get("has_kids", False)))
    # Rank over the full fetch but cap the tool payload: the model
    # only ever recommends 3, so anything past a shortlist only burns
    # prompt tokens on every later round and turn. Ranking quality is
    # unchanged because the sort above still sees all fetched items.
    return {"fabrics": summaries[:wanted],
            "relaxed_constraints": relaxed}


ANALYSES = {}
MAX_ANALYSES = 50


def _image_hash(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def vision_jpeg_bytes(path, max_side=1024):
    """Downscaled JPEG bytes for vision calls. Full file stays for swaps."""
    from PIL import Image
    import io as _io
    try:
        import pillow_heif  # noqa: F401 - registers HEIF opener
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    im = Image.open(path).convert("RGB")
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.BILINEAR)
    buf = _io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def _log_photo_failure(stage, image_path, exc):
    """A photo turn that falls back to "couldn't read that photo" must
    leave the real cause in the server log (the user only sees the
    generic line)."""
    import sys
    import traceback
    try:
        path = image_path if os.path.isabs(image_path) else \
            os.path.join(BASE_DIR, image_path)
        size = os.path.getsize(path) if os.path.exists(path) else None
    except OSError:
        size = None
    print(json.dumps({"event": "photo_failure", "stage": stage,
                      "image": os.path.basename(image_path or ""),
                      "bytes": size, "error": "%s: %s" % (
                          type(exc).__name__, exc),
                      "trace": traceback.format_exc()[-1500:]},
                     ensure_ascii=False), file=sys.stderr, flush=True)


def analyze_room(image_path, lang=None):
    """Vision analysis of a room photo. Returns a JSON dict.

    When lang is a known language code, values come back in that
    language so the room card can render localized. Results are cached
    per image hash: re-uploads and sample rooms never pay twice.
    """
    path = image_path if os.path.isabs(image_path) else \
        os.path.join(BASE_DIR, image_path)
    try:
        from app.services import sample_cache
        hit = sample_cache.get_analysis(image_path, lang)
        if hit is not None:
            return hit
    except Exception:  # noqa: BLE001 - cache is best-effort
        pass
    key = (_image_hash(path), lang)
    if key in ANALYSES:
        return ANALYSES[key]
    b64 = base64.b64encode(vision_jpeg_bytes(path)).decode("ascii")
    ask = ("Analyze this room photo for an upholstery consultant. Reply "
           "with JSON only: {\"room_type\": \"...\", \"wall_colors\": "
           "[{\"name\": \"...\", \"hex\": \"#...\"}] (5 entries), "
           "\"floor\": \"...\", \"furniture\": \"...\", "
           "\"existing_fabrics\": \"...\", \"light_level\": \"low/medium/"
           "high\", \"style\": \"...\"}.")
    if lang in LANG_NAMES:
        ask += " Write every value in %s." % LANG_NAMES[lang]
    messages = [{"role": "user", "content": [
        {"type": "text", "text": ask},
        {"type": "image_url",
         "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]
    body = _call_chat(messages)
    text = body["choices"][0]["message"]["content"] or ""
    try:
        result = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except (ValueError, IndexError):
        result = {"raw": text[:1000]}
    if len(ANALYSES) >= MAX_ANALYSES:
        ANALYSES.pop(next(iter(ANALYSES)))
    ANALYSES[key] = result
    return result


RECO_RE = re.compile(r"```recommendations\s*(\[.*?\])\s*```", re.DOTALL)
OPTIONS_RE = re.compile(r"```options\s*(\[.*?\])\s*```", re.DOTALL)


def extract_recommendations(text):
    """Parse the recommendations block. Returns a list or None."""
    match = RECO_RE.search(text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    return data


def strip_block(text):
    return RECO_RE.sub("", text or "").strip()


def budget_tiers():
    """Budget chip bounds (USD/m) derived from catalog price quartiles."""
    from statistics import quantiles
    from app.services.catalog import load_specs
    prices = sorted(s["price_usd_per_m"] for s in load_specs())
    q1, _, q3 = quantiles(prices, n=4)
    # Dollar prices run 17-67/m: tiers step in fives.
    low = int(q1 // 5 * 5) - 5
    high = int(q3 // 5 * 5)
    return max(low, 5), high


BUDGET_TIERS = budget_tiers()

SYSTEM_PROMPT += (
    "\n\nBUDGET: when you ask about budget, offer exactly these four "
    "chips: Under $%d, $%d-%d, over $%d, No limit. "
    "State every price in US dollars with a $ sign, never in SAR or riyals."
    % (BUDGET_TIERS[0], BUDGET_TIERS[0], BUDGET_TIERS[1],
       BUDGET_TIERS[1]))


def sar_option(option):
    """Rewrite riyal amounts into catalog dollars ("80 SAR" -> "$80")."""
    text = re.sub(r"([\d,]+(?:\.\d+)?)\s*(?:SAR|ر\.?\s?س|ريال)",
                  r"$\1", str(option))
    return text.replace("SAR", "$").strip()


def extract_options(text):
    """Parse the options block. Returns a list of strings or None.

    Amounts are normalized to dollars: the model sometimes prices chips
    in riyals even though the catalog is USD-only.
    """
    match = OPTIONS_RE.search(text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    return [sar_option(o) for o in data[:4] if str(o).strip()]


def strip_options(text):
    return OPTIONS_RE.sub("", text or "").strip()


TIP_RE = re.compile(r"(?mi)^\s*(tip|تلميح|نصيحة)\s*[:：-].*$")


# Localized one-line lead-ins used only when the model returns no visible
# prose: options/recs are still shown, so the lead-in just opens the turn.
EMPTY_LEAD = {
    "options": {
        "en": "Sure — which of these works for you?",
        "ar": "تمام — أي واحد يناسبك؟",
        "hi": "बताइए — इनमें से कौन सा चलेगा?",
        "fr": "Dites-moi — lequel vous convient ?",
        "es": "Dime — ¿cuál te conviene?",
    },
    "recs": {
        "en": "Here are my top picks for you:",
        "ar": "هذه أفضل اختياراتي لك:",
        "hi": "ये मेरे सबसे अच्छे सुझाव हैं:",
        "fr": "Voici mes meilleurs choix :",
        "es": "Estas son mis mejores opciones:",
    },
    "generic": {
        "en": "Could you tell me a little more about what you need?",
        "ar": "ممكن تقول لي أكثر عن اللي تحتاجه؟",
        "hi": "अपनी ज़रूरत के बारे में थोड़ा और बताइए?",
        "fr": "Pouvez-vous m'en dire un peu plus ?",
        "es": "¿Me cuentas un poco más lo que necesitas?",
    },
}


def empty_fallback(has_options, has_recs, lang):
    """Short localized lead-in when the model returns no visible prose."""
    pack = EMPTY_LEAD["options"] if has_options else (
        EMPTY_LEAD["recs"] if has_recs else EMPTY_LEAD["generic"])
    return pack.get(lang) or pack["en"]


# Overridden with a tmp path in unit tests; None means the
# Volume-backed runtime logs dir.
GROUNDING_LOG = None


def _grounding_log_path():
    if GROUNDING_LOG:
        return GROUNDING_LOG
    from app.core.config import runtime_logs_dir
    return os.path.join(runtime_logs_dir(), "grounding_log.json")


def log_grounding(session_id, bad, path, codes):
    """Append one grounding failure record: what failed, how resolved."""
    entry = {"ts": time.time(), "session_id": session_id or "",
             "bad": bad or "", "path": path, "final_codes": codes or []}
    try:
        log = []
        dest = _grounding_log_path()
        if os.path.exists(dest):
            with open(dest, encoding="utf-8") as f:
                log = json.load(f)
        log.append(entry)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=1)
    except (OSError, ValueError):
        pass


def split_final(final_text, turn):
    """Split final model text into (reply, options, recommendations).

    reply holds only visible prose: both fenced blocks are removed and
    the tip line is stripped on turns without recommendations.
    """
    extracted = extract_recommendations(final_text)
    recs, bad = (None, None)
    if extracted is not None:
        recs, bad = valid_recommendations(extracted, turn["seen"])
    recommendations = recs if (recs and not bad) else []
    clean = strip_block(final_text)
    options = extract_options(clean) or []
    reply = strip_options(clean)
    if not recommendations:
        reply = strip_tip(reply)
    return reply.strip(), options, recommendations


def strip_tip(text):
    """Remove tip lines. Used on turns without recommendations."""
    cleaned = TIP_RE.sub("", text or "")
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


# Adjacent duplicate list items ("curtains, curtains", "ستائر، ستائر"):
# the model sometimes stutters on the opening enumeration. Collapsing is
# only safe on the greeting turn, where such repetition is never emphasis.
DUPE_RE = re.compile(
    r"([^-\W\d_'\u2019]+(?: [^-\W\d_'\u2019]+){0,2})([,\u060c])\s*"
    r"\1(?=[\s,.?!\u060c;:]|$)",
    re.IGNORECASE)


def collapse_adjacent_dupes(text):
    """Collapse adjacent duplicate list items, keeping the first."""
    prev = None
    while prev != text:
        prev, text = text, DUPE_RE.sub(r"\1", text)
    return text


RELAX_LABELS = {
    "max_price": ("budget", "الميزانية", "बजट", "budget", "presupuesto"),
    "tone": ("color tone", "درجة اللون", "रंगत", "ton", "tono"),
    "colors": ("colors", "الألوان", "रंग", "couleurs", "colores"),
    "styles": ("style", "الستايل", "स्टाइल", "style", "estilo"),
    "features": ("fabric features", "مواصفات القماش", "कपड़े की खूबियाँ",
                  "caractéristiques", "características"),
    "any_features": ("pet protection", "الحماية من الحيوانات",
                     "पालतू सुरक्षा", "protection animaux",
                     "protección mascotas"),
    "snag_levels": ("claw-safe weave", "قماش آمن من الخدش",
                     "पंजा-सुरक्षित बुनाई", "tissu anti-griffes",
                     "tejido antirrasguños"),
    "min_martindale": ("durability", "المتانة", "टिकाऊपन", "durabilité",
                        "durabilidad"),
    "opacity": ("curtain opacity", "تعتيم الستارة", "परदे की ओपेसिटी",
                "opacité", "opacidad"),
    "suitable_for": ("intended use", "الاستخدام المقصود", "उपयोग",
                     "usage prévu", "uso previsto"),
    "plain_or_patterned": ("pattern", "النقشة", "डिज़ाइन", "motif",
                           "estampado"),
    "usage": ("fabric use", "استخدام القماش", "कपड़े का उपयोग", "usage",
              "uso"),
}

RECEIPT_LANGS = ("en", "ar", "hi", "fr", "es")


def _receipt_lang(lang):
    """Normalize a lang code or legacy arabic bool to a receipt lang."""
    if lang is True or lang == "ar":
        return "ar"
    return lang if lang in RECEIPT_LANGS else "en"


FEATURE_NAMES = {
    "pet-friendly": ("pet-friendly", "مناسب للحيوانات",
                     "पालतू-मित्रवत", "Animaux admis",
                     "Apto para mascotas"),
    "scratch-resistant": ("scratch-resistant", "مقاوم للخدش",
                          "खरोंच-रोधी", "Résistant aux griffes",
                          "Resistente a arañazos"),
    "easy-clean": ("easy-clean", "سهل التنظيف", "आसान-सफ़ाई",
                   "Facile d'entretien", "Fácil de limpiar"),
    "stain-resistant": ("stain-resistant", "مقاوم للبقع", "दाग-रोधी",
                        "Antitache", "Antimanchas"),
    "washable": ("washable", "قابل للغسل", "धोने योग्य", "Lavable",
                 "Lavable"),
    "antibacterial": ("antibacterial", "مضاد للبكتيريا", "जीवाणुरोधी",
                       "Antibactérien", "Antibacteriano"),
    "fire-resistant": ("fire-resistant", "مقاوم للحريق", "आग-रोधी",
                       "Ignifugé", "Ignífugo"),
    "hypoallergenic": ("hypoallergenic", "مضاد للحساسية",
                        "हाइपोएलर्जेनिक", "Hypoallergénique",
                        "Hipoalergénico"),
    "blackout": ("blackout", "تعتيم كامل", "ब्लैकआउट", "Occultant",
                 "Opaco"),
    "fade-resistant": ("fade-resistant", "مقاوم للبهتان", "रंग-टिकाऊ",
                        "Résistant à la décoloration",
                        "Resistente a la decoloración"),
}


def _specific_feature_labels(specific, arabic):
    labels = []
    for key in specific or []:
        pair = FEATURE_NAMES.get(key)
        labels.append(pair[1 if arabic else 0] if pair else key)
    seen = []
    for label in labels:
        if label not in seen:
            seen.append(label)
    return seen


RELAX_PHRASES = {
    "max_price": ("stretched the budget", "وسّعت الميزانية"),
    "tone": ("widened the color tone", "فتحت درجات اللون"),
    "colors": ("widened the colors", "فتحت الألوان"),
    "styles": ("widened the style", "فتحت الستايل"),
    "features": ("eased the fabric features", "خففت شروط المواصفات"),
    "any_features": ("eased the pet protection",
                     "خففت شرط الحماية من الحيوانات"),
    "snag_levels": ("eased the claw-safe weave",
                    "خففت شرط القماش الآمن من الخدش"),
    "min_martindale": ("lowered the durability bar", "نزّلت حد المتانة"),
    "opacity": ("widened the curtain opacity", "فتحت التعتيم"),
    "suitable_for": ("widened the intended use", "فتحت الاستخدام"),
    "plain_or_patterned": ("opened up the pattern", "فتحت النقشة"),
    "usage": ("widened the fabric use", "فتحت استخدام القماش"),
}

# Distinctive words showing the model already disclosed a relaxation.
RELAX_MATCH = {
    "max_price": (["budget"], ["الميزانية"]),
    "tone": (["tone"], ["درجة اللون", "درجات اللون"]),
    "colors": (["color"], ["الألوان", "ألوان"]),
    "styles": (["style"], ["الستايل", "ستايل"]),
    "features": (["feature"], ["المواصفات", "مواصفات"]),
    "any_features": (["pet-friendly", "pet protection", "scratch-resistant"],
                     ["الحماية", "الحيوانات", "مقاوم"]),
    "snag_levels": (["claw", "snag", "weave"], ["الخدش", "خدش", "تشابك"]),
    "min_martindale": (["martindale", "durability", "durable"],
                       ["المتانة", "متانة"]),
    "opacity": (["opacity", "blackout", "sheer"], ["التعتيم", "تعتيم"]),
    "suitable_for": (["intended use", "hotel", "office", "restaurant"],
                     ["الاستخدام", "فندق", "مكتب", "مطعم"]),
    "plain_or_patterned": (["pattern"], ["النقشة", "نقشة"]),
    "usage": (["upholstery", "curtains", "cushions"],
              ["تنجيد", "ستائر", "وسائد"]),
}


def _money(value, arabic):
    """Whole-dollar amount (no symbol), shared formatter."""
    from app.services.money import format_money
    return format_money(int(round(value)), "ar" if arabic else "en",
                        symbol=False)


def _relax_phrase(key, arabic, budget_over=0, specific=()):
    if key == "max_price" and budget_over > 0:
        over = _money(budget_over, arabic)
        if arabic:
            return "طلعت فوق ميزانيتك بـ %s دولار" % over
        return "went $%s over your budget" % over
    if key in ("features", "any_features"):
        labels = _specific_feature_labels(specific, arabic)
        if labels:
            if arabic:
                tail = "، ".join(labels[:-1]) + " و" + labels[-1] \
                    if len(labels) > 1 else labels[0]
                return "خففت شروط %s" % tail
            tail = ", ".join(labels[:-1]) + " and " + labels[-1] \
                if len(labels) > 1 else labels[0]
            return "eased the %s requirement%s" % (
                tail, "s" if len(labels) > 1 else "")
    pair = RELAX_PHRASES.get(key)
    if pair:
        return pair[1 if arabic else 0]
    noun = RELAX_LABELS.get(key, (key, key))[1 if arabic else 0]
    return ("عدّلت " + noun) if arabic else ("adjusted " + noun)


def disclosure_note(relaxed, arabic, budget_over=0, specific=()):
    """Friendly one-line note naming what was relaxed, never raw keys.

    Budget overruns state the real amount: never "slightly" when the
    price is more than 15% over budget. Relaxed features name the
    specific features instead of the vague "fabric features".
    """
    phrases = [_relax_phrase(r, arabic,
                             budget_over if r == "max_price" else 0,
                             specific)
               for r in relaxed]
    over = budget_over > 0 and "max_price" in relaxed
    if arabic:
        if len(phrases) == 1:
            return ("عشان ألقى لك الأنسب، %s%s."
                    % (phrases[0], "" if over else " شوي"))
        if len(phrases) == 2:
            return ("عشان ألقى لك الأنسب، %s و%s%s."
                    % (phrases[0], phrases[1], "" if over else " شوي"))
        tail = "، ".join(phrases[:-1]) + "، و" + phrases[-1]
        return "عشان ألقى لك الأنسب، %s%s." % (tail,
                                               "" if over else " شوي")
    if len(phrases) == 1:
        return "To find these, I %s%s." % (phrases[0],
                                            "" if over else " slightly")
    if len(phrases) == 2:
        return "To find these, I %s and %s." % (phrases[0], phrases[1])
    tail = ", ".join(phrases[:-1]) + ", and " + phrases[-1]
    return "To find these, I %s." % tail


def missing_relaxation(reply, relaxed, arabic):
    """Relaxed constraints the reply does not already name."""
    text = reply or ""
    lowered = text.lower()
    missing = []
    for key in relaxed:
        words = RELAX_MATCH.get(key, ([""], [""]))
        markers = words[1] if arabic else [w.lower() for w in words[0]]
        haystack = text if arabic else lowered
        if not any(m and m in haystack for m in markers):
            missing.append(key)
    return missing


RECEIPT_EXTRA_NAMES = {
    "under-budget": ("Under budget", "ضمن الميزانية", "बजट के अंदर",
                     "Dans le budget", "Dentro del presupuesto"),
    "warm-tone": ("Warm tone", "درجة دافئة", "गर्म रंग", "Ton chaud",
                  "Tono cálido"),
    "cool-tone": ("Cool tone", "درجة باردة", "ठंडा रंग", "Ton froid",
                  "Tono frío"),
    "neutral-tone": ("Neutral tone", "درجة محايدة", "तटस्थ रंग",
                     "Ton neutre", "Tono neutro"),
}

RECEIPT_MATCH_WORD = ("Matches", "يطابق", "मेल", "Conforme",
                       "Coincide")
RECEIPT_EASED_WORD = ("Eased", "خففنا", "ढील दी", "Assoupli",
                       "Flexibilizado")

# Words proving the USER stated a style/color/pattern need. Relaxed
# search dimensions reach the card receipt only when the session's own
# user messages contain one of these; model-inferred filters (e.g. a
# style the model added on its own) stay off the receipt.
STYLE_WORDS = (
    "art-deco", "art deco", "bohemian", "classic", "coastal", "luxury",
    "mediterranean", "minimalist", "modern", "scandinavian",
    "traditional", "مودرن", "كلاسيك",
)
COLOR_WORDS = (
    "antique", "aqua", "beige", "black", "blue", "blush", "bronze",
    "brown", "burgundy", "burnt", "camel", "caramel", "chambray",
    "champagne", "charcoal", "clay", "cocoa", "coral", "cream",
    "crisp", "deep", "desert", "dusty", "emerald", "fig", "forest",
    "gold", "green", "grey", "gray", "indigo", "ink", "ivory", "khaki",
    "light", "mustard", "natural", "navy", "oatmeal", "ocean", "off",
    "olive", "orange", "pale", "palm", "peacock", "pearl", "pink",
    "plum", "pure", "purple", "red", "rose", "rust", "saffron", "sage",
    "sand", "sea", "silver", "sky", "slate", "soft", "stone", "taupe",
    "teal", "terracotta", "veins", "warm", "white", "yellow",
    "color", "colour", "colors", "colours", "tone", "tones", "hue",
    "shade", "لون", "ألوان", "الوان", "درجة", "بيج", "أزرق", "ازرق",
    "أخضر", "اخضر", "رمادي", "أبيض", "ابيض", "أسود", "اسود", "بني",
    "أحمر", "احمر", "كريمي", "عاجي", "رملي", "كحلي", "زيتوني",
    "وردي", "ذهبي", "فضي", "دافئ", "دافئة", "بارد", "باردة",
)
PATTERN_WORDS = (
    "pattern", "patterned", "plain", "motif", "print", "striped",
    "نقشة", "نقش", "سادة", "مشجر", "مقلم",
)


def _session_user_text(turn):
    """Lowercased user messages this session (the stated needs)."""
    try:
        msgs = (turn.get("session") or {}).get("messages") or []
    except AttributeError:
        return ""
    return " ".join(m.get("content", "") for m in msgs
                     if m.get("role") == "user").lower()


def _stated_relaxed_keys(relaxed_keys, turn):
    """Keep only relaxed dims the user actually stated.

    Model-inferred filters (a style, opacity or usage the model added
    on its own) never reach the one-line receipt.
    """
    said = _session_user_text(turn)
    if not said:
        return list(relaxed_keys)
    kept = []
    for key in relaxed_keys:
        if key in ("tone", "colors"):
            if any(w in said for w in COLOR_WORDS):
                kept.append(key)
        elif key == "styles":
            if any(w in said for w in STYLE_WORDS):
                kept.append(key)
        elif key == "plain_or_patterned":
            if any(w in said for w in PATTERN_WORDS):
                kept.append(key)
        elif key == "snag_levels":
            if turn.get("pet_safe"):
                kept.append(key)
        elif key == "min_martindale":
            if turn.get("min_martindale"):
                kept.append(key)
        elif key == "opacity":
            needs = turn.get("needs_all", []) + turn.get("needs_any",
                                                          [])
            if "blackout" in needs:
                kept.append(key)
        elif key in ("usage", "suitable_for"):
            continue
        else:
            kept.append(key)
    return kept


def _receipt_label(key, lang):
    """Label for one receipt key in the session language.

    lang is a code or the legacy arabic bool (True/False still work).
    """
    code = _receipt_lang(lang)
    idx = RECEIPT_LANGS.index(code)
    pair = RECEIPT_EXTRA_NAMES.get(key) or FEATURE_NAMES.get(key)
    if pair:
        return pair[idx] if idx < len(pair) else pair[0]
    noun = RELAX_LABELS.get(key, (key,) * len(RECEIPT_LANGS))
    return noun[idx] if idx < len(noun) else noun[0]


def receipt_summary(matched, relaxed_keys, relaxed_feats, budget_over,
                    arabic, lang=None):
    """One short receipt line, labels never repeated.

    Only needs the user stated this session feed the line (matched /
    relaxed are derived from those needs). Returns "" when empty.
    arabic is the legacy bool; lang (a code) wins when given.
    """
    code = _receipt_lang(lang if lang is not None else arabic)
    idx = RECEIPT_LANGS.index(code)
    match_labels = []
    for key in matched or []:
        label = _receipt_label(key, code)
        if label not in match_labels:
            match_labels.append(label)
    ease_labels = []
    # Stated need-features first, then relaxed dimensions; one short
    # line max, so the eased list is capped.
    for key in (relaxed_feats or []) + (relaxed_keys or []):
        label = _receipt_label(key, code)
        if label not in ease_labels and label not in match_labels:
            ease_labels.append(label)
    ease_labels = ease_labels[:3]
    match_labels = match_labels[:3]
    if budget_over:
        label = "%s (+$%s)" % (
            _receipt_label("max_price", code),
            _money(budget_over, code == "ar"))
        if label not in ease_labels:
            ease_labels.append(label)
    parts = []
    if match_labels:
        parts.append("%s: %s" % (RECEIPT_MATCH_WORD[idx],
                                " · ".join(match_labels)))
    if ease_labels:
        parts.append("%s: %s" % (RECEIPT_EASED_WORD[idx],
                                " · ".join(ease_labels)))
    return " — ".join(parts)


# Words in a model-written reason that assert a catalog feature. A
# sentence asserting a feature the fabric does not have is dropped:
# the pills and receipts are computed, so the prose must not outrun
# them. (Keys are substrings, lower-cased; en + ar.)
FEATURE_CLAIMS = {
    "pet-friendly": ("pet", "cat", "dog", "claw", "paw", "حيوان", "قط",
                     "كلب", "مخالب"),
    "stain-resistant": ("stain", "spill", "بقع", "انسكاب"),
    "washable": ("washable", "machine wash", "wash it", "غسيل",
                 "يتغسل", "تغسل"),
    "fade-resistant": ("fade", "sun-safe", "uv", "sunlight", "بهتان",
                       "يبهت", "الشمس"),
    "blackout": ("blackout", "block", "darken", "معتم",
                 "يحجب"),
    "fire-resistant": ("fire", "flame", "حريق", "لهب"),
    "eco-friendly": ("eco", "recycled", "sustainable", "صديق للبيئة",
                     "معاد تدوير"),
    "antibacterial": ("antibacterial", "hygienic", "مضاد للبكتيريا"),
    "hypoallergenic": ("hypoallergenic", "allerg", "حساسية"),
    "thermal-insulating": ("thermal", "insulat", "عازل للحرارة"),
    "sound-absorbing": ("acoustic", "sound-absorb", "absorbs sound",
                        "عازل للصوت"),
    "crease-resistant": ("crease", "wrinkle", "تجعد", "كرمشة"),
    "scratch-resistant": ("scratch", "خدش", "خدوش"),
}
# A claim that any of these features covers.
CLAIM_ANY = {
    "pet-friendly": ("pet-friendly", "scratch-resistant"),
    "scratch-resistant": ("scratch-resistant", "pet-friendly"),
    "stain-resistant": ("stain-resistant", "easy-clean"),
    "washable": ("washable", "easy-clean"),
}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟])\s+")


def ground_reason(reason, item, lang=None):
    """Keep only the sentences of a model-written reason whose feature
    claims the catalog record supports; fall back to the catalog
    description when nothing survives. Prose never outruns the pills."""
    text = (reason or "").strip()
    feats = set(item.get("features", []) or [])
    kept = []
    for sent in _SENTENCE_SPLIT.split(text):
        low = sent.lower()
        bad = False
        for feat, words in FEATURE_CLAIMS.items():
            if any(w in low for w in words) and not (
                    feats & set(CLAIM_ANY.get(feat, (feat,)))):
                bad = True
                break
        if not bad and sent.strip():
            kept.append(sent.strip())
    out = " ".join(kept)
    if out:
        return out
    key = "description_ar" if lang == "ar" else "description_en"
    return item.get(key, "") or ""


def enrich(recommendations, turn):
    """Attach catalog details plus trust receipts.

    matched/relaxed are derived from the backend's real filters and
    needs, never from the model's words. One pill per dimension: a
    tone, budget or feature shows either as matched or as relaxed,
    never both. Relaxed features and budget overruns carry specifics
    (which feature, how much over) so pills never contradict.
    """
    needs = turn.get("needs_all", []) + turn.get("needs_any", [])
    budgets = turn.get("budgets", [])
    tones = turn.get("tones", [])
    relaxed = list(turn.get("relaxed", []))
    feat_relaxed = bool({"features", "any_features"} & set(relaxed))
    chosen = turn.get("chosen_targets", []) or []
    rec_target = chosen[0] if len(chosen) == 1 else ""
    if not chosen:
        # Nothing matched the photo's target list (the user asked for
        # curtains, the photo has a roller blind): the cards still carry
        # the piece the user named, so a Try reports "curtains · not
        # visible in this photo" instead of defaulting to the sofa.
        topic = (turn.get("session") or {}).get("topic")
        topic = {"chair": "armchair"}.get(topic, topic)
        from app.services import targets as _targets
        if topic in _targets.TARGET_TYPES:
            rec_target = topic
    out = []
    for rec in recommendations:
        item = get_fabric(rec["code"])
        feats = set(item.get("features", []))
        matched = [f for f in needs if f in feats] \
            if not feat_relaxed else []
        relaxed_feats = [f for f in needs if f not in feats] \
            if feat_relaxed else []
        budget = min(budgets) if budgets else None
        price = item["price_usd_per_m"]
        over = 0
        if budget is not None and "max_price" in relaxed \
                and price > budget:
            over = price - budget
        elif budgets and price <= min(budgets):
            matched.append("under-budget")
        if tones and item.get("tone") in tones \
                and "tone" not in relaxed:
            matched.append(item["tone"] + "-tone")
        relaxed_keys = [r for r in relaxed
                        if r not in ("features", "any_features",
                                    "max_price")]
        relaxed_keys = _stated_relaxed_keys(relaxed_keys, turn)
        out.append({"code": rec["code"],
                    "name_en": item["name_en"],
                    "name_ar": item["name_ar"],
                    "description_en": item.get("description_en", ""),
                    "description_ar": item.get("description_ar", ""),
                    "price_usd_per_m": price,
                    "image": item.get("image", ""),
                    "features": item.get("features", []),
                    "snag_risk": item.get("snag_risk", "unknown"),
                    "reason": ground_reason(rec.get("reason", ""), item,
                                            turn.get("lang")),
                    "target": rec_target,
                    "matched": matched,
                    "relaxed": relaxed_keys,
                    "relaxed_features": relaxed_feats,
                    "receipt": receipt_summary(
                        matched, relaxed_keys, relaxed_feats, over,
                        turn.get("lang") == "ar",
                        lang=turn.get("lang") or "en"),
                    "relaxed_budget": {"price": price, "over": over,
                                       "budget": budget}
                    if over > 0 else None})
    return out


def execute_tool(name, args, turn, on_step=None):
    t0 = time.time()
    try:
        return _execute_tool(name, args, turn, on_step)
    finally:
        _perf({"kind": "tool", "name": name,
               "seconds": round(time.time() - t0, 3)})


def _execute_tool(name, args, turn, on_step=None):
    if name == "search_catalog":
        turn["searched"] = True
        if turn.get("curtains_only"):
            args = dict(args or {})
            args["usage"] = "curtains"
        if on_step:
            on_step("search")
            snag = [f for f in _as_list((args or {}).get("snag_levels"))]
            if turn.get("pet_safe") or snag:
                on_step("claw")
        result = run_search(args or {}, turn)
        turn["seen"].extend(f["code"] for f in result["fabrics"])
        for name in result["relaxed_constraints"]:
            if name not in turn["relaxed"]:
                turn["relaxed"].append(name)
        return result
    if name == "get_fabric":
        if on_step:
            on_step("details")
        code = (args or {}).get("code", "")
        item = get_fabric(code)
        # Eligibility comes only from search results: a bare get_fabric
        # must not launder pet/curtain-filtered codes into seen.
        return item or {"error": "unknown code"}
    if name == "preview_fabric":
        code = (args or {}).get("code", "")
        if not turn.get("image"):
            return {"error": "no_photo",
                    "hint": "ask for a room photo or a sample room first"}
        if not get_fabric(code) or code not in (turn.get("seen") or []):
            return {"error": "unknown code",
                    "seen": [c for c in turn.get("seen", [])
                             if get_fabric(c)][:12]}
        target = (args or {}).get("target") or ""
        target = _user_target_wins(turn.get("session"), target)
        if not target:
            chosen = turn.get("chosen_targets", []) or []
            target = chosen[0] if len(chosen) == 1 else ""
        # The photo listing knows what is there: never auto-apply to an
        # item it did not see (a bedroom with a roller blind has no
        # curtains), and never tell the user it was applied.
        visible = (turn.get("session") or {}).get("available_targets")
        if isinstance(visible, list) and target and target not in visible:
            return {"error": "not visible",
                    "target": target, "visible": visible,
                    "hint": ("this photo shows none of that item; say so "
                             "plainly and do not claim it was applied")}
        turn["preview"] = {"code": code, "target": target}
        return {"ok": True, "code": code, "target": target}
    if name == "assign_fabric":
        from app.services import targets as targets_mod
        target = (args or {}).get("target", "")
        code = (args or {}).get("code", "")
        if target not in targets_mod.TARGET_TYPES:
            return {"error": "unknown target",
                    "targets": list(targets_mod.TARGET_TYPES)}
        if not get_fabric(code):
            return {"error": "unknown code"}
        session = turn.get("session")
        if session is None:
            session = {}
        # The item the user tapped or named is the one that gets the
        # fabric: a model guess ("sofa") never re-targets the pick.
        target = _user_target_wins(session, target) or target
        session.setdefault("assignments", {})[target] = code
        turn.setdefault("assigned_now", {})[target] = code
        chosen = session.setdefault("chosen_targets", [])
        if target not in chosen:
            chosen.append(target)
        return {"ok": True, "target": target, "code": code}
    if name == "estimate_cost":
        from app.services import meterage as meterage_mod
        session = turn.get("session")
        if session is None:
            session = {}
        args = args or {}
        target = (args.get("target") or "").lower()
        code = args.get("code", "")
        if not target:
            chosen = session.get("chosen_targets", [])
            target = chosen[0] if chosen else ""
        if not code:
            code = (session.get("assignments", {}) or {}).get(target, "")
        if not code:
            seen = [c for c in turn.get("seen", []) if get_fabric(c)]
            code = seen[0] if seen else ""
        fabric = get_fabric(code) if code else None
        if not target or not fabric:
            return {"error": "no assigned fabric yet",
                    "hint": "recommend or assign a fabric first"}
        if target == "curtains":
            dims = session.setdefault("curtain_dims", {})
            if args.get("width_m"):
                dims["width_m"] = float(args["width_m"])
            if args.get("height_m"):
                dims["height_m"] = float(args["height_m"])
            if args.get("drops"):
                dims["drops"] = int(args["drops"])
            if not dims.get("width_m") or not dims.get("height_m"):
                return {"error": "needs measurements",
                        "hint": "ask once for the window width and "
                                "height in meters"}
        else:
            dims = None
            if args.get("pillows") is not None:
                counts = session.setdefault("pillow_counts", {})
                counts[target] = max(0, int(args["pillows"] or 0))
            elif target == "cushions":
                detected = _count_pillows(session)
                if detected:
                    session.setdefault("pillow_counts", {})[target] = \
                        detected
        extras = {t: n for t, n in
                  (session.get("pillow_counts", {}) or {}).items()}
        pillows = extras.get(target, 0)
        meters, note = meterage_mod.estimate_item(
            target, fabric, dims, pillow_count=pillows)
        if meters is None:
            return {"error": "needs measurements", "target": target,
                    "code": code}
        price = fabric.get("price_usd_per_m")
        line = round(meters * price, 2) if price is not None else None
        result = {"target": target, "code": code, "meters": meters,
                  "price_usd_per_m": price, "line_total": line,
                  "currency": "USD", "preliminary": True, "note": note}
        if target == "cushions":
            result["pillows"] = pillows
        # A quoted fabric is the item's pick: the session quote and the
        # summary card include it even without an Apply-all.
        session.setdefault("assignments", {}).setdefault(target, code)
        turn["quoted"] = dict(result)
        return result


def _count_pillows(session):
    """Throw pillows visible in the cached cushions SAM mask.

    Returns 0 when no mask is cached or it cannot be read. The model
    states the number and the user can correct it (pillows=...).
    """
    try:
        from app.services import targets as targets_mod
        cached = (session or {}).get("targets") or {}
        for item in cached.get("targets", []) or []:
            if (item or {}).get("id") != "cushions":
                continue
            url = (item.get("mask_url") or "")
            path = url if os.path.isabs(url) else os.path.join(
                BASE_DIR, url.lstrip("/"))
            if os.path.isfile(path):
                return targets_mod.count_components(path)
    except (OSError, ValueError):
        pass
    return 0
    return {"error": "unknown tool " + str(name)}


LOOP_FALLBACK = "Let me show you what I found so far."


def agent_turn(messages, chat_fn, turn, on_token=None, on_step=None):
    """Run the tool loop. Returns (final text, exhausted).

    exhausted is True when the model kept calling tools through
    MAX_TOOL_ROUNDS without ever writing a final answer. Callers use it
    to trigger the deterministic recommendations fallback.

    When on_token is given (and chat_fn is None), the live API is used
    in streaming mode and content deltas are pushed to on_token as
    they arrive; on_step gets a short label per tool round.
    """
    streaming = on_token is not None and chat_fn is None
    call = chat_fn or _call_chat
    for _ in range(MAX_TOOL_ROUNDS):
        if streaming:
            shown = FenceFilter()
            text, calls, _ = _call_chat_stream(
                messages, TOOLS,
                lambda t: on_token(shown.feed(t)))
            if not calls:
                tail = shown.flush()
                if tail:
                    on_token(tail)
                return text, False
            messages.append({"role": "assistant", "content": text or None,
                             "tool_calls": calls})
        else:
            body = call(messages, TOOLS)
            msg = body["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            text = msg.get("content") or ""
            if not calls:
                if on_token and text:
                    on_token(text)
                return text, False
            messages.append({"role": "assistant",
                             "content": msg.get("content"),
                             "tool_calls": calls})
        for tc in calls:
            fn = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            try:
                output = execute_tool(fn, args, turn, on_step)
            except Exception as exc:  # noqa: BLE001 - report to model
                output = {"error": str(exc)}
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": json.dumps(output,
                                                   ensure_ascii=False)})
    return LOOP_FALLBACK, True


WANTS_RECS_RE = re.compile(
    r"recommend|recommendation|show me options|show options|"
    r"رشح|رشّح|اقترح|وريني|ورّني|ورني|اعرض|الخيارات|"
    r"सुझा|recommand|recomiend",
    re.IGNORECASE)


def wants_recommendations(message):
    """True when the user explicitly asks to see recommendations."""
    return bool(WANTS_RECS_RE.search(message or ""))


def _needs_ready(turn):
    """True when the session already carries enough stated needs."""
    return bool(turn.get("needs_all") or turn.get("needs_any")
                or turn.get("budgets") or turn.get("min_martindale"))


def _maybe_prefetch_search(history, turn, message, on_step):
    """Search-first: fewer-round rec turns.

    When the session already has enough needs (or the user explicitly
    asks), run search_catalog locally and inject the results as a tool
    exchange, so the model skips its own search round. Details stay the
    model's job: it calls get_fabric for the candidates it judges
    relevant, which keeps specialized retrieval (luxe, sadu,
    fire-resistant) as good as an unassisted turn while cutting the
    usual 3-4 rounds down to 2. Grounding is unchanged: every code
    comes from a real search, turn["seen"] is populated, and
    valid_recommendations still enforces seen-only codes.
    """
    if turn.get("searched"):
        return
    # Only on an explicit "recommend now": a generic seeded search on
    # ordinary need-gathering turns hands the model untargeted results
    # (no style/feature args) and hurt specialized picks in eval.
    # ...and only when the session already carries stated needs: with
    # none (e.g. "sadu cushions"), an empty-args search returns generic
    # top fabrics and the model copies them; let it search with its own
    # pattern/style filters instead.
    explicit = (wants_recommendations(message) or turn.get("skip_needs")
                or turn.get("force_recs"))
    if not explicit or not _needs_ready(turn):
        return
    seed_args = {"usage": "curtains"} if turn.get(
        "curtains_only") else {}
    seed_args["limit"] = 12
    if on_step:
        on_step("search")
    result = run_search(seed_args, turn)
    turn["seen"].extend(f["code"] for f in result["fabrics"])
    for name in result["relaxed_constraints"]:
        if name not in turn["relaxed"]:
            turn["relaxed"].append(name)
    turn["searched"] = True
    # Unique per injection: repeated prefetches in one session must not
    # reuse tool_call ids (the API rejects duplicate ids with a 400).
    tag = uuid.uuid4().hex[:8]
    calls = [{"id": "seed-search-%s" % tag, "type": "function",
              "function": {"name": "search_catalog",
                           "arguments": json.dumps(seed_args)}}]
    history.append({"role": "assistant", "content": None,
                    "tool_calls": calls})
    history.append({"role": "tool",
                    "tool_call_id": "seed-search-%s" % tag,
                    "content": json.dumps(
                        {"fabrics": result["fabrics"][:12],
                         "relaxed_constraints":
                             result["relaxed_constraints"]},
                        ensure_ascii=False)})


def _user_target_wins(session, target):
    """Return the user's own chosen item when it conflicts with target.

    ``user_targets`` is set only from the user's words or taps (never
    from model tool calls). With exactly one user-chosen item, every
    preview / assignment lands on it, whatever target the model passed.
    """
    if not session:
        return target
    user = session.get("user_targets") or []
    if len(user) == 1 and target != user[0]:
        return user[0]
    return target


# "Just show me" chip, offered on every question after the item is
# chosen. Each phrase is matched by targets.SKIP_WORDS so a tap on the
# chip skips the remaining questions and recommends immediately.
JUST_SHOW_LINES = {
    "en": "Just show me",
    "ar": "وريني الحين",
    "hi": "बस दिखाओ",
    "fr": "Montrez-moi",
    "es": "Solo muéstrame",
}


def ensure_just_show_option(options, lang):
    """Append the localized Just-show-me chip when it is missing."""
    from app.services.targets import SKIP_WORDS
    line = JUST_SHOW_LINES.get(lang or "en", JUST_SHOW_LINES["en"])
    opts = list(options or [])
    # The model is told to offer "Just show me" verbatim; in another
    # language that English chip is swapped for the localized one.
    en = JUST_SHOW_LINES["en"].lower()
    opts = [line if str(o).strip().lower() == en else o for o in opts]
    low = [str(o).strip().lower() for o in opts]
    # The model's own skip chip in any language counts as present.
    if any(line.lower() == o or any(w in o for w in SKIP_WORDS)
           for o in low):
        return opts
    if len(opts) >= 4:
        opts = opts[:3]
    opts.append(line)
    return opts


def valid_recommendations(data, seen):
    """Check exactly 3 distinct grounded codes. Returns (recs, bad_code).

    Every code must exist and have come from a search result this turn;
    memory-only picks are rejected the same way as invented codes, and
    duplicates ([A,A,A]) are rejected.
    """
    if not isinstance(data, list) or len(data) != 3:
        return None, "want exactly 3"
    recs = []
    used = set()
    for entry in data:
        code = (entry or {}).get("code", "")
        if code in used:
            return None, code
        if not get_fabric(code) or code not in (seen or []):
            return None, code
        used.add(code)
        recs.append({"code": code,
                     "reason": (entry or {}).get("reason", "")})
    return recs, None


def light_color_note(recommendations, arabic, who):
    """Warn when a light, non-washable fabric is shown for kids or pets."""
    flagged = [r["code"] for r in recommendations
               if is_light_unprotected(get_fabric(r["code"]))]
    if not flagged:
        return ""
    codes = ", ".join(flagged)
    if arabic:
        tail = "مع الأطفال" if who == "kids" else "مع الحيوانات"
        return ("ملاحظة: %s فاتح اللون وغير مقاوم للبقع، ويحتاج عناية "
                "إضافية %s." % (codes, tail))
    tail = "with kids" if who == "kids" else "with pets"
    return ("Note: %s is light-colored and not stain-resistant, so expect "
            "extra care %s." % (codes, tail))


KEEP_RECENT = 6


def trim_history(history):
    """Shrink stored history in place without breaking tool references.

    Only message *contents* are shortened, never removed, so
    tool_call_id links stay intact. The last KEEP_RECENT messages (the
    live context) are left untouched; older tool outputs collapse to a
    one-liner and old room-analysis blocks collapse to a stub, since
    both are re-derived from the trimmed record on later turns.
    """
    system = 1 if history and history[0].get("role") == "system" else 0
    cutoff = max(system, len(history) - KEEP_RECENT)
    for msg in history[system:cutoff]:
        if msg.get("role") == "tool":
            try:
                payload = json.loads(msg.get("content") or "{}")
            except ValueError:
                payload = {}
            if isinstance(payload, dict) and "fabrics" in payload:
                msg["content"] = "[earlier search: %d fabrics]" % len(
                    payload.get("fabrics") or [])
            elif isinstance(payload, dict) and "error" not in payload:
                msg["content"] = "[earlier tool output]"
        elif msg.get("role") == "user" and "[Room photo analyzed:" in (
                msg.get("content") or ""):
            msg["content"] = "[Room photo analyzed before]"


def turn_for(message):
    """Build the expert-rule context for one user message."""
    needs = map_needs_to_features(message)
    pet_needs = [f for f in needs if f in PET_OR_FEATURES]
    core_needs = [f for f in needs if f not in PET_OR_FEATURES]
    protected = []
    if has_pets(message):
        protected.append("pet-friendly")
    if has_kids(message):
        protected.extend(["washable", "antibacterial"])
    return {"seen": [], "relaxed": [], "searched": False,
            "needs_any": pet_needs, "needs_all": core_needs,
            "protected": protected,
            "pet_safe": has_pets(message),
            "has_kids": has_kids(message),
            "min_martindale": 50000 if needs_durable(message) else None}


def accumulate_context(session, turn):
    """Union this turn's needs with the session's running needs.

    Follow-up turns ("recommend now", "something darker") rarely restate
    the household, so protection must persist across the session.
    """
    for key in ("needs_any", "needs_all", "protected"):
        merged = list(session.get(key, []))
        for value in turn[key]:
            if value not in merged:
                merged.append(value)
        turn[key] = merged
        session[key] = merged
    for key in ("pet_safe", "has_kids"):
        turn[key] = turn[key] or session.get(key, False)
        session[key] = turn[key]
    turn["min_martindale"] = max(
        [m for m in (turn["min_martindale"],
                     session.get("min_martindale")) if m] or [None])
    session["min_martindale"] = turn["min_martindale"]
    return turn


LANG5 = ("en", "ar", "hi", "fr", "es")

# Short deterministic server lines in all five journey languages.
# Everything longer (relaxation disclosures, light-color notes) stays
# EN/AR: the model covers those in-language first, verified on live
# hi/fr/es turns.
CLOSEST_LINES = {
    "en": "These are the closest matches I found for you:",
    "ar": "هذه أقرب الخيارات اللي لقيتها لك:",
    "hi": "ये आपके लिए सबसे क़रीबी विकल्प हैं जो मुझे मिले:",
    "fr": "Voici les correspondances les plus proches que j'ai trouvées :",
    "es": "Estas son las opciones más cercanas que encontré para ti:",
}
UNREADABLE_LINES = {
    "en": ("I couldn't read that photo — please send a JPG or PNG photo, "
           "or pick a sample room."),
    "ar": ("ما قدرت أقرأ الصورة — ارسل صورة JPG أو PNG، "
           "أو اختر غرفة جاهزة."),
    "hi": ("मैं वह फ़ोटो पढ़ नहीं पाया — कृपया JPG या PNG फ़ोटो भेजें, "
           "या कोई सैंपल रूम चुनें।"),
    "fr": ("Je n'ai pas pu lire cette photo — envoyez une photo JPG ou "
           "PNG, ou choisissez une pièce d'exemple."),
    "es": ("No pude leer esa foto — envía una foto JPG o PNG, o elige "
           "una habitación de ejemplo."),
}
DECLINE_LINES = {
    "en": ("That's outside my expertise — I'm here for your fabrics "
           "and interiors. What fabric can I help you with?"),
    "ar": ("هذا خارج تخصصي، أنا هنا لأقمشتك وديكورك. "
           "أساعدك بأي قماش اليوم؟"),
    "hi": ("यह मेरी विशेषज्ञता से बाहर है — मैं यहाँ आपके फ़ैब्रिक "
           "और इंटीरियर के लिए हूँ। आज मैं आपकी किस फ़ैब्रिक में "
           "मदद करूँ?"),
    "fr": ("Cela dépasse mon expertise — je suis là pour vos tissus et "
           "votre intérieur. Quel tissu puis-je vous aider à choisir "
           "aujourd'hui ?"),
    "es": ("Eso está fuera de mi especialidad — estoy aquí para tus "
           "telas e interiores. ¿Con qué tela te ayudo hoy?"),
}
CONFIRM_LINES = {
    "en": ("Quick check — you mentioned your %s, but the photo mainly "
           "shows a %s. Which piece should I recommend for?"),
    "ar": ("تأكيد سريع — ذكرت %s، لكن الصورة توضح %s بشكل أساسي. "
           "لأي قطعة تبغى التوصية؟"),
    "hi": ("एक जल्दी पुष्टि — आपने %s कहा, लेकिन तस्वीर में ज़्यादातर "
           "%s है। मैं किसके लिए सुझाव दूँ?"),
    "fr": ("Vérification rapide — vous avez mentionné %s, mais la photo "
           "montre surtout %s. Pour quelle pièce dois-je recommander ?"),
    "es": ("Una comprobación rápida — mencionaste %s, pero la foto "
           "muestra sobre todo %s. ¿Para qué pieza recomiendo?"),
}
PIECE_NAMES_5 = {
    "sofa": ("sofa", "الكنبة", "सोफ़ा", "canapé", "sofá"),
    "armchair": ("armchair", "الكرسي", "कुर्सी", "fauteuil", "sillón"),
    "curtains": ("curtains", "الستائر", "परदे", "rideaux", "cortinas"),
    "cushions": ("cushions", "الوسائد", "कुशन", "coussins", "cojines"),
}
LANG_INDEX = {"en": 0, "ar": 1, "hi": 2, "fr": 3, "es": 4}


def _reply_lang(turn=None, message="", session=None):
    """Best-known 5-lang code for a deterministic server line."""
    lang = (turn or {}).get("lang") or (session or {}).get("lang")
    if lang in LANG5:
        return lang
    try:
        detected = detect_user_lang(message)
    except Exception:  # noqa: BLE001 - fall back to Arabic check
        detected = None
    if detected in LANG5:
        return detected
    return "ar" if is_arabic(message) else "en"


def confirm_piece_question(stated, detected, lang="en"):
    idx = LANG_INDEX.get(lang, 0)
    names = PIECE_NAMES_5
    piece = lambda p: names.get(p, (p, p, p, p, p))[idx]  # noqa: E731
    return CONFIRM_LINES.get(lang, CONFIRM_LINES["en"]) % (piece(stated),
                                                          piece(detected))


def decline_reply(topic, lang="en"):
    """One-line polite decline with a steer back. No model call."""
    if lang in ("en", "ar"):
        if lang == "ar":
            base = "هذا خارج تخصصي، أنا هنا لأقمشتك وديكورك."
            if topic and topic in PIECE_NAMES_AR:
                return base + " نكمل على %s؟" % PIECE_NAMES_AR[topic]
            return base + " أساعدك بأي قماش اليوم؟"
        base = ("That's outside my expertise — I'm here for your fabrics "
                "and interiors.")
        if topic:
            return base + " Shall we continue with your %s?" % topic
        return base + " What fabric can I help you with?"
    return DECLINE_LINES.get(lang, DECLINE_LINES["en"])


ANNOTATION_RE = re.compile(r"\n?\[[^\]]*\]\s*$")
GREET_WORDS = ("hello", "مرحبا", "नमस्ते", "bonjour", "hola")


def visible_user_text(content):
    """User text as typed: server annotations ([...] lines) removed."""
    text = content or ""
    while True:
        cut = ANNOTATION_RE.sub("", text)
        if cut == text:
            break
        text = cut
    text = re.sub(r"\nSuggested features from my needs:.*$", "", text,
                  flags=re.S)
    return text.strip()


def session_state(session_id):
    """Everything the web client needs to rebuild a session after a
    page refresh: visible messages, photo, targets, picks, last recs,
    the last quote. None when the session is unknown."""
    session = SESSIONS.get(session_id)
    if not session:
        return None
    messages = []
    history = session.get("messages", [])
    first_user = True
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        if role == "user":
            text = visible_user_text(content)
            if first_user:
                first_user = False
                if text.lower() in GREET_WORDS:
                    continue
            if not text or text.startswith("[") and text.endswith("]"):
                continue
            messages.append({"who": "me", "text": text})
        elif role == "assistant":
            text = strip_options(strip_block(content)).strip()
            if text:
                messages.append({"who": "them", "text": text})
    quote = None
    assignments = session.get("assignments", {}) or {}
    if assignments:
        from app.services import meterage as meterage_mod
        fabrics = {code: get_fabric(code) for code in set(
            assignments.values()) if get_fabric(code)}
        quote = meterage_mod.quote(assignments, fabrics,
                                   session.get("curtain_dims"),
                                   session.get("pillow_counts", {}))
    last_options = []
    for msg in reversed(history):
        if msg.get("role") == "assistant" and isinstance(
                msg.get("content"), str):
            last_options = extract_options(msg["content"]) or []
            break
    return {"session_id": session_id,
            "lang": session.get("lang"),
            "options": last_options,
            "image_path": session.get("image_path"),
            "room_analysis": session.get("room_analysis"),
            "detected_piece": session.get("detected_piece"),
            "messages": messages,
            "targets": {"available": session.get("available_targets", []),
                        "chosen": session.get("chosen_targets", []),
                        "assignments": assignments},
            "last_recs": session.get("last_recs", []),
            "quote": quote,
            "quoted": bool(session.get("quoted_once"))}


def chat(session_id, message, image_path=None, chat_fn=None,
         on_token=None, on_step=None, lang=None):
    """One user turn. Returns {reply, recommendations, room_analysis?}."""
    t0 = time.time()
    # A5: one turn at a time per session, so a client fallback or a
    # double tap can't interleave two turns into the same history.
    with _session_lock(session_id):
        try:
            return _chat(session_id, message, image_path, chat_fn,
                         on_token=on_token, on_step=on_step, lang=lang)
        finally:
            _perf({"kind": "turn", "seconds": round(time.time() - t0, 2),
                   "image": bool(image_path),
                   "msg_chars": len(message or "")})


_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def _session_lock(session_id):
    with _LOCKS_GUARD:
        lock = _LOCKS.get(session_id)
        if lock is None:
            lock = _LOCKS[session_id] = threading.RLock()
        return lock


def _chat(session_id, message, image_path=None, chat_fn=None,
          on_token=None, on_step=None, lang=None):
    session = SESSIONS.setdefault(session_id, {"messages": [],
                                               "detected_piece": None,
                                               "topic": None})
    history = session["messages"]
    trim_history(history)
    if lang in LANG_NAMES:
        session["lang"] = lang
    if not image_path and not is_in_scope(message) and not (
            _spark_open_enabled() and baseten_scope_allows(message)):
        reply = decline_reply(
            session.get("topic"),
            _reply_lang(None, message, session))
        history.append({"role": "user", "content": message or ""})
        history.append({"role": "assistant", "content": reply})
        return {"reply": reply, "recommendations": []}
    piece = detect_piece(message)
    if piece:
        session["topic"] = piece
    if not history or history[0].get("role") != "system":
        history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    room_analysis = None
    user_text = message or ""
    if lang not in LANG_NAMES:
        detected_lang = detect_user_lang(message)
        if detected_lang:
            session["lang"] = detected_lang
    if session.get("lang"):
        instruction = "Reply only in %s." % LANG_NAMES.get(
            session["lang"], "English")
    else:
        instruction = "Reply in the same language the user wrote in."
    user_text += "\n[%s]" % instruction
    if re.match(r"^[\s?؟!….…]{1,8}$", message or ""):
        user_text += ("\n[The user is confused. Do not start over or ask "
                      "for new information; simply rephrase your last open "
                      "question in short, plain words.]")
    turn = accumulate_context(session, turn_for(message))
    turn["lang"] = session.get("lang")
    if image_path:
        # A new photo drops the old photo's items: stale available /
        # chosen / assignments would otherwise leak across rooms.
        if image_path != session.get("image_path"):
            session["available_targets"] = []
            session["chosen_targets"] = []
            session["user_targets"] = []
            session["asked_after_choice"] = 0
            session["assignments"] = {}
            session.pop("detected_piece", None)
        session["image_path"] = image_path
    turn["image"] = image_path or session.get("image_path")
    turn["session"] = session
    from app.services import targets as targets_mod
    available = session.get("available_targets", [])
    room_analysis = None
    analysis_failed = False
    if image_path:
        path = image_path if os.path.isabs(image_path) else \
            os.path.join(BASE_DIR, image_path)
        if not os.path.exists(path):
            raise FileNotFoundError("image not found: %s" % image_path)
        # Cold photo turn: target listing and room analysis run side by
        # side and share one cached listing with /targets — the turn
        # pays max(), not the sum, of the vision calls.
        box = {}

        def _do_analysis():
            try:
                box["room"] = analyze_room(image_path, turn.get("lang"))
            except Exception as exc:  # noqa: BLE001 - caller sends unreadable
                box["failed"] = True
                _log_photo_failure("analyze_room", image_path, exc)

        analyzer = threading.Thread(target=_do_analysis, daemon=True)
        analyzer.start()
        if not available:
            try:
                available = targets_mod.available_types(image_path)
            except Exception as exc:  # noqa: BLE001 - never break chat
                available = None  # unknown, not "nothing visible"
                _log_photo_failure("available_types", image_path, exc)
            session["available_targets"] = available
            available = available or []
        analyzer.join()
        room_analysis = box.get("room")
        analysis_failed = bool(box.get("failed"))
    chosen, choice_flags = targets_mod.match_targets(
        message, available) if available else ([], {})
    if chosen and choice_flags.get("skip") and session.get("user_targets"):
        # "Just show me" after an item was picked keeps that item; it
        # only skips the remaining questions.
        chosen = []
    if chosen:
        session["chosen_targets"] = chosen
        # Remember what the USER picked (tap, chip or words). Model tool
        # calls may add assignments but never change this list.
        if session.get("user_targets") != chosen:
            session["user_targets"] = list(chosen)
            session["asked_after_choice"] = 0
    turn["chosen_targets"] = session.get("chosen_targets", [])
    turn["skip_needs"] = bool(choice_flags.get("skip"))
    # After the item is chosen the consultant asks at most one more
    # question; the second turn without recommendations is forced.
    if (session.get("user_targets") and turn.get("image")
            and not turn["skip_needs"]
            and session.get("asked_after_choice", 0) >= 1):
        turn["force_recs"] = True
    turn["curtains_only"] = (session.get("chosen_targets", [])
                             == ["curtains"])
    # The "which item to change" question is asked once, right after
    # the photo is analyzed. Repeating it on every later turn (incl.
    # recommendation turns) makes the sofa line appear in every reply.
    if available and not session.get("chosen_targets") and image_path:
        user_text += ("\n[Visible changeable items: %s. Ask which to "
                      "change first.]" % ", ".join(available))
    elif session.get("chosen_targets"):
        user_text += ("\n[Chosen items: %s.]" % ", ".join(
            session["chosen_targets"]))
        if turn.get("skip_needs") or turn.get("force_recs"):
            user_text += ("\n[Recommend now: call search_catalog and end "
                          "this reply with exactly 3 recommendations. "
                          "Do not ask another question.]")
        elif session.get("asked_after_choice", 0) == 0:
            user_text += ("\n[You may ask ONE question at most before "
                          "recommending; include \"Just show me\" among "
                          "the options.]")
    confirm = ""
    if image_path:
        # room_analysis/analysis_failed were computed in parallel with
        # the target listing above; the exists check already raised.
        if analysis_failed:
            lang = _reply_lang(turn, message, session)
            reply = UNREADABLE_LINES.get(lang, UNREADABLE_LINES["en"])
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply})
            return {"reply": reply, "recommendations": [],
                    "options": [], "preview": None,
                    "targets": {"available": [],
                                "chosen": [],
                                "assignments": {}},
                    "detected_lang": session.get("lang")}
        user_text += "\n[Room photo analyzed: %s]" % json.dumps(
            room_analysis, ensure_ascii=False)
        needs_text = ", ".join(turn["needs_all"] + turn["needs_any"]) \
            or "none"
        user_text += "\nSuggested features from my needs: %s" % needs_text
        stated = detect_piece(message)
        detected = detect_piece((room_analysis or {}).get("furniture", ""))
        if stated and detected and stated != detected:
            session["detected_piece"] = detected
            confirm = confirm_piece_question(
                stated, detected,
                _reply_lang(turn, message, session))
    history.append({"role": "user", "content": user_text})
    if on_step and image_path:
        on_step("room")
    _maybe_prefetch_search(history, turn, message, on_step)
    final_text, exhausted = agent_turn(list(history), chat_fn, turn,
                                         on_token=on_token,
                                         on_step=on_step)
    extracted = extract_recommendations(final_text)
    recs, bad = (None, None)
    if extracted is not None:
        recs, bad = valid_recommendations(extracted, turn["seen"])
    attempted = extracted is not None
    ground_bad = bad if isinstance(bad, str) else ""

    # Explicit "recommend now" with no usable search yet: the model
    # dodged the tools (asked a question instead, or its search came
    # back empty). Seed one server-side search from the session needs
    # so the deterministic fallback below still answers in THIS turn —
    # hi/fr/es dodges cost a whole extra model round trip otherwise.
    if wants_recommendations(message) and not [
            c for c in turn["seen"] if get_fabric(c)]:
        seed_args = {"usage": "curtains"} if turn.get(
            "curtains_only") else {}
        seed = run_search(seed_args, turn)
        turn["seen"].extend(f["code"] for f in seed["fabrics"])
        for name in seed["relaxed_constraints"]:
            if name not in turn["relaxed"]:
                turn["relaxed"].append(name)
        turn["searched"] = True
    seen_codes = [c for c in turn["seen"] if get_fabric(c)]
    if bad:
        history.append({"role": "assistant", "content": final_text})
        history.append({"role": "user", "content":
                        "Code %s is not allowed. You must pick exactly 3 "
                        "codes from this exact list and nothing else: %s. "
                        "Same reply text, ending with the "
                        "```recommendations block."
                        % (bad, ", ".join(seen_codes) or "none")})
        final_text, retry_exhausted = agent_turn(
            list(history), chat_fn, turn,
            on_token=on_token, on_step=on_step)
        exhausted = exhausted or retry_exhausted
        extracted = extract_recommendations(final_text)
        if extracted is not None:
            attempted = True
            recs, bad = valid_recommendations(extracted, turn["seen"])
        else:
            recs, bad = None, None

    recommendations = recs if (recs and not bad) else []
    used_fallback = False
    explicit = wants_recommendations(message) and turn.get("searched")
    if not recommendations and (attempted or exhausted or explicit) \
            and seen_codes:
        arabic = (turn.get("lang") or "en") == "ar"
        top = list(dict.fromkeys(seen_codes))[:3]
        reason = ("أقرب خيار لاحتياجك من هذا البحث." if arabic else
                  "Closest match for your needs from this search.")
        recommendations = [{"code": code, "reason": reason}
                           for code in top]
        used_fallback = True
        log_grounding(session_id,
                      ground_bad or (bad if isinstance(bad, str) else ""),
                      "fallback", top)
    elif ground_bad or (exhausted and not recommendations):
        log_grounding(session_id, ground_bad,
                      "retry_ok" if recommendations else "unresolved",
                      [r["code"] for r in recommendations])

    chosen_targets = session.get("chosen_targets", [])
    user_targets = session.get("user_targets") or []
    if len(user_targets) == 1:
        # The user's tap is authoritative for the auto-applied pick.
        chosen_targets = user_targets + [
            tg for tg in chosen_targets if tg != user_targets[0]]
    if (turn.get("preview") and not turn["preview"].get("target")
            and len(chosen_targets) == 1):
        turn["preview"]["target"] = chosen_targets[0]
    # Recommendations never start a render on their own: the user taps
    # Try (or asks for a code) and that is the only way a swap begins.
    # A preview here comes from the preview_fabric tool, i.e. a request
    # in the user's own words.

    reply = strip_block(final_text)
    options = extract_options(reply) or []
    reply = strip_options(reply)
    if turn.get("quoted"):
        # Quote turns offer actions (send to upholsterer / try another
        # fabric) instead of recommendation chips.
        options = []
    elif session.get("user_targets") and turn.get("image"):
        if recommendations:
            session["asked_after_choice"] = 0
        else:
            session["asked_after_choice"] = \
                session.get("asked_after_choice", 0) + 1
            options = ensure_just_show_option(options, _reply_lang(turn))
    if not recommendations:
        reply = strip_tip(reply)
    if not reply.strip():
        nudge = ("[System: your last reply had no visible text. Say it "
                 "again with at least one full sentence of visible prose "
                 "before any fenced block.]")
        retry_text, _ = agent_turn(
            list(history) + [{"role": "user", "content": nudge}],
            chat_fn, turn, on_token=on_token, on_step=on_step)
        retry_reply, retry_options, retry_recs = split_final(
            retry_text, turn)
        if retry_reply:
            reply = retry_reply
            options = retry_options or options
            if retry_recs:
                recommendations = retry_recs
            final_text = retry_text
        else:
            reply = empty_fallback(
                bool(options), bool(recommendations),
                turn.get("lang") or session.get("lang"))
    reply = reply.strip()
    prev_assistant = next((m.get("content") or ""
                           for m in reversed(history)
                           if m.get("role") == "assistant"), "")
    # Strip machine blocks from both sides before comparing: history
    # still holds the raw reply with ```options/```recommendations,
    # while reply is already stripped, so raw comparison scores ~0.57
    # and the guard never fires.
    prev_clean = strip_options(strip_block(prev_assistant))
    reply_clean = strip_options(strip_block(reply))
    if prev_clean and similar_reply(reply_clean, prev_clean) >= 0.9:
        nudge = ("[System: the user already answered your last question "
                 "('%s'). Move forward — ask the next missing thing, "
                 "do not repeat it.]" % (message or "")[:200])
        retry_text2, _ = agent_turn(
            list(history) + [{"role": "user", "content": nudge}],
            chat_fn, turn, on_token=on_token, on_step=on_step)
        retry_reply2, retry_options2, retry_recs2 = split_final(
            retry_text2, turn)
        retry_clean = strip_options(strip_block(retry_reply2 or ""))
        if retry_reply2 and similar_reply(retry_clean, prev_clean) < 0.9:
            reply = retry_reply2
            options = retry_options2 or options
            if retry_recs2:
                recommendations = retry_recs2
            final_text = retry_text2
    if confirm:
        reply = (reply + "\n\n" + confirm).strip()
    enriched_early = enrich(recommendations, turn)
    max_over = max([r["relaxed_budget"]["over"]
                    for r in enriched_early
                    if r["relaxed_budget"]] or [0])
    missing = missing_relaxation(reply, turn["relaxed"],
                                 is_arabic(user_text))
    # On recommendation turns the card's one-line receipt carries the
    # relaxed info, so the prose disclosure stays only on turns
    # without recommendations (never the same feature list twice).
    if missing and not recommendations and not turn.get("quoted"):
        needs = turn.get("needs_all", []) + turn.get("needs_any", [])
        reply = (reply + "\n\n" + disclosure_note(
            missing, is_arabic(user_text), max_over, needs)).strip()
    who = ("kids" if turn.get("has_kids")
           else "pets" if turn.get("pet_safe") else None)
    if recommendations and who:
        note = light_color_note(recommendations, is_arabic(user_text),
                                who)
        if note and note not in reply:
            reply = (reply + "\n\n" + note).strip()
    if used_fallback:
        lang = _reply_lang(turn)
        line = CLOSEST_LINES.get(lang, CLOSEST_LINES["en"])
        if "closest match" not in reply.lower() and "أقرب" not in reply:
            reply = (reply + "\n\n" + line).strip()
    if not any(m.get("role") == "assistant" for m in history):
        reply = collapse_adjacent_dupes(reply)
    history.append({"role": "assistant", "content": final_text})
    trim_history(history)

    if enriched_early:
        session["last_recs"] = enriched_early
    if turn.get("quoted"):
        session["quoted_once"] = True
    if room_analysis is not None:
        session["room_analysis"] = room_analysis
    result = {"reply": reply,
              "recommendations": enriched_early,
              "options": options,
              "quote": turn.get("quoted"),
              "preview": turn.get("preview"),
              "targets": {"available": session.get("available_targets",
                                                    []),
                          "chosen": session.get("chosen_targets", []),
                          "assignments": session.get("assignments", {})},
              "detected_lang": session.get("lang")}
    if room_analysis is not None:
        result["room_analysis"] = room_analysis
        if session.get("detected_piece"):
            result["detected_piece"] = session["detected_piece"]
    return result
