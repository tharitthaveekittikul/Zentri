# Chat Tool Call Auditability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and display the full tool call trace (name, args, result) for every chat message so users can audit exactly what data the LLM used to answer.

**Architecture:** Add a `tool_calls` field to `LLMGatewayResult` and collect it in the agentic loop. Persist to a new nullable JSON column on `ChatSessionMessage` via Alembic migration. Return from both the send and history API endpoints. Render in the chat UI as a collapsible panel per assistant message.

**Tech Stack:** Python/SQLAlchemy async, Alembic, FastAPI/Pydantic, Next.js/React/TypeScript

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/services/llm_gateway.py` | Add `tool_calls` to result dataclass; collect during loop |
| Modify | `backend/app/models/chat_session.py` | Add `tool_calls` JSON column |
| Create | `backend/alembic/versions/045_add_tool_calls_to_chat_session_messages.py` | DB migration |
| Modify | `backend/app/api/chat.py` | Save + return tool_calls in API responses |
| Modify | `frontend/lib/services/chat.ts` | Add `ToolCallRecord` type; update `ChatResponse`, `ChatMessageWithMeta` |
| Modify | `frontend/app/(auth)/chat/page.tsx` | Add `ToolCallsPanel` component; update message construction and rendering |
| Modify | `backend/tests/test_llm_gateway.py` | Test tool_calls collected in complete_chat |

---

## Task 1: Add `tool_calls` to `LLMGatewayResult` and collect in `complete_chat`

**Files:**
- Modify: `backend/app/services/llm_gateway.py`
- Test: `backend/tests/test_llm_gateway.py`

- [ ] **Step 1: Write the failing test**

Add this test to `backend/tests/test_llm_gateway.py`:

```python
@pytest.mark.asyncio
async def test_complete_chat_collects_tool_calls():
    """complete_chat should populate tool_calls on the result when tools are used."""
    from unittest.mock import patch, AsyncMock, MagicMock
    from app.services.llm_gateway import LLMGateway, ToolCall
    from app.services.llm_service import LLMResponse

    user_id = uuid.uuid4()
    provider_cfg_id = uuid.uuid4()

    feature_config = _make_feature_config("chat", provider_cfg_id)
    provider = _make_provider(provider_cfg_id)

    fake_user = FakeUser(currency_primary="USD")

    call_count = 0
    async def execute_side_effect(stmt):
        nonlocal call_count
        result = AsyncMock()
        if call_count == 0:
            result.scalar_one_or_none.return_value = feature_config
        elif call_count == 1:
            result.scalar_one_or_none.return_value = provider
        elif call_count == 2:
            result.scalar_one_or_none.return_value = fake_user
        else:
            result.scalar_one_or_none.return_value = None  # exchange rate
        call_count += 1
        return result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=execute_side_effect)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    # First adapter response: tool call round
    tool_resp = MagicMock()
    tool_resp.content = None
    tool_resp.tool_calls = [ToolCall(id="tc1", name="get_portfolio_summary", arguments={})]
    tool_resp.tokens_in = 100
    tool_resp.tokens_out = 50
    tool_resp.cost_usd = 0.001
    tool_resp.stop_reason = "tool_use"

    # Second adapter response: final answer
    final_resp = MagicMock()
    final_resp.content = "Your portfolio is worth 500k."
    final_resp.tool_calls = []
    final_resp.tokens_in = 120
    final_resp.tokens_out = 60
    final_resp.cost_usd = 0.002
    final_resp.stop_reason = "end_turn"

    mock_adapter = AsyncMock()
    mock_adapter.complete_with_tools = AsyncMock(side_effect=[tool_resp, final_resp])

    with patch("app.services.llm_gateway._build_adapter", return_value=mock_adapter), \
         patch("app.services.chat_tools.execute_tool", new=AsyncMock(return_value="Total value: 500000 USD")):
        gateway = LLMGateway(mock_db)
        result = await gateway.complete_chat(user_id, [{"role": "user", "content": "What's my portfolio worth?"}])

    assert result.tool_calls == [
        {"name": "get_portfolio_summary", "args": {}, "result": "Total value: 500000 USD"}
    ]
    assert result.content == "Your portfolio is worth 500k."


@pytest.mark.asyncio
async def test_complete_chat_empty_tool_calls_when_no_tools_used():
    """complete_chat should return empty tool_calls list when LLM answers directly."""
    from unittest.mock import patch, AsyncMock, MagicMock
    from app.services.llm_gateway import LLMGateway

    user_id = uuid.uuid4()
    provider_cfg_id = uuid.uuid4()

    feature_config = _make_feature_config("chat", provider_cfg_id)
    provider = _make_provider(provider_cfg_id)
    fake_user = FakeUser(currency_primary="USD")

    call_count = 0
    async def execute_side_effect(stmt):
        nonlocal call_count
        result = AsyncMock()
        if call_count == 0:
            result.scalar_one_or_none.return_value = feature_config
        elif call_count == 1:
            result.scalar_one_or_none.return_value = provider
        elif call_count == 2:
            result.scalar_one_or_none.return_value = fake_user
        else:
            result.scalar_one_or_none.return_value = None
        call_count += 1
        return result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=execute_side_effect)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    final_resp = MagicMock()
    final_resp.content = "Hello! How can I help?"
    final_resp.tool_calls = []
    final_resp.tokens_in = 50
    final_resp.tokens_out = 20
    final_resp.cost_usd = 0.0005
    final_resp.stop_reason = "end_turn"

    mock_adapter = AsyncMock()
    mock_adapter.complete_with_tools = AsyncMock(return_value=final_resp)

    with patch("app.services.llm_gateway._build_adapter", return_value=mock_adapter):
        gateway = LLMGateway(mock_db)
        result = await gateway.complete_chat(user_id, [{"role": "user", "content": "Hi"}])

    assert result.tool_calls == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend && .venv-local/bin/python3 -m pytest tests/test_llm_gateway.py::test_complete_chat_collects_tool_calls tests/test_llm_gateway.py::test_complete_chat_empty_tool_calls_when_no_tools_used -v 2>&1 | tail -15
```

Expected: FAIL — `LLMGatewayResult` has no `tool_calls` field.

- [ ] **Step 3: Add `tool_calls` field to `LLMGatewayResult`**

In `backend/app/services/llm_gateway.py`, the `LLMGatewayResult` dataclass starts at line 35. Add the import and field:

At the top of the file, the `dataclasses` import already exists (it has `@dataclass`). Add `field` to it:
```python
from dataclasses import dataclass, field
```

Then add `tool_calls` as the last field of `LLMGatewayResult` (after `provider: str`):
```python
tool_calls: list = field(default_factory=list)
```

The full updated dataclass:
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
    tool_calls: list = field(default_factory=list)
```

- [ ] **Step 4: Collect tool calls in `complete_chat`**

In `backend/app/services/llm_gateway.py`, in the `complete_chat` method:

After line `MAX_TOOL_ROUNDS = 5` (around line 869), add:
```python
        collected_tool_calls: list[dict] = []
```

After the line `tool_result = await execute_tool(tc.name, tc.arguments, self._db, user_id, currency)` (around line 892), add:
```python
                collected_tool_calls.append({"name": tc.name, "args": tc.arguments, "result": tool_result})
```

In the `return LLMGatewayResult(...)` at the end of `complete_chat` (around line 914), add `tool_calls=collected_tool_calls`:
```python
        return LLMGatewayResult(
            content=final_content, prompt="",
            tokens_in=total_tokens_in, tokens_out=total_tokens_out,
            cost_usd=total_cost_usd, cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
            model=config.model, provider=provider.provider,
            tool_calls=collected_tool_calls,
        )
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend && .venv-local/bin/python3 -m pytest tests/test_llm_gateway.py::test_complete_chat_collects_tool_calls tests/test_llm_gateway.py::test_complete_chat_empty_tool_calls_when_no_tools_used -v 2>&1 | tail -15
```

Expected: Both PASS.

---

## Task 2: DB model update + Alembic migration

**Files:**
- Modify: `backend/app/models/chat_session.py`
- Create: `backend/alembic/versions/045_add_tool_calls_to_chat_session_messages.py`

- [ ] **Step 6: Add `tool_calls` column to `ChatSessionMessage` model**

In `backend/app/models/chat_session.py`, add the JSON import and new column.

Add `JSON` to the postgresql dialect import:
```python
from sqlalchemy.dialects.postgresql import JSON, UUID
```

Add the column as the last field of `ChatSessionMessage` (after `created_at`):
```python
    tool_calls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 7: Create Alembic migration**

Create `backend/alembic/versions/045_add_tool_calls_to_chat_session_messages.py` with this content:

```python
"""add tool_calls to chat_session_messages

Revision ID: 045
Revises: 044
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_session_messages",
        sa.Column("tool_calls", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_session_messages", "tool_calls")
```

- [ ] **Step 8: Run the migration**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri && docker compose exec backend alembic upgrade head 2>&1 | tail -5
```

Expected output includes: `Running upgrade 044 -> 045, add tool_calls to chat_session_messages`

---

## Task 3: Update `chat.py` API — save and return `tool_calls`

**Files:**
- Modify: `backend/app/api/chat.py`

- [ ] **Step 9: Update `ChatResponse` and `MessageResponse` Pydantic models**

In `backend/app/api/chat.py`, update the two response models.

`ChatResponse` — add `tool_calls` field:
```python
class ChatResponse(BaseModel):
    content: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cost_thb: float
    model: str
    provider: str
    tool_calls: list[dict]
```

`MessageResponse` — add optional `tool_calls` field:
```python
class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = None
    cost_thb: Optional[float] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    created_at: datetime
```

- [ ] **Step 10: Save `tool_calls` on the assistant message in the `chat` endpoint**

In `backend/app/api/chat.py`, in the `chat` endpoint, update the `ChatSessionMessage` constructor for the assistant message to include `tool_calls`:

```python
    assistant_msg = ChatSessionMessage(
        session_id=session.id,
        role="assistant",
        content=result.content,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        cost_thb=result.cost_thb,
        model=result.model,
        provider=result.provider,
        tool_calls=result.tool_calls or None,
    )
```

Update the `return ChatResponse(...)` to include `tool_calls`:
```python
    return ChatResponse(
        content=result.content,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        cost_thb=result.cost_thb,
        model=result.model,
        provider=result.provider,
        tool_calls=result.tool_calls,
    )
```

- [ ] **Step 11: Return `tool_calls` in `get_session_messages`**

In `backend/app/api/chat.py`, in the `get_session_messages` endpoint, update each `MessageResponse(...)` to include `tool_calls`:

```python
        MessageResponse(
            id=str(m.id),
            role=m.role,
            content=m.content,
            tokens_in=m.tokens_in,
            tokens_out=m.tokens_out,
            cost_usd=float(m.cost_usd) if m.cost_usd is not None else None,
            cost_thb=float(m.cost_thb) if m.cost_thb is not None else None,
            model=m.model,
            provider=m.provider,
            tool_calls=m.tool_calls,
            created_at=m.created_at,
        )
```

- [ ] **Step 12: Verify API changes with a quick smoke test**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend && .venv-local/bin/python3 -m pytest tests/test_chat_tools.py -v 2>&1 | tail -10
```

Expected: All 6 still PASS (no regressions from API changes).

---

## Task 4: Frontend — types + `ToolCallsPanel` component

**Files:**
- Modify: `frontend/lib/services/chat.ts`
- Modify: `frontend/app/(auth)/chat/page.tsx`

- [ ] **Step 13: Add `ToolCallRecord` type and update `ChatResponse` + `ChatMessageWithMeta`**

In `frontend/lib/services/chat.ts`, add the new type and update the two interfaces:

```typescript
export interface ToolCallRecord {
  name: string;
  args: Record<string, unknown>;
  result: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatMessageWithMeta extends ChatMessage {
  id?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  cost_thb?: number;
  model?: string;
  provider?: string;
  tool_calls?: ToolCallRecord[];
}

export interface ChatResponse {
  content: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  cost_thb: number;
  model: string;
  provider: string;
  tool_calls: ToolCallRecord[];
}
```

- [ ] **Step 14: Add `ToolCallsPanel` component to `page.tsx`**

In `frontend/app/(auth)/chat/page.tsx`, add the `ToolCallsPanel` component **before** the `MessageBubble` component.

Add `useState` import is already present. Also add `ChevronDownIcon` and `ChevronRightIcon` to the existing lucide-react import:
```typescript
import { SendIcon, BotIcon, UserIcon, AlertCircleIcon, ChevronDownIcon, ChevronRightIcon } from "lucide-react";
```

Add the import for `ToolCallRecord` in the chat service import:
```typescript
import {
  ChatMessageWithMeta,
  ToolCallRecord,
  sendChatMessage,
  listChatSessions,
  createChatSession,
  getChatMessages,
  ChatSessionSummary,
} from "@/lib/services/chat";
```

Add `ToolCallsPanel` component:
```tsx
function ToolCallsPanel({ toolCalls }: { toolCalls: ToolCallRecord[] }) {
  const [open, setOpen] = useState(false);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (!toolCalls || toolCalls.length === 0) return null;

  function formatArgs(args: Record<string, unknown>): string {
    return Object.entries(args)
      .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
      .join(", ");
  }

  return (
    <div className="mt-2 border border-border rounded-lg text-xs">
      <button
        className="w-full flex items-center gap-1 px-3 py-2 text-muted-foreground hover:text-foreground transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronDownIcon className="w-3 h-3" /> : <ChevronRightIcon className="w-3 h-3" />}
        <span>Tools used ({toolCalls.length})</span>
      </button>
      {open && (
        <div className="border-t border-border divide-y divide-border">
          {toolCalls.map((tc, i) => (
            <div key={i}>
              <button
                className="w-full flex items-center gap-1 px-3 py-2 text-left text-muted-foreground hover:text-foreground transition-colors font-mono"
                onClick={() => setExpandedIndex(expandedIndex === i ? null : i)}
              >
                {expandedIndex === i ? (
                  <ChevronDownIcon className="w-3 h-3 shrink-0" />
                ) : (
                  <ChevronRightIcon className="w-3 h-3 shrink-0" />
                )}
                <span>
                  {tc.name}
                  {Object.keys(tc.args).length > 0 ? `(${formatArgs(tc.args)})` : "()"}
                </span>
              </button>
              {expandedIndex === i && (
                <pre className="px-4 py-2 text-xs text-foreground bg-muted whitespace-pre-wrap break-words font-mono">
                  {tc.result}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 15: Update `MessageBubble` to render `ToolCallsPanel`**

In `frontend/app/(auth)/chat/page.tsx`, find `MessageBubble` and update it to render the panel after the message content for assistant messages:

```tsx
function MessageBubble({ message }: { message: ChatMessageWithMeta }) {
  const isUser = message.role === "user";
  const outOfScope = !isUser && isOutOfScope(message.content);
  const displayContent = outOfScope
    ? "That's outside my scope. I can only help with finance and investment questions — try asking about your portfolio, a stock, or market trends."
    : message.content;

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0 mt-1">
          {outOfScope ? (
            <AlertCircleIcon className="w-4 h-4 text-muted-foreground" />
          ) : (
            <BotIcon className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
      )}
      <div className={cn("max-w-[75%]", isUser ? "items-end" : "items-start", "flex flex-col")}>
        <div
          className={cn(
            "px-4 py-2.5 rounded-xl text-sm leading-relaxed",
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-sm"
              : "bg-muted text-foreground rounded-tl-sm",
          )}
        >
          {displayContent}
        </div>
        {!isUser && !outOfScope && message.tool_calls && message.tool_calls.length > 0 && (
          <ToolCallsPanel toolCalls={message.tool_calls} />
        )}
      </div>
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0 mt-1">
          <UserIcon className="w-4 h-4 text-primary-foreground" />
        </div>
      )}
    </div>
  );
}
```

**Note:** Read the current `MessageBubble` implementation first (`frontend/app/(auth)/chat/page.tsx`) to confirm the exact JSX structure before replacing it — preserve any classes or structure that differ from the above template.

- [ ] **Step 16: Update `assistantMessage` construction to include `tool_calls`**

In `frontend/app/(auth)/chat/page.tsx`, in the `handleSend` callback, update the `assistantMessage` object to carry `tool_calls` from the API response:

```typescript
      const assistantMessage: ChatMessageWithMeta = {
        role: "assistant",
        content: result.content,
        tokens_in: result.tokens_in,
        tokens_out: result.tokens_out,
        cost_usd: result.cost_usd,
        cost_thb: result.cost_thb,
        model: result.model,
        provider: result.provider,
        tool_calls: result.tool_calls,
      };
```

- [ ] **Step 17: Verify TypeScript compiles with no errors**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | tail -20
```

Expected: No output (zero errors).
