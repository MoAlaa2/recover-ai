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
import time
import urllib.request

from app.core.config import (BASE_DIR, CHAT_URL, SPARK_MODEL,
                             require_api_key)
from app.services.catalog import (compact, contains_egyptian, get_fabric,
                                  is_arabic, load_specs,
                                  map_needs_to_features, search_catalog)

SESSIONS = {}
MAX_TOOL_ROUNDS = 6
MAX_RETRIES = 2

SYSTEM_PROMPT = """You are the ReCover consultant, a luxury fabric and \
upholstery advisor for a premium Saudi showroom.
Voice: warm, premium, concise. No emoji spam (at most one emoji, or none).

LANGUAGE: reply in the user's language. Arabic means refined white Saudi \
dialect only (use: أبغى، أبي، ودي، الحين، مره، زين، مجلس، صالة). Never use \
Egyptian words such as: عايز، ازيك، كده، علشان، دلوقتي، فين، ليه. English \
means warm, premium, concise.

OPENING (first message only): introduce yourself in exactly 2 short lines \
(who you are, what you can do: recommend fabrics, analyze a room photo, \
show your own furniture in a new fabric). Then ask exactly one question.

DISCOVERY: first learn the use: upholstery, curtains, cushions, or a mix. \
Then gather naturally, one question at a time, only what is still missing: \
room colors or a room photo, mood (warm/cool/neutral), style, who uses the \
space (kids, pets, hotel, office), opacity for curtains, budget per meter.

TOOLS: you never see the full catalog. Always call search_catalog before \
recommending anything, and get_fabric for details you quote. When the user \
shares a room photo, call analyze_room. Never invent fabric codes: every \
recommended code must come from a tool result in this conversation.

NEEDS MAPPING: pets -> pet-friendly and scratch-resistant; kids -> \
easy-clean, stain-resistant and antibacterial; hotel or restaurant -> \
fire-resistant; bedroom curtains -> blackout.

RECOMMENDATIONS: when you have enough, reply normally and end with one \
fenced block on its own lines:
```recommendations
[{"code": "FA-VL-01", "reason": "why in the user's language"}]
```
Exactly 3 items, codes only from tool results. If you are told a code was \
rejected, fix it with a real code from your tool results.

RELAXED CONSTRAINTS: if a tool result says constraints were relaxed, state \
plainly in your reply which constraint was relaxed (for example budget).

TIP: include one short professional tip with recommendations (martindale \
for heavy use, fade-resistant for sunny rooms, washable for kids).

OFF-TOPIC: if the user greets, asks what you do, or drifts off-topic, \
answer naturally in one or two lines and steer back to fabrics with a \
question."""


def _call_chat(messages, tools=None):
    """Low-level chat call. Monkeypatch this in tests."""
    payload = {"model": SPARK_MODEL, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                CHAT_URL, data=data,
                headers={"Authorization": "Bearer " + require_api_key(),
                         "Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - retry then raise
            last_err = exc
            time.sleep(2 * (attempt + 1))
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
            "features": {"type": "array", "items": {"type": "string"}},
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
        "name": "analyze_room",
        "description": "Analyze a room photo at a server-side image path.",
        "parameters": {"type": "object",
                       "properties": {"image_path": {"type": "string"}},
                       "required": ["image_path"]}}},
]


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def run_search(args):
    summaries, relaxed = search_catalog(
        usage=args.get("usage"), colors=_as_list(args.get("colors")),
        tone=args.get("tone"),
        plain_or_patterned=args.get("plain_or_patterned"),
        styles=_as_list(args.get("styles")),
        features=_as_list(args.get("features")),
        suitable_for=_as_list(args.get("suitable_for")),
        opacity=args.get("opacity"), max_price=args.get("max_price"),
        limit=args.get("limit", 6) or 6)
    return {"fabrics": summaries, "relaxed_constraints": relaxed}


def analyze_room(image_path):
    """Vision analysis of a room photo. Returns a JSON dict."""
    path = image_path if os.path.isabs(image_path) else \
        os.path.join(BASE_DIR, image_path)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    messages = [{"role": "user", "content": [
        {"type": "text", "text":
         "Analyze this room photo for an upholstery consultant. Reply with "
         "JSON only: {\"room_type\": \"...\", \"wall_colors\": "
         "[{\"name\": \"...\", \"hex\": \"#...\"}] (5 entries), "
         "\"floor\": \"...\", \"furniture\": \"...\", "
         "\"existing_fabrics\": \"...\", \"light_level\": \"low/medium/"
         "high\", \"style\": \"...\"}."},
        {"type": "image_url",
         "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]
    body = _call_chat(messages)
    text = body["choices"][0]["message"]["content"] or ""
    try:
        return json.loads(text[text.find("{"):text.rfind("}") + 1])
    except (ValueError, IndexError):
        return {"raw": text[:1000]}


RECO_RE = re.compile(r"```recommendations\s*(\[.*?\])\s*```", re.DOTALL)


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


RELAX_LABELS = {
    "max_price": ("budget", "الميزانية"),
    "features": ("features", "المواصفات"),
    "opacity": ("opacity", "التعتيم"),
    "colors": ("colors", "الألوان"),
    "tone": ("tone", "الدرجة"),
    "suitable_for": ("use", "الاستخدام"),
    "styles": ("style", "الستايل"),
    "plain_or_patterned": ("pattern", "النقشة"),
}


def disclosure_note(relaxed, arabic):
    names = [RELAX_LABELS.get(r, (r, r))[1 if arabic else 0]
             for r in relaxed]
    if arabic:
        return ("ملاحظة: خففت شرط (%s) لأجد لك خيارات مناسبة."
                % "، ".join(names))
    return ("Note: I relaxed the (%s) constraint to find you options."
            % ", ".join(names))


def mentioned_relaxation(text):
    t = (text or "").lower()
    return any(w in t for w in
               ["relax", "خفف", "وسّع", "budget", "الميزانية"])


def enrich(recommendations):
    """Attach catalog details to validated recommendations."""
    out = []
    for rec in recommendations:
        item = get_fabric(rec["code"])
        out.append({"code": rec["code"],
                    "name_en": item["name_en"],
                    "name_ar": item["name_ar"],
                    "price_sar_per_m": item["price_sar_per_m"],
                    "image": item.get("image", ""),
                    "reason": rec.get("reason", "")})
    return out


def execute_tool(name, args, turn):
    if name == "search_catalog":
        result = run_search(args or {})
        turn["seen"].extend(f["code"] for f in result["fabrics"])
        turn["relaxed"] = result["relaxed_constraints"]
        return result
    if name == "get_fabric":
        item = get_fabric((args or {}).get("code", ""))
        return item or {"error": "unknown code"}
    if name == "analyze_room":
        return analyze_room((args or {}).get("image_path", ""))
    return {"error": "unknown tool " + str(name)}


def agent_turn(messages, chat_fn, turn):
    """Run the tool loop. Returns the model's final text."""
    call = chat_fn or _call_chat
    for _ in range(MAX_TOOL_ROUNDS):
        body = call(messages, TOOLS)
        msg = body["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content") or ""
        messages.append({"role": "assistant", "content": msg.get("content"),
                         "tool_calls": calls})
        for tc in calls:
            fn = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            try:
                output = execute_tool(fn, args, turn)
            except Exception as exc:  # noqa: BLE001 - report to model
                output = {"error": str(exc)}
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": json.dumps(output,
                                                   ensure_ascii=False)})
    return "Let me show you what I found so far."


def valid_recommendations(data, seen):
    """Check exactly 3 known codes. Returns (recs, bad_code)."""
    if not isinstance(data, list) or len(data) != 3:
        return None, "want exactly 3"
    recs = []
    for entry in data:
        code = (entry or {}).get("code", "")
        if not get_fabric(code):
            return None, code
        recs.append({"code": code,
                     "reason": (entry or {}).get("reason", "")})
    return recs, None


def chat(session_id, message, image_path=None, chat_fn=None):
    """One user turn. Returns {reply, recommendations, room_analysis?}."""
    history = SESSIONS.setdefault(session_id, [])
    if not history or history[0].get("role") != "system":
        history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    room_analysis = None
    user_text = message or ""
    if image_path:
        path = image_path if os.path.isabs(image_path) else \
            os.path.join(BASE_DIR, image_path)
        if not os.path.exists(path):
            raise FileNotFoundError("image not found: %s" % image_path)
        room_analysis = analyze_room(image_path)
        user_text += "\n[Room photo analyzed: %s]" % json.dumps(
            room_analysis, ensure_ascii=False)
        needs = ", ".join(map_needs_to_features(message)) or "none"
        user_text += "\nSuggested features from my needs: %s" % needs
    history.append({"role": "user", "content": user_text})

    turn = {"seen": [], "relaxed": []}
    final_text = agent_turn(list(history), chat_fn, turn)
    recs, bad = valid_recommendations(
        extract_recommendations(final_text), turn["seen"]) \
        if extract_recommendations(final_text) is not None else (None, None)

    if extract_recommendations(final_text) is None or bad:
        seen_codes = [c for c in turn["seen"] if get_fabric(c)]
        hint = ("The recommendations block was missing." if bad is None
                else "Code %s does not exist." % bad)
        history.append({"role": "assistant", "content": final_text})
        history.append({"role": "user", "content":
                        "%s Reply again with exactly 3 real codes from your "
                        "tool results%s, same reply text, ending with the "
                        "```recommendations block." % (
                            hint, " (for example %s)" % ", ".join(
                                seen_codes[:5]) if seen_codes else "")})
        final_text = agent_turn(list(history), chat_fn, turn)
        recs, bad = valid_recommendations(
            extract_recommendations(final_text), turn["seen"]) \
            if extract_recommendations(final_text) is not None \
            else (None, None)

    recommendations = []
    if recs and not bad:
        recommendations = recs
    elif turn["seen"]:
        fallback = [c for c in dict.fromkeys(turn["seen"])
                    if get_fabric(c)][:3]
        recommendations = [
            {"code": c, "reason": ""} for c in fallback]

    reply = strip_block(final_text)
    if turn["relaxed"] and not mentioned_relaxation(reply):
        reply = (reply + "\n\n" + disclosure_note(
            turn["relaxed"], is_arabic(user_text))).strip()
    history.append({"role": "assistant", "content": final_text})

    result = {"reply": reply,
              "recommendations": enrich(recommendations)}
    if room_analysis is not None:
        result["room_analysis"] = room_analysis
    return result
