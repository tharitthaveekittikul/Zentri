# Zentri — Design Specification

**Date:** 2026-04-22  
**Status:** Approved  
**Project:** Zentri — Privacy-First Personal Financial OS

---

## 1. Project Overview

Zentri is an open-source, privacy-first financial operating system that aggregates diverse assets (Thai/Global Stocks, Mutual Funds, Crypto, Gold) and leverages LLMs to provide institutional-grade analysis — all running locally via Docker to ensure data sovereignty.

**North Star:** Tell the user what to do with their holdings right now, in plain language. The user is a developer, not a financial professional. The LLM reads the documents they don't want to read and gives reasoned BUY/SELL/HOLD recommendations.

**Asset Universe:** US Stocks (primary), Thai Stocks (SET), Thai Mutual Funds, Crypto, Gold

---

## 2. System Architecture

### Approach: Backend + Worker Separation

FastAPI handles API requests. A separate Python ARQ worker handles all background jobs (price fetching, PDF ingestion, LLM analysis). Both share PostgreSQL/TimescaleDB via Redis job queue.

```
nginx → Next.js (frontend)
     → FastAPI (API)
PostgreSQL + TimescaleDB
Redis (job queue + cache)
Python Worker (ARQ)
ChromaDB (vector store)
Ollama (optional — local LLM, native on Mac, Docker on Linux/Windows)
```

### Docker Services

| Service    | Purpose                        | Port  |
|------------|--------------------------------|-------|
| nginx      | Reverse proxy (single entry)   | 80    |
| frontend   | Next.js app                    | 3000  |
| backend    | FastAPI API                    | 8000  |
| worker     | ARQ background jobs            | —     |
| postgres   | PostgreSQL + TimescaleDB       | 5432  |
| redis      | Job queue + cache              | 6379  |
| chromadb   | Vector store for RAG           | 8001  |
| ollama     | Local LLM (optional profile)   | 11434 |

### Monorepo Structure

```
zentri/
├── frontend/          # Next.js 15 (App Router)
├── backend/           # FastAPI + ARQ worker
│   ├── app/           # FastAPI application
│   ├── worker/        # ARQ background jobs
│   └── alembic/       # DB migrations
├── nginx/
├── docker-compose.yml
├── docker-compose.override.yml  # dev hot-reload
├── .env.example
└── docs/
    ├── setup.md
    ├── gpu-setup.md
    └── api-keys.md
```

---

## 3. Data Model

### Core Tables

```sql
-- users
id, username, password_hash, created_at

-- platforms (brokerage apps)
id, user_id, name, asset_types_supported (JSONB), notes

-- assets (master list)
id, user_id, symbol, asset_type (us_stock|thai_stock|th_fund|crypto|gold),
name, currency, metadata (JSONB)

-- holdings
id, user_id, asset_id, quantity, avg_cost_price, currency

-- transactions
id, user_id, asset_id, platform_id,
type (buy|sell|dividend), quantity, price, fee,
source (manual|csv_import), executed_at

-- prices [TimescaleDB hypertable]
asset_id, timestamp, open, high, low, close, volume

-- ai_analyses
id, user_id, asset_id, verdict (buy|sell|hold),
target_price, reasoning (text),
model_used, tokens_in, tokens_out, cost_usd, created_at

-- llm_conversations
id, user_id, ai_analysis_id, role (user|assistant),
content, tokens, created_at

-- watchlist
id, user_id, asset_id, ai_thesis (text),
suggested_entry_price, created_at

-- documents
id, user_id, asset_id,
doc_type (10k|10q|fund_fact|set_report|other),
filename, chroma_collection_id,
ingested_at, status, page_count

-- pipeline_logs
id, job_type (price_fetch|pdf_ingest|llm_analysis|dividend_fetch|watchlist_scan),
status (queued|running|done|failed),
started_at, finished_at, error_message

-- llm_settings
id, user_id, provider (ollama|openai|claude|gemini),
model_name, api_key (AES-256 encrypted), is_default

-- import_profiles
id, user_id, broker_name, column_mapping (JSONB)

-- net_worth_snapshots
id, user_id, total_value, total_cost,
breakdown (JSONB), snapshot_at

-- dividends
id, user_id, asset_id, amount_per_unit, total_amount,
ex_dividend_date, pay_date,
status (upcoming|received), currency

-- benchmarks
id, symbol (^GSPC, ^SET), name
-- benchmark prices stored in prices hypertable
```

### Key Design Decisions

- `user_id` on all tables → multi-user ready from day one
- `prices` as TimescaleDB hypertable → efficient time-series chart queries
- API keys encrypted with AES-256, key derived from `JWT_SECRET`
- `transactions.platform_id` → tracks which broker app each purchase came from
- `import_profiles` → saved column mappings per broker for future CSV imports

---

## 4. Feature Modules (11 Modules)

| # | Module | Purpose |
|---|--------|---------|
| 1 | Auth | First-launch setup wizard, JWT, single-user with multi-user-ready schema |
| 2 | Portfolio | Holdings management, manual entry, CSV import (smart mapper + presets), export |
| 3 | Price Feed Worker | ARQ jobs: yfinance (US), CoinGecko (crypto), gold feed, SET scraper (TBD), Thai fund scraper (TBD) |
| 4 | Charts | lightweight-charts (open-source TradingView engine) per asset detail page |
| 5 | AI Analysis | Core: fetch data → ChromaDB RAG → LLM prompt → BUY/SELL/HOLD verdict + reasoning + target price |
| 6 | Document Intelligence | PDF upload/auto-fetch → text extract → chunk → embed → ChromaDB |
| 7 | Watchlist & Discovery | AI scans universe → surfaces candidates with thesis and entry price |
| 8 | LLM Usage & Logs | Per-analysis cost, token tracking, conversation history, provider switcher |
| 9 | Market Overview | Portfolio total, daily +/-, vs benchmark (S&P500/SET50), allocation donut, AI alerts |
| 10 | Net Worth Timeline | Daily snapshot worker → wealth history chart |
| 11 | Dividend Calendar | Ex-div + pay dates, annual income total, per-asset history |

### AI Analysis Flow (Module 5)

```
fetch prices + holdings
  → search ChromaDB for relevant document chunks
  → build LLM prompt with context
  → LLM returns: verdict + reasoning + target_price
  → save to ai_analyses + llm_conversations
  → display on dashboard
```

### Background Jobs (ARQ Worker)

| Job | Trigger | Schedule |
|-----|---------|----------|
| fetch_prices | Auto | Every 15min (market hours) |
| take_net_worth_snapshot | Auto | Daily midnight |
| ingest_document | POST /documents/upload | On demand |
| run_analysis | POST /analysis/{symbol} | On demand |
| scan_watchlist | POST /watchlist/scan | On demand |
| fetch_dividends | Auto | Weekly |

---

## 5. Frontend Pages

**Tech Stack:** Next.js 15 (App Router), shadcn/ui + Radix UI, Tailwind CSS, TanStack Query, TanStack Table, Zustand, lightweight-charts, recharts (via shadcn Chart)

### Routes

| Route | Page | Key Components |
|-------|------|----------------|
| `/login` | Login | Form, JWT cookie |
| `/setup` | First-launch wizard | Hardware detect, LLM config |
| `/` | Market Overview | Portfolio total, benchmark chart, allocation donut, AI alerts |
| `/portfolio` | Holdings list | DataTable, import drawer, add asset dialog |
| `/portfolio/[symbol]` | Asset detail | lightweight-charts, BUY/SELL/HOLD card, transactions |
| `/watchlist` | AI discovery | Candidate cards, entry thesis, promote button |
| `/net-worth` | Wealth timeline | recharts line chart, breakdown |
| `/dividends` | Dividend calendar | Calendar view, annual income |
| `/documents` | Doc library | Upload, ingest status per asset |
| `/pipeline` | Job monitor | SSE live feed, status badges, error details |
| `/ai-usage` | LLM cost tracker | Cost table, conversation logs |
| `/settings` | Configuration | LLM config, API keys, platforms, benchmarks, universe |

### Key UI Decisions

- **Privacy Mode** — toggle in top nav, replaces all monetary values with `••••`, persisted in localStorage
- **Global Search** — ⌘K Command palette across portfolio + watchlist
- **CSV Import** — Sheet (slide-over) drawer, 3-layer: broker presets → LLM auto-map → manual override
- **shadcn/ui** — Card, DataTable, Badge, Dialog, Sheet, Command, Calendar, Sonner, Progress, Collapsible, Switch

---

## 6. API Design

All endpoints: `POST /api/v1`. Auth via JWT Bearer.

### Domains

- **Auth:** setup, login, logout, me, refresh
- **Portfolio:** holdings CRUD, transactions, import (preview + confirm), export, summary
- **Assets:** search, detail, price, history (OHLCV), dividends
- **Analysis:** trigger, latest, history, conversation log
- **Watchlist:** list, add (manual), scan (AI), delete, promote to portfolio
- **Documents:** list, upload, delete, re-ingest
- **Overview:** summary, performance vs benchmark, allocation
- **Net Worth:** timeline, latest
- **Dividends:** calendar, history, summary
- **Pipeline:** jobs list, job detail, SSE stream, manual trigger
- **LLM:** usage list, usage summary
- **Settings:** get/put general, LLM config, hardware detect, benchmarks, platforms CRUD, universe get/put, test-llm

---

## 7. Docker & Deployment

### Environment Variables (`.env` — minimal, infrastructure only)

```bash
POSTGRES_PASSWORD=changeme
JWT_SECRET=run-openssl-rand-hex-32
TZ=Asia/Bangkok
PRICE_FETCH_INTERVAL=15
OLLAMA_HOST=http://host.docker.internal:11434
```

All user-facing config (API keys, LLM model selection, benchmarks) stored in DB, encrypted, managed via Settings page.

### LLM Setup by Platform

| Platform | Ollama approach |
|----------|----------------|
| Mac M-series | Run Ollama natively (`brew install ollama`), worker connects via `host.docker.internal:11434` |
| Linux/Windows + NVIDIA | `docker compose --profile local-llm up` — NVIDIA Container Toolkit required |
| No GPU / cloud-only | Skip Ollama, configure API key in Settings |

### LLM Model Recommendations

| Hardware | Recommended Local Model | Cloud Fallback |
|----------|------------------------|----------------|
| M3 Pro 18GB | llama3.1:8b or mistral:7b | Claude/GPT-4 for deep analysis |
| RTX 3070 Ti 8GB VRAM | mistral:7b-q4 | Claude/GPT-4 for deep analysis |

**Strategy:** Local = fast triage/summaries. Cloud = deep analysis and final recommendations.

### First-Time Setup

```bash
git clone https://github.com/yourname/zentri
cd zentri
cp .env.example .env
# edit .env (5 lines)
docker compose up -d
# open http://localhost → setup wizard
```

### Data Persistence

All volumes survive `docker compose down`:
- `postgres_data` — portfolio, transactions, analyses
- `redis_data` — job queue state
- `chroma_data` — embedded documents
- `ollama_data` — downloaded LLM models

### Backup

```bash
scripts/backup.sh   # → backups/YYYY-MM-DD.tar.gz
scripts/restore.sh  # ← restore from backup file
```

---

## 8. Configuration Architecture

### Two-Tier Config

**Tier 1 — `.env`** (infrastructure, set once):
Database password, JWT secret, timezone, price fetch interval, Ollama host

**Tier 2 — App Settings DB** (user-configurable at runtime via UI):
LLM provider, model, API keys (encrypted), Polygon key, CoinGecko key, benchmarks, universe, platforms

### Multi-User Readiness

- All tables have `user_id` foreign key
- Upgrade path: add users table + registration/login + row-level security
- No architectural changes needed — just additive work

---

## 9. Open Questions / Future Work

- Thai SET data source (scraper or partner API — TBD by user)
- Thai Mutual Fund data source (AIMC scraper — TBD by user)
- Deep Asset Look-Through (fund deconstruction into weighted holdings)
- Intelligent DCA engine (RSI + mean reversion zone calculation)
- Plugin System (custom Python strategy scripts)
- Multi-user upgrade (Phase N)
