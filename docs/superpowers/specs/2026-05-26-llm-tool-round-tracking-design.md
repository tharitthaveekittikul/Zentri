# LLM Tool Round Tracking in AI Usage View Log — Design Spec

**Date:** 2026-05-26  
**Status:** Approved

## Problem

When an LLM call triggers tool use (e.g., in the chat feature), each tool round consumes tokens and incurs cost. This is already summed into the top-level `LLMCallLog` totals, but the detail is lost: the user cannot see how many rounds ran, which tools were called, or how much each round cost. The AI Usage "View Log" modal shows only the final totals.

## Goal

Persist per-round token/cost/tool data inside `LLMCallLog`, and surface it in the View Log modal as collapsible round rows — feature-agnostic, working for any feature that uses tool calling.

## Architecture Overview

Four layers change:

1. `LLMCallLog` model + Alembic migration — add nullable `tool_rounds` JSON column
2. `LLMGatewayResult` — carry `tool_rounds` out of the agentic loop
3. `complete_chat` / gateway — accumulate per-round data during the loop
4. `GET /api/v1/llm/call-logs/{id}` + frontend modal — return and display the rounds

---

## Design

### 1. `LLMCallLog` model — new column

**File:** `backend/app/models/llm_call_log.py`

Add one nullable JSON column after `created_at`:

```python
tool_rounds: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
```

Each element has the shape:

```python
{
    "round": int,          # 1-based round index
    "tokens_in": int,
    "tokens_out": int,
    "cost_usd": float,
    "tool_calls": [        # tools called during this round (may be empty for final round)
        {"name": str, "args": dict, "result": str}
    ]
}
```

The **final round** (LLM generates a text response with no more tool calls) is included as a round entry with `tool_calls: []`. This lets the user see the breakdown of where tokens were spent.

### 2. Alembic migration — 046

**File:** `backend/alembic/versions/046_add_tool_rounds_to_llm_call_log.py`

```python
revision = "046"
down_revision = "045"

def upgrade() -> None:
    op.add_column(
        "llm_call_logs",
        sa.Column("tool_rounds", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("llm_call_logs", "tool_rounds")
```

### 3. `LLMGatewayResult` — new field

**File:** `backend/app/services/llm_gateway.py`

Add to the `LLMGatewayResult` dataclass:

```python
tool_rounds: list[dict] = field(default_factory=list)
```

Each entry is built during the agentic loop (see §4).

### 4. `complete_chat` — accumulate per-round data

**File:** `backend/app/services/llm_gateway.py`

Inside the agentic tool loop in `complete_chat`, initialize before the loop:

```python
collected_tool_rounds: list[dict] = []
round_index = 0
```

At the start of each iteration (before the API call):
```python
round_index += 1
```

After the API call returns (usage is available at `response.usage`):
```python
round_cost = _compute_cost(provider, model, usage.input_tokens, usage.output_tokens)
round_tool_calls = []  # filled in the tool dispatch block below
```

After all tool dispatches for this iteration complete, append:
```python
collected_tool_rounds.append({
    "round": round_index,
    "tokens_in": usage.input_tokens,
    "tokens_out": usage.output_tokens,
    "cost_usd": float(round_cost),
    "tool_calls": round_tool_calls,
})
```

Each tool call appends to `round_tool_calls`:
```python
round_tool_calls.append({"name": tc.name, "args": tc.arguments, "result": tool_result})
```

Return `tool_rounds=collected_tool_rounds` in `LLMGatewayResult`.

> **Note:** `_compute_cost` is the existing internal helper that calculates cost from token counts. The loop already tracks `total_tokens_in`, `total_tokens_out`, and `total_cost`; per-round numbers feed from the same `response.usage` object, just captured per iteration instead of only at the end.

### 5. Saving to `LLMCallLog`

**File:** `backend/app/api/chat.py` (and any other feature that creates `LLMCallLog` entries)

When constructing the `LLMCallLog` row after `complete_chat` returns:

```python
log = LLMCallLog(
    ...
    tool_rounds=result.tool_rounds or None,  # store None when no tool rounds
)
```

### 6. `GET /api/v1/llm/call-logs/{id}` — return tool_rounds

**File:** `backend/app/api/llm_usage.py`

Add `tool_rounds` to the response schema and the query result:

```python
class CallLogDetail(BaseModel):
    ...
    tool_rounds: Optional[list[dict]] = None
```

In the endpoint handler:
```python
return CallLogDetail(
    ...
    tool_rounds=log.tool_rounds,
)
```

### 7. Frontend — View Log modal

**File:** wherever the AI Usage view log modal is rendered (likely `frontend/app/(auth)/ai-usage/` or similar)

**Type additions:**

```typescript
export interface ToolRound {
  round: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  tool_calls: { name: string; args: Record<string, unknown>; result: string }[];
}

// On the existing CallLogDetail type:
tool_rounds?: ToolRound[];
```

**"Tool Rounds" section** — rendered inside the modal when `tool_rounds` is present and non-empty:

- Section header: `"Tool Rounds (N rounds)"`
- Each round: a collapsible summary row
  - Collapsed: `Round N — {tokens_in} in / {tokens_out} out — $X.XXXX — tools: name1, name2`
  - If no tools were called (final text round): `Round N — {tokens_in} in / {tokens_out} out — $X.XXXX — (final response)`
  - Expanded: per-tool-call rows, each showing `tool_name(arg=value, ...)` as header and the full `result` in a `<pre>` / monospace block
- Default state: all rounds collapsed
- Use CSS variables from `globals.css` only — no hardcoded colors

---

## Data Flow

```
LLM agentic loop runs
  └─► Round 1: API call → tools called → tokens recorded
  └─► Round 2: API call → tools called → tokens recorded
  └─► Round N: API call → final text → tokens recorded
  └─► LLMGatewayResult(tool_rounds=[...], tool_calls=[...])
  └─► chat.py saves tool_rounds on LLMCallLog
  └─► GET /api/v1/llm/call-logs/{id} returns tool_rounds
  └─► Frontend modal renders collapsible rounds panel
```

---

## Edge Cases

| Case | Behavior |
|------|----------|
| No tools called (single round) | `tool_rounds = [{round:1, tokens_in:X, tokens_out:Y, cost_usd:Z, tool_calls:[]}]`; stored as single-element list |
| Feature does not use tools | `tool_rounds = None` in DB; field absent in response |
| Old logs without column | `tool_rounds = None`; modal renders nothing for that section |
| Very long tool result | Stored as-is; frontend uses `<pre>` with overflow scroll |
| Multiple tools in one round | All appear as rows under that round's expanded view |

## Out of Scope

- Real-time streaming of round progress to the UI
- Aggregating tool usage across multiple log entries
- Showing tool rounds in the log list table (only in the detail modal)
- Modifying non-chat features to pass `tool_rounds` (only `complete_chat` is in scope for this iteration)
