# LLM Prompt Engineering & Overview AI Analysis Design

**Date:** 2026-05-08
**Scope:** Prompt quality overhaul for all 6 existing features + new `overview_analysis` feature + chat tool-calling architecture + news RAG + cost UX

---

## 1. Universal Gateway Changes

### 1.1 Current Date Injection (all features)
Inject into every system prompt prefix, unconditionally:
```
Current date: {current_date}  (e.g. 2026-05-08, Thursday)
```
Implemented in `LLMGateway.complete()` before all other prefixes.

### 1.2 Age Context — Opt-In Per Feature
Currently prepended to ALL system prompts. Must become opt-in.

**Rule:** inject only when the task involves personal investment decisions.

```python
FEATURES_WITH_AGE_CONTEXT: frozenset = frozenset({
    "portfolio_analysis",
    "chat",
    "watchlist_scan",
    "watchlist_discovery",
    "ipo_analysis",
    "overview_analysis",
})
```

For these features, age context goes into:
- **System prompt prefix** for conversational/one-shot tasks: `chat`, `watchlist_scan`, `watchlist_discovery`, `ipo_analysis`
- **Human prompt** (as data, via `variables` dict) for analysis tasks: `portfolio_analysis`, `overview_analysis`

`import_translator` — no age context, ever.

**Gateway implementation note:** for `portfolio_analysis` and `overview_analysis`, pass `current_age`, `plan_to_age`, `years_remaining` as keys in the `variables` dict so they are formatted into the human prompt via `.format(**variables)`. Do NOT prepend age prefix to system prompt for these two features.

### 1.3 System Prompt Variable Formatting
System prompts may contain `{primary_currency}` and `{current_date}` template variables. `LLMGateway.complete()` must format **both** system and human prompts with the variables dict before sending to the adapter:
```python
system = system_template.format_map(variables)   # safe — unknown keys left as-is
human  = human_template.format_map(variables)
```
Use `str.format_map()` (not `.format()`) so missing keys don't raise `KeyError`.

### 1.4 AI Usage Tracking
Every `LLMGateway.complete()` call already logs to `LLMCallLog`. All new features (`overview_analysis`, chat tool-calls) must follow the same pattern. Each individual tool call in chat logs separately so users see per-message cost breakdown in ai-usage.

---

## 2. Feature Prompts

### 2.1 `import_translator`
**No changes.** System and human prompts are best-in-class. Age context: ❌.

---

### 2.2 `portfolio_analysis`

**Age context:** ✅ injected into human prompt (it's per-request data, not a static role instruction).

**System prompt:**
```
Current date: {current_date}

You are a portfolio advisor. Analyze the portfolio and provide actionable
guidance on allocation, risk balance, and rebalancing opportunities
suited to the user's age and investment horizon.

Respond ONLY with valid JSON — no markdown, no explanation outside the object:
{
  "health": "GOOD" | "FAIR" | "POOR",
  "insights": [
    {
      "type": "OVERWEIGHT" | "UNDERWEIGHT" | "REBALANCE" | "BUY" | "SELL" | "RISK" | "DIVERSIFY",
      "symbol": "<ticker or null>",
      "title": "<5 words max>",
      "message": "<2 sentences max>",
      "priority": "HIGH" | "MEDIUM" | "LOW"
    }
  ],
  "summary": "<3 sentences max>"
}
Provide 3–5 insights only. Be specific with numbers. Use {primary_currency} as base currency.
```

**Human prompt:**
```
User: age {current_age}, planning until age {plan_to_age} ({years_remaining} years remaining)

Holdings:
{holdings_table}

Cash:
{cash_table}

Performance: 1M {perf_1m}%  3M {perf_3m}%  YTD {perf_ytd}%

Total portfolio value: {total_value} {primary_currency}
```

`holdings_table` columns: `symbol | asset_type | qty | avg_cost | current_price | value_{primary_currency} | alloc_%`
`cash_table` columns: `currency | amount | value_{primary_currency}`

---

### 2.3 `chat` (tool-calling, major change)

**Age context:** ✅ injected into system prompt prefix (persistent user profile shaping all responses).

**System prompt:**
```
Current date: {current_date}
User context: age {current_age}, planning until age {plan_to_age} ({years_remaining} years remaining).

You are a finance assistant for Zentri. Help users understand their portfolio,
investments, markets, and topics that affect financial markets
(economics, policy, geopolitics, macro events).

You have tools to fetch real user data — call them when the question needs actual numbers.

SCOPE: Only answer finance-relevant questions.
For anything off-topic respond with:
  {"type": "out_of_scope", "message": "I can only help with finance topics — try asking about your portfolio, holdings, market news, or investment ideas."}

For all finance answers respond with:
  {"type": "answer", "message": "<your answer, 150 words max>"}

Be concise. No bullet lists longer than 5 items. No filler.
```

**Human prompt:** `{message}` only — context comes via tool calls.

**Tools exposed to LLM:**
| Tool | Returns |
|---|---|
| `get_portfolio_summary()` | total value, allocation breakdown, health |
| `get_holdings()` | full holdings list with current prices |
| `get_holding_detail(symbol)` | deep detail on one ticker |
| `get_cash_balance()` | cash by currency |
| `get_performance(range)` | 1M / 3M / YTD / 1Y performance |
| `search_news(query, symbol?)` | top 5 relevant news articles from RAG + API |

**`data_used` field:** populated server-side from actual tool call records — not by the LLM (LLMs can hallucinate tool call history). Before returning response to frontend, gateway injects `data_used: [list of tool names called]`.

**Finance guardrail:** enforced by system prompt instruction + structured `out_of_scope` response type. No pre-filter LLM call needed. Frontend detects `type: "out_of_scope"` and renders a styled redirect card.

---

### 2.4 `watchlist_scan`

**Age context:** ✅ system prompt prefix.

**System prompt change:** add to reasoning field constraint:
```
"reasoning": "<2 sentences max>"
```
No other changes — output format already excellent.

---

### 2.5 `watchlist_discovery`

**Age context:** ✅ system prompt prefix.

**System prompt change:** add:
```
"reasoning": "<2 sentences max per suggestion>"
```

---

### 2.6 `ipo_analysis`

**Age context:** ✅ system prompt prefix.

**System prompt change:** add:
```
"reasoning": "<2 sentences max>"
```

---

### 2.7 `overview_analysis` (NEW)

**Age context:** ✅ injected into human prompt.

**System prompt:**
```
Current date: {current_date}

You are a portfolio coach. Review the user's complete portfolio and give honest,
concise guidance on how well they are positioned for their age and goals.

portfolio_adherence_pct: estimated % alignment with an age-appropriate diversified
strategy (0 = poorly aligned, 100 = ideal alignment).

Respond ONLY with valid JSON — no markdown, no explanation outside the object:
{
  "score": <0–100>,
  "grade": "A" | "B" | "C" | "D",
  "portfolio_adherence_pct": <0–100>,
  "health": "GOOD" | "FAIR" | "POOR",
  "insights": [
    {
      "type": "info" | "warning" | "critical",
      "title": "<5 words max>",
      "message": "<1 sentence>"
    }
  ],
  "top_action": "<single most important thing to do next, 1 sentence>"
}
Max 5 insights. No filler.
```

**Human prompt:**
```
User: age {current_age}, planning until age {plan_to_age} ({years_remaining} years remaining)

Holdings:
{holdings_table}

Cash:
{cash_table}

Allocation breakdown:
{allocation_table}

Performance: 1M {perf_1m}%  3M {perf_3m}%  YTD {perf_ytd}%

Total portfolio value: {total_value} {primary_currency}
```

---

## 3. search_news Tool + RAG Store

### Tool behavior
```
search_news(query, symbol?) called
    ↓
Check RAG store: articles < 6h old matching query/symbol
    ↓ (cache miss)
Fetch from financial news API (Finnhub / Alpha Vantage / existing source)
    ↓
Save to news_rag_store table + generate embedding
    ↓
Return top 5 relevant articles as context to LLM
```

### `news_rag_store` table
```
id, user_id (nullable — shared cache), symbol (nullable),
headline, summary, source, url,
fetched_at, embedding (vector),
created_at
```

### User-visible Research Library
Browsable at a "Research" tab (Watchlist or Chat section).
Filterable by: symbol, date range, source.
Every fetch from chat `search_news` or `watchlist_scan` RAG feeds this store.

---

## 4. Overview AI Analysis Feature

### 4.1 Backend

**New `feature_key`:** `overview_analysis`

**New API endpoints:**
```
POST /overview/ai-analysis          — triggers LLM call, stores result
GET  /overview/ai-analysis/latest   — returns latest stored result for user
```

**New model `OverviewAnalysis`:**
```
id (uuid, pk)
user_id (uuid, fk)
score (int, 0–100)
grade (varchar: A/B/C/D)
portfolio_adherence_pct (int, 0–100)
health (varchar: GOOD/FAIR/POOR)
insights (JSONB)
top_action (text)
provider (varchar)
model (varchar)
tokens_in (int)
tokens_out (int)
cost_usd (numeric)
cost_primary (numeric)        ← cost in user's primary currency
cost_secondary (numeric)      ← cost in user's secondary currency
created_at (timestamptz)
```

**POST flow:**
```
User clicks "Analyze"
    ↓
Confirmation dialog shown (see Section 5)
    ↓
POST /overview/ai-analysis
    ↓
Gateway fetches: holdings + cash + allocation + performance + age_ctx + primary_currency
    ↓
LLMGateway.complete("overview_analysis", user_id, variables)
    ↓
Parse structured JSON response
    ↓
Save to OverviewAnalysis + LLMCallLog
    ↓
Return result to frontend
```

**Re-analysis guard:**
- First POST: if last analysis was < 30 min ago, return HTTP 200 with `{"requires_confirmation": true, "last_analyzed_minutes_ago": N}` — no LLM call fired.
- Frontend shows: *"Already analyzed {N} min ago. Analyze again?"* with [Cancel] / [Confirm].
- Second POST with `?force=true`: bypasses guard, fires LLM call unconditionally.

### 4.2 Frontend — Overview Page Section

**With data:**
```
┌─────────────────────────────────────────────────────┐
│  AI Portfolio Analysis          [Analyze]  🕐 2h ago │
├─────────────────────────────────────────────────────┤
│  Score: 72/100  Grade: B   Adherence: 68%           │
├─────────────────────────────────────────────────────┤
│  ⚠  OVERWEIGHT   You hold 35% in tech — consider   │
│                  trimming NVDA or AAPL.             │
│  ✦  DIVERSIFY    No bond exposure for age 32.       │
│  ✓  GOOD         Cash reserve is healthy at 12%.   │
├─────────────────────────────────────────────────────┤
│  Top action: Reduce NVDA below 15% to match your    │
│              53-year investment horizon.            │
└─────────────────────────────────────────────────────┘
```

**Empty state:**
```
┌─────────────────────────────────────────────────────┐
│  AI Portfolio Analysis                               │
│                                                     │
│  Get AI-powered guidance on your portfolio          │
│  health, allocation, and next steps.                │
│                                                     │
│              [Analyze My Portfolio]                 │
└─────────────────────────────────────────────────────┘
```

---

## 5. Cost UX — Confirmation Dialog + Chat Badge

### 5.1 Confirmation dialog (all one-shot LLM tasks)
Shown before: `portfolio_analysis`, `watchlist_scan`, `watchlist_discovery`, `ipo_analysis`, `overview_analysis`, `import_translator`.

```
┌─────────────────────────────────────┐
│  Run AI Analysis?                   │
│                                     │
│  Feature:   Portfolio Analysis      │
│  Model:     Claude Sonnet           │
│  Provider:  Anthropic               │
│  Est. cost: ฿0.11 / $0.003         │
│                                     │
│        [Cancel]  [Confirm]          │
└─────────────────────────────────────┘
```

- Est. cost calculated client-side: approximate input token count × model pricing
- Cost shown in **primary currency first, secondary currency second**
- Displayed as a rough estimate, not a guarantee

### 5.2 Chat cost badge (persistent, no dialog per message)
```
[Chat header]  Claude Sonnet  ~฿0.04 / $0.001 per message
```
Shown in chat header. Updates if user changes model in settings. No per-message interruption.

---

## 6. Model Recommendations UI

Shown as **tooltip** on model selector in Settings → AI → Feature Config.
Not a forced default — user selects freely, tooltip informs.

| Feature | Recommended | Why | Alternatives |
|---|---|---|---|
| `import_translator` | Haiku 3.5 / GPT-4o-mini / Gemini Flash | Pure JSON mapping, no reasoning needed. Cheapest. | Any small model |
| `portfolio_analysis` | Claude Sonnet / GPT-4o | Financial reasoning + structured output | Opus for deeper analysis |
| `chat` | Claude Sonnet / GPT-4o | Tool-calling support + reasoning | Haiku for lighter use |
| `watchlist_scan` | Claude Sonnet / GPT-4o | Market analysis requires reasoning | Opus for thoroughness |
| `watchlist_discovery` | Haiku / GPT-4o-mini | Lighter task, structured holdings input | Sonnet for better suggestions |
| `ipo_analysis` | Claude Sonnet / GPT-4o | IPO analysis needs financial depth | Opus for complex offerings |
| `overview_analysis` | Claude Sonnet / GPT-4o | Holistic portfolio coaching | Opus for detailed guidance |

---

## 7. Summary of Changes

| Area | Change |
|---|---|
| Gateway | Inject `current_date` universally |
| Gateway | Age context opt-in via `FEATURES_WITH_AGE_CONTEXT` |
| Gateway | Age context placement: system prefix for chat/scan/discovery/ipo; human prompt for portfolio_analysis/overview_analysis |
| `import_translator` | No changes |
| `portfolio_analysis` | New system + human prompts; full holdings + cash + perf in human; structured JSON output; primary_currency variable |
| `chat` | Tool-calling architecture; 6 tools; finance guardrail; structured output; `data_used` server-side |
| `watchlist_scan` | Add `"reasoning": "<2 sentences max>"` constraint |
| `watchlist_discovery` | Add `"reasoning": "<2 sentences max>"` constraint |
| `ipo_analysis` | Add `"reasoning": "<2 sentences max>"` constraint |
| `overview_analysis` | New feature key, model, API endpoints, frontend section |
| `search_news` | New chat tool; RAG-backed; feeds Research Library |
| Cost UX | Confirmation dialog (one-shot), cost badge (chat); primary + secondary currency |
| Settings | Model tooltip with why + alternatives |
| AI Usage | All calls tracked; chat tool-calls logged individually |
