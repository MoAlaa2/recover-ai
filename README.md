# ReCover — AI Fabric and Upholstery Consultant

> **"Change the look, not the furniture."**

ReCover is an AI consultant that recommends suitable fabrics and upholstery
for furniture pieces from a photo, with practical explanations for each choice.

## Models

- **muse-spark-1.3** — analysis and conversation
- **muse-image-1.0** — image generation
- **SAM 3.1** — upholstery region segmentation

## Setup

1. Put the key in the environment file only (never hardcode it):

   ```bash
   echo 'MODEL_API_KEY=...' > .env
   ```

2. Install dependencies and run (once app code is added later):

   ```bash
   pip install -r requirements.txt
   ```

## Project structure

```text
recover-ai/
├── app/            # FastAPI code (added later)
│   ├── api/        # routers
│   ├── core/       # settings (reads the key from .env only)
│   ├── services/   # model integrations
│   └── schemas/    # Pydantic models
├── tests/          # tests
├── uploads/        # uploaded images (gitignored)
├── results/        # generated results (gitignored)
├── requirements.txt
└── README.md
```

## Language rule

- All code, comments, commit messages, docs, and README are in English.
- The app itself is bilingual for end users: the consultant replies in the
  customer's language (English, Arabic in refined Saudi dialect, or any other
  language they write in).
- The UI defaults to English with an Arabic toggle (RTL).

## Fixed rules

- All code is new and does not depend on any legacy files.
- The key is read from `.env` only and must never appear in code.
- Python + FastAPI.
- Never change anything working without asking the project owner.
- Commit after every working step.
