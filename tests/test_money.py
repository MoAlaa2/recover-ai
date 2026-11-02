"""One money string per number, on every surface."""
import json
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.main import ASSET_CACHE, VERSION, app, current_version
from app.services.money import format_money


def test_format_money_separators_and_cents():
    assert format_money(1090.5) == "$1,090.50"
    assert format_money(155) == "$155"
    assert format_money(2557.5) == "$2,557.50"
    assert format_money(1234567.891) == "$1,234,567.89"
    assert format_money(37, symbol=False) == "37"
    assert format_money(None) == ""
    assert format_money(0.1 + 0.2) == "$0.30"


def test_format_money_arabic_digits():
    assert format_money(1090.5, "ar") == "$١,٠٩٠.٥٠"


@pytest.mark.skipif(not shutil.which("node"), reason="node required")
def test_client_formatter_matches_server():
    cases = [1090.5, 155, 2557.5, 1234567.891, 0.3, 19.999]
    out = subprocess.run(
        ["node", "-e",
         "global.window={};require('./app/static/common.js');"
         "console.log(JSON.stringify(%s.map(function(n){"
         "return [window.RC.money(n,'en'), window.RC.money(n,'ar')];})))"
         % json.dumps(cases)],
        capture_output=True, text=True, timeout=30, check=True)
    got = json.loads(out.stdout)
    for n, (en, ar) in zip(cases, got):
        assert en == format_money(n), n
        assert ar == format_money(n, "ar"), n


def test_pdf_and_whatsapp_use_the_formatter():
    from app.services import proposal
    assert proposal.fmt_money(2557.5, "en") == "2,557.50"
    assert proposal.fmt_money(155, "en") == "155"


def test_versioned_assets_cache_a_week_html_never():
    client = TestClient(app)
    page = client.get("/consult")
    assert page.headers["cache-control"] == "no-store"
    assert "/common.js?v=%s" % current_version() in page.text
    asset = client.get("/app.js?v=%s" % current_version())
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == ASSET_CACHE
    assert "immutable" in ASSET_CACHE and "max-age=604800" in ASSET_CACHE
    sample = client.get("/data/samples/living.jpg")
    assert sample.headers["cache-control"] == ASSET_CACHE
    api = client.get("/api/fabrics")
    assert "immutable" not in (api.headers.get("cache-control") or "")


def test_version_is_a_commit_hash_when_git_is_present():
    if not shutil.which("git"):
        pytest.skip("git required")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    if head:
        assert VERSION == head


def test_local_version_tracks_asset_edits(monkeypatch, tmp_path):
    """Without RC_BUILD (local dev) the version moves with the newest
    static file, so an immutable cache never serves a stale edit."""
    import os
    from app import main as m
    monkeypatch.delenv("RC_BUILD", raising=False)
    before = m.current_version()
    assert before.startswith(VERSION + "-")
    path = os.path.join(m.STATIC_DIR, "common.js")
    st = os.stat(path)
    try:
        os.utime(path, (st.st_atime, st.st_mtime + 10 ** 6))
        assert m.current_version() != before
    finally:
        os.utime(path, (st.st_atime, st.st_mtime))
    monkeypatch.setenv("RC_BUILD", "abc1234")
    assert m.current_version() == VERSION
