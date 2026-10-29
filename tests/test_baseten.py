"""Baseten Spark Open fallback + scope classifier (all faked)."""
import io
import json
import urllib.error
import urllib.request

import pytest

from app.services import consultant as c


class FakeResp:
    def __init__(self, payload=b"", chunks=()):
        self._payload = payload
        self._chunks = list(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._payload

    def __iter__(self):
        return iter(self._chunks)


CHAT_BODY = {"choices": [{"message": {"content": "baseten here"}}]}


def sse(*texts):
    chunks = []
    for t in texts:
        chunks.append(('data: {"choices": [{"delta": {"content": %s}}]}'
                       % json.dumps(t)).encode() + b"\n\n")
    chunks.append(b"data: [DONE]\n\n")
    return chunks


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setattr(c, "require_api_key", lambda: "meta-k")
    monkeypatch.setenv("SPARK_OPEN_FALLBACK", "1")
    monkeypatch.setenv("BASETEN_API_KEY", "b-k")
    return None


def test_disabled_by_default(monkeypatch):
    monkeypatch.setattr(c, "require_api_key", lambda: "meta-k")
    monkeypatch.delenv("SPARK_OPEN_FALLBACK", raising=False)
    monkeypatch.setenv("BASETEN_API_KEY", "b-k")
    hits = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *a, **k: (hits.append(a[0].full_url),
                         (_ for _ in ()).throw(TimeoutError("t")))[1])
    with pytest.raises(RuntimeError, match="chat call failed"):
        c._call_chat([{"role": "user", "content": "hi"}])
    assert hits and all("meta.ai" in u for u in hits)


def test_fallback_after_two_timeouts(monkeypatch, keyed):
    hits = []
    calls = {"n": 0}

    def fake(req, timeout=None):
        hits.append(req.full_url)
        calls["n"] += 1
        if calls["n"] <= 2:
            raise TimeoutError("timed out")
        return FakeResp(json.dumps(CHAT_BODY).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    out = c._call_chat([{"role": "user", "content": "hi"}])
    assert out == CHAT_BODY
    assert [u for u in hits if "meta.ai" in u].__len__() == 2
    assert any("baseten.co" in u for u in hits)


def test_no_fallback_on_mixed_errors(monkeypatch, keyed):
    hits = []

    def fake(req, timeout=None):
        hits.append(req.full_url)
        if len(hits) == 1:
            raise TimeoutError("timed out")
        raise urllib.error.HTTPError(req.full_url, 500, "x", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(RuntimeError, match="chat call failed"):
        c._call_chat([{"role": "user", "content": "hi"}])
    assert not any("baseten.co" in u for u in hits)


def test_fallback_failure_reports_both(monkeypatch, keyed):
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(TimeoutError("t")))
    with pytest.raises(RuntimeError,
                       match="baseten fallback failed"):
        c._call_chat([{"role": "user", "content": "hi"}])


def test_stream_fallback(monkeypatch, keyed):
    calls = {"n": 0}

    def fake(req, timeout=None):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise TimeoutError("timed out")
        return FakeResp(chunks=sse("hel", "lo"))

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    seen = []
    text, tool_calls, usage = c._call_chat_stream(
        [{"role": "user", "content": "hi"}], None, seen.append)
    assert text == "hello"
    assert tool_calls == []


def test_is_timeout():
    assert c._is_timeout(TimeoutError("t"))
    assert c._is_timeout(
        urllib.error.URLError(TimeoutError("t")))
    assert not c._is_timeout(ValueError("x"))
    assert not c._is_timeout(
        urllib.error.URLError("connection refused"))


def test_classifier_matrix(monkeypatch):
    monkeypatch.setenv("SPARK_OPEN_FALLBACK", "1")
    monkeypatch.setenv("BASETEN_API_KEY", "b-k")
    monkeypatch.setattr(
        c, "_post_baseten",
        lambda p: {"choices": [{"message": {"content": "  YES  "}}]})
    assert c.baseten_scope_allows("sofa") is True
    monkeypatch.setattr(
        c, "_post_baseten",
        lambda p: {"choices": [{"message": {"content": "no"}}]})
    assert c.baseten_scope_allows("sofa") is False

    def boom(p):
        raise RuntimeError("down")
    monkeypatch.setattr(c, "_post_baseten", boom)
    assert c.baseten_scope_allows("sofa") is False


def test_classifier_off_by_default(monkeypatch):
    monkeypatch.delenv("SPARK_OPEN_FALLBACK", raising=False)
    monkeypatch.setenv("BASETEN_API_KEY", "b-k")
    called = []
    monkeypatch.setattr(
        c, "_post_baseten",
        lambda p: called.append(p) or {"choices": []})
    assert c.baseten_scope_allows("sofa") is False
    assert called == []


def test_enabled_requires_key(monkeypatch):
    monkeypatch.setenv("SPARK_OPEN_FALLBACK", "1")
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    assert c._spark_open_enabled() is False


def test_second_opinion_undeclines(monkeypatch):
    monkeypatch.setenv("SPARK_OPEN_FALLBACK", "1")
    monkeypatch.setenv("BASETEN_API_KEY", "b-k")
    monkeypatch.setattr(c, "is_in_scope", lambda m: False)
    monkeypatch.setattr(c, "baseten_scope_allows", lambda m: True)

    def fake(messages, tools=None):
        return {"choices": [{"message": {"content": "hello there"}}]}

    out = c.chat("test-baseten-scope", "1+1", chat_fn=fake)
    assert out["reply"] == "hello there"


def test_second_opinion_declines_when_closed(monkeypatch):
    monkeypatch.setattr(c, "is_in_scope", lambda m: False)
    monkeypatch.setattr(c, "baseten_scope_allows", lambda m: False)

    def fake(messages, tools=None):
        raise AssertionError("model must not be called")

    out = c.chat("test-baseten-scope-closed", "1+1", chat_fn=fake)
    assert out["recommendations"] == []
