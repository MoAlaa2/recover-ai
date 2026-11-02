"""WhatsApp Cloud API bot reusing the web pipeline.

Same consultant, catalog, swap, voice and meterage services — no
duplicated logic. Disabled unless the WA_* env vars are present (modal
secret "recover-whatsapp"); without them the webhook answers 404 and
nothing is sent anywhere.
"""
import contextvars
import hashlib
import hmac
import json
import os
import threading
import time
import traceback
import uuid

import httpx

from app.core.config import BASE_DIR, PRIVATE_DIR, UPLOAD_DIR
from app.services import consultant as consultant_mod

GRAPH_VERSION = "v21.0"
TEXT_LIMIT = 4096
BUTTON_TITLE_LIMIT = 20
LIST_ROW_LIMIT = 10
INTERACTIVE_BODY_LIMIT = 1024
SESSION_TTL_S = 24 * 3600
MAX_SEEN_IDS = 200


def wa_env():
    """WA_* settings. Empty values mean the bot is not configured."""
    return {
        "token": os.environ.get("WA_TOKEN", ""),
        "phone_id": os.environ.get("WA_PHONE_NUMBER_ID", ""),
        "app_secret": os.environ.get("WA_APP_SECRET", ""),
        "verify_token": os.environ.get("WA_VERIFY_TOKEN", ""),
    }


def configured():
    env = wa_env()
    return all(env.values())


def sessions_dir():
    """Private sessions dir, outside the served uploads/ mount."""
    path = os.path.join(PRIVATE_DIR, "wa_sessions")
    os.makedirs(path, exist_ok=True)
    return path


def session_path(wa_id):
    safe = "".join(c if c.isalnum() else "_" for c in wa_id or "")
    return os.path.join(sessions_dir(), safe + ".json")


def load_wa_session(wa_id):
    """Persisted session or {}. Expired (>24h) files start fresh."""
    try:
        with open(session_path(wa_id), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if time.time() - data.get("saved_at", 0) > SESSION_TTL_S:
        return {}
    data.pop("saved_at", None)
    return data if isinstance(data, dict) else {}


def save_wa_session(wa_id, session):
    try:
        payload = dict(session or {})
        payload["saved_at"] = time.time()
        with open(session_path(wa_id), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except OSError:
        pass


def verify_signature(raw_body, header):
    """HMAC-SHA256 check of X-Hub-Signature-256. Constant time."""
    secret = wa_env()["app_secret"]
    if not secret or not header:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body or b"",
                      "sha256").hexdigest()
    return hmac.compare_digest("sha256=" + digest, header or "")


def parse_webhook(body):
    """Yield (wa_id, message) for each inbound message.

    message has kind text/image/audio/interactive plus its payload.
    Unknown shapes are skipped (never crash a webhook).
    """
    out = []
    try:
        entries = body.get("entry", [])
    except AttributeError:
        return out
    for entry in entries or []:
        for change in (entry or {}).get("changes", []) or []:
            value = (change or {}).get("value", {}) or {}
            contacts = value.get("contacts", []) or []
            wa_id = (contacts[0].get("wa_id", "")
                     if contacts else "")
            # The business number this message arrived on; replies go
            # back out FROM it (multi-number WABAs).
            via = ((value.get("metadata", {}) or {})
                   .get("phone_number_id", ""))
            for msg in value.get("messages", []) or []:
                kind = (msg or {}).get("type", "")
                mid = (msg or {}).get("id", "")
                if kind == "text":
                    out.append((wa_id, {
                        "kind": "text", "id": mid, "via": via,
                        "text": ((msg.get("text") or {}).get("body")
                                 or "")}))
                elif kind == "image":
                    out.append((wa_id, {
                        "kind": "image", "id": mid, "via": via,
                        "media_id": (msg.get("image") or {}).get("id",
                                                                 ""),
                        "caption": ((msg.get("image") or {}).get(
                            "caption") or "")}))
                elif kind == "audio":
                    out.append((wa_id, {
                        "kind": "audio", "id": mid, "via": via,
                        "media_id": (msg.get("audio") or {}).get("id",
                                                                 "")}))
                elif kind == "interactive":
                    inter = msg.get("interactive") or {}
                    payload = ""
                    if inter.get("type") == "button_reply":
                        payload = ((inter.get("button_reply") or {})
                                   .get("id") or "")
                    elif inter.get("type") == "list_reply":
                        payload = ((inter.get("list_reply") or {})
                                   .get("id") or "")
                    out.append((wa_id, {"kind": "interactive",
                                        "id": mid, "via": via,
                                        "payload": payload}))
    return [(w, m) for w, m in out if w and m.get("id")]


# Outbound sender: replaced by a recorder in tests and the simulator.
SEND_FN = None


def _wa_tag(wa_id):
    """Short non-PII correlation tag (never the phone number)."""
    return hashlib.sha256(
        (wa_id or "").encode("utf-8")).hexdigest()[:8]


def log_wa(event, wa_id="", **fields):
    """One JSON log line to stdout (Modal captures it). Never logs token."""
    record = {"wa": _wa_tag(wa_id), "event": event}
    record.update(fields)
    try:
        print(json.dumps(record, ensure_ascii=False), flush=True)
    except Exception:  # noqa: BLE001 - logging never crashes the bot
        pass


def apology_text(wa_id):
    session = consultant_mod.SESSIONS.get(wa_session_id(wa_id), {})
    if (session.get("lang") or "en") == "ar":
        return "عذرا، حصل خطأ — حاول مرة ثانية."
    return "Sorry, something went wrong — please try again."


def media_failed_text(wa_id, kind):
    """Short friendly retry line, localized. Never carries raw errors."""
    session = consultant_mod.SESSIONS.get(wa_session_id(wa_id), {})
    arabic = (session.get("lang") or "en") == "ar"
    if kind == "audio":
        if arabic:
            return ("عذرا، ما قدرت أفتح رسالتك الصوتية — "
                    "ممكن ترسلها مرة ثانية؟")
        return ("Sorry, I couldn't open that voice note — "
                "could you send it again?")
    if arabic:
        return "عذرا، ما قدرت أفتح الصورة — ممكن ترسلها مرة ثانية؟"
    return "Sorry, I couldn't open that photo — could you send it again?"


def send_apology(wa_id):
    """Last-resort short text reply. Logs instead of raising."""
    try:
        send_payload(text_payload(wa_id, apology_text(wa_id)))
    except Exception as exc:  # noqa: BLE001 - nothing left to try
        log_wa("apology_failed", wa_id, error=str(exc)[:500])


def graph_url(path):
    return ("https://graph.facebook.com/%s/%s%s"
            % (GRAPH_VERSION, _send_phone_id(), path))


# Phone number the current message arrived on (metadata.phone_number_id).
# Replies must go out FROM that number; the env default is only a fallback
# when the webhook carried no metadata (simulator, old payloads).
_send_phone_ctx = contextvars.ContextVar("wa_send_phone_id", default="")


def _send_phone_id():
    """Sender number for this message, else WA_PHONE_NUMBER_ID."""
    return _send_phone_ctx.get() or wa_env()["phone_id"]


def _post_graph(path, payload, files=None):
    env = wa_env()
    headers = {"Authorization": "Bearer " + env["token"]}
    with httpx.Client(timeout=60) as client:
        if files:
            resp = client.post(graph_url(path), headers=headers,
                               data=payload, files=files)
        else:
            resp = client.post(graph_url(path), headers=headers,
                               json=payload)
    try:
        resp.raise_for_status()
    except Exception as exc:
        # Status + Graph error body, never the token or headers.
        log_wa("graph_error", (payload or {}).get("to", ""),
               path=path, status=getattr(resp, "status_code", "?"),
               body=(getattr(resp, "text", "") or "")[:2000],
               error="%s: %s" % (type(exc).__name__, exc))
        raise
    log_wa("graph_ok", (payload or {}).get("to", ""),
           path=path, status=getattr(resp, "status_code", "?"))
    return resp.json()


def send_payload(payload):
    """POST one /messages payload. Returns the Graph response."""
    if SEND_FN is not None:
        return SEND_FN(payload)
    return _post_graph("/messages", dict(payload,
                                         messaging_product="whatsapp"))


def split_text(text, limit=TEXT_LIMIT):
    """Split long prose into sendable chunks (never drop words)."""
    words, chunks, current = (text or "").split(), [], ""
    for word in words:
        piece = (current + " " + word).strip()
        if len(piece) > limit and current:
            chunks.append(current)
            current = word
        else:
            current = piece[:limit] if len(piece) <= limit else word
    if current:
        chunks.append(current)
    return chunks or [""]


def text_payload(to, body):
    return {"messaging_product": "whatsapp", "to": to,
            "type": "text", "text": {"body": body, "preview_url": False}}


def buttons_payload(to, body, buttons):
    """Reply buttons: max 3, titles capped at 20 chars."""
    trimmed = [{"id": b["id"][:256],
                "title": b["title"][:BUTTON_TITLE_LIMIT]}
               for b in buttons[:3]]
    return {"messaging_product": "whatsapp", "to": to, "type":
            "interactive", "interactive": {
                "type": "button",
                "body": {"text": body[:1024]},
                "action": {"buttons": [
                    {"type": "reply",
                     "reply": {"id": b["id"], "title": b["title"]}}
                    for b in trimmed]}}}


def list_payload(to, body, button_text, rows):
    """List message: up to 10 rows, titles capped at 24 chars."""
    trimmed = [{"id": r["id"][:200], "title": r["title"][:24],
                "description": (r.get("description") or "")[:72]}
               for r in rows[:LIST_ROW_LIMIT]]
    return {"messaging_product": "whatsapp", "to": to, "type":
            "interactive", "interactive": {
                "type": "list",
                "body": {"text": body[:1024]},
                "action": {"button": button_text[:20],
                           "sections": [{"title": button_text[:24],
                                         "rows": trimmed}]}}}


def image_payload(to, media_id=None, link=None, caption=""):
    image = {}
    if media_id:
        image["id"] = media_id
    elif link:
        image["link"] = link
    if caption:
        image["caption"] = caption[:1024]
    return {"messaging_product": "whatsapp", "to": to, "type": "image",
            "image": image}


def upload_media(path, mime="image/jpeg"):
    """Upload a local file, returns the Graph media id."""
    env = wa_env()
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f, mime)}
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                graph_url("/media"),
                headers={"Authorization": "Bearer " + env["token"]},
                data={"messaging_product": "whatsapp"}, files=files)
    resp.raise_for_status()
    return resp.json().get("id", "")


def media_cache_path():
    return os.path.join(sessions_dir(), "media_cache.json")


def cached_media_id(key):
    try:
        with open(media_cache_path(), encoding="utf-8") as f:
            return json.load(f).get(key, "")
    except (OSError, ValueError):
        return ""


def store_media_id(key, media_id):
    try:
        try:
            with open(media_cache_path(), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        data[key] = media_id
        with open(media_cache_path(), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def send_typing(wa_id):
    try:
        send_payload({"messaging_product": "whatsapp", "to": wa_id,
                      "type": "text",
                      "text": {"body": "…", "preview_url": False},
                      "sender_action": "typing"})
    except Exception:  # noqa: BLE001 - typing is best-effort
        pass


def media_object_url(media_id):
    """Graph media node URL. The media id is global: the sender phone
    number id must NOT appear in this path (it 400s)."""
    return "https://graph.facebook.com/%s/%s" % (GRAPH_VERSION,
                                                 media_id)


def download_media_bytes(media_id):
    """Graph media object -> raw bytes. Raises on failure."""
    env = wa_env()
    headers = {"Authorization": "Bearer " + env["token"]}
    with httpx.Client(timeout=60) as client:
        meta = client.get(media_object_url(media_id),
                          headers=headers)
        meta.raise_for_status()
        url = meta.json().get("url", "")
        if not url:
            raise RuntimeError("no media url")
        blob = client.get(url, headers=headers)
        blob.raise_for_status()
        return blob.content


DOWNLOAD_FN = None


def fetch_media(media_id):
    if DOWNLOAD_FN is not None:
        return DOWNLOAD_FN(media_id)
    return download_media_bytes(media_id)


def wa_session_id(wa_id):
    return "wa:" + (wa_id or "")


def restore_session(wa_id):
    """Bridge in-memory consultant state with the Volume copy."""
    sid = wa_session_id(wa_id)
    if sid not in consultant_mod.SESSIONS:
        saved = load_wa_session(wa_id)
        if saved:
            session = consultant_mod.SESSIONS.setdefault(
                sid, {"messages": []})
            session.update(saved)
    return consultant_mod.SESSIONS.setdefault(sid, {"messages": []})


def persist_session(wa_id):
    session = consultant_mod.SESSIONS.get(wa_session_id(wa_id), {})
    keep = {k: session.get(k) for k in (
        "messages", "lang", "detected_piece", "topic",
        "available_targets", "chosen_targets", "assignments",
        "curtain_dims", "pillow_counts", "image_path", "seen_ids")}
    save_wa_session(wa_id, keep)


def mark_seen(session, mid):
    seen = session.setdefault("seen_ids", [])
    if mid in seen:
        return False
    seen.append(mid)
    del seen[:-MAX_SEEN_IDS]
    return True


def reset_wa(wa_id):
    consultant_mod.SESSIONS.pop(wa_session_id(wa_id), None)
    try:
        os.remove(session_path(wa_id))
    except OSError:
        pass


LANG_NAMES = {"en": "English", "ar": "العربية", "hi": "हिन्दी",
              "fr": "Français", "es": "Español"}

NEW_WORDS = ("new", "جديد", "reset", "start over", "ابدأ من جديد")
LANG_WORDS = ("language", "اللغة", "langue", "idioma", "lang")
SUMMARY_WORDS = ("summary", "ملخص", "résumé", "resumen")
APPLY_ALL_WORDS = ("apply all", "طبق", "apply them all", "طبق الكل")


def is_command(text, words):
    low = (text or "").strip().lower()
    return any(low == w or low.startswith(w + " ") for w in words)


def options_message(wa_id, reply, options, force_list=False):
    """Options as reply buttons (<=3 short) or a list (<=10 rows)."""
    options = [o for o in (options or []) if o][:LIST_ROW_LIMIT]
    if not options:
        return
    if (not force_list and len(options) <= 3
            and all(len(o) <= BUTTON_TITLE_LIMIT for o in options)):
        send_payload(buttons_payload(
            wa_id, reply or "…",
            [{"id": "chip:" + o, "title": o} for o in options]))
        return
    send_payload(list_payload(
        wa_id, reply or "…", options[0][:20],
        [{"id": "chip:" + o, "title": o,
          "description": ""} for o in options]))


def rec_caption(rec, lang):
    """One fabric caption: name, code, price, why + receipts."""
    if lang == "ar":
        name = rec.get("name_ar") or rec.get("name_en") or ""
    else:
        name = rec.get("name_en") or rec.get("name_ar") or ""
    lines = ["*%s*" % name,
             "%s · $%s/m" % (rec.get("code", ""),
                                rec.get("price_usd_per_m", ""))]
    if rec.get("reason"):
        lines.append(rec["reason"])
    matched = rec.get("matched") or []
    if matched:
        lines.append("✓ " + ", ".join(matched))
    return "\n".join(lines)[:1024]


def swatch_media_id(code, image_rel):
    """Catalog swatch file -> Graph media id (cached per code)."""
    key = "swatch:" + code
    cached = cached_media_id(key)
    if cached:
        return cached
    path = image_rel if os.path.isabs(image_rel) else os.path.join(
        BASE_DIR, (image_rel or "").lstrip("/"))
    media_id = upload_media(path)
    if media_id:
        store_media_id(key, media_id)
    return media_id


def send_recommendations(wa_id, recs, lang):
    """One image message per fabric, then Try-it buttons."""
    for rec in recs or []:
        media_id = ""
        try:
            media_id = swatch_media_id(rec.get("code", ""),
                                       rec.get("image", ""))
        except Exception:  # noqa: BLE001 - fall back to text
            media_id = ""
        caption = rec_caption(rec, lang)
        if media_id:
            send_payload(image_payload(wa_id, media_id=media_id,
                                       caption=caption))
        else:
            send_payload(text_payload(wa_id, caption))
    codes = [r.get("code", "") for r in recs or [] if r.get("code")]
    if codes:
        send_payload(buttons_payload(
            wa_id, "Try it" if lang != "ar" else "جرّبه",
            [{"id": "try:" + c, "title": ("Try " + c)[:20]}
             for c in codes[:3]]))


def summary_text(wa_id, lang):
    """Forwardable handoff block: items, meters, price, total, CO2."""
    from app.services import catalog as catalog_mod
    from app.services import impact as impact_mod
    from app.services import meterage as meterage_mod
    from app.services.money import format_money as money
    session = consultant_mod.SESSIONS.get(wa_session_id(wa_id), {})
    assignments = session.get("assignments", {})
    fabrics = {}
    for code in set((assignments or {}).values()):
        item = catalog_mod.get_fabric(code)
        if item:
            fabrics[code] = item
    res = meterage_mod.quote(assignments, fabrics,
                             session.get("curtain_dims"),
                             session.get("pillow_counts", {}))
    if lang == "ar":
        lines = ["اختيارات ReCover لغرفتك:"]
    else:
        lines = ["Your ReCover picks:"]
    for item in res["items"]:
        if lang == "ar":
            name = item["fabric_name_ar"] or item["fabric_name_en"]
        else:
            name = item["fabric_name_en"] or item["fabric_name_ar"]
        if item["meters"] is None:
            lines.append("• %s → %s (%s): %s" % (
                item["target"], name, item["code"],
                "needs measurements" if lang != "ar" else
                "يحتاج مقاسات"))
        else:
            lines.append("• %s → %s (%s): %s m × %s = %s" % (
                item["target"], name, item["code"], item["meters"],
                money(item["price_usd_per_m"], lang),
                money(item["line_total"], lang)))
    if lang == "ar":
        lines.append("الإجمالي (تقدير مبدئي): %s" % money(res["total"], lang))
        lines.append("تقدير مبدئي — المقاس النهائي من المنجّد.")
    else:
        lines.append("Total (preliminary estimate): %s"
                     % money(res["total"], lang))
        lines.append("Preliminary estimate — your upholsterer will "
                     "measure.")
    co2, waste = impact_mod.avoided(assignments)
    if co2 > 0:
        if lang == "ar":
            lines.append("تتجنّب ≈%s كغ CO₂e (%s)." % (co2,
                                                     impact_mod
                                                     .CO2_SOURCE))
        else:
            lines.append("Avoids ≈%s kg CO₂e (%s)." % (
                co2, impact_mod.CO2_SOURCE))
    return "\n".join(lines)


def run_try_swap(wa_id, code, target=""):
    """Execute one fabric swap and send the result as an image."""
    from app.services import swap as swap_mod
    session = consultant_mod.SESSIONS.get(wa_session_id(wa_id), {})
    image_path = session.get("image_path", "")
    if not image_path:
        ask = ("Please share a room photo first — send a photo or "
               "pick a sample room on the web demo.")
        if (session.get("lang") or "en") == "ar":
            ask = ("ارسل صورة غرفتك أول — صورة مباشرة من جوالك.")
        send_payload(text_payload(wa_id, ask))
        return
    if not target or target not in swap_mod.TARGET_CONCEPTS:
        target = "sofa"
    send_typing(wa_id)
    lang = session.get("lang") or "en"
    try:
        res = swap_mod.swap(image_path, code, target)
    except swap_mod.CheckFailed as exc:
        # Honest: the fabric was NOT applied; say which item and why,
        # and never record it as a pick.
        send_payload(text_payload(wa_id, not_applied_text(
            target, code, exc.reason, lang)))
        return
    except swap_mod.SwapError as exc:
        send_payload(text_payload(wa_id, str(exc)))
        return
    except RuntimeError as exc:
        send_payload(text_payload(wa_id, str(exc)))
        return
    try:
        path = (res["result_url"] if os.path.isabs(
            res.get("result_url", "")) else os.path.join(
                BASE_DIR, (res.get("result_url") or "").lstrip("/")))
        media_id = upload_media(path)
    except Exception as exc:  # noqa: BLE001 - fall back to text below
        log_wa("media_upload_error", wa_id, kind="try_swap", code=code,
               error="%s: %s" % (type(exc).__name__, exc))
        media_id = ""
    checks = res.get("checks") or {}
    score = min((res.get("scores") or {}).values() or [0])
    if lang == "ar":
        caption = "قبل ← بعد · %s → %s · تطابق %s/10" % (
            TARGET_WORDS_AR.get(target, target), code, score)
    else:
        caption = "Before → after · %s → %s · match %s/10" % (
            target, code, score)
    if checks.get("delta_e") is not None:
        caption += " · ΔE %s" % checks["delta_e"]
    if media_id:
        send_payload(image_payload(wa_id, media_id=media_id,
                                   caption=caption))
    else:
        # The swap ran but the photo cannot be delivered: say so
        # instead of going silent.
        send_payload(text_payload(wa_id, apology_text(wa_id)))
    session.setdefault("assignments", {})[target] = code
    persist_session(wa_id)


def send_turn_result(wa_id, out):
    """Map one consultant turn onto WhatsApp messages."""
    session = consultant_mod.SESSIONS.get(wa_session_id(wa_id), {})
    lang = session.get("lang") or out.get("detected_lang") or "en"
    reply = out.get("reply", "")
    options = out.get("options", [])
    recs = out.get("recommendations", [])
    targets = out.get("targets", {})
    # The reply travels once: inside the buttons/list message when
    # there are options (an interactive body holds 1024 chars), as
    # plain text otherwise. Sending both showed every reply twice.
    inline = bool(options and not recs
                  and len(reply or "") <= INTERACTIVE_BODY_LIMIT)
    if not inline:
        for chunk in split_text(reply):
            if chunk.strip():
                send_payload(text_payload(wa_id, chunk))
    if recs:
        send_recommendations(wa_id, recs, lang)
    elif options:
        force_list = bool(targets.get("available")
                          and not targets.get("chosen"))
        body = reply if inline else (
            "اختر:" if lang == "ar" else "Choose:")
        options_message(wa_id, body, options, force_list=force_list)
    preview = out.get("preview") or {}
    if preview.get("code"):
        run_try_swap(wa_id, preview["code"],
                     preview.get("target", ""))


def handle_text(wa_id, text):
    session = restore_session(wa_id)
    if is_command(text, NEW_WORDS):
        reset_wa(wa_id)
        ok = ("Fresh start — send a room photo and tell me what "
              "your home needs.")
        if (session.get("lang") or "en") == "ar":
            ok = "بداية جديدة — ارسل صورة غرفتك وقل وش يحتاج بيتك."
        send_payload(text_payload(wa_id, ok))
        return
    if is_command(text, LANG_WORDS):
        options_message(
            wa_id,
            "Pick your language — اختر لغتك",
            ["English", "العربية"],
            force_list=False)
        return
    low = (text or "").strip().lower()
    if low in ("english", "العربية"):
        code = "ar" if low != "english" else "en"
        session["lang"] = code
        persist_session(wa_id)
        confirm = ("Language set to English." if code == "en"
                   else "تم، أكلمك بالعربية من الحين.")
        send_payload(text_payload(wa_id, confirm))
        return
    if is_command(text, SUMMARY_WORDS):
        send_payload(text_payload(
            wa_id, summary_text(wa_id, session.get("lang") or "en")))
        return
    if is_command(text, APPLY_ALL_WORDS):
        run_apply_all(wa_id)
        return
    try:
        out = consultant_mod.chat(wa_session_id(wa_id), text or "")
    except Exception as exc:  # noqa: BLE001 - apologize, never silent
        log_wa("consultant_error", wa_id, kind="text",
               error="%s: %s" % (type(exc).__name__, exc),
               traceback=traceback.format_exc()[-4000:])
        send_apology(wa_id)
        return
    persist_session(wa_id)
    try:
        send_turn_result(wa_id, out)
    except Exception as exc:  # noqa: BLE001 - send/media failed
        log_wa("send_error", wa_id, kind="text",
               error="%s: %s" % (type(exc).__name__, exc),
               traceback=traceback.format_exc()[-4000:])
        send_apology(wa_id)


def handle_image(wa_id, media_id, caption=""):
    restore_session(wa_id)
    try:
        raw = fetch_media(media_id)
    except Exception as exc:  # noqa: BLE001 - friendly line, log details
        log_wa("media_fetch_error", wa_id, kind="image",
               error="%s: %s" % (type(exc).__name__, exc),
               traceback=traceback.format_exc()[-4000:])
        send_payload(text_payload(wa_id, media_failed_text(wa_id,
                                                           "image")))
        return
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # Unique per message: a shared pid-named file lets one user's
    # photo leak into another user's turn under concurrency.
    tmp = os.path.join(UPLOAD_DIR, "wa-in-%s.bin" % uuid.uuid4().hex)
    with open(tmp, "wb") as f:
        f.write(raw)
    dest = os.path.join(UPLOAD_DIR, "wa-%s.jpg" % mid_tag(media_id))
    try:
        from app.api.chat import convert_to_jpg
        ok = convert_to_jpg(tmp, dest)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if not ok:
        send_payload(text_payload(
            wa_id, "I couldn't read that image. Please send a JPG "
                   "or PNG photo."))
        return
    rel = os.path.join("uploads", os.path.basename(dest))
    try:
        out = consultant_mod.chat(wa_session_id(wa_id), caption or "", rel)
    except Exception as exc:  # noqa: BLE001 - apologize, never silent
        log_wa("consultant_error", wa_id, kind="image",
               error="%s: %s" % (type(exc).__name__, exc),
               traceback=traceback.format_exc()[-4000:])
        send_apology(wa_id)
        return
    persist_session(wa_id)
    try:
        send_turn_result(wa_id, out)
    except Exception as exc:  # noqa: BLE001 - send/media failed
        log_wa("send_error", wa_id, kind="image",
               error="%s: %s" % (type(exc).__name__, exc),
               traceback=traceback.format_exc()[-4000:])
        send_apology(wa_id)


def mid_tag(media_id):
    return hashlib.sha256(
        (media_id or "").encode("utf-8")).hexdigest()[:12]


def handle_audio(wa_id, media_id):
    restore_session(wa_id)
    try:
        raw = fetch_media(media_id)
    except Exception as exc:  # noqa: BLE001 - friendly line, log details
        log_wa("media_fetch_error", wa_id, kind="audio",
               error="%s: %s" % (type(exc).__name__, exc),
               traceback=traceback.format_exc()[-4000:])
        send_payload(text_payload(wa_id, media_failed_text(wa_id,
                                                           "audio")))
        return
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    tmp = os.path.join(UPLOAD_DIR, "wa-au-%s.ogg" % uuid.uuid4().hex)
    with open(tmp, "wb") as f:
        f.write(raw)
    try:
        from app.services import voice as voice_mod
        text = voice_mod.transcribe(tmp)["text"].strip()
    except Exception as exc:  # noqa: BLE001 - friendly line, log details
        log_wa("media_fetch_error", wa_id, kind="transcribe",
               error="%s: %s" % (type(exc).__name__, exc),
               traceback=traceback.format_exc()[-4000:])
        send_payload(text_payload(wa_id, media_failed_text(wa_id,
                                                           "audio")))
        return
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if not text:
        send_payload(text_payload(wa_id, "No speech detected — please "
                                        "try again."))
        return
    handle_text(wa_id, text)


def handle_interactive(wa_id, payload):
    restore_session(wa_id)
    if not payload:
        return
    if payload.startswith("chip:"):
        handle_text(wa_id, payload[len("chip:"):])
        return
    if payload.startswith("try:"):
        session = consultant_mod.SESSIONS.get(wa_session_id(wa_id),
                                             {})
        targets = (session.get("chosen_targets", []) or ["sofa"])
        run_try_swap(wa_id, payload[len("try:"):], targets[0])
        return
    if payload.startswith("lang:"):
        handle_text(wa_id, payload[len("lang:"):])
        return


TARGET_WORDS_AR = {"sofa": "الكنبة", "cushions": "الوسائد",
                   "curtains": "الستائر", "armchair": "الكرسي"}
REASON_AR = {"colour mismatch": "اللون ما طابق",
             "low coverage": "القماش ما غطّى القطعة كاملة"}


def not_applied_text(target, code, reason, lang):
    if lang == "ar":
        return "%s · %s — ما تركّب (%s). جرّب مرة ثانية أو اختر قماش " \
               "ثاني." % (TARGET_WORDS_AR.get(target, target), code,
                          REASON_AR.get(reason, reason))
    return "%s · %s — not applied (%s). Try again or pick another " \
           "fabric." % (target, code, reason)


def run_apply_all(wa_id):
    """Multi-swap every assignment, then the summary block."""
    from app.services import swap as swap_mod
    session = consultant_mod.SESSIONS.get(wa_session_id(wa_id), {})
    assignments = session.get("assignments", {})
    image_path = session.get("image_path", "")
    lang = session.get("lang") or "en"
    if not assignments or not image_path:
        send_payload(text_payload(
            wa_id, "Nothing assigned yet — pick fabrics first." if
            lang != "ar" else "لسه ما اخترت شيء — اختر الأقمشة أول."))
        return
    send_typing(wa_id)
    cleaned = [{"target": t, "code": c}
               for t, c in assignments.items()]
    try:
        res = swap_mod.swap_multi(image_path, cleaned)
    except (swap_mod.SwapError, RuntimeError) as exc:
        send_payload(text_payload(wa_id, str(exc)))
        return
    try:
        path = os.path.join(BASE_DIR, (res.get("final_url") or "")
                            .lstrip("/"))
        media_id = upload_media(path)
    except Exception:  # noqa: BLE001 - degraded image send
        media_id = ""
    applied = res.get("results", [])
    skipped = res.get("skipped", []) or []
    # Only applied items stay as picks; a skipped one is not a result.
    for item in skipped:
        session.get("assignments", {}).pop(item.get("target"), None)
    persist_session(wa_id)
    if media_id:
        send_payload(image_payload(wa_id, media_id=media_id,
                                   caption=apply_caption(applied, skipped,
                                                         lang)))
    elif skipped:
        send_payload(text_payload(wa_id, apply_caption(applied, skipped,
                                                       lang)))
    send_payload(text_payload(wa_id, summary_text(wa_id, lang)))


def apply_caption(applied, skipped, lang):
    """Caption listing only applied items (each with its own score),
    then the items that were not applied and why."""
    lines = []
    for r in applied:
        score = min((r.get("scores") or {}).values() or [0])
        tgt = TARGET_WORDS_AR.get(r["target"], r["target"]) \
            if lang == "ar" else r["target"]
        if lang == "ar":
            lines.append("✓ %s → %s · تطابق %s/10" % (tgt, r["code"],
                                                   score))
        else:
            lines.append("✓ %s → %s · match %s/10" % (tgt, r["code"],
                                                   score))
    for item in skipped:
        reason = item.get("reason", "")
        tgt = item.get("target", "")
        if lang == "ar":
            lines.append("✗ %s · %s — ما تركّب (%s)" % (
                TARGET_WORDS_AR.get(tgt, tgt), item.get("code", ""),
                REASON_AR.get(reason, reason)))
        else:
            lines.append("✗ %s · %s — not applied (%s)" % (
                tgt, item.get("code", ""), reason))
    return "\n".join(lines)[:1024]


def process_message(wa_id, message):
    """One inbound message -> outbound payloads. Idempotent."""
    if not configured():
        return
    # Reply FROM the number the message arrived on; env is the fallback.
    via = message.get("via") or ""
    token = _send_phone_ctx.set(via)
    try:
        log_wa("inbound", wa_id, kind=message.get("kind", ""),
               via=via or "env-fallback")
        session = restore_session(wa_id)
        if not mark_seen(session, message.get("id", "")):
            return
        persist_session(wa_id)
        kind = message.get("kind", "")
        try:
            if kind == "text":
                handle_text(wa_id, message.get("text", ""))
            elif kind == "image":
                handle_image(wa_id, message.get("media_id", ""),
                             message.get("caption", ""))
            elif kind == "audio":
                handle_audio(wa_id, message.get("media_id", ""))
            elif kind == "interactive":
                handle_interactive(wa_id, message.get("payload", ""))
        except Exception as exc:  # noqa: BLE001 - webhook never crashes
            log_wa("process_error", wa_id, kind=kind,
                   error="%s: %s" % (type(exc).__name__, exc),
                   traceback=traceback.format_exc()[-4000:])
            send_apology(wa_id)
    finally:
        _send_phone_ctx.reset(token)


_WORKERS = []
SYNC_MODE = False


def dispatch(wa_id, message):
    """Return 200 fast; work happens in a background thread."""
    if SYNC_MODE:
        process_message(wa_id, message)
        return
    worker = threading.Thread(target=process_message,
                              args=(wa_id, message), daemon=True)
    _WORKERS.append(worker)
    _WORKERS[:] = [w for w in _WORKERS if w.is_alive()]
    worker.start()


def join_workers(timeout=120):
    for worker in list(_WORKERS):
        worker.join(timeout=max(1, timeout / max(1, len(_WORKERS))))
    _WORKERS[:] = [w for w in _WORKERS if w.is_alive()]
