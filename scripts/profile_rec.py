"""Profile ONE rec turn per language against the live model (read-only).

Usage: .venv/bin/python scripts/profile_rec.py en ar [--reps 2]
Clears CHAT_PERF log per turn; prints wall time, model-call count,
per-call seconds, tokens, tool events, recs. Needs MODEL_API_KEY.
"""
import json
import os
import sys
import time
import uuid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ["CHAT_PERF"] = "1"

from app.core.config import runtime_logs_dir  # noqa: E402
from app.services import consultant  # noqa: E402

PRIMES = {
    "en": "I need a pet-friendly velvet sofa fabric under 120 SAR per "
          "meter.",
    "ar": "أبغى قماش مخمل للكنبة مناسب للحيوانات تحت 120 ريال للمتر.",
    "hi": "मुझे सोफ़े के लिए पालतू-मित्रवत मखमल कपड़ा चाहिए, 120 SAR "
          "प्रति मीटर से कम।",
    "fr": "Je cherche un tissu en velours pour canapé, adapté aux "
          "animaux, moins de 120 SAR le mètre.",
    "es": "Busco una tela de terciopelo para el sofá, apta para "
          "mascotas, menos de 120 SAR el metro.",
}

MESSAGES = {
    "en": "Recommend 3 options now.",
    "ar": "رشح لي 3 خيارات الحين.",
    "hi": "अब 3 विकल्प सुझाएं।",
    "fr": "Recommandez 3 options maintenant.",
    "es": "Recomienda 3 opciones ahora.",
}

# Exact fallback rec requests from scripts/lang_e2e.py (needs + ask).
FALLBACK = {
    "en": "Warm beige, kids, budget 150 per meter. "
          "Recommend 3 fabrics now.",
    "ar": "درجات بيج دافية، عندي أطفال، الميزانية ١٥٠ للمتر. "
          "رشّح لي ٣ أقمشة الحين.",
    "hi": "गर्म बेज रंग, बच्चे हैं, बजट 150 प्रति मीटर। "
          "अभी 3 फ़ैब्रिक सुझाएँ।",
    "fr": "Beige chaud, enfants, budget 150 par mètre. "
          "Recommandez 3 tissus maintenant.",
    "es": "Beige cálido, niños, presupuesto 150 por metro. "
          "Recomienda 3 telas ahora.",
}


def perf_path():
    return os.path.join(runtime_logs_dir(), "chat_perf.jsonl")


def read_new(path, offset):
    events = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return events, offset
    for line in lines[offset:]:
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    return events, len(lines)


def one_turn(lang, image=None):
    sid = "prof-%s-%s" % (lang, uuid.uuid4().hex[:8])
    path = perf_path()
    measured_text = MESSAGES[lang]
    if image == "prime":
        img = os.path.join(BASE_DIR, "data", "samples", "living.jpg")
        consultant.ANALYSES.clear()
        consultant.chat(sid, PRIMES[lang], image_path=img,
                        lang=lang)  # photo prime, unmeasured
        image = None
        measured_text = (FALLBACK[lang] if "--e2e" in sys.argv
                         else MESSAGES[lang])
    else:
        consultant.chat(sid, PRIMES[lang], lang=lang)  # prime, unmeasured
        measured_text = MESSAGES[lang]
    try:
        with open(path, encoding="utf-8") as f:
            offset = len(f.readlines())
    except OSError:
        offset = 0
    t0 = time.time()
    if image:
        consultant.ANALYSES.clear()  # every rep pays vision like a new user
        res = consultant.chat(sid, measured_text, image_path=image,
                              lang=lang)
    else:
        res = consultant.chat(sid, measured_text, lang=lang)
    wall = time.time() - t0
    events, _ = read_new(path, offset)
    models = [e for e in events if e.get("kind") == "model"]
    tools = [e for e in events if e.get("kind") == "tool"]
    msecs = [e.get("seconds", 0) for e in models]
    prompt = sum(e.get("prompt_tokens") or 0 for e in models)
    compl = sum(e.get("completion_tokens") or 0 for e in models)
    return {
        "lang": lang,
        "wall_s": round(wall, 1),
        "model_calls": len(models),
        "model_s_total": round(sum(msecs), 1),
        "model_s_max": round(max(msecs) if msecs else 0, 1),
        "model_s_list": [round(s, 1) for s in msecs],
        "prompt_chars": [e.get("prompt_chars") for e in models],
        "prompt_tokens": prompt,
        "completion_tokens": compl,
        "tool_events": len(tools),
        "tool_names": [e.get("name") for e in tools],
        "recs": len(res.get("recommendations") or []),
        "reply_chars": len(res.get("reply") or ""),
        "attempts": [e.get("attempt") for e in models],
        "image": bool(image),
    }


def main():
    reps = 2
    skip_next = False
    langs = []
    for a in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if a == "--reps":
            skip_next = True
            try:
                reps = int(sys.argv[sys.argv.index(a) + 1])
            except (ValueError, IndexError):
                pass
            continue
        if a.startswith("--"):
            continue
        langs.append(a)
    out = []
    image = None
    if "--image" in sys.argv:
        image = os.path.join(BASE_DIR, "data", "samples", "living.jpg")
    elif "--photo-prime" in sys.argv:
        image = "prime"
    for lang in langs:
        if lang not in MESSAGES:
            print("unknown lang %s" % lang)
            continue
        for r in range(reps):
            try:
                row = one_turn(lang, image=image)
            except Exception as exc:  # noqa: BLE001 - report, continue
                row = {"lang": lang, "error": "%s: %s" % (
                    type(exc).__name__, str(exc)[:200])}
            print(json.dumps(row, ensure_ascii=False), flush=True)
            out.append(row)
            time.sleep(2)
    with open(os.path.join(BASE_DIR, "uploads", "logs",
                           "rec_profile.jsonl"), "a",
              encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
