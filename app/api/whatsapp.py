"""WhatsApp Cloud API webhook (no duplicated consultant logic)."""
from fastapi import APIRouter, Request, Response

from app.services import whatsapp as wa

router = APIRouter()


@router.get("/webhook/whatsapp")
def whatsapp_challenge(request: Request):
    """Meta hub verification. Needs WA_VERIFY_TOKEN configured."""
    if not wa.configured():
        return Response("whatsapp not configured", status_code=404)
    params = dict(request.query_params)
    if (params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token")
            == wa.wa_env()["verify_token"]):
        return Response(content=params.get("hub.challenge", ""),
                        media_type="text/plain")
    return Response("forbidden", status_code=403)


@router.post("/webhook/whatsapp")
async def whatsapp_inbound(request: Request):
    """Meta message callback. HMAC-verified, 200 fast, async work."""
    if not wa.configured():
        return Response("whatsapp not configured", status_code=404)
    raw = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not wa.verify_signature(raw, signature):
        return Response("bad signature", status_code=403)
    try:
        import json
        body = json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        return Response("ok")
    for wa_id, message in wa.parse_webhook(body):
        wa.dispatch(wa_id, message)
    return Response("ok")
