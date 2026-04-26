# Phase 6 — AI/LLM Analysis Design

**Date:** 2026-04-26
**Status:** Approved
**Approach:** Option A — Sequential/Layered

---

## Overview

Phase 6 adds a full AI analysis stack to Zentri. Users can upload PDF research documents, configure an LLM provider, and trigger a BUY/SELL/HOLD analysis on any portfolio asset. The analysis uses RAG (Retrieval-Augmented Generation) to pull relevant document chunks into the LLM prompt alongside live price and holdings data.

---

## Architecture

Seven layers built in dependency order:

```
[Security]          encryption.py — AES-256-GCM for API keys at rest
      ↓
[LLM Abstraction]   llm_service.py — unified interface for Ollama / OpenAI / Claude / Gemini
      ↓
[Vector Store]      rag_service.py + ChromaDB Docker service
      ↓
[Document Pipeline] ingest_document ARQ job — PDF → chunk → embed → ChromaDB
      ↓
[Analysis Engine]   run_analysis ARQ job — RAG + LLM → structured verdict
      ↓
[API Layer]         /documents, /analysis, /settings/llm routers
      ↓
[Frontend]          Document library page, VerdictCard, AI usage page
```

**New Docker service:** `chromadb` added to `docker-compose.yml` with a persistent named volume.

---

## Database Schema

Single Alembic migration (`003_phase6_ai_schema.py`) adds:

### `llm_settings`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| provider | varchar | `ollama`, `openai`, `claude`, `gemini` |
| encrypted_api_key | text | AES-256-GCM encrypted, null for Ollama |
| model | varchar | e.g. `claude-sonnet-4-6`, `gpt-4o` |
| is_active | bool | only one active at a time |
| created_at | timestamptz | |

### `documents`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| filename | varchar | original filename |
| file_path | varchar | path inside Docker volume |
| asset_id | UUID FK nullable | linked asset, null = global |
| status | varchar | `pending`, `processing`, `done`, `failed` |
| chunk_count | int | set after ingestion |
| chroma_collection_id | varchar | ChromaDB collection name |
| error_msg | text | set on failure |
| created_at | timestamptz | |

### `ai_analyses`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| asset_id | UUID FK | |
| job_id | varchar | ARQ job ID |
| verdict | varchar | `BUY`, `SELL`, `HOLD` |
| target_price | numeric nullable | |
| reasoning | text | |
| provider | varchar | |
| model | varchar | |
| tokens_in | int | |
| tokens_out | int | |
| cost_usd | numeric | |
| created_at | timestamptz | |

### `llm_conversations`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| analysis_id | UUID FK | |
| role | varchar | `system`, `user`, `assistant` |
| content | text | |
| message_order | int | message sequence |

---

## Components

### Backend

#### `backend/app/core/encryption.py`
- `encrypt(plaintext: str) -> str` — AES-256-GCM, key derived from `settings.JWT_SECRET` (SHA-256 hash)
- `decrypt(ciphertext: str) -> str`
- Output format: `base64(nonce + ciphertext + tag)`

#### `backend/app/services/llm_service.py`
- Abstract `LLMProvider` with `complete(messages) -> LLMResponse` and `embed(text) -> list[float]`
- `LLMResponse`: `content`, `tokens_in`, `tokens_out`, `cost_usd`
- Concrete providers:
  - `OllamaProvider` — HTTP to Ollama REST API (no key needed)
  - `OpenAIProvider` — `openai` SDK
  - `ClaudeProvider` — `anthropic` SDK, default model `claude-sonnet-4-6`
  - `GeminiProvider` — `google-generativeai` SDK
- `get_llm_provider(db) -> LLMProvider` — loads active `llm_settings` record, decrypts key
- Per-provider pricing table for cost calculation

#### `backend/app/services/rag_service.py`
- `get_or_create_collection(asset_symbol: str | None) -> Collection` — uses `"global"` collection when `asset_symbol` is None
- `add_chunks(collection, chunks: list[str], metadatas: list[dict])` — embed + upsert
- `search(collection, query: str, n_results=5) -> list[str]`
- Default embedding model: `all-MiniLM-L6-v2` (local, via `sentence-transformers`)
- Cloud fallback: `text-embedding-3-small` via OpenAI when active provider is OpenAI

#### `backend/app/api/documents.py`
- `POST /api/v1/documents/upload` — multipart PDF, saves to volume, inserts DB record (status=`pending`), enqueues `ingest_document`
- `GET /api/v1/documents?asset={symbol}` — list with status
- `DELETE /api/v1/documents/{id}` — delete DB record + ChromaDB collection
- `POST /api/v1/documents/{id}/reingest` — reset status to `pending`, re-enqueue

#### `backend/app/api/analysis.py`
- `POST /api/v1/analysis/{symbol}` → 202 `{ job_id }`
- `GET /api/v1/analysis/{symbol}/latest` → latest `ai_analyses` record
- `GET /api/v1/analysis/{symbol}/history` → paginated list
- `GET /api/v1/analysis/{id}/conversation` → ordered `llm_conversations`

#### `backend/app/api/settings.py` (additions)
- `GET /api/v1/settings/llm` — list providers, masked key (`sk-ant-...****`)
- `PUT /api/v1/settings/llm` — save/update provider config, encrypt API key
- `POST /api/v1/settings/test-llm` — decrypt key, send test prompt, return `{ ok, latency_ms }`

#### `backend/worker/jobs/ingest_document.py`
1. Load document record, set status → `processing`
2. Extract text with `PyMuPDF` (`fitz`)
3. Recursive character split: chunk_size=1000, overlap=200
4. Attach metadata: `asset_symbol`, `doc_type`, `page_number`, `document_id`
5. `RAGService.add_chunks()` → ChromaDB
6. Update DB: status=`done`, chunk_count, chroma_collection_id
7. On failure: status=`failed`, error_msg stored
8. Log to `pipeline_logs`, publish `pipeline_events`

#### `backend/worker/jobs/run_analysis.py`
1. Fetch holdings, 90-day price history, latest dividend data for asset
2. `RAGService.search(asset_symbol, query=asset_name, n_results=5)` — may return empty if no docs
3. Build system prompt: financial analyst persona, instructions for JSON output `{ verdict, target_price, reasoning }`
4. Build user prompt: holdings context + price data + RAG chunks (or note "no documents available")
5. `LLMService.complete(messages)` → parse JSON response
6. Retry once with explicit formatting reminder if JSON malformed; mark `failed` if still bad
7. Insert `ai_analyses` record
8. Insert `llm_conversations` records (system, user, assistant messages)
9. Log tokens/cost, publish `pipeline_events`

### Frontend

#### `frontend/components/analysis/VerdictCard.tsx`
- Verdict badge: BUY=green, SELL=red, HOLD=yellow
- Fields: verdict, target_price (masked `••••` in Privacy Mode), reasoning, model_used, cost_usd, created_at
- "Run Analysis" button → `POST /analysis/{symbol}` → subscribe to SSE stream → loading state → refresh on done
- Analysis history dropdown (past verdicts)
- "View Conversation" expandable section
- Embedded on `frontend/app/(auth)/portfolio/[symbol]/page.tsx`

#### `frontend/app/(auth)/documents/page.tsx`
- Document table: symbol, filename, status badge, chunk_count, created_at
- Status badges: pending=gray, processing=blue pulse, done=green, failed=red
- Upload button → dialog (asset selector, doc_type selector, file drop zone)
- Delete button with confirm dialog
- Re-ingest button for failed documents
- Asset filter (search input)

#### `frontend/app/(auth)/ai-usage/page.tsx`
- Summary cards: total spend, this-month spend, total analyses run
- Provider breakdown bar chart (recharts)
- Analysis table: symbol, verdict, model, tokens_in, tokens_out, cost_usd, date
- Expandable conversation log per row (Collapsible)
- Filter by provider + date range picker

---

## Data Flow

### Document Ingestion
```
User uploads PDF
  → POST /documents/upload
  → save file to /app/uploads volume
  → INSERT documents (status=pending)
  → enqueue ingest_document(document_id)
  → ARQ job: PyMuPDF → chunk → embed → ChromaDB
  → UPDATE documents SET status=done, chunk_count=N
  → pipeline_logs + pipeline_events
```

### Analysis
```
User clicks "Run Analysis"
  → POST /analysis/{symbol} → 202 { job_id }
  → Frontend subscribes to SSE (existing pipeline stream)
  → ARQ: fetch holdings + 90d prices + RAGService.search(top 5)
  → build prompt → LLMService.complete()
  → parse { verdict, target_price, reasoning }
  → INSERT ai_analyses + llm_conversations
  → publish pipeline_events (job done)
  → Frontend receives SSE done → refresh VerdictCard
```

### LLM Settings
```
PUT /settings/llm
  → encryption.encrypt(api_key) → INSERT/UPDATE llm_settings
GET /settings/llm
  → return { provider, model, masked_key, is_active }
POST /settings/test-llm
  → encryption.decrypt(key) → send test prompt → return { ok, latency_ms }
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| LLM returns malformed JSON | Retry once with formatting reminder; mark `failed` if still bad |
| ChromaDB unreachable | Ingest job fails fast → status=`failed`, error_msg stored, pipeline log |
| No documents for asset | Analysis proceeds without RAG context; reasoning notes "no documents available" |
| Invalid API key | `test-llm` catches auth error → 400 with provider error message |
| Large PDF | 1000-char chunks with 200 overlap keeps ChromaDB queries performant |

---

## Build Order (Sequential)

1. `encryption.py` + LLM settings migration + `GET/PUT /settings/llm` + `POST /settings/test-llm`
2. `llm_service.py` — all 4 providers + `get_llm_provider` factory
3. ChromaDB Docker service + `rag_service.py`
4. `documents` migration + `documents.py` API + `ingest_document` ARQ job
5. `ai_analyses` + `llm_conversations` migration + `run_analysis` ARQ job + `analysis.py` API
6. `VerdictCard.tsx` on asset detail page
7. `documents/page.tsx` — document library
8. `ai-usage/page.tsx` — usage tracking

---

## Dependencies

New Python packages:
- `cryptography` — AES-256-GCM
- `pymupdf` — PDF text extraction
- `chromadb` — vector store client
- `sentence-transformers` — local embeddings
- `anthropic` — Claude provider
- `openai` — OpenAI provider
- `google-generativeai` — Gemini provider

New Docker service: `chromadb` (image: `chromadb/chroma`, persistent volume: `chroma_data`)
