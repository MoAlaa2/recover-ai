"""Chat param guards: reasoning effort + combined output cap, length
fallback, and a full rec reply that must fit the base cap."""
import json
import urllib.request

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


def sse(*texts, finish="stop"):
    chunks = []
    for t in texts:
        chunks.append(('data: {"choices": [{"delta": {"content": %s}}]}'
                       % json.dumps(t)).encode() + b"\n\n")
    chunks.append(('data: {"choices": [{"delta": {}, '
                  '"finish_reason": "%s"}]}' % finish).encode() + b"\n\n")
    chunks.append(b"data: [DONE]\n\n")
    return chunks


def body_of(text, finish="stop"):
    return json.dumps(
        {"choices": [{"message": {"content": text},
                      "finish_reason": finish}]}).encode()


def test_payload_carries_reasoning_and_cap(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen["payload"] = json.loads(req.data.decode())
        return FakeResp(payload=body_of("hi"))

    monkeypatch.setattr(c, "require_api_key", lambda: "k")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    c._call_chat([{"role": "user", "content": "hi"}])
    assert seen["payload"]["reasoning_effort"] == c.REASONING_EFFORT
    assert seen["payload"]["max_tokens"] == c.CHAT_MAX_TOKENS


def test_length_finish_retries_once_at_high_cap(monkeypatch):
    calls = []

    def fake(req, timeout=None):
        payload = json.loads(req.data.decode())
        calls.append(payload["max_tokens"])
        if len(calls) == 1:
            return FakeResp(payload=body_of("cut off…", "length"))
        return FakeResp(payload=body_of("full reply here", "stop"))

    monkeypatch.setattr(c, "require_api_key", lambda: "k")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    out = c._call_chat([{"role": "user", "content": "hi"}])
    assert calls == [c.CHAT_MAX_TOKENS, c.CHAT_MAX_TOKENS_RETRY]
    assert out["choices"][0]["message"]["content"] == "full reply here"


def test_second_length_is_accepted_not_looped(monkeypatch):
    calls = []

    def fake(req, timeout=None):
        calls.append(1)
        return FakeResp(payload=body_of("stub", "length"))

    monkeypatch.setattr(c, "require_api_key", lambda: "k")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    out = c._call_chat([{"role": "user", "content": "hi"}])
    assert len(calls) == 2
    assert out["choices"][0]["message"]["content"] == "stub"


def test_full_rec_reply_fits_base_cap():
    """A longest-realistic rec reply (prose + 3 reasons + options, at a
    conservative 2 chars/token for non-Latin scripts) plus 4000 tokens
    of reasoning headroom must fit CHAT_MAX_TOKENS."""
    prose = ("These are my top picks for your living room, grounded in "
             "what you told me about kids, pets and sun. ") * 4
    reasons = ["durable easy-clean weave that survives kids and cats, "
               "warm beige tone for your palette"] * 3
    block = "```recommendations\n%s\n```" % json.dumps(
        [{"code": "FA-VL-%02d" % i, "reason": r}
         for i, r in enumerate(reasons)], ensure_ascii=False)
    options = '```options\n["Show me darker", "Under 100 SAR"]\n```'
    reply = prose + "\n" + block + "\n" + options
    estimate = len(reply) // 2 + 4000
    assert estimate <= c.CHAT_MAX_TOKENS, (
        "rec reply ~%d tokens + headroom exceeds cap %d"
        % (estimate, c.CHAT_MAX_TOKENS))


def test_stream_length_refetches_silently(monkeypatch):
    calls = []
    full = "Here is the whole reply with recs."

    def fake(req, timeout=None):
        payload = json.loads(req.data.decode())
        calls.append(payload.get("max_tokens"))
        if len(calls) == 1:
            return FakeResp(chunks=sse("part", finish="length"))
        return FakeResp(chunks=sse(full, finish="stop"))

    monkeypatch.setattr(c, "require_api_key", lambda: "k")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    seen = []
    text, tool_calls, usage = c._stream_once(
        c.CHAT_URL, "k", c.SPARK_MODEL,
        [{"role": "user", "content": "hi"}], None, seen.append)
    assert calls == [c.CHAT_MAX_TOKENS, c.CHAT_MAX_TOKENS_RETRY]
    assert text == full
    assert seen == ["part"]  # first pass streamed, retry silent


def test_search_first_answers_explicit_ask_in_one_call():
    seen = {}
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        seen["messages"] = messages
        codes = []
        for m in messages:
            if m.get("role") == "tool":
                try:
                    payload = json.loads(m.get("content") or "{}")
                except ValueError:
                    continue
                codes = [f["code"] for f in
                         payload.get("fabrics", [])[:3]]
                if codes:
                    break
        return {"choices": [{"message": {"content":
                 "Here you go.\n```recommendations\n%s\n```"
                 % json.dumps([{"code": code, "reason": "r"}
                               for code in codes])}}]}

    out = c.chat("test-prefetch-explicit",
                 "We have kids. Recommend 3 sofa fabrics now",
                 chat_fn=fake)
    assert calls["n"] == 1
    assert len(out["recommendations"]) == 3
    seeds = [m for m in seen["messages"]
             if (m.get("tool_calls") or [{}])[0].get("id", "")
             .startswith("seed-")]
    assert seeds, "expected the injected search-first exchange"


def test_search_first_answers_needs_turn_in_one_call():
    calls = {"n": 0}

    def fake(messages, tools=None):
        calls["n"] += 1
        codes = []
        for m in messages:
            if m.get("role") == "tool":
                try:
                    payload = json.loads(m.get("content") or "{}")
                except ValueError:
                    continue
                codes = [f["code"] for f in
                         payload.get("fabrics", [])[:3]]
                if codes:
                    break
        return {"choices": [{"message": {"content":
                 "Here you go.\n```recommendations\n%s\n```"
                 % json.dumps([{"code": code, "reason": "r"}
                               for code in codes])}}]}

    # Prefetch fires only on an explicit request (a generic seeded
    # search on need-gathering turns hurt specialized picks in eval).
    out = c.chat("test-prefetch-needs",
                 "my cat ruins our sofa, recommend something tough",
                 chat_fn=fake)
    assert calls["n"] == 1
    assert len(out["recommendations"]) == 3
    assert all(c.get_fabric(r["code"]) for r in
               out["recommendations"])


def test_prefetch_ids_unique_across_turns():
    """Repeated prefetches in one session must not reuse tool_call ids
    (the API rejects duplicates with a 400)."""
    seen = {}

    def fake(messages, tools=None):
        seen["messages"] = messages
        return {"choices": [{"message": {"content": "noted"}}]}

    c.chat("test-seed-ids", "We have kids. Recommend 3 sofa fabrics now",
           chat_fn=fake)
    c.chat("test-seed-ids", "Recommend 3 curtain fabrics now",
           chat_fn=fake)
    ids = [tc.get("id") for m in seen["messages"]
           for tc in (m.get("tool_calls") or [])]
    seeds = [i for i in ids if (i or "").startswith("seed-")]
    assert len(seeds) >= 2
    assert len(seeds) == len(set(seeds))


def test_question_turn_has_no_prefetch():
    seen = {}

    def fake(messages, tools=None):
        seen["messages"] = messages
        return {"choices": [{"message": {"content":
                             "I can help with fabrics. What piece?"}}]}

    out = c.chat("test-no-prefetch", "what can you do", chat_fn=fake)
    assert out["recommendations"] == []
    assert not [m for m in seen["messages"]
                if (m.get("tool_calls") or [{}])[0].get("id", "")
                .startswith("seed-")]


def test_no_prefetch_on_need_gathering_turn():
    seen = {}

    def fake(messages, tools=None):
        seen["messages"] = messages
        return {"choices": [{"message": {"content": "Got it. Any kids?"}}]}

    c.chat("test-no-prefetch", "my cat ruins our sofa", chat_fn=fake)
    assert not [m for m in seen["messages"] if m.get("role") == "tool"]


def test_no_prefetch_without_stated_needs():
    """'Sadu cushions, recommend now' carries no extractable needs: the
    model must search with its own filters (no generic seeded list)."""
    seen = {}

    def fake(messages, tools=None):
        seen["messages"] = messages
        return {"choices": [{"message": {"content": "Which colours?"}}]}

    c.chat("test-no-seed-sadu", "Recommend 3 sadu cushion fabrics now",
           chat_fn=fake)
    assert not [m for m in seen["messages"]
                if (m.get("tool_calls") or [{}])[0].get("id", "")
                .startswith("seed-search")]


def test_fire_resistant_is_never_relaxed():
    """Hotel: fire-resistant + high martindale. Martindale may relax,
    the safety feature may not (FA-NL-16 regression)."""
    from app.services.catalog import get_fabric
    turn = {"needs_all": ["fire-resistant"], "min_martindale": 50000,
            "seen": [], "relaxed": []}
    out = c.run_search({"limit": 12}, turn)
    assert out["fabrics"]
    for f in out["fabrics"]:
        spec = get_fabric(f["code"])
        assert "fire-resistant" in spec.get("features", []), f["code"]
