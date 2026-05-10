# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Requirements

Python 3.11+, Node.js 18+, npm 9+. Local HTTP proxy needed for overseas RSS sources.

## Commands

### Backend (from `backend/`)
```bash
uvicorn app.main:app --reload --port 8000   # dev server
pytest tests/ -v                              # all 31 tests
pytest tests/test_fetcher.py -v               # single test file
pytest tests/test_fetcher.py::test_fn -k keyword  # single test or by keyword
python -m app.scripts.probe_sources [--proxy] # test RSS source reachability
```

> If `uvicorn` can't find modules, run from `backend/` dir or set `PYTHONPATH=.` first.

### Frontend (from `frontend/`)
```bash
npm run dev    # dev server on 0.0.0.0:3000
npm run build  # production build
```

## Architecture

### Data Pipeline (7 steps, `app/pipeline/orchestrator.py`)

```
fetch_all_sources → filter_by_time → classify_and_score → select_top_per_cat
    → extract_full_text → summarize → persist
```

- **fetch**: async concurrent RSS, semaphore=10, dedup by source_id+guid
- **classify**: LLM batch (40 items/batch), assigns category + importance 0-100
- **select**: top 8 per category by importance
- **extract**: trafilatura for full text, fallback to raw_summary
- **summarize**: LLM per-article → summary, full_summary, viewpoints, background
- **persist**: final 6 items per category to `news_items` table

Pipeline runs daily at 08:00 Asia/Shanghai via APScheduler. Manual trigger: `POST /api/admin/refresh`.

### Frontend-Backend Connection

- Dev: Next.js rewrites `/api/*` → `http://127.0.0.1:8000/api/*` (in `next.config.ts`)
- Production: set `NEXT_PUBLIC_API_URL` env var
- `app/page.tsx` is a client component — auto-triggers pipeline if today's data is empty, polls status every 5s

### Database

SQLite (WAL mode), 4 tables: `sources`, `raw_articles`, `news_items`, `favorites`. Schema auto-created via SQLAlchemy `create_all` on startup — no migration files.

### Config Files

- `backend/.env` — LLM credentials (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`), `PROXY_URL`, `DATABASE_URL`
- `backend/config/sources.yaml` — 45 RSS sources with `use_proxy` and `enabled` flags
- `backend/config/categories.yaml` — 8 categories with descriptions. **Must stay in sync** with `CATEGORIES` list in `app/pipeline/classifier.py`

## Gotchas

- **Next.js 16 breaking changes**: read `node_modules/next/dist/docs/` before modifying routing or config
- **shadcn/ui 4.7.0** uses base-nova style with `@base-ui/react` primitives, not Radix
- **Overseas RSS sources** require `PROXY_URL` in `.env` (default `http://127.0.0.1:7897`)
- **LLM provider**: OpenAI SDK pointed at DeepSeek-compatible endpoint. Default model: `deepseek-chat`
- **No DB migrations**: schema changes require dropping the SQLite file or manual Alembic migration
