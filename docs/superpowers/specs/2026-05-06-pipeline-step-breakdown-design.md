# Pipeline Step Breakdown Design

**Date:** 2026-05-06  
**Feature:** Per-job step tracking with real-time UI expansion  
**Approach:** Option A — full `pipeline_steps` table with live SSE updates

---

## Overview

Add step-level tracking to every pipeline job so the Pipeline Monitor page can expand each job row to show what happened inside it. LLM steps expose token usage, cost (USD + THB), prompt, and response. Data steps expose record counts. All steps appear live via the existing SSE stream.

---

## Data Model

### New table: `pipeline_steps`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | UUID PK | no | |
| `pipeline_log_id` | UUID FK → `pipeline_logs.id` | no | cascade delete |
| `step_name` | varchar | no | e.g. `llm_call`, `insert_db` |
| `status` | enum(`running`,`done`,`failed`) | no | |
| `started_at` | timestamptz | no | set on create |
| `finished_at` | timestamptz | yes | null while running |
| `metadata` | JSONB | yes | step-specific payload |
| `error_message` | text | yes | set on failure |

### Migration

New Alembic migration: create `pipeline_steps` table and `pipeline_step_status_enum`.

### Schema update: `PipelineStepResponse`

```python
class PipelineStepResponse(BaseModel):
    id: uuid.UUID
    pipeline_log_id: uuid.UUID
    step_name: str
    status: Literal["running", "done", "failed"]
    started_at: datetime
    finished_at: datetime | None
    metadata: dict | None
    error_message: str | None
    model_config = {"from_attributes": True}
```

`PipelineLogResponse` gains: `steps: list[PipelineStepResponse] = []`

---

## Step Service

New functions in `backend/app/services/pipeline.py`:

- `create_step(db, pipeline_log_id, step_name) -> PipelineStep` — inserts a `running` step, commits
- `finish_step(db, step, *, success, metadata=None, error=None) -> PipelineStep` — sets status/finished_at/metadata, commits

---

## Worker Instrumentation

Steps emitted per job type:

### price_fetch_us / price_fetch_crypto / price_fetch_gold / price_fetch_benchmark
1. `fetch_prices` — metadata: `{symbol_count: N}` (where applicable)
2. `insert_db` — metadata: `{inserted: N}`

### watchlist_discovery
1. `load_portfolio` — metadata: `{holdings: N, watchlist: N}`
2. `llm_call` — metadata: `{tokens_in, tokens_out, cost_usd, cost_thb, exchange_rate, model, provider, prompt, response}`
3. `save_suggestions` — metadata: `{saved: N, skipped: N}`

### run_analysis
1. `load_asset` — metadata: `{symbol, holdings: N, price_days: N}`
2. `rag_retrieval` — metadata: `{chunks_found: N}`
3. `llm_call` — metadata: `{tokens_in, tokens_out, cost_usd, cost_thb, exchange_rate, model, provider, prompt, response}`
4. `save_analysis` — metadata: `{verdict, analysis_id}`

### watchlist_scan
1. `load_asset` — metadata: `{symbol}`
2. `rag_retrieval` — metadata: `{chunks_found: N}`
3. `llm_call` — metadata: `{tokens_in, tokens_out, cost_usd, cost_thb, exchange_rate, model, provider, prompt, response}`
4. `save_suggestion` — metadata: `{symbol, verdict}`

### ingest_document
1. `load_document` — metadata: `{filename, size_bytes}`
2. `chunk_text` — metadata: `{chunks: N}`
3. `embed_store` — metadata: `{embedded: N}`

---

## API Changes

### Modified endpoints

**`GET /api/v1/pipeline/jobs`** — response model changes from `list[PipelineLogResponse]` to include steps. Service `list_logs()` eagerly loads `steps` relationship ordered by `started_at`.

**`GET /api/v1/pipeline/jobs/{id}`** — same, includes steps.

**`GET /api/v1/pipeline/stream`** (SSE) — each job dict in the payload gains a `steps` array with full step data. Pushes every 3s as before.

### No new routes required.

### LLMGateway change required

`LLMGateway.complete()` currently returns only `str`. It must be changed to return a named tuple or dataclass `(content: str, usage: LLMUsage)` where `LLMUsage` holds `tokens_in`, `tokens_out`, `cost_usd`, `cost_thb`, `exchange_rate`, `model`, `provider`. Workers that call `gateway.complete()` (`watchlist_discover.py`, `watchlist_scan.py`) use the returned `usage` to populate the `llm_call` step metadata. `run_analysis.py` calls `llm.complete()` directly and already has `resp.tokens_in` etc., so no change needed there.

---

## Frontend Changes

### `lib/services/pipeline.ts`

Add `PipelineStep` type and extend `PipelineJob` with `steps: PipelineStep[]`.

### `components/pipeline/JobsTable.tsx`

- Table rows become clickable; clicking toggles an expansion panel
- Expanded panel renders a `<StepList>` component

### New: `components/pipeline/StepList.tsx`

Renders the step list for one job:

```
├ load_portfolio   ✓  0.1s    holdings: 12 · watchlist: 5
├ llm_call         ✓  3.1s    ↑1,240 / ↓380 · $0.0023 · ฿0.08   [Prompt ▾] [Response ▾]
└ save_suggestions ✓  0.1s    saved: 4 · skipped: 1
```

- Running step shows pulsing dot + "running…" duration
- LLM step shows token chips, cost in USD and THB, collapsible Prompt/Response panels
- Data steps show counts inline
- Failed step shows red badge + error message

### Real-time

SSE payload already drives the job list. Steps arrive as part of each job object — no new EventSource connection needed. Running steps update every 3s until `finished_at` is set.

---

## Files to Create / Modify

### Backend
| File | Action |
|---|---|
| `backend/alembic/versions/015_pipeline_steps.py` | Create |
| `backend/app/models/pipeline_step.py` | Create |
| `backend/app/schemas/pipeline.py` | Modify — add `PipelineStepResponse`, extend `PipelineLogResponse` |
| `backend/app/services/pipeline.py` | Modify — add `create_step`, `finish_step`, eager-load steps in `list_logs`/`get_log` |
| `backend/app/api/pipeline.py` | Modify — SSE stream includes steps |
| `backend/worker/jobs/price_fetch.py` | Modify — add step calls |
| `backend/worker/jobs/watchlist_discover.py` | Modify — add step calls |
| `backend/worker/jobs/run_analysis.py` | Modify — add step calls |
| `backend/worker/jobs/watchlist_scan.py` | Modify — add step calls |
| `backend/worker/jobs/ingest_document.py` | Modify — add step calls |

### Frontend
| File | Action |
|---|---|
| `frontend/lib/services/pipeline.ts` | Modify — add `PipelineStep` type, extend `PipelineJob` |
| `frontend/components/pipeline/JobsTable.tsx` | Modify — expandable rows |
| `frontend/components/pipeline/StepList.tsx` | Create |
