"""Tests for the Modal demo lock (pure ASGI, no network)."""
import asyncio
import base64
import os

from deploy.modal_app import DemoLockMiddleware


def run(scope, env):
    old = dict(os.environ)
    os.environ.update(env)
    messages = []

    async def inner(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    try:
        asyncio.run(DemoLockMiddleware(inner)(scope, receive, send))
    finally:
        os.environ.clear()
        os.environ.update(old)
    return messages


def basic(user, pwd):
    token = base64.b64encode(("%s:%s" % (user, pwd)).encode()).decode()
    return [(b"authorization", ("Basic " + token).encode())]


def headers_of(messages):
    start = [m for m in messages if m["type"] == "http.response.start"][0]
    return start["status"], dict(start["headers"])


def test_unlocked_passes_through():
    out = run({"type": "http", "headers": []}, {})
    status, headers = headers_of(out)
    assert status == 200
    assert b"x-robots-tag" not in headers


def test_locked_rejects_anonymous():
    out = run({"type": "http", "headers": []},
              {"DEMO_LOCK": "1", "DEMO_USER": "u", "DEMO_PASS": "p"})
    status, headers = headers_of(out)
    assert status == 401
    assert headers[b"x-robots-tag"] == b"noindex, nofollow"
    assert b"www-authenticate" in headers


def test_locked_rejects_wrong_password():
    out = run({"type": "http", "headers": basic("u", "wrong")},
              {"DEMO_LOCK": "1", "DEMO_USER": "u", "DEMO_PASS": "p"})
    assert headers_of(out)[0] == 401


def test_locked_accepts_credentials_and_tags():
    out = run({"type": "http", "headers": basic("u", "p")},
              {"DEMO_LOCK": "1", "DEMO_USER": "u", "DEMO_PASS": "p"})
    status, headers = headers_of(out)
    assert status == 200
    assert headers[b"x-robots-tag"] == b"noindex, nofollow"
