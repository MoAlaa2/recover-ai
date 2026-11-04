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
    assert all(0 < t <= 0.2 for t in calls)
    entries = read_log()
    assert len(entries) == 2
    assert all(e["stage"] == "edit" for e in entries)
    assert all(e["model"] == "muse-image-1.0" for e in entries)
    assert all(0 < e["timeout_s"] <= 0.2 for e in entries)


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


def test_swap_stream_marks_timeout(monkeypatch, tmp_path):
    """SSE error events carry timeout=true for TimeoutSwapError."""
    from fastapi.testclient import TestClient

    import app.api.chat as chat_api
    from app.main import app

    # The stream route validates image_path like /api/swap does, so the
    # path must be a real file under the uploads dir.
    monkeypatch.setattr(chat_api, "UPLOAD_DIR", str(tmp_path))
    Image.new("RGB", (8, 8)).save(str(tmp_path / "x.jpg"))
    image_path = str(tmp_path / "x.jpg")

    def boom(*a, **k):
        raise s.TimeoutSwapError("swap timed out in edit")

    monkeypatch.setattr(chat_api, "swap", boom)
    client = TestClient(app)
    resp = client.post("/api/swap/stream",
                       json={"session_id": "s",
                             "image_path": image_path,
                             "fabric_code": "FA-NL-02", "target": "sofa"})
    assert resp.status_code == 200
    assert '"timeout": true' in resp.text

    def fail(*a, **k):
        raise s.SwapError("could not find the sofa in this photo")

    monkeypatch.setattr(chat_api, "swap", fail)
    resp = client.post("/api/swap/stream",
                       json={"session_id": "s",
                             "image_path": image_path,
                             "fabric_code": "FA-NL-02", "target": "sofa"})
    assert resp.status_code == 200
    assert '"timeout": false' in resp.text


def test_swap_stream_rejects_paths_outside_uploads(monkeypatch):
    """/api/swap/stream fails closed on a path outside the allow-list,
    like /api/swap, and never reaches the swap."""
    from fastapi.testclient import TestClient

    import app.api.chat as chat_api
    from app.main import app

    reached = []
    monkeypatch.setattr(chat_api, "swap",
                        lambda *a, **k: reached.append(a))
    client = TestClient(app)
    for bad in ("/etc/passwd", "uploads/../../app/main.py", ""):
        resp = client.post("/api/swap/stream",
                           json={"session_id": "s", "image_path": bad,
                                 "fabric_code": "FA-NL-02",
                                 "target": "sofa"})
        assert resp.status_code == 400, bad
    assert reached == []


def test_multi_stream_input_error_is_a_clean_event(monkeypatch):
    """Bad Apply-all input yields one SSE error event, not a 500 from
    `exc` being read after its except block."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post("/api/swap/multi/stream",
                       json={"session_id": "s", "image_path": "/etc/passwd",
                             "assignments": []})
    assert resp.status_code == 200
    assert '"type": "error"' in resp.text
    assert "image not found" in resp.text


def test_retry_skipped_when_first_attempt_used_the_budget(monkeypatch):
    """A timeout that ran the whole budget is not retried: the retry
    would double the stage against the overall swap budget."""
    calls = []

    def hang_then_timeout(req, timeout=None):
        calls.append(timeout)
        time.sleep(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(s.urllib.request, "urlopen", hang_then_timeout)
    t0 = time.time()
    with pytest.raises(s.TimeoutSwapError):
        s._post_json("http://x", {}, "k", 0.5, stage="edit",
                     model="muse-image-1.0")
    assert len(calls) == 1
    assert time.time() - t0 < 4  # 0.5 s attempt + 2 s sleep, no retry


def test_retry_gets_only_the_remaining_budget(monkeypatch):
    """A fast failure is retried, with the time left, not a fresh cap."""
    calls = []

    def fail_fast_then_ok(req, timeout=None):
        calls.append(timeout)
        if len(calls) == 1:
            time.sleep(0.3)
            raise ConnectionResetError("reset")

        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"ok": 1}'
        return R()

    monkeypatch.setattr(s.urllib.request, "urlopen", fail_fast_then_ok)
    assert s._post_json("http://x", {}, "k", 10.0, stage="segment") == {
        "ok": 1}
    assert len(calls) == 2
    assert calls[0] == 10.0
    # 10 s minus the 0.3 s first attempt; the 2 s pause is not charged
    assert 9.0 <= calls[1] <= 9.8
