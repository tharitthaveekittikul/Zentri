---

## Project: Zentri

Privacy-first personal financial OS — aggregates US/Thai stocks, mutual funds, crypto, and gold. LLM-powered BUY/SELL/HOLD recommendations. Runs entirely via Docker for data sovereignty.

## Architecture

```
frontend/   Next.js 16 + React 19 + Tailwind v4 + shadcn/ui
backend/    FastAPI + SQLAlchemy async + Alembic (Python 3.12+)
  app/      API routes, models, schemas, services
  worker/   ARQ background jobs (price fetch, dividend calendar)
nginx/      Reverse proxy — single entry point on :80
docs/       Design specs and implementation plans
```

**Services:** nginx(:80) → frontend(:3000) + backend(:8000) | postgres(:5432, TimescaleDB) | redis(:6379) | chromadb (vector store) | ollama (optional local LLM)

## Commands

### Docker (primary workflow)
```bash
cp .env.example .env          # fill POSTGRES_PASSWORD and JWT_SECRET first
docker compose up             # start all services
docker compose up --profile local-llm  # include Ollama local LLM
docker compose down -v        # stop + wipe volumes
```

### Local dev (with hot-reload via override)
```bash
docker compose up             # uses docker-compose.override.yml automatically
# frontend hot-reloads on :3000, backend on :8000
```

### Backend (inside container or venv)
```bash
cd backend
uv sync                       # install deps
uvicorn app.main:app --reload # dev server
pytest                        # run tests (asyncio_mode=auto)
alembic upgrade head          # apply migrations
alembic revision --autogenerate -m "description"  # new migration
```

### Frontend
```bash
cd frontend
npm install
npm run dev    # :3000
npm run build
npm run lint
```

### Backup / Restore
```bash
./scripts/backup.sh
./scripts/restore.sh
```

## Environment Variables

Required in `.env` before first run:

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | DB password (any strong string) |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `TZ` | Timezone, e.g. `Asia/Bangkok` |
| `PRICE_FETCH_INTERVAL` | Minutes between price jobs (default: 15) |
| `OLLAMA_HOST` | Mac: `http://host.docker.internal:11434`; Linux/Windows with `--profile local-llm`: `http://ollama:11434` |

## Gotchas

- `docker-compose.override.yml` is auto-applied in dev — mounts source dirs and enables hot-reload. Don't commit local hacks there.
- Worker uses `arq` + Redis for job queues. If jobs hang, check Redis health first.
- TimescaleDB image (`timescale/timescaledb-ha:pg16-latest`) — not vanilla Postgres. Alembic migrations must be compatible.
- `bcrypt` is pinned `<5` due to passlib compatibility — don't upgrade without testing auth.
- Frontend `NEXT_PUBLIC_API_URL` is baked at build time in Docker; change it in `docker-compose.yml` environment, not `.env`.

## Git

User handles all git operations manually — do NOT run `git add`, `git commit`, or `git push`.

---

<!-- code-review-graph MCP tools -->

## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool                        | Use when                                               |
| --------------------------- | ------------------------------------------------------ |
| `detect_changes`            | Reviewing code changes — gives risk-scored analysis    |
| `get_review_context`        | Need source snippets for review — token-efficient      |
| `get_impact_radius`         | Understanding blast radius of a change                 |
| `get_affected_flows`        | Finding which execution paths are impacted             |
| `query_graph`               | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes`     | Finding functions/classes by name or keyword           |
| `get_architecture_overview` | Understanding high-level codebase structure            |
| `refactor_tool`             | Planning renames, finding dead code                    |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
