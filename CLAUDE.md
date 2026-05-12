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

## Documentation Structure

When generating or placing documentation files:
- Backend docs → `docs/Backend/` (endpoints → `docs/Backend/Endpoints/`)
- Frontend docs → `docs/Frontend/`
- Database docs → `docs/Database/`
- DevOps docs → `docs/DevOps/`

## Design System

- All colors must use CSS variables from `frontend/app/globals.css` — never hardcode hex values, `green`, `red`, or Tailwind color literals
- P&L colors, brand colors, chart colors, and elevation shadows all come from CSS tokens defined there
- Before adding any color, check `globals.css` for the correct variable name
- Dark mode: cards must contrast against the page background — test both modes when touching background/card colors
- Check for per-component `border` classes when adjusting global border CSS — they override base rules

## Multi-Currency

- Any sizing, sorting, or aggregation across positions MUST normalize to a single currency first
- Display currency as ISO codes (USD, THB, etc.) — never symbols ($, ฿, €)
- LLM pricing is centralized — update `backend/llm_pricing.py` and `frontend/llmPricing.ts` together and keep them in sync

## Migrations & Schema

- Never edit an already-applied migration file — always create a new `alembic revision` for schema changes
- Use `Decimal` (not `float`) for all monetary and financial fields in Python models and Pydantic schemas

## Quality Checks

After any significant implementation, run a self-review pass before declaring done:

1. **Cache/state** — no overwrite bugs where new data silently drops existing entries
2. **TypeScript** — no type errors (hook runs `tsc --noEmit` automatically, check its output)
3. **Currency** — cross-position math is normalized
4. **Design tokens** — no hardcoded colors; all values from `globals.css`
5. **Visualizations** — verify axis orientation, alternation logic, and fallback positioning with 3 test cases: (a) mixed currencies, (b) single item, (c) extreme aspect ratio

## Git

User handles all git operations manually.

- NEVER run `git add`, `git commit`, or `git push` — not even as a final step
- NEVER include commit/push steps in plans, brainstorms, or task lists — omit them entirely, not just mark them optional
- If a plan naturally ends at "implementation complete", stop there — git is the user's responsibility

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

---

## MCP Tools: Serena

Use Serena for **precise symbol-level navigation** when code-review-graph doesn't have enough detail.

| Tool                       | Use when                                              |
| -------------------------- | ----------------------------------------------------- |
| `find_symbol`              | Locate a function/class/variable by name              |
| `find_declaration`         | Go-to-definition for a symbol                         |
| `find_referencing_symbols` | Find all usages of a symbol across the codebase       |
| `find_implementations`     | Find all implementations of an interface/base class   |
| `get_diagnostics_for_file` | Check type errors and lint issues in a file           |
| `get_symbols_overview`     | List all symbols in a file                            |
| `rename_symbol`            | Rename a symbol safely across the codebase            |

**CRITICAL:** Call `initial_instructions` at the start of any coding task to load the Serena manual.

---

## Tool Priority for Code Exploration

Follow this order — stop at the first layer that answers the question:

1. **code-review-graph** — impact analysis, architecture, relationships, code review
2. **Serena** — precise symbol lookup, find-usages, diagnostics, rename
3. **Grep/Glob/Read** — only if both MCP tools don't cover the need
