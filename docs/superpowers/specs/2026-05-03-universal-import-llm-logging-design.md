# Design: Universal Portfolio Import + LLM Logging & Cost Tracking

**Date:** 2026-05-03  
**Status:** Approved  
**Features:** `feat - universal portfolio import with global template` + `feat - LLM logging and cost tracking for data imports`

---

## Overview

Two tightly coupled features implemented together as one coherent system:

1. **Universal Portfolio Import** — every broker file (CSV/JSON) is translated by the LLM into a fixed canonical schema. The mapping is cached per platform so the LLM is only called once per new format.
2. **LLM Logging & Cost Tracking** — the LLM gateway is upgraded to capture tokens and cost for every call across all features, auto-logged to a unified `llm_call_logs` table.

---

## Section 1 — Canonical Schema (Global Template)

A new constant `CANONICAL_FIELDS` in `app/core/canonical.py` is the single source of truth for what every import must produce.

```python
# app/core/canonical.py
CANONICAL_FIELDS = [
    "trade_date",     # datetime — required — when trade was executed
    "type",           # BUY | SELL | DIVIDEND | REWARD | FEE | TRANSFER — required
    "symbol",         # str — ticker or fund code — required
    "unit",           # decimal — number of units — required
    "price",          # decimal | null — price per unit in original currency
    "currency",       # str — ISO code e.g. USD, THB — default THB
    "exchange",       # str | null — NYSE, SET, etc. — LLM infers if possible
    "gross_amount",   # decimal | null — unit × price in original currency
    "fee",            # decimal | null — fee in original currency
    "gross_thb",      # decimal | null — total value in THB
    "fee_thb",        # decimal | null — fee in THB
    "exchange_rate",  # decimal | null — historical rate to THB at trade_date
    "asset_type",     # us_stock | thai_stock | th_fund | etf | crypto | gold | cash | null
    "platform",       # str | null — broker/platform name
    "notes",          # str | null — source file reference or raw notes
]
```

**Exchange rate priority for `exchange_rate` field:**
1. Source file provides it → use it (most accurate, broker's actual rate)
2. Source doesn't provide it → fetch historical rate for `trade_date` from BOT API (Bank of Thailand — free, official)
3. Historical API unavailable → store `null`, log a warning

**Exchange rate cache** — new DB table `exchange_rate_cache (date, from_currency, to_currency, rate)` so the same date is never fetched twice.

**Three broker mappings to canonical schema:**

| Canonical field | Finnomena CSV | DIME JSON | Streaming JSON |
|---|---|---|---|
| `trade_date` | `Trade_Date` | `settlement_date` | `trading_date` |
| `type` | `Template` → transform (`"Buy Note"→"BUY"`) | `type` (already correct) | `type` (already correct) |
| `symbol` | `Fund_Code` | `symbol` | `share_name` |
| `unit` | `Number_of_Units` | `unit` | `unit` |
| `price` | **derived**: `gross_thb / unit` | `price` | `unit_price` |
| `gross_thb` | `Total_Amount` | `total_buy_thb` / `total_sell_thb` | `net_amount` |
| `currency` | default `THB` | `currency` | default `THB` |
| `exchange` | default `SET` | `null` | default `SET` |
| `exchange_rate` | fetch BOT API for `trade_date` | `exchange_rate` (in file) | fetch BOT API for `trade_date` |

---

## Section 2 — Unified LLM Gateway

### Architecture

```
All code  →  llm_gateway.py  →  llm_service.py (adapters only)  →  API providers
                  ↓
          llm_call_logs (auto-logged on every call)
```

`llm_service.py` is **internal adapters only** — never called directly by application code. `llm_gateway.py` is the single entry point for all LLM calls.

### Changes to `llm_gateway.py`

`LLMGateway.complete()` updated:

```
complete(feature_key, user_id, variables)
    ├── resolve FeatureLLMConfig → provider + model
    ├── build system + human prompt from templates
    ├── call adapter → returns LLMResponse(content, tokens_in, tokens_out, cost_usd)
    ├── fetch current USD/THB rate (Redis cache, 24h TTL)
    ├── write 1 row to llm_call_logs
    └── return content (str) — all callers unchanged
```

All adapters (Anthropic, OpenAI, Gemini, Ollama) upgraded to return `LLMResponse` instead of `str`.

### Gemini Token Fix

Currently `GeminiProvider` returns `tokens_in=0, tokens_out=0`. Fix:

```python
tokens_in = response.usage_metadata.prompt_token_count
tokens_out = response.usage_metadata.candidates_token_count
cost_usd = _calc_cost(self.model, tokens_in, tokens_out)
```

### Pricing Table (consolidated in `llm_service.py`)

```python
PRICING: dict[str, tuple[float, float]] = {
    # (input $/M tokens, output $/M tokens)
    "claude-sonnet-4-6":         (3.0,   15.0),
    "claude-opus-4-7":           (15.0,  75.0),
    "claude-haiku-4-5-20251001": (0.8,   4.0),
    "gpt-4o":                    (2.5,   10.0),
    "gpt-4o-mini":               (0.15,  0.6),
    "gemini-2.0-flash":          (0.1,   0.4),
    "gemini-1.5-pro":            (1.25,  5.0),
    "gemini-1.5-flash":          (0.075, 0.3),
    "gemini-2.5-flash-lite":     (0.0,   0.0),  # update when pricing known
}
```

### New Table: `llm_call_logs`

```
id              UUID PK
user_id         UUID NOT NULL
feature_key     str  NOT NULL  — import_template_generator | transaction_classifier | portfolio_analysis | chat
provider        str  NOT NULL  — gemini | openai | claude | ollama
model           str  NOT NULL
prompt_in       Text NOT NULL
response_out    Text NOT NULL
tokens_in       int  default 0
tokens_out      int  default 0
cost_usd        Numeric(10,6) default 0
cost_thb        Numeric(10,6) default 0
exchange_rate   Numeric(10,4) default 0  — USD/THB rate at call time
created_at      timestamptz
```

`llm_conversations` table is **untouched** — it stores conversation turn history (role/order) for the analysis chat feature. `llm_call_logs` is the cost audit trail — different purpose.

---

## Section 3 — Universal Import Pipeline

### Extended `ImportTemplate` Model

Three new JSONB columns added to `import_templates` table:

```
value_transforms   JSONB  — { "type": { "Buy Note": "BUY", "Manual": "BUY" } }
derived_fields     JSONB  — { "price": "gross_thb / unit" }
defaults           JSONB  — { "currency": "THB", "exchange": "SET" }
```

### Updated LLM System Prompt for `import_template_generator`

The prompt now includes the full canonical schema so the LLM knows the exact output contract. It must return:

```json
{
  "file_format": "csv|json",
  "json_path": "optional dotted path for JSON",
  "field_map": { "source_key": "canonical_key" },
  "value_transforms": { "canonical_key": { "source_value": "canonical_value" } },
  "derived_fields": { "canonical_key": "expression using other canonical fields" },
  "defaults": { "canonical_key": "value" },
  "asset_type_rules": [ { "field": "...", "values": [...], "asset_type": "..." } ],
  "asset_type_fallback": "us_stock"
}
```

### Import Flow — First Import (New Platform / New Signature)

```
1. User uploads file
2. Detect format (CSV/JSON) + extract structure
3. Compute column_signature → no cached template found
4. LLM call → returns full mapping JSON (auto-logged to llm_call_logs)
5. Fetch historical exchange_rate for each row's trade_date from BOT API
6. Save ImportTemplate (user + platform + signature)
7. Apply template → produce canonical preview rows
8. User reviews canonical rows → confirms
9. Save Transactions to DB
```

### Import Flow — Repeat Import (Same Platform, Same Signature)

```
1. User uploads file
2. Compute column_signature → cached template found ✅
3. Apply template mechanically (no LLM call, zero cost)
4. Fetch historical exchange_rate for each row's trade_date from BOT API
5. User reviews canonical rows → confirms
6. Save Transactions to DB
```

### `apply_template` Function (extended)

Handles 4 transformation steps in order:

1. **Direct mapping** — `field_map`: `source_key → canonical_key`
2. **Value transforms** — `value_transforms`: map source values to canonical values
3. **Derived fields** — `derived_fields`: compute fields from simple arithmetic expressions using other canonical field values. Supported operators: `+`, `-`, `*`, `/`. Implemented as a safe custom parser (no code execution — parses `"a / b"` into operands + operator only). Example: `{ "price": "gross_thb / unit" }`. If any referenced field is null, derived field is null.
4. **Defaults** — fill remaining nulls with `defaults`

### Re-map Escape Hatch

A "Re-map" button on the import UI calls `DELETE /import/template/{platform_id}` which deletes the cached `ImportTemplate` for that platform. The next upload from that platform triggers a fresh LLM call automatically. Covers cases where the broker changes their export format or the cached mapping is wrong.

---

## Section 4 — AI Usage Page Update

### New API Endpoint

`GET /llm/call-logs` with optional query params:

```
?feature_key=import_template_generator
?from_date=2026-01-01
?to_date=2026-05-03
```

Response includes paginated rows + aggregated totals:

```json
{
  "total_cost_primary": "฿1.52",
  "total_cost_secondary": "$0.043",
  "total_tokens_in": 12400,
  "total_tokens_out": 3200,
  "logs": [ ... ]
}
```

### AI Usage Page Layout

```
AI Usage
├── Summary cards (top)
│     Total spend (primary currency) | Total tokens | Calls this month
│
├── Tab: All Calls        ← default — all feature_keys
│     date | feature | provider | model | tokens_in | tokens_out | cost (primary)
│
├── Tab: Import Mapping   ← feature_key = import_template_generator
│
└── Tab: Analysis         ← feature_key = portfolio_analysis (existing logs)
```

### Currency Display Preference

New fields on user settings model:

```
currency_primary    str  default "THB"
currency_secondary  str  default "USD"
```

New endpoint: `PATCH /settings/display` — updates display preferences.

Settings page gets a small "Display" section with two currency dropdowns. All cost displays in the app read these preferences:

```
Primary:   ฿1.52 THB
Secondary: ($0.043 USD)
```

**Scope:** Full Settings page UI is a separate Kanban item. This feature adds only the model fields, endpoint, and the display section in Settings → AI.

---

## Files to Create / Modify

### New Files
- `backend/app/core/canonical.py` — canonical schema constant + apply_template logic
- `backend/app/models/llm_call_log.py` — `LLMCallLog` SQLAlchemy model
- `backend/app/models/exchange_rate_cache.py` — `ExchangeRateCache` model
- `backend/app/services/exchange_rate.py` — BOT API fetch + Redis cache
- `backend/alembic/versions/XXXX_add_llm_call_logs_exchange_rate_cache.py`
- `backend/alembic/versions/XXXX_extend_import_templates.py`
- `backend/alembic/versions/XXXX_add_display_currency_settings.py`

### Modified Files
- `backend/app/services/llm_gateway.py` — adapters return `LLMResponse`, auto-log to `llm_call_logs`
- `backend/app/services/llm_service.py` — add Gemini token fix, consolidate pricing table
- `backend/app/services/import_pipeline.py` — updated prompt, extended apply_template
- `backend/app/models/import_template.py` — add `value_transforms`, `derived_fields`, `defaults`
- `backend/app/schemas/import_template.py` — expose new fields
- `backend/app/models/user.py` (or settings model) — add `currency_primary`, `currency_secondary`
- `backend/app/api/import_pipeline.py` — add re-map endpoint
- `backend/app/api/llm_usage.py` — **new file** — add `GET /llm/call-logs` endpoint
- `backend/app/api/settings.py` — add `PATCH /settings/display` endpoint
- `frontend/app/(auth)/settings/ai/page.tsx` — AI Usage tabs + summary cards
- `frontend/app/(auth)/settings/page.tsx` — currency display preference section

---

## Constraints & Notes

- `bcrypt` pinned `<5` — unrelated, do not touch
- TimescaleDB migrations must be Alembic-compatible — no raw DDL outside migrations
- Gemini pricing for `gemini-2.5-flash-lite` is TBD — store 0.0 until confirmed
- BOT API rate: if unavailable, `exchange_rate = null`, `cost_thb = null` — import still succeeds
- `llm_service.py` rule: internal adapter layer only, never imported directly by application code
