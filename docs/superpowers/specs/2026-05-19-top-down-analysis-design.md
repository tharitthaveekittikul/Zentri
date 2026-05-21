# Top-Down Analysis with Document Auto-Fetch

**Date:** 2026-05-19  
**Status:** Approved

## Overview

Upgrade the existing per-ticker analysis from a simple BUY/SELL/HOLD verdict to a structured Top-Down Analysis: mega trend → financial health → SWOT → verdict. Documents (SEC filings, news) are auto-fetched per ticker before the LLM runs, with a cache check by source URL to avoid duplicate downloads.

Phase A (this spec): pre-fetch documents + structured LLM output + UI.  
Phase B (future): agentic tool-calling so LLM can request documents mid-analysis.

---

## Architecture

### New Backend Components

| Component | Path | Responsibility |
|---|---|---|
| `DocumentFetcher` | `backend/app/services/document_fetcher.py` | Resolve document URLs for a ticker from SEC EDGAR (10-Q/10-K) and news |
| `DocumentManager` | `backend/app/services/document_manager.py` | Check store by source URL → download → save → enqueue ChromaDB ingest |
| `TopDownAnalysis` model | `backend/app/models/top_down_analysis.py` | New DB table with all structured output fields |
| `job_run_top_down_analysis` | `backend/worker/jobs/run_top_down_analysis.py` | 5-step ARQ job |
| API router | `backend/app/api/top_down_analysis.py` | POST trigger + GET latest/history endpoints |
| Alembic migration | new revision | Add `source_url` to `documents`; create `top_down_analyses` table |
| File serve endpoint | added to `backend/app/api/documents.py` | `GET /documents/{doc_id}/file` — serve PDF in-browser |

### Existing Components — Unchanged

- `job_run_analysis` — old simple analysis still works
- `AIAnalysis` model — unchanged
- `Document` model — only one new column: `source_url`

### Job Flow

```
POST /analysis/top-down/{symbol}
  → enqueue job_run_top_down_analysis(symbol)
      Step 1: load_asset
                Load Asset from DB by symbol
      Step 2: fetch_documents
                DocumentFetcher.fetch_for_ticker(ticker)
                  → SEC EDGAR: latest 10-Q + 10-K filing URLs
                  → News: existing news_articles in DB for ticker
                  → User-supplied: Documents with source_url set manually
                For each URL:
                  DocumentManager.check_exists(source_url) → skip if found
                  else → download file → save to UPLOAD_DIR/{ticker}/{doc_type}/
                       → create Document record (source_url, doc_type, asset_id)
                       → enqueue job_ingest_document (ChromaDB chunking)
      Step 3: rag_retrieval
                ChromaDB search for ticker across all ingested docs
      Step 4: llm_call
                Send structured prompt → expect TopDown JSON
                Retry once on malformed response
      Step 5: save_analysis
                Save TopDownAnalysis to DB
                Save LLMConversation messages
```

---

## Data Model

### `top_down_analyses` table (new)

```python
class TopDownAnalysis(Base):
    __tablename__ = "top_down_analyses"

    id: UUID (PK)
    asset_id: UUID (FK → assets, nullable)
    job_id: str | None

    # Structured LLM output
    mega_trend: str
    financial_health: str
    swot_strengths: list[str]       # JSON array column
    swot_weaknesses: list[str]
    swot_opportunities: list[str]
    swot_threats: list[str]
    verdict: str                    # BUY / SELL / HOLD
    target_price: Decimal | None

    # Cost tracking
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal

    created_at: datetime
```

### `documents` table (add one column)

```python
source_url: str | None   # dedup key — same URL = skip download
```

### File storage structure

```
UPLOAD_DIR/
  {TICKER}/
    10-Q/
      {doc_id}_{filename}.pdf
    10-K/
      {doc_id}_{filename}.pdf
    general/
      {doc_id}_{filename}.pdf
```

Old flat uploads remain as-is. New auto-fetched documents use the structured path.

---

## Document Fetching

### Dedup Rule

`source_url` is the unique key. If a `Document` row already exists with the same `source_url`, skip download — regardless of age, ticker, or doc type.

### `DocumentFetcher`

```
fetch_for_ticker(ticker: str) -> list[{"url": str, "doc_type": str, "filename": str}]
```

- **SEC EDGAR**: Look up CIK from `data.sec.gov/submissions` by ticker. Fetch latest 10-Q and 10-K filing document URLs from the EDGAR API.
- **News**: Query existing `news_articles` DB table for the ticker. For articles that have a PDF or full-text URL, include them. Skip articles already indexed in ChromaDB.
- **User-supplied**: Query `Document` table for rows with `asset_id` matching the ticker and `source_url` not null — these are already stored, so they appear in RAG automatically without re-fetch.

### `DocumentManager`

```
pre_fetch(ticker: str, asset_id: UUID, db: AsyncSession) -> dict
  Returns: {"fetched": N, "skipped": N, "failed": N}
```

Download: HTTP GET with `User-Agent` header (required by SEC EDGAR). Save raw bytes to `UPLOAD_DIR/{ticker}/{doc_type}/{doc_id}_{filename}`. Create `Document` DB record. Enqueue `job_ingest_document`.

---

## LLM Structured Output

### Prompt contract

The LLM system prompt instructs it to return only valid JSON:

```json
{
  "mega_trend": "string — industry trend and ATH pullback context",
  "financial_health": "string — revenue/profit trend summary",
  "swot": {
    "strengths": ["...", "..."],
    "weaknesses": ["..."],
    "opportunities": ["..."],
    "threats": ["..."]
  },
  "verdict": "BUY | SELL | HOLD",
  "target_price": 210.0
}
```

### Validation

Parse JSON → check `verdict` in `{BUY, SELL, HOLD}` → check `swot` has all 4 keys → retry once with format reminder if invalid.

---

## API Endpoints

### New: `POST /analysis/top-down/{symbol}`
Triggers `job_run_top_down_analysis`. Returns `{"symbol": "AAPL", "job_id": "..."}`.

### New: `GET /analysis/top-down/{symbol}/latest`
Returns the most recent `TopDownAnalysis` for the symbol, serialized with all SWOT fields.

### New: `GET /analysis/top-down/{symbol}/history?limit=20`
Returns list of past analyses.

### New: `GET /documents/{doc_id}/file`
Serves the stored file with correct `Content-Type` (application/pdf for PDFs). Used by the frontend to open documents in a new browser tab.

---

## Frontend UI

### Page / Panel: Top-Down Analysis per ticker

```
┌─────────────────────────────────────────┐
│  AAPL Top-Down Analysis          [BUY]  │
│  Target Price: $210.00                  │
├─────────────────────────────────────────┤
│  Mega Trend                             │
│  "AI infrastructure boom, pulling       │
│   back 25% from ATH..."                │
├─────────────────────────────────────────┤
│  Financial Health                       │
│  "Revenue +18% YoY, profit margin..."  │
├─────────────────────────────────────────┤
│  SWOT Analysis                          │
│  ┌──────────┐ ┌──────────┐             │
│  │Strengths │ │Weaknesses│             │
│  │ • ...    │ │ • ...    │             │
│  └──────────┘ └──────────┘             │
│  ┌──────────┐ ┌──────────┐             │
│  │Opportunit│ │Threats   │             │
│  │ • ...    │ │ • ...    │             │
│  └──────────┘ └──────────┘             │
├─────────────────────────────────────────┤
│  Documents used (3)  [Fetch & Analyze] │
│                                         │
│  • AAPL_10Q_2024Q1.pdf      [↗ Open]  │
│    /uploads/AAPL/10-Q/                  │
│                                         │
│  • AAPL_10K_2023.pdf        [↗ Open]  │
│    /uploads/AAPL/10-K/                  │
│                                         │
│  • News: AAPL Q1 Earnings...  [↗ Open]│
│    source: reuters.com                  │
└─────────────────────────────────────────┘
```

### UI Rules

- SWOT rendered as 2×2 grid
- Colors use CSS variables only — `--color-success` (strengths), `--color-warning` (weaknesses/threats), `--color-info` (opportunities) — no hardcoded hex
- Verdict badge reuses existing BUY/SELL/HOLD color system
- `[↗ Open]` on local PDFs → calls `GET /documents/{doc_id}/file` with `target="_blank"`
- `[↗ Open]` on news articles → opens `source_url` directly in new tab
- Storage path shown below each document filename
- `[Fetch & Analyze]` button triggers POST, then polls `GET /latest` until result appears

---

## Phase B (Future)

When ready to add agentic tool-calling:
- `DocumentManager.check_exists()` and `DocumentManager.fetch_and_store()` become individual LLM tools
- `DocumentFetcher.fetch_for_ticker()` becomes a `list_available_documents(ticker)` tool
- The ARQ job switches from pre-fetch → LLM-with-tools loop
- No DB schema changes needed — same `Document` + `TopDownAnalysis` models

---

## Out of Scope (Phase A)

- Automatic ATH pullback screening (mega trend step is LLM-reasoned from docs, not live price data)
- Financial statement structured parsing (financial_health is LLM summary from RAG chunks)
- SWOT comparison across multiple tickers
