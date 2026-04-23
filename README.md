# Zentri

> Privacy-first personal financial OS — tell me what to do with my holdings, right now, in plain language.

Zentri aggregates US/Thai stocks, Thai mutual funds, crypto, and gold into a single dashboard. An LLM reads the documents you don't want to read and delivers reasoned **BUY / SELL / HOLD** recommendations. Everything runs locally via Docker — your financial data never leaves your machine.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Tailwind v4, shadcn/ui, TanStack Query |
| Backend | FastAPI, SQLAlchemy async, Alembic, Python 3.12+ |
| Background jobs | ARQ + Redis (price fetch, dividend calendar) |
| Database | PostgreSQL 16 + TimescaleDB |
| Vector store | ChromaDB (RAG for financial documents) |
| Local LLM | Ollama (optional — GPU or CPU) |
| Proxy | Nginx |

## Prerequisites

- Docker + Docker Compose v2
- (Optional) Ollama installed natively on Mac for local LLM

## Quick Start

```bash
# 1. Clone
git clone <repo-url> zentri && cd zentri

# 2. Configure
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD and JWT_SECRET (see Environment section)

# 3. Start
docker compose up

# 4. Open
open http://localhost
```

To include the local LLM (Ollama):

```bash
docker compose --profile local-llm up
```

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | Yes | Any strong password |
| `JWT_SECRET` | Yes | Run: `openssl rand -hex 32` |
| `TZ` | Yes | Timezone, e.g. `Asia/Bangkok` |
| `PRICE_FETCH_INTERVAL` | No | Minutes between price syncs (default: `15`) |
| `OLLAMA_HOST` | LLM only | Mac: `http://host.docker.internal:11434`<br>Linux/Windows with `--profile local-llm`: `http://ollama:11434` |

## Architecture

```
zentri/
├── frontend/       Next.js app (port 3000 in dev)
├── backend/
│   ├── app/        FastAPI — routes, models, schemas, services
│   ├── worker/     ARQ background jobs
│   └── alembic/    Database migrations
├── nginx/          Reverse proxy config (port 80)
├── scripts/        backup.sh / restore.sh
├── docs/           Design specs and implementation plans
└── docker-compose.yml
```

**Request flow:** Browser → nginx:80 → frontend:3000 or backend:8000

## Development

Hot-reload is automatic — `docker-compose.override.yml` mounts source directories and enables `--reload` on the backend.

```bash
docker compose up   # starts with override applied automatically
```

### Backend only

```bash
cd backend
uv sync                                              # install deps
uvicorn app.main:app --reload                        # dev server
pytest                                               # run tests
alembic upgrade head                                 # apply migrations
alembic revision --autogenerate -m "description"    # create migration
```

### Frontend only

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
npm run build
npm run lint
```

## Data Backup & Restore

```bash
./scripts/backup.sh
./scripts/restore.sh
```

## Asset Universe

- **US Stocks** (primary)
- **Thai Stocks** (SET)
- **Thai Mutual Funds**
- **Crypto**
- **Gold**
