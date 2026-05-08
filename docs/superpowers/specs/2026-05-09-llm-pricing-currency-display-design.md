# LLM Pricing Centralization + Currency Display Fixes

**Date:** 2026-05-09  
**Status:** Approved

## Problem

1. `PRICING` dict exists in two places — `backend/app/services/llm_service.py` and `frontend/lib/llmPricing.ts` — with divergent model entries. Either can be updated while the other is forgotten.
2. LLM costs are displayed with a hardcoded `$` prefix in 4 UI locations, inconsistent with the rest of the app (which uses ISO codes like `USD`/`THB`).
3. Recorded `cost_usd` (VerdictCard, AI usage page) is always shown in USD, ignoring the user's primary/secondary currency preference.

## Scope

- **Backend**: Extract pricing into a shared module; expose via API endpoint.
- **Frontend**: Replace static pricing dict with a fetched cache; fix `$` symbols; convert recorded costs to primary currency.
- **Out of scope**: `cost_thb` field in llm_gateway (legacy field, untouched); pricing for Ollama (always free).

---

## Section 1: Backend — Single Pricing Source

### New file: `backend/app/core/llm_pricing.py`

Moves `PRICING` dict and `calc_cost()` out of `llm_service.py` into a dedicated core module.

```
PRICING: dict[str, tuple[float, float]] = {
    # (input_per_mtoken_usd, output_per_mtoken_usd)
    ...  # all models, same values as current llm_service.py
}

def calc_cost(model: str, tokens_in: int, tokens_out: int) -> float: ...
```

### `backend/app/services/llm_service.py`

Remove inline `PRICING` dict and `calc_cost`. Import both from `app.core.llm_pricing`. No behavioral change.

### New endpoint: `GET /api/v1/llm/pricing`

Returns the full pricing table as JSON so the frontend can sync from it.

```json
{
  "claude-sonnet-4-6": { "input_per_mtoken": 3.0, "output_per_mtoken": 15.0 },
  ...
}
```

Added to `backend/app/api/` as a small router (e.g., `llm_pricing.py`) and registered in `main.py`. No auth required (pricing is public data).

---

## Section 2: Frontend — Pricing Service

### `frontend/lib/llmPricing.ts`

Keep `ModelPricing` type, `estimateTokens`, `estimateCostUsd`, `getPricingForModel` — all unchanged in interface.

Replace the static `MODEL_PRICING` object with:

- **Bundled fallback**: hardcoded copy of current values, used synchronously before fetch completes or on fetch failure.
- **Module-level cache**: starts as the bundled fallback, updated by `loadPricing()`.
- **`loadPricing()`**: async function, calls `GET /api/v1/llm/pricing`, merges result into cache. Called once on app boot (e.g., in root layout or a settings hook).

All consumers (`useLLMCost`, `ModelTooltip`, etc.) call `getPricingForModel` as before — they automatically use the live cache once loaded.

### `frontend/hooks/useLLMCost.ts`

No changes. Estimates remain USD-only (acceptable for rough pre-call estimates).

---

## Section 3: Currency Display Fixes

### 3a. Fix hardcoded `$` prefix (3 locations)

Target prices change from `$X.XX` → `X.XX USD`. Line 155 in VerdictCard is handled in 3b (primary currency conversion supersedes plain symbol fix).

| File | Line | Before | After |
|------|------|--------|-------|
| `components/analysis/VerdictCard.tsx` | 149 | `` `$${target_price.toFixed(2)}` `` | `` `${target_price.toFixed(2)} USD` `` |
| `app/(auth)/events/page.tsx` | 261 | `` Target: ${suggested_price} `` | `` Target: {suggested_price} USD `` |
| `app/(auth)/watchlist/page.tsx` | 639 | `` suggested ${price.toFixed(2)} `` | `` suggested {price.toFixed(2)} USD `` |

### 3b. VerdictCard cost line — primary currency

`VerdictCardProps` gains two optional props:
```ts
primaryCurrency?: string        // default "USD"
primaryExchangeRate?: number    // default 1
```

Line 155 changes from displaying `cost_usd` raw to displaying `cost_usd * primaryExchangeRate` with `primaryCurrency` label.

`frontend/app/(auth)/portfolio/[symbol]/page.tsx` already holds `primaryCurrency` and exchange rate state — it passes them down to `<VerdictCard>`.

### 3c. AI usage page — primary + secondary cost columns

`app/(auth)/ai-usage/page.tsx` fetches user settings (already done for other columns). Cost cells that use `formatNative(cost, "USD")` switch to `<DualCurrencyAmount>` passing the user's primary/secondary currencies and exchange rates — matching the pattern used elsewhere in the app.

---

## Data Flow

```
backend/app/core/llm_pricing.py
    ├── imported by llm_service.py (cost recording)
    └── served by GET /api/v1/llm/pricing
            └── fetched by frontend/lib/llmPricing.ts (cache)
                    └── used by useLLMCost (estimates, USD only)
                    └── used by ModelTooltip (estimates, USD only)
```

---

## Files Changed

### Backend
- `backend/app/core/llm_pricing.py` — **new**
- `backend/app/services/llm_service.py` — remove `PRICING` + `calc_cost`, import from core
- `backend/app/api/llm_pricing.py` — **new** (single endpoint)
- `backend/app/main.py` — register new router

### Frontend
- `frontend/lib/llmPricing.ts` — add cache + `loadPricing()`
- `frontend/app/layout.tsx` — call `loadPricing()` on boot
- `frontend/components/analysis/VerdictCard.tsx` — add currency props, fix `$` ×2
- `frontend/app/(auth)/portfolio/[symbol]/page.tsx` — pass currency props to VerdictCard
- `frontend/app/(auth)/events/page.tsx` — fix `$` ×1
- `frontend/app/(auth)/watchlist/page.tsx` — fix `$` ×1
- `frontend/app/(auth)/ai-usage/page.tsx` — DualCurrencyAmount for cost columns
