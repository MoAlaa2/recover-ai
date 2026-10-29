"""Simulated full WhatsApp conversation against the DEPLOYED webhook.

Runs on Modal with the recover-whatsapp secret (signing only; the
secret never leaves Modal). Posts HMAC-signed fake-Meta payloads to
the deployed /webhook/whatsapp for a NONEXISTENT wa_id, so Graph
rejects every outbound send and nothing real is ever delivered.

Proves end-to-end wiring: challenge verify, signature verify, parse,
dispatch, session persist, message-id dedupe. Prints only statuses
and session-shape metadata (counts, lang), never message content.

Usage: .venv/bin/modal run scripts/wa_deployed_sim.py::sim
"""

import modal

app = modal.App("wa-deployed-sim")

image = modal.Image.debian_slim(python_version="3.11").pip_install("httpx")

vol = modal.Volume.from_name("recover-data", create_if_missing=False)

DEPLOYED = "https://moalaa2--recover-ai-web.us-east.modal.run"
WA_ID = "15550009991"  # fake recipient: Graph rejects, never delivered


def _payload(mid, kind, **kw):
    if kind == "text":
        msg = {"id": mid, "type": "text",
               "text": {"body": kw["text"]}}
    elif kind == "image":
        msg = {"id": mid, "type": "image",
               "image": {"id": "fake-media-1",
                         "caption": kw.get("caption", "")}}
    elif kind == "audio":
        msg = {"id": mid, "type": "audio",
               "audio": {"id": "fake-aud-1"}}
    else:
        msg = {"id": mid, "type": "interactive",
               "interactive": {"type": "button_reply",
                               "button_reply": {"id": kw["pid"]}}}
    return {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": WA_ID}],
        "messages": [msg]}}]}]}


CONVO = [
    ("greet-needs", "text",
     {"text": "Hi, I need fabric for my sofa. I have kids and a cat."}),
    ("ask-recs", "text",
     {"text": "Warm beige, budget 150 per meter. Recommend 3 now."}),
    ("try-bad-code", "button", {"pid": "try:FA-XX-99"}),
    ("ask-recs-DUPE", "text",
     {"text": "Warm beige, budget 150 per meter. Recommend 3 now.",
      "dup_of": "ask-recs"}),
    ("summary-empty", "text", {"text": "summary"}),
    ("reset", "text", {"text": "new"}),
    ("language", "text", {"text": "language"}),
    ("photo-bad-media", "image", {}),
    ("voice-bad-media", "audio", {}),
]


@app.function(image=image,
             secrets=[modal.Secret.from_name("recover-whatsapp")],
             volumes={"/root/recover/uploads": vol},
             timeout=600)
def sim():
    import hashlib
    import hmac
    import json
    import os
    import time

    import httpx

    secret = os.environ.get("WA_APP_SECRET", "")
    verify = os.environ.get("WA_VERIFY_TOKEN", "")
    print("ENV app_secret=%s verify_token=%s" % (bool(secret),
                                                 bool(verify)))
    if not secret or not verify:
        print("MISSING_SECRET_FIELDS")
        return

    client = httpx.Client(timeout=60)

    def sign(raw):
        return "sha256=" + hmac.new(secret.encode(), raw,
                                    hashlib.sha256).hexdigest()

    # 1. Challenge round-trip (correct + wrong token).
    r = client.get(DEPLOYED + "/webhook/whatsapp",
                   params={"hub.mode": "subscribe",
                           "hub.verify_token": verify,
                           "hub.challenge": "CHAL123"})
    print("CHALLENGE ok=%s echo=%s" % (r.status_code == 200,
                                       r.text[:20]))
    r = client.get(DEPLOYED + "/webhook/whatsapp",
                   params={"hub.mode": "subscribe",
                           "hub.verify_token": "wrong",
                           "hub.challenge": "CHAL123"})
    print("CHALLENGE wrong-token=%d (want 403)" % r.status_code)

    # 2. Signed conversation. One mid is reused to prove dedupe.
    mids = {}
    posted = 0
    for i, (label, kind, kw) in enumerate(CONVO):
        kw = dict(kw)
        dup_of = kw.pop("dup_of", None)
        mid = mids[dup_of] if dup_of else "sim-%s-%d" % (label, i)
        if not dup_of:
            mids[label] = mid
        body = _payload(mid, kind, **kw)
        raw = json.dumps(body).encode()
        r = client.post(DEPLOYED + "/webhook/whatsapp", content=raw,
                        headers={"X-Hub-Signature-256": sign(raw),
                                 "Content-Type": "application/json"})
        print("POST %-15s mid=%s dupe=%s -> %d" % (
            label, mid[-8:], bool(dup_of), r.status_code))
        posted += 1
        time.sleep(3)

    # 3. Bad signature is rejected.
    raw = json.dumps(_payload("sim-bad", "text",
                              text="hi")).encode()
    r = client.post(DEPLOYED + "/webhook/whatsapp", content=raw,
                    headers={"X-Hub-Signature-256": "sha256=bad",
                             "Content-Type": "application/json"})
    print("POST bad-signature -> %d (want 403)" % r.status_code)

    # 4. Drain: background threads finish consultant turns (~20s each,
    # several in parallel). A trailing post then forces the Volume
    # commit cycle so background-thread session writes are durable.
    print("POSTED=%d, draining..." % posted)
    time.sleep(150)
    flush = _payload("sim-flush", "text", text="new")
    raw = json.dumps(flush).encode()
    r = client.post(DEPLOYED + "/webhook/whatsapp", content=raw,
                    headers={"X-Hub-Signature-256": sign(raw),
                             "Content-Type": "application/json"})
    print("POST flush -> %d" % r.status_code)
    time.sleep(20)
    vol.reload()
    path = "/root/recover/private/wa_sessions/%s.json" % WA_ID
    try:
        with open(path, encoding="utf-8") as f:
            sess = json.load(f)
    except OSError:
        print("SESSION_FILE missing")
        return
    msgs = sess.get("messages") or []
    seen = sess.get("seen_ids") or []
    roles = {}
    for m in msgs:
        roles[m.get("role", "?")] = roles.get(m.get("role", "?"), 0) + 1
    print("SESSION lang=%s messages=%d roles=%s seen_ids=%d "
          "assignments=%s" % (sess.get("lang"), len(msgs), roles,
                              len(seen), sess.get("assignments") or {}))
    print("DEDUPE unique_mids_posted=9 seen=%d" % len(seen))
    print("SIM_DONE")
