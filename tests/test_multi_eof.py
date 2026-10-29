"""A4: multi-swap stream must not spin forever on EOF without done."""
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"


def src():
    return APP_JS.read_text(encoding="utf-8")


def test_multi_has_deadline_and_abort():
    s = src()
    assert "MULTI_DEADLINE_MS" in s
    assert "multiFail(true)" in s
    # AbortController wired into the multi fetch init
    assert "if (ctrl) init.signal = ctrl.signal;" in s


def test_multi_eof_without_done_is_error():
    s = src()
    assert "EOF without done" in s
    assert "if (step.done) { multiFail(true); return; }" in s


def test_multi_clears_running_on_all_paths():
    s = src()
    # multiFail is the single funnel that always clears the flag
    assert "state.multiRunning = false;" in s
    assert "function multiFail(timedOut)" in s
    assert "function multiDone(result)" in s
