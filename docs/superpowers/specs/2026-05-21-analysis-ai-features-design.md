# Analysis AI Features Design

**Date:** 2026-05-21  
**Status:** Draft  
**Scope:** Deep Dive, Peer Comparison, Bear Case, Combined Verdict — plus Settings registration and AI Usage logging

---

## Overview

Add four new AI-powered analysis features to the Analysis `[symbol]` page. Each feature is independent (Approach A — separate modules) but all feed into a **Combined Verdict** synthesis at the top of the page. Every LLM call is automatically auditable via the existing `LLMCallLog` infrastructure.

**Future (out of scope here):** Position sizing — "given my cash and a Buy verdict, how many shares should I buy?" — will consume the Combined Verdict output in a future plan.

---

## Features

### 1. Deep Dive (`deep_dive`)
4-part company breakdown: Business Model, Moat (top 3 competitors + durable edge type), Catalysts (next 12 months), Asymmetry (valuation floor vs growth ceiling).

- **Data source:** LLM knowledge only
- **Prompt variables injected:** `{symbol}`, `{company_name}`, `{sector}`, `{current_date}`
- **Output JSON schema:**
```json
{
  "business_model": "string — how they make money in plain English",
  "moat": {
    "edge_type": "patent | switching_cost | network_effect | cost_structure | none",
    "summary": "string",
    "competitors": ["TICKER1", "TICKER2", "TICKER3"]
  },
  "catalysts": [
    { "title": "string", "timeframe": "string", "impact": "high | medium | low" }
  ],
  "asymmetry": {
    "verdict": "yes | no | mixed",
    "floor": "string",
    "ceiling": "string",
    "reasoning": "string"
  }
}
```

---

### 2. Peer Comparison (`peer_comparison`)
Relative valuation table ranked by Value/Growth Score (P/S TTM ÷ YoY Revenue Growth %). Auto-selects 3–5 sector peers.

- **Data source:** yfinance (financial metrics) + LLM (peer selection, scoring narrative)
- **Execution flow (inside ARQ job):**
  1. **LLM peer discovery sub-call** — uses the same `peer_comparison` `FeatureLLMConfig` (provider + model) but calls the adapter directly with a hardcoded peer-discovery prompt. Writes manually to `LLMCallLog` with `feature_key="peer_comparison"`. This bypasses `LLMGateway.complete()` because that method only supports one `SYSTEM_PROMPTS[feature_key]` entry.
  2. **yfinance fetch** — for main ticker + all peers: P/S TTM, forward P/S, EV/EBITDA, gross margin %, YoY revenue growth %, revenue trend direction.
  3. **LLM main call** — goes through `LLMGateway.complete("peer_comparison", ...)` normally. Inject full financial table, return ranked analysis with Value/Growth Scores and labels. Logged to `LLMCallLog` automatically.
- **Prompt variables injected (main call):** `{symbol}`, `{sector}`, `{financial_table}`, `{current_date}`
- **Output JSON schema:**
```json
{
  "sector_label": "string e.g. AI Compute / CPU",
  "methodology_note": "Value/Growth Score = P/S TTM ÷ YoY Revenue Growth %",
  "ranked": [
    {
      "ticker": "AMD",
      "company_name": "Advanced Micro Devices",
      "ps_ttm": 8.1,
      "ps_forward": 7.4,
      "ev_ebitda": 34.0,
      "gross_margin_pct": 51.2,
      "yoy_revenue_growth_pct": 22.0,
      "revenue_trend": "Reaccelerating | Accelerating | Stable | Decelerating | Declining",
      "value_growth_score": 0.37,
      "label": "BEST | FAIR | AVOID",
      "notes": "string"
    }
  ]
}
```
- **Note:** Both LLM sub-calls log to `LLMCallLog` under the same `peer_comparison` feature key. yfinance data is fetched but not stored separately — it is embedded in the logged `prompt_in`.

---

### 3. Bear Case (`bear_case`)
3 biggest reasons NOT to own the stock, ranked by severity. Combines real margin/revenue data with LLM structural risk assessment.

- **Data source:** yfinance (margins, revenue growth, short interest, debt/equity) + LLM knowledge (customer concentration, regulatory risk, moat erosion)
- **Prompt variables injected:** `{symbol}`, `{company_name}`, `{sector}`, `{gross_margins_4q}` (last 4 quarters), `{revenue_growth_yoy}`, `{operating_margin}`, `{debt_equity}`, `{short_interest_pct}`, `{current_date}`
- **Output JSON schema:**
```json
{
  "red_flags": [
    {
      "rank": 1,
      "title": "string",
      "severity": "high | medium | low",
      "data_source": "yfinance | llm_knowledge",
      "evidence": "string — specific data point or reasoning",
      "detail": "string — full explanation"
    }
  ],
  "summary": "string — one paragraph synthesis"
}
```
- **UI note:** Show `data_source` badge per flag so users know which risks are data-backed vs. LLM-inferred.

---

### 4. Combined Verdict (`combined_verdict`)
Synthesizes all four analyses (deep_dive + peer_comparison + bear_case + top_down_analysis) into a single investment verdict.

- **Data source:** Reads latest result rows from DB for all four analyses — no external data fetch
- **Behavior:** Can run with partial data. Minimum requirement: at least 1 analysis must be available. UI shows "X/4 analyses available" before running, and the reasoning output will note which analyses were missing.
- **Prompt variables injected:** `{symbol}`, `{top_down_summary}`, `{deep_dive_summary}`, `{peer_comparison_summary}`, `{bear_case_summary}`, `{available_analyses}`, `{current_date}`
- **Output JSON schema:**
```json
{
  "verdict": "strong_buy | buy | hold | sell | strong_sell",
  "conviction": 8,
  "bull_thesis": "string",
  "bear_thesis": "string",
  "key_risks": ["string", "string", "string"],
  "reasoning": "string",
  "based_on": ["top_down_analysis", "deep_dive", "peer_comparison", "bear_case"]
}
```
- **Future hook:** `verdict` + `conviction` fields are the interface that position sizing will consume.

---

## Architecture

### Backend per feature (×4)

```
backend/app/
├── models/
│   ├── deep_dive_analysis.py        # DeepDiveAnalysis SQLAlchemy model
│   ├── peer_comparison_analysis.py  # PeerComparisonAnalysis
│   ├── bear_case_analysis.py        # BearCaseAnalysis
│   └── combined_verdict.py          # CombinedVerdict
├── services/
│   ├── deep_dive_analysis.py        # run_deep_dive(symbol, user_id, db)
│   ├── peer_comparison_analysis.py  # run_peer_comparison(symbol, user_id, db)
│   ├── bear_case_analysis.py        # run_bear_case(symbol, user_id, db)
│   └── combined_verdict.py          # run_combined_verdict(symbol, user_id, db)
├── api/
│   ├── deep_dive_analysis.py        # GET/POST /analysis/deep-dive/{symbol}
│   ├── peer_comparison_analysis.py  # GET/POST /analysis/peer-comparison/{symbol}
│   ├── bear_case_analysis.py        # GET/POST /analysis/bear-case/{symbol}
│   └── combined_verdict.py          # GET/POST /analysis/combined-verdict/{symbol}
└── alembic/versions/
    └── 041_add_analysis_ai_features.py
```

Each service follows the existing pattern:
- Calls `LLMGateway(db).complete(feature_key, user_id, variables)`
- `LLMGateway.complete()` automatically writes `LLMCallLog` — no extra logging code needed in services
- Stores result in its own DB table
- Each ARQ worker job calls the service function
- **Age context:** Do NOT add any of the 4 new keys to `FEATURES_WITH_AGE_CONTEXT` or `FEATURES_AGE_IN_HUMAN_PROMPT` in `llm_gateway.py`. These are company-level analyses, not portfolio/user-level. Age context is irrelevant here.

### DB models (all follow `TopDownAnalysis` pattern)

Each table has: `id` (UUID PK), `user_id` (UUID), `asset_id` (UUID FK → assets), `result` (JSONB), `model` (String), `provider` (String), `created_at` (DateTime).

Single Alembic migration creates all four tables.

### ARQ worker jobs (4 new jobs in worker)

```python
job_run_deep_dive(symbol: str, user_id: str)
job_run_peer_comparison(symbol: str, user_id: str)
job_run_bear_case(symbol: str, user_id: str)
job_run_combined_verdict(symbol: str, user_id: str)
```

### Feature key registration checklist (MUST complete all 5 for each key)

New keys: `deep_dive`, `peer_comparison`, `bear_case`, `combined_verdict`

| # | File | Change |
|---|------|--------|
| 1 | `backend/app/models/feature_llm_config.py` | Add 4 keys to `FEATURE_KEYS` tuple |
| 2 | `backend/app/services/llm_gateway.py` | Add to `FEATURE_KEYS`, `SYSTEM_PROMPTS`, `HUMAN_PROMPTS` |
| 3 | `frontend/lib/services/feature-llm-config.ts` | Add 4 entries to `FEATURE_LABELS` |
| 4 | `frontend/components/settings/AISettings.tsx` | Add 4 keys to `FEATURE_KEYS` array |

---

## Frontend

### Symbol page layout (`/analysis/[symbol]`)

```
┌─────────────────────────────────────┐
│  Combined Verdict Card              │  ← top, prominent
│  Strong Buy  |  Conviction: 8/10    │
│  Based on: 4/4 analyses             │
└─────────────────────────────────────┘
┌───────────┐ ┌───────────┐ ┌─────────────┐ ┌────────────┐
│ Top-Down  │ │ Deep Dive │ │    Peer     │ │ Bear Case  │
│ (existing)│ │           │ │ Comparison  │ │            │
└───────────┘ └───────────┘ └─────────────┘ └────────────┘
```

Each card shares a common behavior:
- **Empty state:** "No analysis yet" + "Run Analysis" button
- **Running state:** Pulsing indicator "Analyzing…" — frontend polls `GET /{symbol}` every 3s
- **Done state:** Renders result, shows timestamp + model used, "Re-run" button
- **Error state:** Shows error message, "Retry" button

### New frontend components

```
frontend/components/analysis/
├── DeepDiveCard.tsx
├── PeerComparisonCard.tsx     # renders ranked table matching design
├── BearCaseCard.tsx           # renders 3 flags with severity + data_source badge
└── CombinedVerdictCard.tsx    # prominent verdict display, conviction meter
```

### Polling hook

Single shared `useAnalysisPolling(endpoint, interval = 3000)` hook — starts polling after a trigger, stops when data arrives or an error occurs.

---

## Settings page

Four new rows appear automatically in **Settings → AI → Task Assignment** once the feature keys are registered. No Settings UI changes needed — the existing `AISettings.tsx` renders all `FEATURE_KEYS` dynamically.

Display labels:
- `deep_dive` → "Deep Dive Analysis"
- `peer_comparison` → "Peer Comparison"
- `bear_case` → "Bear Case"
- `combined_verdict` → "Combined Verdict"

---

## AI Usage (audit log)

No changes needed. Every `LLMGateway.complete()` call already writes to `LLMCallLog` with the `feature_key`. The existing `/ai-usage` page will automatically show all four new feature keys in its filter dropdown once they start generating logs.

---

## Out of scope (future plan)

**Position sizing:** Consumes `combined_verdict.verdict` + `combined_verdict.conviction` + user's cash balance. Will be a separate plan once analysis features are stable. Interface is already defined — no breaking changes needed.

---

## Open questions resolved

| Question | Decision |
|----------|----------|
| Data source for Peer Comparison | yfinance + LLM (2-step: peer discovery → data fetch → analysis) |
| Peer selection | LLM auto-selects 3–5 sector peers, not from user holdings |
| Data source for Bear Case | yfinance (margins, revenue, short interest) + LLM knowledge |
| Async vs sync | ARQ background jobs, frontend polls every 3s |
| Real-time push | Polling (not SSE) — discrete job completion, not streaming |
| Combined verdict with partial data | Runs on available analyses, shows "X/4" in UI |
| Position sizing | Out of scope, future plan |
