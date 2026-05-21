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

# context-mode — MANDATORY routing rules

You have context-mode MCP tools available. These rules are NOT optional — they protect your context window from flooding. A single unrouted command can dump 56 KB into context and waste the entire session.

## BLOCKED commands — do NOT attempt these

### curl / wget — BLOCKED
Any Bash command containing `curl` or `wget` is intercepted and replaced with an error message. Do NOT retry.
Instead use:
- `ctx_fetch_and_index(url, source)` to fetch and index web pages
- `ctx_execute(language: "javascript", code: "const r = await fetch(...)")` to run HTTP calls in sandbox

### Inline HTTP — BLOCKED
Any Bash command containing `fetch('http`, `requests.get(`, `requests.post(`, `http.get(`, or `http.request(` is intercepted and replaced with an error message. Do NOT retry with Bash.
Instead use:
- `ctx_execute(language, code)` to run HTTP calls in sandbox — only stdout enters context

### WebFetch — BLOCKED
WebFetch calls are denied entirely. The URL is extracted and you are told to use `ctx_fetch_and_index` instead.
Instead use:
- `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` to query the indexed content

## REDIRECTED tools — use sandbox equivalents

### Bash (>20 lines output)
Bash is ONLY for: `git`, `mkdir`, `rm`, `mv`, `cd`, `ls`, `npm install`, `pip install`, and other short-output commands.
For everything else, use:
- `ctx_batch_execute(commands, queries)` — run multiple commands + search in ONE call
- `ctx_execute(language: "shell", code: "...")` — run in sandbox, only stdout enters context

### Read (for analysis)
If you are reading a file to **Edit** it → Read is correct (Edit needs content in context).
If you are reading to **analyze, explore, or summarize** → use `ctx_execute_file(path, language, code)` instead. Only your printed summary enters context. The raw file content stays in the sandbox.

### Grep (large results)
Grep results can flood context. Use `ctx_execute(language: "shell", code: "grep ...")` to run searches in sandbox. Only your printed summary enters context.

## Tool selection hierarchy

1. **GATHER**: `ctx_batch_execute(commands, queries)` — Primary tool. Runs all commands, auto-indexes output, returns search results. ONE call replaces 30+ individual calls.
2. **FOLLOW-UP**: `ctx_search(queries: ["q1", "q2", ...])` — Query indexed content. Pass ALL questions as array in ONE call.
3. **PROCESSING**: `ctx_execute(language, code)` | `ctx_execute_file(path, language, code)` — Sandbox execution. Only stdout enters context.
4. **WEB**: `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` — Fetch, chunk, index, query. Raw HTML never enters context.
5. **INDEX**: `ctx_index(content, source)` — Store content in FTS5 knowledge base for later search.

## Subagent routing

When spawning subagents (Agent/Task tool), the routing block is automatically injected into their prompt. Bash-type subagents are upgraded to general-purpose so they have access to MCP tools. You do NOT need to manually instruct subagents about context-mode.

## Output constraints

- Keep responses under 500 words.
- Write artifacts (code, configs, PRDs) to FILES — never return them as inline text. Return only: file path + 1-line description.
- When indexing content, use descriptive source labels so others can `ctx_search(source: "label")` later.

## ctx commands

| Command | Action |
|---------|--------|
| `ctx stats` | Call the `ctx_stats` MCP tool and display the full output verbatim |
| `ctx doctor` | Call the `ctx_doctor` MCP tool, run the returned shell command, display as checklist |
| `ctx upgrade` | Call the `ctx_upgrade` MCP tool, run the returned shell command, display as checklist |
