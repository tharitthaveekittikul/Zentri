# Chat Symbol Analysis Tool — Design Spec

**Date:** 2026-05-25  
**Status:** Approved

## Problem

The chat agent can already access portfolio data (holdings, cash, watchlist) via existing tools in `chat_tools.py`. However, it has no way to retrieve stored AI analysis for a specific ticker. When a user asks "should I buy AAPL?" or "what's your take on SCB?", the LLM cannot surface the `CombinedVerdict` or `AIAnalysis` records that already exist in the database.

## Goal

Add a single new tool `get_symbol_analysis` to `chat_tools.py` so the chat agent can retrieve stored analysis for any ticker the user asks about. No other files need to change.

## Design

### Single file change: `backend/app/services/chat_tools.py`

#### 1. New entry in `TOOL_DEFINITIONS`

```python
{
    "name": "get_symbol_analysis",
    "description": (
        "Get the stored AI analysis for a specific ticker symbol, including verdict "
        "(BUY/SELL/HOLD), conviction score, price targets, bull and bear thesis, and "
        "key risks. Call this when the user asks about a specific stock or whether to "
        "buy or sell it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "The ticker symbol, e.g. AAPL, SCB, BTC.",
            }
        },
        "required": ["symbol"],
    },
}
```

#### 2. Dispatch in `execute_tool`

```python
if name == "get_symbol_analysis":
    return await _get_symbol_analysis(db, arguments.get("symbol", ""), user_id)
```

#### 3. New implementation function `_get_symbol_analysis`

**Logic:**

1. Look up `Asset` by `symbol.upper()` where `Asset.user_id == user_id`
2. Query `CombinedVerdict` for that `asset_id`, ordered by `created_at DESC`, limit 1
3. If `CombinedVerdict` found → return formatted block (see output format below)
4. Else query `AIAnalysis` for that `asset_id`, ordered by `created_at DESC`, limit 1
5. If `AIAnalysis` found → return lighter summary (verdict + reasoning)
6. Else return `"No analysis found for {symbol.upper()}."`

**CombinedVerdict output format:**

```
AAPL — BUY (conviction: 8/10)
As of: 2026-05-20

Entry: 180.00 | Target: 220.00 | Stop: 165.00 | R/R: 2.7x

Bull thesis:
<bull_thesis>

Bear thesis:
<bear_thesis>

Key risks:
- <risk 1>
- <risk 2>

Reasoning:
<reasoning>

Based on: deep_dive, peer_comparison, bear_case
```

**AIAnalysis fallback output format:**

```
AAPL — BUY (AI analysis, no combined verdict)
Target price: 220.00
Reasoning:
<reasoning>
As of: 2026-05-20
```

### What does NOT change

- `backend/app/api/chat.py` — no changes
- `backend/app/services/llm_gateway.py` — no changes
- The existing agentic loop (`MAX_TOOL_ROUNDS = 5`) already handles multi-tool turns, so portfolio + analysis in one conversation turn works automatically with no extra wiring

## Data flow

```
User: "Should I buy AAPL given my current portfolio?"
  └─► LLM decides to call get_symbol_analysis("AAPL") AND get_portfolio_summary()
        └─► _get_symbol_analysis queries CombinedVerdict → returns formatted summary
        └─► _get_portfolio_summary queries Holdings/Assets → returns portfolio table
  └─► LLM synthesizes both results into one answer
```

## Edge cases

| Case | Behavior |
|------|----------|
| Symbol not in user's assets | `"No analysis found for {symbol}."` |
| Asset exists but no analysis run yet | Same — falls through both queries |
| Only `AIAnalysis` exists (no `CombinedVerdict`) | Returns lighter fallback format |
| `key_risks` JSON is empty list | Omit the "Key risks" section |

## Out of scope

- Fetching DeepDive, BearCase, or PeerComparison content directly (can be added later as separate tools if needed)
- Streaming analysis results
- Any frontend changes
