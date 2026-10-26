"""Build a review grid of all catalog swatches.

Reads data/fabric_specs.json and data/verify_report.json (when present)
and writes data/contact_sheet.html: one card per fabric with its swatch,
code, English name, price, and verify scores.
"""
import html
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS_PATH = os.path.join(BASE_DIR, "data", "fabric_specs.json")
REPORT_PATH = os.path.join(BASE_DIR, "data", "verify_report.json")
OUT_PATH = os.path.join(BASE_DIR, "data", "contact_sheet.html")
PASS_MARK = 7


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def score_cell(value):
    if value is None:
        return '<span class="na">n/a</span>'
    cls = "ok" if value >= PASS_MARK else "low"
    return '<span class="%s">%d</span>' % (cls, value)


def main():
    specs = load_json(SPECS_PATH, [])
    report = {r["code"]: r for r in load_json(REPORT_PATH, [])}

    by_collection = {}
    for item in specs:
        by_collection.setdefault(item["collection"], []).append(item)

    parts = ["<!DOCTYPE html>", "<html lang=\"en\">", "<head>",
             "<meta charset=\"utf-8\">",
             "<title>ReCover catalog review</title>",
             "<style>",
             "body{font-family:-apple-system,Segoe UI,Helvetica,Arial,"
             "sans-serif;margin:24px;color:#222;background:#fff}",
             "h1{font-size:22px}h2{font-size:17px;margin-top:28px;"
             "border-bottom:1px solid #ddd;padding-bottom:4px}",
             ".grid{display:flex;flex-wrap:wrap;gap:12px}",
             ".card{width:180px;border:1px solid #ddd;padding:8px}",
             ".card img{width:100%;aspect-ratio:1;object-fit:cover;"
             "display:block;background:#eee}",
             ".code{font-size:12px;color:#555;margin-top:6px}",
             ".name{font-size:14px;font-weight:600}",
             ".price{font-size:13px}",
             ".scores{font-size:12px}",
             ".ok{color:#1a7f37;font-weight:700}",
             ".low{color:#b42318;font-weight:700}",
             ".na{color:#888}",
             "</style>", "</head>", "<body>",
             "<h1>ReCover catalog review (%d fabrics)</h1>" % len(specs)]

    for collection, items in by_collection.items():
        parts.append("<h2>%s (%d)</h2>" % (html.escape(collection),
                                          len(items)))
        parts.append('<div class="grid">')
        for item in items:
            rep = report.get(item["code"], {})
            parts.append(
                '<div class="card">'
                '<img src="catalog/%s.jpg" alt="%s" loading="lazy">'
                '<div class="code">%s</div>'
                '<div class="name">%s</div>'
                '<div class="price">%d SAR/m</div>'
                '<div class="scores">color %s pattern %s material %s</div>'
                '<div class="scores">%s</div>'
                "</div>" % (
                    item["code"], html.escape(item["code"]),
                    html.escape(item["code"]),
                    html.escape(item["name_en"]),
                    item["price_sar_per_m"],
                    score_cell(rep.get("color_match")),
                    score_cell(rep.get("pattern_match")),
                    score_cell(rep.get("material_look")),
                    html.escape(rep.get("issues", "not verified")),
                ))
        parts.append("</div>")

    parts += ["</body>", "</html>"]
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print("wrote %s with %d cards" % (OUT_PATH, len(specs)))


if __name__ == "__main__":
    main()
