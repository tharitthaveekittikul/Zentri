# LLM Gateway & Prompt Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul LLMGateway to inject current_date universally, make age context opt-in per feature, support format_map on system prompts, and rewrite all feature prompts to best-practice standards.

**Architecture:** All changes are confined to `llm_gateway.py` (gateway logic + prompt constants) and the one service/API that calls `portfolio_analysis`. Age context is split: system prefix for conversational features, human prompt variables for analysis features. Both system and human prompts are formatted with `str.format_map()`.

**Tech Stack:** Python, SQLAlchemy async, FastAPI, pytest

---

## File Map

| File | Change |
|---|---|
| `backend/app/services/llm_gateway.py` | Add constants, refactor `complete()`, rewrite prompts |
| `backend/app/api/portfolio.py` or service that calls `portfolio_analysis` | Pass new variables dict |
| `backend/tests/test_llm_gateway.py` | Extend with new gateway behaviour tests |
| `frontend/components/settings/ModelTooltip.tsx` | NEW: tooltip with recommendation data |
| `frontend/app/(auth)/settings/` | Wire tooltip to feature LLM config selector |

---

### Task 1: Add FEATURES_WITH_AGE_CONTEXT constants and refactor LLMGateway.complete()

**Files:**
- Modify: `backend/app/services/llm_gateway.py`
- Test: `backend/tests/test_llm_gateway.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_llm_gateway.py`:

```python
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.services.llm_gateway import LLMGateway, FEATURES_WITH_AGE_CONTEXT, FEATURES_AGE_IN_HUMAN_PROMPT

class FakeUser:
    def __init__(self, birth_date=None, plan_to_age=None, currency_primary="USD"):
        self.id = uuid.uuid4()
        self.birth_date = birth_date
        self.plan_to_age = plan_to_age
        self.currency_primary = currency_primary

@pytest.mark.asyncio
async def test_current_date_always_injected(mock_gateway_deps):
    """current_date prefix appears in system prompt for every feature."""
    gw, mock_adapter, _ = mock_gateway_deps
    await gw.complete("import_translator", uuid.uuid4(), {"file_format": "csv", "headers": "a,b", "sample_rows": "1,2"})
    system_arg = mock_adapter.complete.call_args[0][0]
    assert "Current date:" in system_arg

@pytest.mark.asyncio
async def test_age_context_NOT_injected_for_import_translator(mock_gateway_deps_with_user):
    """import_translator must never receive age context."""
    gw, mock_adapter, _ = mock_gateway_deps_with_user
    await gw.complete("import_translator", uuid.uuid4(), {"file_format": "csv", "headers": "a,b", "sample_rows": "1,2"})
    system_arg = mock_adapter.complete.call_args[0][0]
    human_arg = mock_adapter.complete.call_args[0][1]
    assert "planning horizon" not in system_arg
    assert "planning horizon" not in human_arg

@pytest.mark.asyncio
async def test_age_context_in_system_for_watchlist_scan(mock_gateway_deps_with_user):
    """watchlist_scan gets age context in system prompt prefix."""
    gw, mock_adapter, _ = mock_gateway_deps_with_user
    await gw.complete("watchlist_scan", uuid.uuid4(), {"symbol": "AAPL", "prices_txt": "...", "rag_context": "..."})
    system_arg = mock_adapter.complete.call_args[0][0]
    assert "planning horizon" in system_arg

@pytest.mark.asyncio
async def test_age_context_in_human_for_portfolio_analysis(mock_gateway_deps_with_user):
    """portfolio_analysis gets age context in human prompt, NOT system."""
    gw, mock_adapter, _ = mock_gateway_deps_with_user
    variables = {
        "holdings_table": "AAPL | 10 | 150 | 170 | 1700 | 50%",
        "cash_table": "USD | 1000 | 1000",
        "perf_1m": "5.2", "perf_3m": "12.1", "perf_ytd": "8.3",
        "total_value": "3400",
    }
    await gw.complete("portfolio_analysis", uuid.uuid4(), variables)
    system_arg = mock_adapter.complete.call_args[0][0]
    human_arg = mock_adapter.complete.call_args[0][1]
    assert "planning horizon" not in system_arg
    assert "planning until age" in human_arg

@pytest.mark.asyncio
async def test_primary_currency_formatted_in_system(mock_gateway_deps_with_user):
    """primary_currency variable replaces {primary_currency} in system prompt."""
    gw, mock_adapter, user = mock_gateway_deps_with_user
    user.currency_primary = "THB"
    variables = {
        "holdings_table": "", "cash_table": "",
        "perf_1m": "0", "perf_3m": "0", "perf_ytd": "0", "total_value": "0",
    }
    await gw.complete("portfolio_analysis", user.id, variables)
    system_arg = mock_adapter.complete.call_args[0][0]
    assert "THB" in system_arg
    assert "{primary_currency}" not in system_arg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py::test_current_date_always_injected tests/test_llm_gateway.py::test_age_context_NOT_injected_for_import_translator -v
```
Expected: `FAILED` — constants don't exist yet.

- [ ] **Step 3: Add constants and refactor complete() in llm_gateway.py**

At the top of `backend/app/services/llm_gateway.py`, after existing imports, add:

```python
from datetime import datetime

FEATURES_WITH_AGE_CONTEXT: frozenset = frozenset({
    "portfolio_analysis",
    "chat",
    "watchlist_scan",
    "watchlist_discovery",
    "ipo_analysis",
    "overview_analysis",
})

FEATURES_AGE_IN_HUMAN_PROMPT: frozenset = frozenset({
    "portfolio_analysis",
    "overview_analysis",
})
```

Replace the body of `LLMGateway.complete()` with:

```python
async def complete(self, feature_key: str, user_id: uuid.UUID, variables: dict) -> LLMGatewayResult:
    from app.models.llm_call_log import LLMCallLog

    config = await self._get_feature_config(feature_key, user_id)
    provider = await self._get_provider(config.provider_config_id)
    api_key = decrypt(provider.encrypted_api_key) if provider.encrypted_api_key else None
    adapter = _build_adapter(provider.provider, api_key, provider.host_url)

    user_row = (await self._db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    # Build mutable copy — add universal variables
    vars_ = dict(variables)
    vars_["current_date"] = datetime.now().strftime("%A, %Y-%m-%d")
    if user_row:
        vars_["primary_currency"] = getattr(user_row, "currency_primary", None) or "USD"

    # Age context — opt-in per feature
    age_prefix = ""
    if feature_key in FEATURES_WITH_AGE_CONTEXT and user_row:
        age_ctx = get_user_age_context(user_row)
        if age_ctx:
            if feature_key in FEATURES_AGE_IN_HUMAN_PROMPT:
                vars_["current_age"] = age_ctx["current_age"]
                vars_["plan_to_age"] = age_ctx["plan_to_age"]
                vars_["years_remaining"] = age_ctx["years_remaining"]
            else:
                age_prefix = f"{age_ctx['prompt']}\n\n"

    system_template = config.system_prompt or DEFAULT_SYSTEM_PROMPTS.get(feature_key, "")
    human_template = HUMAN_PROMPTS[feature_key]

    current_date_prefix = f"Current date: {vars_['current_date']}\n\n"
    system = current_date_prefix + age_prefix + system_template.format_map(vars_)
    human = human_template.format_map(vars_)

    logger.info("LLM call: feature=%s provider=%s model=%s", feature_key, provider.provider, config.model)
    response: LLMResponse = await adapter.complete(system, human, config.model)

    usd_thb = await get_current_usd_thb(self._db)
    cost_thb = float(response.cost_usd) * float(usd_thb) if usd_thb else 0.0

    log = LLMCallLog(
        user_id=user_id,
        feature_key=feature_key,
        provider=provider.provider,
        model=config.model,
        prompt_in=f"SYSTEM: {system}\n\nHUMAN: {human}",
        response_out=response.content,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=response.cost_usd,
        cost_thb=cost_thb,
        exchange_rate=float(usd_thb) if usd_thb else 0.0,
    )
    self._db.add(log)
    await self._db.flush()

    logger.info("LLM logged: tokens_in=%d tokens_out=%d cost_usd=%.6f",
                response.tokens_in, response.tokens_out, response.cost_usd)
    return LLMGatewayResult(
        content=response.content,
        prompt=human,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=float(response.cost_usd),
        cost_thb=cost_thb,
        exchange_rate=float(usd_thb) if usd_thb else 0.0,
        model=config.model,
        provider=provider.provider,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py -v
```
Expected: all new tests `PASSED`.

---

### Task 2: Rewrite DEFAULT_SYSTEM_PROMPTS

**Files:**
- Modify: `backend/app/services/llm_gateway.py`

- [ ] **Step 1: Write failing test for portfolio_analysis system prompt content**

```python
def test_portfolio_analysis_system_prompt_no_thai_investor():
    from app.services.llm_gateway import DEFAULT_SYSTEM_PROMPTS
    prompt = DEFAULT_SYSTEM_PROMPTS["portfolio_analysis"]
    assert "Thai investor" not in prompt
    assert "THB" not in prompt
    assert "{primary_currency}" in prompt
    assert "GOOD" in prompt and "FAIR" in prompt and "POOR" in prompt

def test_chat_system_prompt_has_finance_guardrail():
    from app.services.llm_gateway import DEFAULT_SYSTEM_PROMPTS
    prompt = DEFAULT_SYSTEM_PROMPTS["chat"]
    assert "out_of_scope" in prompt
    assert "finance" in prompt.lower()

def test_watchlist_scan_reasoning_constraint():
    from app.services.llm_gateway import DEFAULT_SYSTEM_PROMPTS
    prompt = DEFAULT_SYSTEM_PROMPTS["watchlist_scan"]
    assert "2 sentences" in prompt
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py::test_portfolio_analysis_system_prompt_no_thai_investor tests/test_llm_gateway.py::test_chat_system_prompt_has_finance_guardrail -v
```
Expected: `FAILED`.

- [ ] **Step 3: Replace DEFAULT_SYSTEM_PROMPTS in llm_gateway.py**

Replace the entire `DEFAULT_SYSTEM_PROMPTS` dict:

```python
DEFAULT_SYSTEM_PROMPTS: dict[str, str] = {
    "import_translator": (
        "You are a financial data normalization expert. Given a broker export file's structure "
        "and sample data, produce a JSON template that maps source fields to the canonical schema.\n\n"
        "CANONICAL FIELDS (use ONLY these as field_map values):\n"
        "trade_date, type, symbol, unit, price, currency, exchange, gross_amount, fee, "
        "gross_thb, fee_thb, exchange_rate, asset_type, platform, notes\n\n"
        "FIELD NOTES:\n"
        "- trade_date: output as dd/mm/yyyy (e.g. 26/04/2026). Convert any other format.\n"
        "- symbol: ALWAYS map the fund code / ticker / symbol source column to this. Never omit it.\n"
        "- type: ALWAYS map the source column that contains transaction type (Buy, Sell, Buy Note, etc.) "
        "  to 'type' in field_map. If you use value_transforms for 'type', the source column MUST also "
        "  appear in field_map (e.g. {\"Template\": \"type\"}). A value_transform without a field_map "
        "  entry has no effect.\n"
        "- price: cost per unit. Derive it via derived_fields (e.g. 'gross_amount / unit') if not explicit.\n"
        "- exchange: the stock exchange (e.g. SET, mai, NYSE, NASDAQ, FUND). Infer from context or set "
        "  a sensible default (Thai mutual funds → 'FUND', Thai stocks → 'SET', US stocks → 'NYSE').\n\n"
        "VALID type VALUES: BUY, SELL, DIVIDEND, REWARD, FEE, TRANSFER\n"
        "VALID asset_type VALUES: us_stock, thai_stock, th_fund, etf, crypto, gold, cash\n\n"
        "For nested JSON files, set json_path to the key path to the transaction array "
        "(e.g. \"transactions\"). For CSV or top-level arrays, set json_path to null.\n\n"
        "Return ONLY valid JSON — no explanation, no markdown:\n"
        "{\n"
        "  \"file_format\": \"csv\" or \"json\",\n"
        "  \"json_path\": null or \"transactions\",\n"
        "  \"field_map\": {\"source_col\": \"canonical_field\", ...},\n"
        "  \"value_transforms\": {\"type\": {\"Buy Note\": \"BUY\"}},\n"
        "  \"derived_fields\": {\"gross_thb\": \"unit * price * exchange_rate\"},\n"
        "  \"defaults\": {\"currency\": \"THB\", \"platform\": \"Broker Name\", \"exchange\": \"FUND\"},\n"
        "  \"asset_type_rules\": [{\"field\": \"exchange\", \"values\": [\"SET\"], \"asset_type\": \"thai_stock\"}],\n"
        "  \"asset_type_fallback\": \"thai_stock\"\n"
        "}"
    ),
    "portfolio_analysis": (
        "You are a portfolio advisor. Analyze the portfolio and provide actionable guidance "
        "on allocation, risk balance, and rebalancing opportunities suited to the user's age "
        "and investment horizon.\n\n"
        "Respond ONLY with valid JSON — no markdown, no explanation outside the object:\n"
        "{{\n"
        "  \"health\": \"GOOD\" | \"FAIR\" | \"POOR\",\n"
        "  \"insights\": [\n"
        "    {{\n"
        "      \"type\": \"OVERWEIGHT\" | \"UNDERWEIGHT\" | \"REBALANCE\" | \"BUY\" | \"SELL\" | \"RISK\" | \"DIVERSIFY\",\n"
        "      \"symbol\": \"<ticker or null>\",\n"
        "      \"title\": \"<5 words max>\",\n"
        "      \"message\": \"<2 sentences max>\",\n"
        "      \"priority\": \"HIGH\" | \"MEDIUM\" | \"LOW\"\n"
        "    }}\n"
        "  ],\n"
        "  \"summary\": \"<3 sentences max>\"\n"
        "}}\n"
        "Provide 3–5 insights only. Be specific with numbers. "
        "Use {{primary_currency}} as base currency."
    ),
    "chat": (
        "You are a finance assistant for Zentri. Help users understand their portfolio, "
        "investments, markets, and topics that affect financial markets "
        "(economics, policy, geopolitics, macro events).\n\n"
        "You have tools to fetch real user data — call them when the question needs actual numbers.\n\n"
        "SCOPE: Only answer finance-relevant questions. "
        "For anything off-topic respond with:\n"
        "  {{\"type\": \"out_of_scope\", \"message\": \"I can only help with finance topics — "
        "try asking about your portfolio, holdings, market news, or investment ideas.\"}}\n\n"
        "For finance answers respond with:\n"
        "  {{\"type\": \"answer\", \"message\": \"<your answer, 150 words max>\"}}\n\n"
        "Be concise. No bullet lists longer than 5 items. No filler."
    ),
    "watchlist_scan": (
        "You are a financial analyst evaluating an asset as a potential buy opportunity. "
        "The user does not currently hold this asset. Analyze the recent price history and research context. "
        "Respond ONLY with valid JSON in this exact format:\n"
        "{\"verdict\": \"BUY\" | \"SELL\" | \"HOLD\", \"suggested_price\": <number or null>, "
        "\"reasoning\": \"<2 sentences max>\"}\n"
        "Do not include any text outside the JSON object."
    ),
    "watchlist_discovery": (
        "You are a portfolio advisor. Based on the user's current holdings, suggest assets they should consider watching. "
        "Respond ONLY with a valid JSON array in this exact format:\n"
        "[{\"symbol\": \"<TICKER>\", \"verdict\": \"BUY\" | \"SELL\" | \"HOLD\", "
        "\"suggested_price\": <number or null>, \"reasoning\": \"<2 sentences max>\"}]\n"
        "Suggest exactly 3 to 5 assets not already in the portfolio or watchlist. "
        "Do not include any text outside the JSON array."
    ),
    "ipo_analysis": (
        "You are a financial analyst specializing in IPO evaluations. "
        "Given IPO data, assess whether to Buy, Watch, or Skip this offering. "
        "Provide a suggested entry price and concise reasoning. "
        "Respond ONLY with valid JSON in this exact format:\n"
        "{\"verdict\": \"BUY\" | \"WATCH\" | \"SKIP\", \"suggested_price\": <number or null>, "
        "\"reasoning\": \"<2 sentences max>\"}\n"
        "Do not include any text outside the JSON object."
    ),
    "overview_analysis": (
        "You are a portfolio coach. Review the user's complete portfolio and give honest, "
        "concise guidance on how well they are positioned for their age and goals.\n\n"
        "portfolio_adherence_pct: estimated % alignment with an age-appropriate diversified "
        "strategy (0 = poorly aligned, 100 = ideal alignment).\n\n"
        "Respond ONLY with valid JSON — no markdown, no explanation outside the object:\n"
        "{{\n"
        "  \"score\": <0-100>,\n"
        "  \"grade\": \"A\" | \"B\" | \"C\" | \"D\",\n"
        "  \"portfolio_adherence_pct\": <0-100>,\n"
        "  \"health\": \"GOOD\" | \"FAIR\" | \"POOR\",\n"
        "  \"insights\": [\n"
        "    {{\n"
        "      \"type\": \"info\" | \"warning\" | \"critical\",\n"
        "      \"title\": \"<5 words max>\",\n"
        "      \"message\": \"<1 sentence>\"\n"
        "    }}\n"
        "  ],\n"
        "  \"top_action\": \"<single most important thing to do next, 1 sentence>\"\n"
        "}}\n"
        "Max 5 insights. No filler."
    ),
}
```

> **Note on double braces:** Python f-string–style format requires `{{` and `}}` to produce literal `{` and `}` in the output when the string is later passed through `.format_map()`. The `import_translator` prompt does NOT use `{primary_currency}` so its braces are already literal — leave them as-is (they are already escaped in the original).

- [ ] **Step 4: Rewrite HUMAN_PROMPTS — update portfolio_analysis entry**

Replace only the `"portfolio_analysis"` entry in `HUMAN_PROMPTS`:

```python
"portfolio_analysis": (
    "User: age {current_age}, planning until age {plan_to_age} ({years_remaining} years remaining)\n\n"
    "Holdings:\n{holdings_table}\n\n"
    "Cash:\n{cash_table}\n\n"
    "Performance: 1M {perf_1m}%  3M {perf_3m}%  YTD {perf_ytd}%\n\n"
    "Total portfolio value: {total_value} {primary_currency}"
),
```

Add `"overview_analysis"` entry to `HUMAN_PROMPTS`:

```python
"overview_analysis": (
    "User: age {current_age}, planning until age {plan_to_age} ({years_remaining} years remaining)\n\n"
    "Holdings:\n{holdings_table}\n\n"
    "Cash:\n{cash_table}\n\n"
    "Allocation breakdown:\n{allocation_table}\n\n"
    "Performance: 1M {perf_1m}%  3M {perf_3m}%  YTD {perf_ytd}%\n\n"
    "Total portfolio value: {total_value} {primary_currency}"
),
```

- [ ] **Step 5: Run all tests**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py -v
```
Expected: all tests `PASSED`.

---

### Task 3: Update portfolio_analysis caller to pass new variables

**Files:**
- Find and modify: the service/API that calls `gateway.complete("portfolio_analysis", ...)`

- [ ] **Step 1: Locate the caller**

```bash
cd backend && grep -r "portfolio_analysis" app/ --include="*.py" -l
```

- [ ] **Step 2: Write failing test for variable shape**

In the test file for the found caller, add:

```python
async def test_portfolio_analysis_variables_include_holdings_table(client, auth_headers, db_with_holdings):
    """POST to portfolio analysis endpoint must pass holdings_table, cash_table, perf_* to gateway."""
    with patch("app.services.llm_gateway.LLMGateway.complete") as mock_complete:
        mock_complete.return_value = MagicMock(content='{"health":"GOOD","insights":[],"summary":"ok"}')
        resp = await client.post("/portfolio/analyze", headers=auth_headers)
        assert resp.status_code == 200
        call_variables = mock_complete.call_args[0][2]  # 3rd arg is variables dict
        assert "holdings_table" in call_variables
        assert "cash_table" in call_variables
        assert "perf_1m" in call_variables
        assert "total_value" in call_variables
```

- [ ] **Step 3: Update the caller**

In the found caller file, replace the variables dict passed to `gateway.complete("portfolio_analysis", ...)` with:

```python
from app.services import overview as overview_svc

summary = await overview_svc.get_summary(db, user.id, user.currency_primary)
allocation = await overview_svc.get_allocation(db, user.id, user.currency_primary)
performance = await overview_svc.get_performance(db, user.id, "1M")

# Build holdings_table: symbol | asset_type | qty | avg_cost | current_price | value | alloc_%
holdings_rows = "\n".join(
    f"{h['symbol']} | {h.get('asset_type','')} | {h.get('quantity','')} | "
    f"{h.get('avg_cost','')} | {h.get('current_price','')} | "
    f"{h.get('current_value','')} | {h.get('allocation_pct','')}%"
    for h in (summary.holdings if hasattr(summary, 'holdings') else [])
)

# Build cash_table: currency | amount | value_primary
cash_rows = "\n".join(
    f"{c.currency} | {c.amount} | {c.value_primary}"
    for c in (summary.cash_accounts if hasattr(summary, 'cash_accounts') else [])
)

perf_1m = getattr(performance, 'change_pct', 0) or 0

variables = {
    "holdings_table": holdings_rows or "No holdings",
    "cash_table": cash_rows or "No cash accounts",
    "perf_1m": f"{perf_1m:.2f}",
    "perf_3m": "N/A",
    "perf_ytd": "N/A",
    "total_value": str(getattr(summary, 'total_value', 0)),
}
result = await gateway.complete("portfolio_analysis", user.id, variables)
```

> Adjust field names to match the actual schema returned by `overview_svc`. Run the test after checking the actual field names.

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/ -k "portfolio_analysis" -v
```
Expected: `PASSED`.

---

### Task 4: Model Recommendation Tooltip (Frontend)

**Files:**
- Create: `frontend/components/settings/ModelTooltip.tsx`
- Modify: Settings page that renders the feature LLM config model selector

- [ ] **Step 1: Create tooltip data constant**

Create `frontend/lib/modelRecommendations.ts`:

```typescript
export interface ModelRecommendation {
  tier: string
  recommended: string[]
  why: string
  alternatives: string[]
}

export const MODEL_RECOMMENDATIONS: Record<string, ModelRecommendation> = {
  import_translator: {
    tier: "Small",
    recommended: ["claude-haiku-3-5", "gpt-4o-mini", "gemini-flash"],
    why: "Pure JSON field mapping — no financial reasoning needed. Use the cheapest model.",
    alternatives: ["Any small/fast model works well here"],
  },
  portfolio_analysis: {
    tier: "Mid",
    recommended: ["claude-sonnet-4-6", "gpt-4o"],
    why: "Needs financial reasoning and structured JSON output with actionable insights.",
    alternatives: ["claude-opus-4-7 for deeper analysis (higher cost)"],
  },
  chat: {
    tier: "Mid",
    recommended: ["claude-sonnet-4-6", "gpt-4o"],
    why: "Tool-calling support and reasoning both required for finance Q&A.",
    alternatives: ["claude-haiku-4-5 for lighter usage (may miss nuance)"],
  },
  watchlist_scan: {
    tier: "Mid",
    recommended: ["claude-sonnet-4-6", "gpt-4o"],
    why: "Market analysis and buy/sell decisions require good reasoning.",
    alternatives: ["claude-opus-4-7 for more thorough analysis"],
  },
  watchlist_discovery: {
    tier: "Small–Mid",
    recommended: ["claude-haiku-4-5", "gpt-4o-mini"],
    why: "Holdings are already structured; discovery is a lighter reasoning task.",
    alternatives: ["claude-sonnet-4-6 for better suggestions"],
  },
  ipo_analysis: {
    tier: "Mid",
    recommended: ["claude-sonnet-4-6", "gpt-4o"],
    why: "IPO evaluation needs financial depth and sector knowledge.",
    alternatives: ["claude-opus-4-7 for complex offerings"],
  },
  overview_analysis: {
    tier: "Mid",
    recommended: ["claude-sonnet-4-6", "gpt-4o"],
    why: "Holistic portfolio coaching needs broad financial reasoning.",
    alternatives: ["claude-opus-4-7 for detailed guidance"],
  },
}
```

- [ ] **Step 2: Create ModelTooltip component**

Create `frontend/components/settings/ModelTooltip.tsx`:

```tsx
import { Info } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { MODEL_RECOMMENDATIONS } from "@/lib/modelRecommendations"

interface Props {
  featureKey: string
}

export function ModelTooltip({ featureKey }: Props) {
  const rec = MODEL_RECOMMENDATIONS[featureKey]
  if (!rec) return null

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Info className="h-4 w-4 text-muted-foreground cursor-help" />
        </TooltipTrigger>
        <TooltipContent className="max-w-xs space-y-2">
          <p className="font-medium">Recommended: {rec.tier} tier</p>
          <p className="text-sm">{rec.why}</p>
          <div>
            <p className="text-xs text-muted-foreground font-medium">Best models:</p>
            <ul className="text-xs text-muted-foreground list-disc list-inside">
              {rec.recommended.map((m) => <li key={m}>{m}</li>)}
            </ul>
          </div>
          <div>
            <p className="text-xs text-muted-foreground font-medium">Alternatives:</p>
            <ul className="text-xs text-muted-foreground list-disc list-inside">
              {rec.alternatives.map((a) => <li key={a}>{a}</li>)}
            </ul>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
```

- [ ] **Step 3: Wire into feature LLM config model selector**

Find the settings page/component that renders the model input for each feature. Add `<ModelTooltip featureKey={config.feature_key} />` next to the model label:

```tsx
// In the model field row, e.g.:
<div className="flex items-center gap-2">
  <label>Model</label>
  <ModelTooltip featureKey={config.feature_key} />
</div>
```

- [ ] **Step 4: Verify visually**

Start dev server and navigate to Settings → AI. Hover the info icon next to each feature's model field — tooltip should appear with tier, why, and alternatives.

```bash
cd frontend && npm run dev
```
