"""settle_console_errors: recovered 404s warn, persistent ones fail."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from live_e2e import settle_console_errors


class StubPage:
    def __init__(self, status_by_url):
        self.status_by_url = status_by_url

    def evaluate(self, _js, url):
        return self.status_by_url.get(url, -1)


def test_settled_errors():
    good = "https://x/uploads/a.jpg"
    bad = "https://x/uploads/b.jpg"
    errors = ["HTTP 404 <%s>" % good,
              "Failed to load resource: 404 () <%s>" % good,
              "HTTP 404 <%s>" % bad,
              "ReferenceError: nope"]
    out = settle_console_errors(StubPage({good: 200, bad: 404}), errors)
    assert not [e for e in out if good in e], out
    assert any("persistent" in e and bad in e for e in out), out
    assert any("ReferenceError" in e for e in out), out
