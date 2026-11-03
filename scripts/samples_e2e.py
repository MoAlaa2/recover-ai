"""End-to-end proof of the 5 judge samples on the LIVE deploy.

Per sample (fresh iPhone-15-Pro WebKit context per run):
  pick sample -> analysis+outlines check -> 3 recs -> swap each piece
  separately -> apply-all (multi) -> quote.
Saves the best result per piece to
  <Desktop>/Meta Hackathon/Video/samples_test/<sample>/
and a run table (times, colour-check pass/fail, issues) to results.json.

Usage: .venv/bin/python scripts/samples_e2e.py [--sample ID] [--runs N]
Model calls run against the deployed app with demo Basic Auth from
.env.demo (memory only, never printed). Slow by design: ~10-20 min/run.
"""
import base64
import json
import os
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

DEPLOYED = "https://moalaa2--recover-ai-web.us-east.modal.run"
OUT_DIR = os.path.join(BASE_DIR, "uploads", "e2e-samples")
DESK_DIR = ("/Users/mohamedalaa/Desktop/Meta Hackathon/Video/"
            "samples_test")

SAMPLES = {
    "sofa_pillows": ["sofa", "cushions"],
    "sage_curtains": ["curtains"],
    "navy_living": ["sofa", "armchair", "cushions", "curtains"],
    "majlis_burgundy": ["sofa", "cushions", "curtains"],
    "mustard_armchair": ["armchair"],
}

PIECE_USAGE = {"sofa": "upholstery", "armchair": "upholstery",
               "cushions": "cushions", "curtains": "curtains"}

CANDIDATE_ENV_FILES = [
    os.path.join(BASE_DIR, ".env.demo"),
    os.path.join(os.path.dirname(BASE_DIR), ".env.demo"),
    os.path.expanduser("~/.env.demo"),
]


def load_demo_creds():
    if os.environ.get("DEMO_USER") and os.environ.get("DEMO_PASS"):
        return os.environ["DEMO_USER"], os.environ["DEMO_PASS"]
    for path in CANDIDATE_ENV_FILES:
        if not os.path.isfile(path):
            continue
        creds = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    creds[key.strip()] = value.strip()
        if creds.get("DEMO_USER") and creds.get("DEMO_PASS"):
            return creds["DEMO_USER"], creds["DEMO_PASS"]
    raise FileNotFoundError("demo credentials not found")


USER, PW = None, None


def _auth():
    return {"Authorization": "Basic " + base64.b64encode(
        ("%s:%s" % (USER, PW)).encode()).decode()}


def api(method, path, payload=None, timeout=600):
    data = (json.dumps(payload).encode("utf-8")
            if payload is not None else None)
    url = DEPLOYED + path
    headers = dict(_auth())
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return raw


def api_bytes(path, timeout=300):
    req = urllib.request.Request(DEPLOYED + path, headers=_auth())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def save(url_path, dest):
    try:
        blob = api_bytes(url_path if url_path.startswith("/")
                         else "/" + url_path)
    except Exception as exc:  # noqa: BLE001 - record, keep going
        return "download-fail: %s" % str(exc)[:120]
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(blob)
    return "saved %dKB" % (len(blob) // 1024)


def fallback_fabric(piece):
    with open(os.path.join(BASE_DIR, "data", "fabric_specs.json"),
              encoding="utf-8") as f:
        specs = json.load(f)
    want = PIECE_USAGE[piece]
    cands = [s for s in specs
             if s.get("usage") == want
             and s.get("plain_or_patterned") == "plain"]
    cands.sort(key=lambda s: s["code"])
    return cands[0]["code"]


def settle_console_errors(pg, errors):
    urls = []
    for entry in errors:
        import re as _re
        m = _re.search(r"<(https?://[^>\s]+)>", entry or "")
        if m and m.group(1) not in urls:
            urls.append(m.group(1))
    fatal = []
    for url in urls:
        try:
            status = pg.evaluate(
                "u => fetch(u, {method: 'GET', cache: 'reload'})"
                ".then(function (r) { return r.status; })"
                ".catch(function () { return -1; })", url)
        except Exception:  # noqa: BLE001
            status = -1
        if status != 200:
            fatal.append(url)
    out = []
    for entry in errors:
        import re as _re
        m = _re.search(r"<(https?://[^>\s]+)>", entry or "")
        if m and m.group(1) in urls and m.group(1) not in fatal:
            continue
        if m and m.group(1) in fatal:
            entry = entry + " [persistent]"
        out.append(entry)
    return out


def run_one(pw_browser, device, sample, run_n):
    """One fresh-session run. Returns a result dict (never raises)."""
    from urllib.parse import quote as _quote
    res = {"sample": sample, "run": run_n, "issues": [],
           "swaps": {}, "console_errors": []}
    tag = "%s-r%d" % (sample, run_n)
    errors = []
    ctx = pw_browser.new_context(
        **device, http_credentials={"username": USER,
                                     "password": PW})
    pg = ctx.new_page()

    def _console(m):
        if m.type != "error":
            return
        try:
            loc = m.location or {}
            url = loc.get("url", "") if isinstance(loc, dict) \
                else getattr(loc, "url", "")
        except Exception:
            url = ""
        errors.append(("%s <%s>" % (m.text, url))[:260])
    pg.on("console", _console)
    pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
    pg.on("response", lambda r: errors.append(
        ("HTTP %s <%s>" % (r.status, r.url))[:260])
        if r.status >= 400 else None)

    def shot(name):
        try:
            pg.screenshot(path=os.path.join(OUT_DIR, tag + "-" + name
                                             + ".png"))
        except Exception:  # noqa: BLE001 - best effort
            pass

    image_path = "data/samples/%s.jpg" % sample
    try:
        t0 = time.perf_counter()
        pg.goto(DEPLOYED + "/consult?sample=" + sample + "&new=1",
                wait_until="networkidle", timeout=90000)
        pg.wait_for_function(
            "() => document.querySelectorAll("
            "'#messages .msg.them').length >= 2", timeout=300000)
        res["analysis_s"] = round(time.perf_counter() - t0, 1)
        shot("analysis")
        sid = pg.evaluate(
            "() => window.localStorage.getItem('recover_sid')")
        res["sid"] = (sid or "")[:8]
        try:
            st = api("GET", "/api/session/" + sid + "/state",
                     timeout=60)
            res["has_room_analysis"] = bool(
                (st or {}).get("room_analysis"))
            if not res["has_room_analysis"]:
                res["issues"].append("no room_analysis in state")
        except Exception as exc:  # noqa: BLE001
            res["issues"].append("state fetch: %s" % str(exc)[:120])
        try:
            tg = api("GET", "/api/session/" + sid + "/targets"
                     "?image_path=" + _quote(image_path, safe=""),
                     timeout=300)
            listed = tg.get("targets", []) if isinstance(tg, dict) \
                else []
        except Exception as exc:  # noqa: BLE001
            listed = []
            res["issues"].append("targets fetch: %s" % str(exc)[:120])
        res["pieces_listed"] = [t.get("type") for t in listed
                                if isinstance(t, dict)]
        for t in listed:
            try:
                box = t.get("box") or []
                size = t.get("size") or [1, 1]
                area = ((box[2] - box[0]) * (box[3] - box[1])
                        / float(size[0] * size[1]))
                if not 0.005 <= area <= 0.95:
                    res["issues"].append(
                        "outline %s area %.3f" % (t.get("type"), area))
            except Exception:  # noqa: BLE001 - malformed box
                res["issues"].append("outline %s bad box"
                                     % (t.get("id") if isinstance(
                                         t, dict) else "?"))
        for want in SAMPLES[sample]:
            if want not in res["pieces_listed"]:
                res["issues"].append("missed piece: %s" % want)
        shot("outlines")
        t1 = time.perf_counter()
        for _ in range(6):
            try:
                pg.wait_for_selector("#chips:not([hidden])",
                                     timeout=60000)
            except Exception:
                break
            texts = pg.eval_on_selector_all(
                "#chips button", "els => els.map(e => e.textContent)")
            if not texts:
                break
            pick = next((c for c in texts
                         if any(w in c.lower()
                                for w in ("all", "mix", "everything",
                                          "both"))), texts[0])
            pg.click("#chips button:has-text('%s')" % pick[:14])
            pg.wait_for_timeout(2500)
            pg.wait_for_function(
                "() => !document.getElementById('pending')",
                timeout=120000)
            if pg.eval_on_selector_all(
                    "#messages .mini-card", "e => e.length") > 0:
                break
        cards = pg.eval_on_selector_all(
            "#messages .mini-try",
            "e => e.map(x => ({code: x.getAttribute('data-try'), "
            "target: x.getAttribute('data-target')}))")
        res["rec_s"] = round(time.perf_counter() - t1, 1)
        res["recs"] = cards[-3:] if len(cards) >= 3 else cards
        if len(cards) < 3:
            res["issues"].append("only %d rec cards" % len(cards))
            raise RuntimeError("no 3 recs")
        shot("recs")
        by_target = {}
        for c in res["recs"]:
            if c.get("target") and c.get("code"):
                by_target.setdefault(c["target"], c["code"])
        codes = {}
        for piece in SAMPLES[sample]:
            if piece not in res["pieces_listed"]:
                continue
            codes[piece] = by_target.get(piece) or fallback_fabric(
                piece)
        res["codes"] = codes
        for piece, code in codes.items():
            t2 = time.perf_counter()
            try:
                out = api("POST", "/api/swap",
                          {"session_id": sid, "image_path": image_path,
                           "fabric_code": code, "target": piece},
                          timeout=600)
            except Exception as exc:  # noqa: BLE001
                res["swaps"][piece] = {"error": str(exc)[:200]}
                res["issues"].append("swap %s failed" % piece)
                continue
            dt = round(time.perf_counter() - t2, 1)
            scores = (out or {}).get("scores", {}) if isinstance(
                out, dict) else {}
            color = scores.get("color")
            passed = (isinstance(color, (int, float)) and color >= 6)
            dest = os.path.join(DESK_DIR, sample,
                                "%s-run%d.jpg" % (piece, run_n))
            dl = save((out or {}).get("result_url", "") or "", dest)
            res["swaps"][piece] = {"s": dt, "code": code,
                                    "color": color,
                                    "colour_pass": bool(passed),
                                    "dl": dl}
            if not passed:
                res["issues"].append(
                    "swap %s colour %s" % (piece, color))
            shot("swap-" + piece)
        t3 = time.perf_counter()
        try:
            multi = api("POST", "/api/swap/multi",
                        {"session_id": sid, "image_path": image_path,
                         "assignments": [{"target": p, "code": c}
                                         for p, c in codes.items()]},
                        timeout=900)
            res["multi_s"] = round(time.perf_counter() - t3, 1)
            results = (multi or {}).get("results", []) if isinstance(
                multi, dict) else []
            if len(results) == len(codes) and all(
                    r.get("result_url") for r in results):
                last = results[-1].get("result_url", "")
                res["multi_dl"] = save(
                    last, os.path.join(
                        DESK_DIR, sample, "multi-run%d.jpg" % run_n))
            else:
                res["issues"].append(
                    "multi results %d/%d" % (len(results),
                                             len(codes)))
            skipped = (multi or {}).get("skipped", [])
            if skipped:
                res["issues"].append("multi skipped %r" % (skipped,))
        except Exception as exc:  # noqa: BLE001
            res["multi_s"] = round(time.perf_counter() - t3, 1)
            res["issues"].append("multi failed: %s" % str(exc)[:160])
        try:
            quote = api("GET", "/api/session/" + sid + "/quote",
                        timeout=120)
            # Curtains lines legitimately show "needs measure" until the
            # user gives window dimensions; that is product behavior,
            # not a sample failure. Everything else must total.
            res["quote_total"] = (quote or {}).get("total")
            items = (quote or {}).get("items", []) if isinstance(
                quote, dict) else []
            bad = [i for i in items
                   if i.get("target") != "curtains"
                   and i.get("line_total") is None]
            res["quote_ok"] = (
                isinstance(quote, dict)
                and quote.get("currency") == "USD"
                and not bad
                and {i.get("target") for i in quote.get("items", [])}
                >= set(codes))
            res["quote_missing"] = (quote or {}).get("missing", [])
            if not res["quote_ok"]:
                res["issues"].append("quote bad: %s" % json.dumps(
                    quote, ensure_ascii=False)[:200])
        except Exception as exc:  # noqa: BLE001
            res["quote_ok"] = False
            res["issues"].append("quote failed: %s" % str(exc)[:160])
        shot("done")
    except Exception as exc:  # noqa: BLE001 - one run never kills all
        res["issues"].append("run error: %s" % str(exc)[:200])
        shot("fail")
    finally:
        try:
            res["console_errors"] = settle_console_errors(pg, errors)
        except Exception:  # noqa: BLE001
            res["console_errors"] = errors
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass
    res["pass"] = (not res["issues"]
                   and not res["console_errors"]
                   and len(res.get("recs", [])) >= 3
                   and bool(res.get("quote_ok")))
    return res


def main():
    global USER, PW
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="")
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    USER, PW = load_demo_creds()
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(DESK_DIR, exist_ok=True)
    samples = [args.sample] if args.sample else list(SAMPLES)
    from playwright.sync_api import sync_playwright
    table = []
    with sync_playwright() as p:
        browser = p.webkit.launch()
        device = dict(p.devices["iPhone 15 Pro"])
        device["viewport"] = {"width": 390, "height": 844}
        for sample in samples:
            for run_n in range(1, args.runs + 1):
                for attempt in range(2):
                    res = run_one(browser, device, sample, run_n)
                    print(json.dumps(res, ensure_ascii=False),
                          flush=True)
                    table.append(res)
                    if res.get("pass") or attempt == 1:
                        break
                    print("RETRY %s run %d" % (sample, run_n),
                          flush=True)
        browser.close()
    with open(os.path.join(DESK_DIR, "results.json"), "w",
              encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=1)
    print("SAMPLES-E2E-DONE %d runs" % len(table), flush=True)


if __name__ == "__main__":
    main()
