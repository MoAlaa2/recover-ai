"""Item 2: single in-flight outlines fetch per photo (no duplicate SAM)."""
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"


def src():
    return APP_JS.read_text(encoding="utf-8")


def test_outlines_fetch_guarded():
    s = src()
    assert "state.outlinesFetching === path" in s
    assert 'state.outlinesFetching = ""' in s
