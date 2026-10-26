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
from app.services.catalog import (LANG_NAMES, PIECE_NAMES_AR,
                                  contains_egyptian, detect_piece,
                                  detect_user_lang, get_fabric, has_kids,
                                  has_pets, is_arabic, is_in_scope,
                                  is_light_unprotected,
                                  map_needs_to_features, needs_durable,
                                  search_catalog)

SESSIONS = {}
MAX_TOOL_ROUNDS = 6
MAX_RETRIES = 2

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

RECOMMENDATIONS: only when you have gathered enough and are ready to \
recommend, reply normally and end with one fenced block on its own lines:
```recommendations
[{"code": "FA-VL-01", "reason": "why in the user's language"}]
```
Exactly 3 items, codes only from tool results. On turns where you are still \
asking questions, do NOT include the block and give NO tip. If you are told \
a code was rejected, fix it with a real code from your tool results.

RELAXED CONSTRAINTS: if a tool result says constraints were relaxed, state \
plainly in your reply which constraint was relaxed (for example budget).

TIP: include one short professional tip (martindale for heavy use, \
fade-resistant for sunny rooms, washable for kids) only on turns where you \
give recommendations, never otherwise.

ROOM PHOTOS: describe what you see with the word "looks", never "sounds". \
In Arabic use تبدو / شكلها, never any hearing word.

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
                 and item["price_sar_per_m"] > max_price) else 0
    style_hit = len(set(wanted_styles) & set(item.get("styles", [])))
    if wanted_tone and item.get("tone") == wanted_tone:
        style_hit += 1
    return (-fit, snag, light, over, -style_hit,
            item["price_sar_per_m"])


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
    wanted = args.get("limit", 6) or 6
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
        protected=turn.get("protected", ()),
        pet_safe=turn.get("pet_safe", False),
        snag_levels=snag or None,
        min_martindale=mart)
    required = model_all + needs_all + model_any + needs_any
    summaries.sort(key=lambda s: rank_key(
        s, required, _as_list(args.get("styles")), args.get("tone"),
        args.get("max_price"), turn.get("has_kids", False)))
    return {"fabrics": summaries[:wanted],
            "relaxed_constraints": relaxed}


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


TIP_RE = re.compile(r"(?mi)^\s*(tip|تلميح|نصيحة)\s*[:：-].*$")


def strip_tip(text):
    """Remove tip lines. Used on turns without recommendations."""
    cleaned = TIP_RE.sub("", text or "")
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


RELAX_LABELS = {
    "max_price": ("budget", "الميزانية"),
    "features": ("features", "المواصفات"),
    "any_features": ("pet-friendly filter", "شرط مقاومة الحيوانات"),
    "snag_levels": ("claw-safe filter", "شرط تحمل المخالب"),
    "min_martindale": ("durability", "المتانة"),
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


def missing_relaxation(reply, relaxed, arabic):
    """Relaxed constraints the reply does not already name."""
    text = reply or ""
    lowered = text.lower()
    missing = []
    for key in relaxed:
        en, ar = RELAX_LABELS.get(key, (key, key))
        if en.lower() not in lowered and ar not in text:
            missing.append(key)
    return missing


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
        result = run_search(args or {}, turn)
        turn["seen"].extend(f["code"] for f in result["fabrics"])
        for name in result["relaxed_constraints"]:
            if name not in turn["relaxed"]:
                turn["relaxed"].append(name)
        return result
    if name == "get_fabric":
        code = (args or {}).get("code", "")
        item = get_fabric(code)
        if item and code not in turn["seen"]:
            turn["seen"].append(code)
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
    """Check exactly 3 grounded codes. Returns (recs, bad_code).

    Every code must exist and have come from a tool result this turn;
    memory-only picks are rejected the same way as invented codes.
    """
    if not isinstance(data, list) or len(data) != 3:
        return None, "want exactly 3"
    recs = []
    for entry in data:
        code = (entry or {}).get("code", "")
        if not get_fabric(code) or code not in (seen or []):
            return None, code
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
    return {"seen": [], "relaxed": [],
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


def confirm_piece_question(stated, detected, arabic):
    if arabic:
        return ("تأكيد سريع — ذكرت %s، لكن الصورة توضح %s بشكل أساسي. "
                "لأي قطعة تبغى التوصية؟"
                % (PIECE_NAMES_AR.get(stated, stated),
                   PIECE_NAMES_AR.get(detected, detected)))
    return ("Quick check — you mentioned your %s, but the photo mainly "
            "shows a %s. Which piece should I recommend for?"
            % (stated, detected))


def decline_reply(topic, arabic):
    """One-line polite decline with a steer back. No model call."""
    if arabic:
        base = "هذا خارج تخصصي، أنا هنا لأقمشتك وديكورك."
        if topic and topic in PIECE_NAMES_AR:
            return base + " نكمل على %s؟" % PIECE_NAMES_AR[topic]
        return base + " أساعدك بأي قماش اليوم؟"
    base = ("That's outside my expertise — I'm here for your fabrics "
            "and interiors.")
    if topic:
        return base + " Shall we continue with your %s?" % topic
    return base + " What fabric can I help you with?"


def chat(session_id, message, image_path=None, chat_fn=None):
    """One user turn. Returns {reply, recommendations, room_analysis?}."""
    session = SESSIONS.setdefault(session_id, {"messages": [],
                                               "detected_piece": None,
                                               "topic": None})
    history = session["messages"]
    if not image_path and not is_in_scope(message):
        arabic = is_arabic(message)
        reply = decline_reply(session.get("topic"), arabic)
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
    detected_lang = detect_user_lang(message)
    if detected_lang:
        session["lang"] = detected_lang
    reply_lang = session.get("lang", "en")
    user_text += "\n[Reply only in %s.]" % LANG_NAMES.get(reply_lang,
                                                         "English")
    turn = accumulate_context(session, turn_for(message))
    confirm = ""
    if image_path:
        path = image_path if os.path.isabs(image_path) else \
            os.path.join(BASE_DIR, image_path)
        if not os.path.exists(path):
            raise FileNotFoundError("image not found: %s" % image_path)
        room_analysis = analyze_room(image_path)
        user_text += "\n[Room photo analyzed: %s]" % json.dumps(
            room_analysis, ensure_ascii=False)
        needs_text = ", ".join(turn["needs_all"] + turn["needs_any"]) \
            or "none"
        user_text += "\nSuggested features from my needs: %s" % needs_text
        stated = detect_piece(message)
        detected = detect_piece((room_analysis or {}).get("furniture", ""))
        if stated and detected and stated != detected:
            session["detected_piece"] = detected
            confirm = confirm_piece_question(stated, detected,
                                             is_arabic(message))
    history.append({"role": "user", "content": user_text})
    final_text = agent_turn(list(history), chat_fn, turn)
    extracted = extract_recommendations(final_text)
    recs, bad = (None, None)
    if extracted is not None:
        recs, bad = valid_recommendations(extracted, turn["seen"])

    if bad:
        seen_codes = [c for c in turn["seen"] if get_fabric(c)]
        history.append({"role": "assistant", "content": final_text})
        history.append({"role": "user", "content":
                        "Code %s is not allowed: use only codes from your "
                        "tool results%s, same reply text, ending with the "
                        "```recommendations block."
                        % (bad, " (for example %s)" % ", ".join(
                            seen_codes[:5]) if seen_codes else "")})
        final_text = agent_turn(list(history), chat_fn, turn)
        extracted = extract_recommendations(final_text)
        if extracted is not None:
            recs, bad = valid_recommendations(extracted, turn["seen"])
        else:
            recs, bad = None, None

    recommendations = recs if (recs and not bad) else []

    reply = strip_block(final_text)
    if not recommendations:
        reply = strip_tip(reply)
    if confirm:
        reply = (reply + "\n\n" + confirm).strip()
    missing = missing_relaxation(reply, turn["relaxed"],
                                   is_arabic(user_text))
    if missing:
        reply = (reply + "\n\n" + disclosure_note(
            missing, is_arabic(user_text))).strip()
    who = ("kids" if turn.get("has_kids")
           else "pets" if turn.get("pet_safe") else None)
    if recommendations and who:
        note = light_color_note(recommendations, is_arabic(user_text),
                                who)
        if note and note not in reply:
            reply = (reply + "\n\n" + note).strip()
    history.append({"role": "assistant", "content": final_text})

    result = {"reply": reply,
              "recommendations": enrich(recommendations)}
    if room_analysis is not None:
        result["room_analysis"] = room_analysis
    return result
