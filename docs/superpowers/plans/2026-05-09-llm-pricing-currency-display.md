# LLM Pricing Centralization + Currency Display Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize LLM pricing in the backend as a single source of truth, expose it via API, and fix all hardcoded `$`/`฿` currency symbols to use ISO codes after the number with primary/secondary currency support.

**Architecture:** A new `backend/app/core/llm_pricing.py` module holds the canonical `PRICING` dict and `calc_cost()`; `llm_service.py` imports from it instead of defining its own copy; a new `GET /api/v1/llm/pricing` endpoint serves the table. The frontend replaces its static `MODEL_PRICING` dict with a live cache populated by fetching that endpoint, keeping a bundled fallback for offline/pre-fetch use.

**Tech Stack:** FastAPI, Pydantic, pytest-anyio (backend); Next.js App Router, TypeScript, TanStack Query, `useDualCurrency` hook (frontend)

---

## File Map

| File                                           | Action | Responsibility                                            |
| ---------------------------------------------- | ------ | --------------------------------------------------------- |
| `backend/app/core/llm_pricing.py`              | Create | Canonical `PRICING` dict + `calc_cost()`                  |
| `backend/app/services/llm_service.py`          | Modify | Remove inline `PRICING`/`calc_cost`, import from core     |
| `backend/app/api/llm_pricing.py`               | Create | `GET /api/v1/llm/pricing` endpoint                        |
| `backend/app/main.py`                          | Modify | Register `llm_pricing` router                             |
| `backend/tests/test_llm_pricing.py`            | Create | Unit tests for core pricing module                        |
| `backend/tests/test_llm_service.py`            | Modify | Update `calc_cost` import path                            |
| `frontend/lib/llmPricing.ts`                   | Modify | Replace static dict with cache + `loadPricing()`          |
| `frontend/components/settings/AISettings.tsx`  | Modify | Call `loadPricing()` on mount                             |
| `frontend/components/analysis/VerdictCard.tsx` | Modify | Fix target_price `$`, use `useDualCurrency` for cost line |
| `frontend/app/(auth)/events/page.tsx`          | Modify | Fix `$` on suggested_price                                |
| `frontend/app/(auth)/watchlist/page.tsx`       | Modify | Fix `$` on suggested_price                                |
| `frontend/app/(auth)/ai-usage/page.tsx`        | Modify | Fix hardcoded "Cost (THB)" header and `฿` cell            |

---

## Task 1: Create `backend/app/core/llm_pricing.py`

**Files:**

- Create: `backend/app/core/llm_pricing.py`
- Create: `backend/tests/test_llm_pricing.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_llm_pricing.py
import pytest
from app.core.llm_pricing import PRICING, calc_cost


def test_calc_cost_known_model():
    cost = calc_cost("claude-sonnet-4-6", tokens_in=1_000_000, tokens_out=1_000_000)
    assert cost == pytest.approx(18.0)  # 3.0 in + 15.0 out


def test_calc_cost_unknown_model_returns_zero():
    assert calc_cost("unknown-model-xyz", 100, 100) == 0.0


def test_pricing_covers_all_major_providers():
    providers = {m.split("-")[0] for m in PRICING}
    assert "claude" in providers
    assert "gpt" in providers
    assert "gemini" in providers


def test_all_models_have_positive_rates():
    for model, (inp, out) in PRICING.items():
        assert inp > 0, f"{model} input rate must be > 0"
        assert out > 0, f"{model} output rate must be > 0"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && python -m pytest tests/test_llm_pricing.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.core.llm_pricing'`

- [ ] **Step 3: Create the core module**

```python
# backend/app/core/llm_pricing.py
PRICING: dict[str, tuple[float, float]] = {
    # (input_per_mtoken_usd, output_per_mtoken_usd)
    # Anthropic
    "claude-sonnet-4-6":         (3.0,   15.0),
    "claude-opus-4-7":           (5.0,   25.0),
    "claude-haiku-4-5-20251001": (1.0,    5.0),
    # OpenAI GPT-5 series
    "gpt-5.5":                   (5.0,   30.0),
    "gpt-5.4":                   (2.5,   15.0),
    "gpt-5.4-mini":              (0.75,   4.5),
    "gpt-5.4-nano":              (0.2,    1.25),
    # OpenAI GPT-4o series
    "gpt-4o":                    (2.5,   10.0),
    "gpt-4o-mini":               (0.15,   0.6),
    # Google Gemini 2.5 series
    "gemini-2.5-pro":            (1.25,  10.0),
    "gemini-2.5-flash":          (0.3,    2.5),
    "gemini-2.5-flash-lite":     (0.1,    0.4),
    # Google Gemini 3 series
    "gemini-3.1-flash-lite":     (0.25,   1.5),
    # Google Gemini legacy
    "gemini-1.5-pro":            (1.25,   5.0),
    "gemini-1.5-flash":          (0.075,  0.3),
    "gemini-2.0-flash":          (0.1,    0.4),
}


def calc_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    if model not in PRICING:
        return 0.0
    in_rate, out_rate = PRICING[model]
    return (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/test_llm_pricing.py -v
```

Expected: 4 tests PASS

---

## Task 2: Refactor `llm_service.py` to import from core

**Files:**

- Modify: `backend/app/services/llm_service.py`
- Modify: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Update `llm_service.py`**

In `backend/app/services/llm_service.py`:

Remove the entire `PRICING` dict and `calc_cost` function (approx lines 10–30 where they currently appear).

Add this import after the existing imports:

```python
from app.core.llm_pricing import PRICING, calc_cost  # noqa: F401  (re-exported for backwards compat)
```

The `noqa` comment keeps the import even though it's only used via the re-export; callers in `llm_gateway.py` that do `from app.services.llm_service import calc_cost` continue to work unchanged.

- [ ] **Step 2: Update `test_llm_service.py` to import from new location**

In `backend/tests/test_llm_service.py`, find:

```python
from app.services.llm_service import (
    ClaudeProvider,
    OllamaProvider,
    OpenAIProvider,
    LLMResponse,
    LLMQuotaExceededError,
    calc_cost as _calc_cost,
)
```

Change to:

```python
from app.services.llm_service import (
    ClaudeProvider,
    OllamaProvider,
    OpenAIProvider,
    LLMResponse,
    LLMQuotaExceededError,
)
from app.core.llm_pricing import calc_cost as _calc_cost
```

- [ ] **Step 3: Run the full backend test suite**

```bash
cd backend && python -m pytest tests/test_llm_service.py tests/test_llm_pricing.py tests/test_llm_gateway.py -v
```

Expected: all tests PASS

---

## Task 3: Add `GET /api/v1/llm/pricing` endpoint

**Files:**

- Create: `backend/app/api/llm_pricing.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing integration test**

```python
# backend/tests/test_llm_pricing_api.py
import pytest


@pytest.mark.anyio
async def test_get_llm_pricing_returns_all_models(client):
    r = await client.get("/api/v1/llm/pricing")
    assert r.status_code == 200
    data = r.json()
    assert "claude-sonnet-4-6" in data
    assert "gpt-4o" in data
    assert "gemini-2.5-pro" in data
    entry = data["claude-sonnet-4-6"]
    assert entry["input_per_mtoken"] == pytest.approx(3.0)
    assert entry["output_per_mtoken"] == pytest.approx(15.0)


@pytest.mark.anyio
async def test_get_llm_pricing_all_entries_have_positive_rates(client):
    r = await client.get("/api/v1/llm/pricing")
    assert r.status_code == 200
    for model, entry in r.json().items():
        assert entry["input_per_mtoken"] > 0, f"{model} input rate <= 0"
        assert entry["output_per_mtoken"] > 0, f"{model} output rate <= 0"
```

Note: uses `client` fixture (unauthenticated) because this endpoint is public.

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && python -m pytest tests/test_llm_pricing_api.py -v
```

Expected: `404 Not Found` (route not registered yet)

- [ ] **Step 3: Create the endpoint**

```python
# backend/app/api/llm_pricing.py
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.llm_pricing import PRICING

router = APIRouter()


class ModelPricing(BaseModel):
    input_per_mtoken: float
    output_per_mtoken: float


@router.get("/llm/pricing", response_model=dict[str, ModelPricing])
def get_llm_pricing() -> dict[str, ModelPricing]:
    return {
        model: ModelPricing(input_per_mtoken=inp, output_per_mtoken=out)
        for model, (inp, out) in PRICING.items()
    }
```

- [ ] **Step 4: Register the router in `main.py`**

In `backend/app/main.py`, add `llm_pricing` to the import block:

```python
from app.api import (
    analysis, assets, auth, cash_balance, chat, dividends, documents,
    events, feature_llm_config, health, import_pipeline, ipos, llm_pricing,
    llm_usage, overview, pipeline, platforms, portfolio, provider_config,
    research, settings, system, watchlist,
)
```

Add the router registration (after `llm_usage`):

```python
app.include_router(llm_pricing.router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/test_llm_pricing_api.py -v
```

Expected: 2 tests PASS

---

## Task 4: Frontend — update `llmPricing.ts` with live cache

**Files:**

- Modify: `frontend/lib/llmPricing.ts`
- Modify: `frontend/components/settings/AISettings.tsx`

- [ ] **Step 1: Replace `frontend/lib/llmPricing.ts` with cache version**

```typescript
// frontend/lib/llmPricing.ts
export interface ModelPricing {
  inputPerMToken: number;
  outputPerMToken: number;
}

// Bundled fallback — used synchronously before fetch completes or on fetch failure.
// Keep in sync with backend/app/core/llm_pricing.py whenever models change.
const BUNDLED_PRICING: Record<string, ModelPricing> = {
  // Anthropic
  "claude-opus-4-7": { inputPerMToken: 5.0, outputPerMToken: 25.0 },
  "claude-sonnet-4-6": { inputPerMToken: 3.0, outputPerMToken: 15.0 },
  "claude-haiku-4-5-20251001": { inputPerMToken: 1.0, outputPerMToken: 5.0 },
  // OpenAI GPT-5 series
  "gpt-5.5": { inputPerMToken: 5.0, outputPerMToken: 30.0 },
  "gpt-5.4": { inputPerMToken: 2.5, outputPerMToken: 15.0 },
  "gpt-5.4-mini": { inputPerMToken: 0.75, outputPerMToken: 4.5 },
  "gpt-5.4-nano": { inputPerMToken: 0.2, outputPerMToken: 1.25 },
  // OpenAI GPT-4o series
  "gpt-4o": { inputPerMToken: 2.5, outputPerMToken: 10.0 },
  "gpt-4o-mini": { inputPerMToken: 0.15, outputPerMToken: 0.6 },
  // Google Gemini 2.5 series
  "gemini-2.5-pro": { inputPerMToken: 1.25, outputPerMToken: 10.0 },
  "gemini-2.5-flash": { inputPerMToken: 0.3, outputPerMToken: 2.5 },
  "gemini-2.5-flash-lite": { inputPerMToken: 0.1, outputPerMToken: 0.4 },
  // Google Gemini 3 series
  "gemini-3.1-flash-lite": { inputPerMToken: 0.25, outputPerMToken: 1.5 },
  // Google Gemini legacy
  "gemini-1.5-pro": { inputPerMToken: 1.25, outputPerMToken: 5.0 },
  "gemini-1.5-flash": { inputPerMToken: 0.075, outputPerMToken: 0.3 },
  "gemini-2.0-flash": { inputPerMToken: 0.1, outputPerMToken: 0.4 },
};

let _cache: Record<string, ModelPricing> = { ...BUNDLED_PRICING };
let _loading = false;
let _loaded = false;

export async function loadPricing(): Promise<void> {
  if (_loaded || _loading) return;
  _loading = true;
  try {
    const res = await fetch("/api/v1/llm/pricing");
    if (!res.ok) return;
    const data: Record<
      string,
      { input_per_mtoken: number; output_per_mtoken: number }
    > = await res.json();
    _cache = Object.fromEntries(
      Object.entries(data).map(([model, p]) => [
        model,
        {
          inputPerMToken: p.input_per_mtoken,
          outputPerMToken: p.output_per_mtoken,
        },
      ]),
    );
    _loaded = true;
  } catch {
    // silently keep bundled fallback
  } finally {
    _loading = false;
  }
}

const CHARS_PER_TOKEN = 4;

export function estimateTokens(text: string): number {
  return Math.ceil(text.length / CHARS_PER_TOKEN);
}

export function getPricingForModel(model: string): ModelPricing | null {
  if (_cache[model]) return _cache[model];
  const lower = model.toLowerCase();
  for (const [key, pricing] of Object.entries(_cache)) {
    if (
      lower.includes(key.toLowerCase()) ||
      key.toLowerCase().includes(lower)
    ) {
      return pricing;
    }
  }
  return null;
}

export function estimateCostUsd(
  model: string,
  inputTokens: number,
  outputTokens: number,
): number {
  const pricing = getPricingForModel(model);
  if (!pricing) return 0;
  return (
    (inputTokens / 1_000_000) * pricing.inputPerMToken +
    (outputTokens / 1_000_000) * pricing.outputPerMToken
  );
}
```

- [ ] **Step 2: Call `loadPricing()` in `AISettings.tsx`**

In `frontend/components/settings/AISettings.tsx`, find the existing imports and add:

```typescript
import { loadPricing } from "@/lib/llmPricing";
```

Inside the component body (before the return), add a `useEffect`:

```typescript
useEffect(() => {
  loadPricing();
}, []);
```

---

## Task 5: Fix `$` symbols and VerdictCard cost display

**Files:**

- Modify: `frontend/components/analysis/VerdictCard.tsx`
- Modify: `frontend/app/(auth)/events/page.tsx`
- Modify: `frontend/app/(auth)/watchlist/page.tsx`

- [ ] **Step 1: Fix `VerdictCard.tsx` — target price (line 149) and cost line (line 155)**

Read the file first, then make two edits.

**Edit 1** — Fix target price display (line 149).

Find:

```tsx
                    : `$${displayed.target_price.toFixed(2)}`}
```

Replace with:

```tsx
                    : `${displayed.target_price.toFixed(2)} USD`}
```

**Edit 2** — Fix cost display (line 155) to use primary currency.

First add the import for `useDualCurrency` at the top of the file (after existing imports):

```typescript
import { useDualCurrency } from "@/hooks/useDualCurrency";
```

Then inside the component function body (before the return), add:

```typescript
const { formatNative } = useDualCurrency();
```

Then find:

```tsx
              {displayed.model} · ${displayed.cost_usd.toFixed(4)} ·{" "}
```

Replace with:

```tsx
              {displayed.model} · {formatNative(displayed.cost_usd, "USD", 4).primary} ·{" "}
```

- [ ] **Step 2: Fix `events/page.tsx` — suggested price (line 261)**

Find:

```tsx
<span className="text-sm font-medium">Target: ${analysis.suggested_price}</span>
```

Replace with:

```tsx
<span className="text-sm font-medium">
  Target: {parseFloat(analysis.suggested_price).toFixed(2)} USD
</span>
```

- [ ] **Step 3: Fix `watchlist/page.tsx` — suggested price (line 639)**

Find:

```tsx
                        suggested ${parseFloat(s.suggested_price).toFixed(2)}
```

Replace with:

```tsx
                        suggested {parseFloat(s.suggested_price).toFixed(2)} USD
```

---

## Task 6: Fix AI usage page — remove hardcoded `฿` and "Cost (THB)"

**Files:**

- Modify: `frontend/app/(auth)/ai-usage/page.tsx`

The page already uses `useDualCurrency` and `DualCurrencyAmount` for most cost cells. Two spots still use the old pattern.

- [ ] **Step 1: Fix the table header (line 474)**

Find:

```tsx
<th className="text-right py-2">Cost (THB)</th>
```

Replace with:

```tsx
<th className="text-right py-2">Cost</th>
```

- [ ] **Step 2: Fix the cost cell (line 489)**

Find:

```tsx
<td className="py-2 text-right">฿{log.cost_thb.toFixed(4)}</td>
```

Replace with:

```tsx
<td className="py-2 text-right">
  <DualCurrencyAmount value={formatNative(log.cost_usd, "USD", 6)} inline />
</td>
```

`formatNative` and `DualCurrencyAmount` are already imported and in scope at line 185 (`const { formatNative } = useDualCurrency();`).

---

## Self-Review Notes

- Spec §1 (backend core module): covered by Tasks 1–2
- Spec §2 (frontend pricing cache): covered by Task 4
- Spec §3a (3 `$` fixes): covered by Task 5 steps 1–3
- Spec §3b (VerdictCard cost → primary currency): covered by Task 5 step 1
- Spec §3c (AI usage page): covered by Task 6
- `llm_gateway.py` imports `calc_cost` from `llm_service` via re-export — no changes needed there
- No migration needed (no DB changes)
- `cost_thb` field on the log interface remains in the TypeScript type but the cell no longer reads it — acceptable; removing the field from the type is out of scope
