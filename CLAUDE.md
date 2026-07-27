# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Requirements

Python 3.11+, Node.js 18+, npm 9+, Docker. Local HTTP proxy needed for overseas RSS sources.

## Commands

### Backend (from `backend/`)
```bash
uvicorn app.main:app --reload --port 8000   # dev server
pytest tests/ -v                              # full test suite
pytest tests/test_fetcher.py -v               # single test file
pytest tests/test_fetcher.py::test_fn -k keyword  # single test or by keyword
python -m app.scripts.probe_sources [--proxy] # test RSS source reachability
```

> If `uvicorn` can't find modules, run from `backend/` dir or set `PYTHONPATH=.` first. Same applies to `pytest`.

### Frontend (from `frontend/`)
```bash
npm run dev    # dev server on 0.0.0.0:3000
npm run build  # production build
```

### Docker (from project root)
```bash
docker-compose up -d                    # start all services
docker-compose up --build -d            # rebuild and start
docker-compose down                     # stop all services
docker logs news-backend -f             # view backend logs
docker ps                               # check container status
# 4 containers: backend, frontend, nginx, rsshub (RSSHub proxy for some sources)
```

## Architecture

### Data Pipeline (7 steps, `app/pipeline/orchestrator.py`)

```
fetch_all_sources → filter_by_time → classify_and_score → select_top_per_cat
    → extract_full_text → summarize → persist
```

- **fetch**: async concurrent RSS, semaphore=10, dedup by link AND (source_id, guid) — both checks required due to UNIQUE constraint on raw_articles
- **classify**: LLM batch (60 items/batch, see `_BATCH_SIZE` in `classifier.py`), assigns category + importance 0-100
- **select**: top 8 per category by importance
- **extract**: trafilatura for full text, fallback to raw_summary
- **summarize**: LLM per-article → summary, full_summary, viewpoints, background
- **persist**: final 6 items per category to `news_items` table

Pipeline runs daily at 08:00 Asia/Shanghai via APScheduler. Manual trigger: `POST /api/admin/refresh`. Pipeline log: `/app/logs/pipeline.log` (inside container).

### Frontend-Backend Connection

- Dev: Next.js rewrites `/api/*` → `http://127.0.0.1:8000/api/*` (in `next.config.ts`)
- Production (Docker): Nginx reverse proxy, `/api/*` → `backend:8000`
- `app/page.tsx` is a server component (exports `dynamic="force-dynamic"`) that renders `HomeContent.tsx` (client component)
- `HomeContent` auto-triggers pipeline if today's data is empty, polls status every 5s

### Production Deployment

- Server: Tencent Cloud Lightweight (Beijing), 4核4GB, IP: 82.156.105.34
- Access: http://82.156.105.34
- Docker Compose: `backend` + `frontend` + `nginx` containers
- Data persistence: Docker volumes (`sqlite-data`, `backend-logs`)
- No proxy configured: overseas RSS sources may fail

### Database

SQLite (WAL mode), 5 tables: `users`, `sources`, `raw_articles`, `news_items`, `favorites`. Schema auto-created via SQLAlchemy `create_all` on startup — no migration files.

### Config Files

- `backend/.env` — LLM credentials (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`), `PROXY_URL`, `DATABASE_URL`
- `backend/config/sources.yaml` — 45 RSS sources with `use_proxy` and `enabled` flags
- `backend/config/categories.yaml` — 8 categories with descriptions. **Must stay in sync** with `CATEGORIES` list in `app/pipeline/classifier.py`

## Multi-Session Workflow

Users may develop across multiple devices/sessions. These rules prevent context loss.

### Session Start
1. `git pull` to get latest code and SESSION_LOG.md
2. Read `SESSION_LOG.md` for recent activity from other sessions
3. Check `git log --oneline -10` for recent commits

### After Completing Important Tasks (mandatory)
- **Remind user to push**: After any meaningful task (feature, bugfix, config change), remind user to `git push`
- Update `SESSION_LOG.md` with: what was done, why, key decisions, related files, open issues
- Commit SESSION_LOG.md updates alongside the push

### What Counts as "Important"
- Anything that changes project behavior or structure (new feature, fix, refactor, config change)
- NOT: reading code for exploration, answering questions, discussing unimplemented plans

## Test Pattern

Tests use in-memory SQLite (`StaticPool`) and monkeypatch `start_scheduler`/`stop_scheduler`/`init_db`/`sync_sources` to isolate from real DB and scheduler. See `backend/tests/conftest.py`. The `make_news` fixture is a factory for inserting `NewsItem` rows.

## Gotchas

- **Next.js 16 breaking changes**: read `node_modules/next/dist/docs/` before modifying routing or config
- **shadcn/ui 4.7.0** uses base-nova style with `@base-ui/react` primitives, not Radix
- **Overseas RSS sources** require `PROXY_URL` in `.env` (default `http://127.0.0.1:7897`)
- **LLM provider**: OpenAI SDK pointed at DeepSeek-compatible endpoint. Default model: `deepseek-chat`
- **No DB migrations**: schema changes require dropping the SQLite file or manual Alembic migration
- **Docker healthcheck**: use `127.0.0.1` not `localhost` (IPv6 issue)
- **BuildKit issue**: use `DOCKER_BUILDKIT=0` if BuildKit fails to pull images
- **JWT secret** comes from `JWT_SECRET` in `backend/.env` (`settings.jwt_secret`); if unset, a random per-process key is generated — all logins invalidate on restart
- **Admin endpoints**: `/api/admin/refresh` and `/api/admin/status` stay anonymous (homepage auto-trigger), but refresh has cooldown + anonymous daily limits; other `/api/admin/*` endpoints require admin JWT
- **Date/timezone**: `new Date().toISOString()` returns UTC. In China (UTC+8), after midnight this returns yesterday's date. All date functions must use local timezone: `getFullYear()`, `getMonth()`, `getDate()`. See `frontend/lib/utils.ts` and `frontend/components/DateSwitcher.tsx`
- **Next.js static caching**: Pages with `"use client"` are still statically prerendered with `s-maxage=31536000`. For pages that must be dynamic (e.g. homepage with date-dependent data), use a server component wrapper that exports `export const dynamic = "force-dynamic"` and renders the client component
- **Pipeline partial writes**: The orchestrator commits per-category, so a crash mid-pipeline writes partial data (e.g. "ai" succeeds, then "tech" crashes → only ai data persists). `app/pipeline/llm.py::extract_json` with `expect="dict"` must only return `dict`, never `list`
