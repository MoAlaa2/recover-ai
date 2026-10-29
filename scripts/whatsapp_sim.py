"""Local WhatsApp simulator: fake Meta payloads -> app, print outbound.

No real sends (SEND/box recorder), no Graph network (media faked).
Consultant turns are LIVE (needs MODEL_API_KEY); swap is faked with a
local copy so the simulator burns no image-edit calls.
"""
import json
import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault("WA_TOKEN", "sim")
os.environ.setdefault("WA_PHONE_NUMBER_ID", "sim")
os.environ.setdefault("WA_APP_SECRET", "sim-secret")
os.environ.setdefault("WA_VERIFY_TOKEN", "sim-verify")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import BASE_DIR as APP_BASE  # noqa: E402
from app.core.config import UPLOAD_DIR  # noqa: E402
from app.main import app  # noqa: E402
from app.services import whatsapp as wa  # noqa: E402

SENT = []


def show(payload):
    kind = payload.get("type")
    if kind == "text":
        print("  OUT text: %s"
              % payload["text"]["body"][:220].replace("\n", " | "))
    elif kind == "image":
        print("  OUT image: id=%s caption=%s"
              % (payload["image"].get("id"),
                 (payload["image"].get("caption") or "")[:120]))
    elif kind == "interactive":
        inner = payload["interactive"]
        if inner.get("type") == "button":
            print("  OUT buttons: %s" % [
                b["reply"]["title"]
                for b in inner["action"]["buttons"]])
        else:
            rows = inner["action"]["sections"][0]["rows"]
            print("  OUT list: %s" % [r["title"] for r in rows])
    else:
        print("  OUT %s: %s" % (kind, json.dumps(payload)[:160]))


def main():
    for wid in ("15550000001", "15550000002"):
        try:
            os.remove(wa.session_path(wid))
        except OSError:
            pass
        wa.consultant_mod.SESSIONS.pop(wa.wa_session_id(wid), None)
    try:
        os.remove(wa.media_cache_path())
    except OSError:
        pass
    wa.SYNC_MODE = True
    wa.SEND_FN = lambda payload: SENT.append(payload) or {"ok": True}
    with open(os.path.join(APP_BASE, "data/samples/living.jpg"),
              "rb") as f:
        living = f.read()
    wa.DOWNLOAD_FN = lambda mid: living
    counter = [0]

    def fake_upload(path, mime="image/jpeg"):
        counter[0] += 1
        return "sim-media-%d" % counter[0]

    wa.upload_media = fake_upload

    import app.services.swap as swap_mod

    def fake_swap(room_path, code, target="sofa", **kwargs):
        out_dir = os.path.join(UPLOAD_DIR, "swap")
        os.makedirs(out_dir, exist_ok=True)
        src = (room_path if os.path.isabs(room_path)
               else os.path.join(APP_BASE, room_path))
        dest = os.path.join(out_dir, "sim-%s.jpg" % code)
        shutil.copy(src, dest)
        return {"result_url": os.path.join(
                    "uploads", "swap", "sim-%s.jpg" % code),
                "mask_url": "",
                "scores": {"color": 8, "pattern": 8, "scale": 8,
                           "isolation": 8},
                "attempts": 1}

    def fake_multi(room_path, assignments, **kwargs):
        results = []
        for item in assignments:
            res = fake_swap(room_path, item["code"],
                            item.get("target", "sofa"))
            results.append({"target": item.get("target", "sofa"),
                            "code": item["code"],
                            "result_url": res["result_url"],
                            "mask_url": "", "scores": res["scores"],
                            "attempts": 1, "cached": False})
        return {"results": results,
                "final_url": results[0]["result_url"]}

    swap_mod.swap = fake_swap
    swap_mod.swap_multi = fake_multi

    import app.services.voice as voice_mod
    voice_mod.transcribe = lambda path: {
        "text": "I need a washable fabric for my sofa"}

    client = TestClient(app)
    print("== challenge ==")
    resp = client.get("/webhook/whatsapp",
                      params={"hub.mode": "subscribe",
                              "hub.verify_token": "sim-verify",
                              "hub.challenge": "CHAL"})
    print("  challenge:", resp.status_code, resp.text[:20])

    import hmac
    import hashlib

    def post(mid, wa_id, kind, **kw):
        if kind == "text":
            msg = {"id": mid, "type": "text",
                   "text": {"body": kw["text"]}}
        elif kind == "image":
            msg = {"id": mid, "type": "image",
                   "image": {"id": "media-1",
                             "caption": kw.get("caption", "")}}
        elif kind == "audio":
            msg = {"id": mid, "type": "audio",
                   "audio": {"id": "aud-1"}}
        else:
            msg = {"id": mid, "type": "interactive",
                   "interactive": {"type": "button_reply",
                                   "button_reply": {"id": kw["pid"]}}}
        body = {"entry": [{"changes": [{"value": {
            "contacts": [{"wa_id": wa_id}],
            "messages": [msg]}}]}]}
        raw = json.dumps(body).encode("utf-8")
        sig = hmac.new(b"sim-secret", raw,
                       hashlib.sha256).hexdigest()
        resp = client.post(
            "/webhook/whatsapp", content=raw,
            headers={"X-Hub-Signature-256": "sha256=" + sig})
        assert resp.status_code == 200, resp.text
        return resp

    convo = [
        ("EN greeting", "15550000001", "text",
         {"text": "Hi, I need fabric for my sofa. I have kids and a cat."}),
        ("EN photo", "15550000001", "image", {}),
        ("EN all items", "15550000001", "text",
         {"text": "all of them, sofa and cushions"}),
        ("EN needs+recs", "15550000001", "text",
         {"text": "Warm beige, budget 150 per meter. Recommend 3 now."}),
        ("EN try-it button", "15550000001", "button",
         {"pid": "try:FA-AC-01"}),
        ("EN summary", "15550000001", "text", {"text": "summary"}),
        ("EN apply all", "15550000001", "text",
         {"text": "apply all"}),
        ("AR greeting", "15550000002", "text",
         {"text": "مرحبا، أبغى قماش للكنبة، عندي أطفال."}),
        ("AR photo", "15550000002", "image", {}),
        ("AR all", "15550000002", "text",
         {"text": "كلها، الكنبة والوسائد"}),
        ("AR recs", "15550000002", "text",
         {"text": "درجات بيج دافية. رشّح لي ٣ أقمشة الحين."}),
        ("AR voice", "15550000002", "audio", {}),
        ("AR chip tap", "15550000002", "button",
         {"pid": "chip:الكنبة فقط"}),
        ("AR new", "15550000002", "text", {"text": "جديد"}),
        ("language cmd", "15550000001", "text",
         {"text": "language"}),
    ]
    for label, wid, kind, kw in convo:
        print("== %s ==" % label)
        before = len(SENT)
        post("sim-%s" % label.replace(" ", "-"), wid, kind, **kw)
        for payload in SENT[before:]:
            show(payload)
        if len(SENT) == before:
            print("  OUT (none)")
    print("sent %d payloads total" % len(SENT))


if __name__ == "__main__":
    main()
