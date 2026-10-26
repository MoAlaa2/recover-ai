# ReCover — AI Fabric and Upholstery Consultant

> **"Change the look, not the furniture."**

ReCover is an AI consultant that recommends suitable fabrics and upholstery
for furniture pieces, with practical explanations for each choice.

## Models

- **muse-spark-1.3** — analysis, conversation, verification, tagging
- **muse-image-1.0** — swatch image generation
- **SAM 3.1** — upholstery region segmentation (planned)

## Fabric catalog

80 fabrics in `data/fabric_specs.json`, 5 collections x 16 (8 plain +
8 patterned): Velvet Luxe (FA-VL), Natural Living (FA-NL), Light & Air
sheers (FA-LA), Shade & Calm opaque curtains (FA-SC), Accent cushions
(FA-AC, incl. 2 Saudi Sadu patterns). Each fabric carries EN/AR names and
descriptions, material specs, features, pricing, and an image prompt.

Pipeline (all keys from `.env` only):

- `scripts/generate_images.py` — renders `data/catalog/[code].jpg`
  (`--test`, `--only`, `--force`).
- `scripts/verify_catalog.py` — scores every swatch against its spec
  with vision (`--only`), writes `data/verify_report.json`.
- `scripts/fix_catalog.py` — rewrites weak prompts, regenerates,
  re-verifies (keeps the best of 2 tries), logs to `data/fix_log.json`.
- `scripts/tag_snag_risk.py` — vision-tags `snag_risk`
  (low/medium/high) for pet safety.
- `scripts/contact_sheet.py` — builds `data/contact_sheet.html`, a
  review grid with scores and snag chips.

## Consultant (backend only, no UI yet)

`app/services/consultant.py` is a real multi-turn agent on
muse-spark-1.3 with native tool calling: `search_catalog`,
`get_fabric`, `analyze_room`. The model never sees the full catalog.

- Session memory per `session_id` (in-memory); needs accumulate
  across turns.
- Expert rules merged into every search: needs mapping (pets, kids,
  hotel, allergies), pet-safe filtering (no boucle/honeycomb, tight
  weaves first), vision-based snag gate for pets (low only, medium as
  fallback), functional-fit ranking, in-budget preference, honest
  relaxed-constraint disclosure, light-color warnings for kids/pets,
  piece confirmation from room photos.
- Scope guard: home topics are answered; math, coding, news, personal
  advice and the like get one polite decline line, no model call.
- Replies in the user's language (Saudi dialect Arabic supported);
  language is detected in code and pinned per session.

API (`app/`, FastAPI):

- `POST /api/chat {session_id, message, image_path?}` →
  `{reply, recommendations[], room_analysis?}`
- `POST /api/upload` — image upload, converts webp/heic to JPG.

## Eval suite

`scripts/eval_scenarios.py` + `data/scenarios.json`: 15 scripted
multi-turn scenarios checked against catalog fields (fire resistance,
Martindale, blackout, snag risk, Sadu presence, 5-language replies,
off-topic handling, ...). Writes `data/eval_report.json`.

## Run everything

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# API + terminal chat
uvicorn app.main:app --port 8000
python scripts/chat_cli.py

# Catalog pipeline
python scripts/generate_images.py --test
python scripts/verify_catalog.py
python scripts/fix_catalog.py
python scripts/tag_snag_risk.py
python scripts/contact_sheet.py

# Tests and eval
pytest tests/ -q
python scripts/eval_scenarios.py [--only <scenario>]
```

## Project structure

```text
recover-ai/
├── app/                # FastAPI app
│   ├── api/            # chat + upload routes
│   ├── core/           # settings (key from .env only)
│   ├── services/       # catalog store + consultant agent
│   └── schemas/        # (reserved for Pydantic models)
├── data/               # specs, catalog images, reports, sheet
├── scripts/            # catalog + eval tooling
├── tests/              # pytest suite
├── uploads/            # uploaded images (gitignored)
├── results/            # generated results (gitignored)
├── requirements.txt
└── README.md
```

## Fixed rules

- All code is new and does not depend on any legacy files.
- The key is read from `.env` only and must never appear in code.
- Python + FastAPI.
- Never change anything working without asking the project owner.
- Commit after every working step.

## Language rule

- All code, comments, commit messages, docs, and README are in English.
- The app itself is bilingual for end users: the consultant replies in the
  customer's language (English, Arabic in refined Saudi dialect, or any other
  language they write in).
- The UI defaults to English with an Arabic toggle (RTL).
