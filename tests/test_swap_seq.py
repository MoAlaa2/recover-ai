"""A3: overlapping swaps must not corrupt each other.

Static guard for the client swap sequence token: every entry point rides
tryFabric, a new swap bumps swapSeq + aborts the previous fetch, and
stale stream events are ignored.
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"


def src():
    return APP_JS.read_text(encoding="utf-8")


def test_swap_seq_token_exists():
    s = src()
    assert "swapSeq" in s
    assert "swapController" in s


def test_tryfabric_aborts_previous_and_bumps_seq():
    s = src()
    assert "state.swapSeq = (state.swapSeq || 0) + 1" in s
    assert "state.swapController.abort()" in s
    assert "mySeq !== state.swapSeq" in s or "mySeq!==state.swapSeq" in s


def test_openSwap_routes_through_tryfabric():
    s = src()
    assert "All entry points must ride the sequence token in tryFabric" in s
    # openSwap without an internal seq must delegate to tryFabric
    assert "if (!opts._seq && !opts.review)" in s


def test_stale_events_ignored():
    s = src()
    assert "if (isStale()) return;" in s
    assert "if (settled || isStale()) return;" in s


def test_no_direct_openSwap_entry_points():
    s = src()
    calls = [m.start() for m in re.finditer(r"openSwap\(", s)]
    # Allowed: function def, internal call with openOpts (has _seq),
    # review-path guard inside openSwap itself.
    for pos in calls:
        window = s[max(0, pos - 200):pos + 120]
        assert (
            "function openSwap" in window
            or "openSwap(code, openOpts)" in s[pos:pos + 60]
            or "!opts._seq" in window
        ), f"direct openSwap entry point remains near: ...{window[-120:]}"
