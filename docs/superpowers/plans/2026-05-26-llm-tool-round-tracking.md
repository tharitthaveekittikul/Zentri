# LLM Tool Round Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist per-round token/cost/tool data in `LLMCallLog` and surface it in the AI Usage view log modal as collapsible round rows.

**Architecture:** Add a nullable `tool_rounds` JSON column to `LLMCallLog`, accumulate per-round data in `complete_chat`'s tool loop, pass it through `LLMGatewayResult`, save to the log, return it from the detail API endpoint, and render a collapsible "Tool Rounds" section in the frontend modal.

**Tech Stack:** Python/SQLAlchemy async, Alembic, FastAPI, Next.js/TypeScript, pytest

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `backend/app/models/llm_call_log.py` | Modify | Add `tool_rounds` nullable JSON column |
| `backend/alembic/versions/046_add_tool_rounds_to_llm_call_log.py` | Create | Migration to add column |
| `backend/app/services/llm_gateway.py` | Modify | Add `tool_rounds` field to `LLMGatewayResult`; refactor `complete_chat` loop to accumulate per-round data; save `tool_rounds` on `LLMCallLog` |
| `backend/app/api/llm_usage.py` | Modify | Return `tool_rounds` from detail endpoint |
| `frontend/app/(auth)/ai-usage/page.tsx` | Modify | Add `ToolRound` type, update `CallLogDetail`, render Tool Rounds section in modal |
| `backend/tests/test_llm_tool_rounds.py` | Create | Tests for model column, result field, loop accumulation, and API response |

---

## Task 1: Add `tool_rounds` column to `LLMCallLog` model and create migration

**Files:**
- Modify: `backend/app/models/llm_call_log.py`
- Create: `backend/alembic/versions/046_add_tool_rounds_to_llm_call_log.py`
- Create: `backend/tests/test_llm_tool_rounds.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_llm_tool_rounds.py`:

```python
def test_llm_call_log_has_tool_rounds_column():
    from app.models.llm_call_log import LLMCallLog
    from sqlalchemy import inspect as sa_inspect
    cols = {c.key for c in sa_inspect(LLMCallLog).mapper.column_attrs}
    assert "tool_rounds" in cols
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && .venv-local/bin/python3 -m pytest tests/test_llm_tool_rounds.py::test_llm_call_log_has_tool_rounds_column -v
```

Expected: FAIL — `AssertionError: assert 'tool_rounds' in {...}`

- [ ] **Step 3: Update `backend/app/models/llm_call_log.py`**

Add `Optional` to the `typing` import, add `JSON` to the postgresql dialect import, and add the column as the last field:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    feature_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_in: Mapped[str] = mapped_column(Text, nullable=False)
    response_out: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    cost_thb: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    tool_rounds: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 4: Create migration `backend/alembic/versions/046_add_tool_rounds_to_llm_call_log.py`**

```python
"""add tool_rounds to llm_call_log

Revision ID: 046
Revises: 045
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_call_logs",
        sa.Column("tool_rounds", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("llm_call_logs", "tool_rounds")
```

- [ ] **Step 5: Run test to verify it passes**

```
cd backend && .venv-local/bin/python3 -m pytest tests/test_llm_tool_rounds.py::test_llm_call_log_has_tool_rounds_column -v
```

Expected: PASS

---

## Task 2: Add `tool_rounds` to `LLMGatewayResult` and accumulate in `complete_chat`

**Files:**
- Modify: `backend/app/services/llm_gateway.py`
- Modify: `backend/tests/test_llm_tool_rounds.py`

- [ ] **Step 1: Write two failing tests — append to `backend/tests/test_llm_tool_rounds.py`**

```python
def test_llm_gateway_result_has_tool_rounds_field():
    from app.services.llm_gateway import LLMGatewayResult
    r = LLMGatewayResult(
        content="hi", prompt="", tokens_in=10, tokens_out=5,
        cost_usd=0.001, cost_thb=0.03, exchange_rate=33.0,
        model="claude-3-5-sonnet-20241022", provider="anthropic",
    )
    assert r.tool_rounds == []


import pytest


@pytest.mark.asyncio
async def test_complete_chat_accumulates_tool_rounds():
    import uuid
    import json as _json
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.services.llm_gateway import LLMGateway, ToolLLMResponse, ToolCall

    user_id = uuid.uuid4()

    mock_config = MagicMock()
    mock_config.system_prompt = "You are helpful."
    mock_config.model = "claude-3-5-sonnet-20241022"
    mock_config.provider_config_id = uuid.uuid4()

    mock_provider = MagicMock()
    mock_provider.provider = "anthropic"
    mock_provider.encrypted_api_key = None
    mock_provider.host_url = None
    mock_provider.is_connected = True

    mock_adapter = AsyncMock()
    mock_adapter.complete_with_tools = AsyncMock(side_effect=[
        ToolLLMResponse(
            content=None,
            tool_calls=[ToolCall(id="tc1", name="get_portfolio_summary", arguments={})],
            tokens_in=100, tokens_out=20, cost_usd=0.001, stop_reason="tool_use",
        ),
        ToolLLMResponse(
            content="Your portfolio is worth $10,000.",
            tool_calls=[],
            tokens_in=150, tokens_out=40, cost_usd=0.002, stop_reason="end_turn",
        ),
    ])

    mock_user = MagicMock()
    mock_user.currency_primary = "USD"
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none = MagicMock(return_value=mock_user)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_execute_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    with patch("app.services.llm_gateway._build_adapter", return_value=mock_adapter), \
         patch("app.services.llm_gateway.get_current_usd_thb", AsyncMock(return_value=33.0)), \
         patch("app.services.llm_gateway.get_user_age_context", return_value=None), \
         patch("app.services.chat_tools.execute_tool", AsyncMock(return_value="Portfolio: $10,000")):
        gateway = LLMGateway(mock_db)
        gateway._get_feature_config = AsyncMock(return_value=mock_config)
        gateway._get_provider = AsyncMock(return_value=mock_provider)
        result = await gateway.complete_chat(
            user_id, [{"role": "user", "content": "What is my portfolio?"}]
        )

    assert len(result.tool_rounds) == 2

    r1 = result.tool_rounds[0]
    assert r1["round"] == 1
    assert r1["tokens_in"] == 100
    assert r1["tokens_out"] == 20
    assert r1["cost_usd"] == pytest.approx(0.001)
    assert len(r1["tool_calls"]) == 1
    assert r1["tool_calls"][0]["name"] == "get_portfolio_summary"
    assert r1["tool_calls"][0]["result"] == "Portfolio: $10,000"

    r2 = result.tool_rounds[1]
    assert r2["round"] == 2
    assert r2["tokens_in"] == 150
    assert r2["tokens_out"] == 40
    assert r2["tool_calls"] == []

    # verify tool_rounds was saved on the LLMCallLog object
    log_arg = mock_db.add.call_args[0][0]
    assert log_arg.tool_rounds is not None
    assert len(log_arg.tool_rounds) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && .venv-local/bin/python3 -m pytest tests/test_llm_tool_rounds.py -v -k "tool_rounds_field or accumulates"
```

Expected: FAIL — `tool_rounds` attribute not found on `LLMGatewayResult`

- [ ] **Step 3: Add `tool_rounds` field to `LLMGatewayResult` in `backend/app/services/llm_gateway.py`**

The `LLMGatewayResult` dataclass is at the top of the file. Add the new field (already has `tool_calls`, add `tool_rounds` right after it):

```python
@dataclass
class LLMGatewayResult:
    content: str
    prompt: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cost_thb: float
    exchange_rate: float
    model: str
    provider: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_rounds: list[dict] = field(default_factory=list)
```

- [ ] **Step 4: Refactor `complete_chat` loop to accumulate per-round data**

In `backend/app/services/llm_gateway.py`, the `complete_chat` method has this section (the loop starts around line 865):

Replace from `total_tokens_in = 0` through `collected_tool_calls: list[dict] = []` and the entire `for _ in range(MAX_TOOL_ROUNDS):` block — including the `else:` clause — with:

```python
        chat_messages = list(messages)
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost_usd = 0.0
        final_content = ""
        MAX_TOOL_ROUNDS = 5
        collected_tool_calls: list[dict] = []
        collected_tool_rounds: list[dict] = []
        round_index = 0

        for _ in range(MAX_TOOL_ROUNDS):
            round_index += 1
            resp = await adapter.complete_with_tools(system, chat_messages, config.model, TOOL_DEFINITIONS)
            total_tokens_in += resp.tokens_in
            total_tokens_out += resp.tokens_out
            total_cost_usd += resp.cost_usd

            if resp.stop_reason == "end_turn" or not resp.tool_calls:
                final_content = resp.content or ""
                collected_tool_rounds.append({
                    "round": round_index,
                    "tokens_in": resp.tokens_in,
                    "tokens_out": resp.tokens_out,
                    "cost_usd": resp.cost_usd,
                    "tool_calls": [],
                })
                break

            round_tool_calls: list[dict] = []
            chat_messages.append({
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name, "arguments": _json.dumps(tc.arguments)}}
                    for tc in resp.tool_calls
                ],
            })
            for tc in resp.tool_calls:
                logger.info("Chat tool call: %s args=%s", tc.name, tc.arguments)
                tool_result = await execute_tool(tc.name, tc.arguments, self._db, user_id, currency)
                round_tool_calls.append({"name": tc.name, "args": tc.arguments, "result": tool_result})
                collected_tool_calls.append({"name": tc.name, "args": tc.arguments, "result": tool_result})
                chat_messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})
            collected_tool_rounds.append({
                "round": round_index,
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
                "cost_usd": resp.cost_usd,
                "tool_calls": round_tool_calls,
            })
        else:
            final_content = resp.content or "I ran into a loop — please rephrase your question."
```

- [ ] **Step 5: Pass `tool_rounds` to `LLMCallLog` and `LLMGatewayResult` in `complete_chat`**

Find the `LLMCallLog(...)` constructor call inside `complete_chat` (currently does NOT have `tool_rounds`). Replace it with:

```python
        log = LLMCallLog(
            user_id=user_id, feature_key="chat",
            provider=provider.provider, model=config.model,
            prompt_in=_json.dumps(messages[-1]) if messages else "",
            response_out=final_content,
            tokens_in=total_tokens_in, tokens_out=total_tokens_out,
            cost_usd=total_cost_usd, cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
            tool_rounds=collected_tool_rounds or None,
        )
```

Find the `return LLMGatewayResult(...)` at the end of `complete_chat`. Replace it with:

```python
        return LLMGatewayResult(
            content=final_content, prompt="",
            tokens_in=total_tokens_in, tokens_out=total_tokens_out,
            cost_usd=total_cost_usd, cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
            model=config.model, provider=provider.provider,
            tool_calls=collected_tool_calls,
            tool_rounds=collected_tool_rounds,
        )
```

- [ ] **Step 6: Run tests to verify they pass**

```
cd backend && .venv-local/bin/python3 -m pytest tests/test_llm_tool_rounds.py -v -k "tool_rounds_field or accumulates"
```

Expected: PASS (both tests)

---

## Task 3: Return `tool_rounds` from the detail API endpoint

**Files:**
- Modify: `backend/app/api/llm_usage.py`
- Modify: `backend/tests/test_llm_tool_rounds.py`

- [ ] **Step 1: Write the failing test — append to `backend/tests/test_llm_tool_rounds.py`**

```python
@pytest.mark.asyncio
async def test_call_log_detail_includes_tool_rounds():
    import uuid
    from datetime import datetime, timezone
    from decimal import Decimal
    from unittest.mock import AsyncMock, MagicMock
    from app.api.llm_usage import get_call_log_detail

    log_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_log = MagicMock()
    mock_log.id = log_id
    mock_log.feature_key = "chat"
    mock_log.provider = "anthropic"
    mock_log.model = "claude-3-5-sonnet-20241022"
    mock_log.tokens_in = 250
    mock_log.tokens_out = 60
    mock_log.cost_usd = Decimal("0.003")
    mock_log.cost_thb = Decimal("0.099")
    mock_log.created_at = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    mock_log.prompt_in = "What is my portfolio?"
    mock_log.response_out = "Your portfolio is worth $10,000."
    mock_log.tool_rounds = [
        {"round": 1, "tokens_in": 100, "tokens_out": 20, "cost_usd": 0.001,
         "tool_calls": [{"name": "get_portfolio_summary", "args": {}, "result": "Portfolio: $10,000"}]},
        {"round": 2, "tokens_in": 150, "tokens_out": 40, "cost_usd": 0.002, "tool_calls": []},
    ]

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none = MagicMock(return_value=mock_log)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    mock_user = MagicMock()
    mock_user.id = user_id

    result = await get_call_log_detail(log_id=log_id, db=mock_db, current_user=mock_user)

    assert "tool_rounds" in result
    assert len(result["tool_rounds"]) == 2
    assert result["tool_rounds"][0]["round"] == 1
    assert result["tool_rounds"][0]["tool_calls"][0]["name"] == "get_portfolio_summary"
    assert result["tool_rounds"][1]["tool_calls"] == []
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && .venv-local/bin/python3 -m pytest tests/test_llm_tool_rounds.py::test_call_log_detail_includes_tool_rounds -v
```

Expected: FAIL — `assert 'tool_rounds' in data`

- [ ] **Step 3: Update `get_call_log_detail` in `backend/app/api/llm_usage.py`**

Find the `return { ... }` dict in `get_call_log_detail` (currently ends after `"response_out": log.response_out`). Replace the entire return statement with:

```python
    return {
        "id": str(log.id),
        "feature_key": log.feature_key,
        "provider": log.provider,
        "model": log.model,
        "tokens_in": log.tokens_in,
        "tokens_out": log.tokens_out,
        "cost_usd": float(log.cost_usd),
        "cost_thb": float(log.cost_thb),
        "created_at": log.created_at.isoformat(),
        "prompt_in": log.prompt_in,
        "response_out": log.response_out,
        "tool_rounds": log.tool_rounds,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```
cd backend && .venv-local/bin/python3 -m pytest tests/test_llm_tool_rounds.py::test_call_log_detail_includes_tool_rounds -v
```

Expected: PASS

- [ ] **Step 5: Run full test file to confirm no regressions**

```
cd backend && .venv-local/bin/python3 -m pytest tests/test_llm_tool_rounds.py -v
```

Expected: all tests PASS

---

## Task 4: Display Tool Rounds section in the frontend view log modal

**Files:**
- Modify: `frontend/app/(auth)/ai-usage/page.tsx`

- [ ] **Step 1: Add `ToolRound` type and update `CallLogDetail`**

In `frontend/app/(auth)/ai-usage/page.tsx`, find the existing `interface CallLog` and `interface CallLogDetail` blocks. Replace both with:

```typescript
interface CallLog {
  id: string;
  feature_key: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  cost_thb: number;
  created_at: string;
}

interface ToolCallRecord {
  name: string;
  args: Record<string, unknown>;
  result: string;
}

interface ToolRound {
  round: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  tool_calls: ToolCallRecord[];
}

interface CallLogDetail extends CallLog {
  prompt_in: string;
  response_out: string;
  tool_rounds?: ToolRound[];
}
```

- [ ] **Step 2: Add `ChevronDownIcon` and `ChevronRightIcon` import**

Find the existing imports at the top of the file. Add the lucide-react import after the existing imports:

```typescript
import { ChevronDown, ChevronRight } from "lucide-react";
```

- [ ] **Step 3: Add `ToolRoundsPanel` component — insert before `function AIUsageContent()`**

```typescript
function ToolRoundsPanel({ rounds }: { rounds: ToolRound[] }) {
  const [openRounds, setOpenRounds] = useState<Set<number>>(new Set());
  const [openTools, setOpenTools] = useState<Set<string>>(new Set());

  function toggleRound(n: number) {
    setOpenRounds((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });
  }

  function toggleTool(key: string) {
    setOpenTools((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div>
      <p className="font-semibold mb-2">Tool Rounds ({rounds.length})</p>
      <div className="space-y-1">
        {rounds.map((r) => {
          const isOpen = openRounds.has(r.round);
          const toolNames =
            r.tool_calls.length > 0
              ? r.tool_calls.map((tc) => tc.name).join(", ")
              : null;
          return (
            <div
              key={r.round}
              className="border border-border rounded overflow-hidden"
            >
              <button
                className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-muted/50 transition-colors"
                onClick={() => toggleRound(r.round)}
              >
                {isOpen ? (
                  <ChevronDown className="h-3 w-3 shrink-0" />
                ) : (
                  <ChevronRight className="h-3 w-3 shrink-0" />
                )}
                <span className="font-medium">Round {r.round}</span>
                <span className="text-muted-foreground">
                  — {r.tokens_in.toLocaleString()} in /{" "}
                  {r.tokens_out.toLocaleString()} out — $
                  {r.cost_usd.toFixed(6)}
                </span>
                {toolNames ? (
                  <span className="ml-auto text-muted-foreground truncate max-w-[40%]">
                    {toolNames}
                  </span>
                ) : (
                  <span className="ml-auto text-muted-foreground italic">
                    final response
                  </span>
                )}
              </button>

              {isOpen && r.tool_calls.length > 0 && (
                <div className="border-t border-border divide-y divide-border">
                  {r.tool_calls.map((tc, i) => {
                    const toolKey = `${r.round}-${i}`;
                    const isToolOpen = openTools.has(toolKey);
                    const argsLabel = Object.entries(tc.args)
                      .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                      .join(", ");
                    return (
                      <div key={toolKey}>
                        <button
                          className="w-full flex items-center gap-2 px-4 py-1.5 text-xs text-left hover:bg-muted/30 transition-colors"
                          onClick={() => toggleTool(toolKey)}
                        >
                          {isToolOpen ? (
                            <ChevronDown className="h-3 w-3 shrink-0" />
                          ) : (
                            <ChevronRight className="h-3 w-3 shrink-0" />
                          )}
                          <code className="font-mono">
                            {tc.name}
                            {argsLabel ? `(${argsLabel})` : "()"}
                          </code>
                        </button>
                        {isToolOpen && (
                          <pre className="bg-muted px-4 py-2 text-xs whitespace-pre-wrap overflow-x-auto max-h-[20vh]">
                            {tc.result}
                          </pre>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Render `ToolRoundsPanel` inside the modal**

In `AIUsageContent`, find the section inside `{callLogDetail && (...)` that renders the `<div className="space-y-4 text-sm">`. It currently has two children (Input Prompt and Output Response). Add the Tool Rounds panel as the **first** child, conditionally rendered:

```typescript
            {callLogDetail && (
              <div className="space-y-4 text-sm">
                {callLogDetail.tool_rounds && callLogDetail.tool_rounds.length > 0 && (
                  <ToolRoundsPanel rounds={callLogDetail.tool_rounds} />
                )}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <p className="font-semibold">Input Prompt</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs px-2"
                      onClick={() => copyToClipboard(callLogDetail.prompt_in, "prompt")}
                    >
                      {copiedPrompt ? "✓ Copied" : "Copy"}
                    </Button>
                  </div>
                  <pre className="bg-muted rounded p-3 whitespace-pre-wrap text-xs overflow-x-auto max-h-[35vh]">
                    {callLogDetail.prompt_in}
                  </pre>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <p className="font-semibold">Output Response</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs px-2"
                      onClick={() => copyToClipboard(callLogDetail.response_out, "response")}
                    >
                      {copiedResponse ? "✓ Copied" : "Copy"}
                    </Button>
                  </div>
                  <pre className="bg-muted rounded p-3 whitespace-pre-wrap text-xs overflow-x-auto max-h-[35vh]">
                    {callLogDetail.response_out}
                  </pre>
                </div>
              </div>
            )}
```

- [ ] **Step 5: Check TypeScript compiles cleanly**

```
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors in `app/(auth)/ai-usage/page.tsx`
