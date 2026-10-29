"""Swap hang guard: 75s per-call cap, one silent retry, overall budget,
timeout logging with stage + model. The model is faked slow; no
network is touched."""
import inspect
import json
import os
import time

import pytest
from PIL import Image

from app.services import swap as s

TMP = "/tmp/recover-swap-timeout-test"


def setup_function(_):
    os.makedirs(TMP, exist_ok=True)
    s.TIMEOUT_LOG = os.path.join(TMP, "swap_timeouts.jsonl")
    try:
        os.remove(s.TIMEOUT_LOG)
    except OSError:
        pass


def teardown_function(_):
    s.TIMEOUT_LOG = None


def read_log():
    try:
        with open(s.TIMEOUT_LOG, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except OSError:
        return []


def test_slow_model_retried_once_then_timeout(monkeypatch):
    """Fake slow model: two attempts, then TimeoutSwapError + log."""
    calls = []

    def slow_urlopen(req, timeout=None):
        calls.append(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(s.urllib.request, "urlopen", slow_urlopen)
    t0 = time.time()
    with pytest.raises(s.TimeoutSwapError):
        s._post_json("http://x", {}, "k", 0.2, stage="edit",
                     model="muse-image-1.0")
    assert time.time() - t0 < 5
    assert len(calls) == 2  # one silent retry on a fresh request
    assert all(t == 0.2 for t in calls)
    entries = read_log()
    assert len(entries) == 2
    assert all(e["stage"] == "edit" for e in entries)
    assert all(e["model"] == "muse-image-1.0" for e in entries)
    assert all(e["timeout_s"] == 0.2 for e in entries)


def test_nontimeout_failure_is_plain_swap_error(monkeypatch):
    """Deterministic failures stay SwapError and are never logged."""

    def boom(req, timeout=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(s.urllib.request, "urlopen", boom)
    with pytest.raises(s.SwapError) as exc_info:
        s._post_json("http://x", {}, "k", 0.2, stage="segment",
                     model="sam-3.1")
    assert not isinstance(exc_info.value, s.TimeoutSwapError)
    assert read_log() == []


def test_per_call_timeout_is_75s():
    """The 300s edit default is gone; budget stays under two minutes."""
    assert s.MODEL_TIMEOUT == 75
    for fn in (s.segment, s.edit_room, s.verify):
        assert inspect.signature(fn).parameters["timeout"].default == 75
    assert s.SWAP_BUDGET_S <= 110


def test_swap_budget_guard_fires_fast(monkeypatch, tmp_path):
    """Exhausted overall budget raises TimeoutSwapError naming a stage."""
    room = tmp_path / "room.jpg"
    Image.new("RGB", (64, 48), (10, 20, 30)).save(str(room))
    monkeypatch.setattr(
        s, "get_fabric",
        lambda code: {"image": "data/samples/living.jpg",
                      "primary_color": "beige", "name_en": "x",
                      "pattern_type": "plain"})
    monkeypatch.setattr(
        s, "segment",
        lambda *a, **k: [{"box": (0, 0, 32, 24),
                          "frame_size": (64, 48)}])
    monkeypatch.setattr(
        s, "sam_mask", lambda records, size: Image.new("L", size, 255))
    ticks = iter([1000.0, 1000.0, 1000.0, 1300.0])

    def fake_clock():
        try:
            return next(ticks)
        except StopIteration:
            return 1300.0

    monkeypatch.setattr(s.time, "monotonic", fake_clock)
    t0 = time.time()
    with pytest.raises(s.TimeoutSwapError, match="edit"):
        s.swap(str(room), "FAKE", "sofa", out_dir=str(tmp_path))
    assert time.time() - t0 < 5


def test_swap_stream_marks_timeout(monkeypatch):
    """SSE error events carry timeout=true for TimeoutSwapError."""
    from fastapi.testclient import TestClient

    import app.api.chat as chat_api
    from app.main import app

    def boom(*a, **k):
        raise s.TimeoutSwapError("swap timed out in edit")

    monkeypatch.setattr(chat_api, "swap", boom)
    client = TestClient(app)
    resp = client.post("/api/swap/stream",
                       json={"session_id": "s",
                             "image_path": "uploads/x.jpg",
                             "fabric_code": "FA-NL-02", "target": "sofa"})
    assert resp.status_code == 200
    assert '"timeout": true' in resp.text

    def fail(*a, **k):
        raise s.SwapError("could not find the sofa in this photo")

    monkeypatch.setattr(chat_api, "swap", fail)
    resp = client.post("/api/swap/stream",
                       json={"session_id": "s",
                             "image_path": "uploads/x.jpg",
                             "fabric_code": "FA-NL-02", "target": "sofa"})
    assert resp.status_code == 200
    assert '"timeout": false' in resp.text
