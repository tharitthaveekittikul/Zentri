# Chat Tool Call Auditability — Design Spec

**Date:** 2026-05-25  
**Status:** Approved

## Problem

When the chat agent calls tools (e.g., `get_symbol_analysis`, `get_portfolio_summary`), the user has no visibility into which tools were invoked, what arguments were passed, or what data the LLM received. Tool calls are currently ephemeral — lost after the response is returned.

## Goal

Persist the full tool call trace (name, arguments, result) for every assistant message, and surface it in the chat UI as a collapsible audit panel.

## Architecture Overview

Four layers change:
1. `LLMGatewayResult` — carry tool calls out of the agentic loop
2. `ChatSessionMessage` model + Alembic migration — persist tool calls in DB
3. `chat.py` API — save and return tool calls in both `ChatResponse` and `MessageResponse`
4. Frontend chat UI — collapsible "Tools used" panel per assistant message

---

## Design

### 1. `LLMGatewayResult` — new field

**File:** `backend/app/services/llm_gateway.py`

Add one field to the `LLMGatewayResult` dataclass:

```python
tool_calls: list[dict]  # [{name, args, result}] — empty list if no tools used
```

Each dict has the shape:
```python
{"name": str, "args": dict, "result": str}
```

### 2. `complete_chat` — collect tool calls during the loop

**File:** `backend/app/services/llm_gateway.py`

In `complete_chat`, initialize an accumulator before the tool loop:
```python
collected_tool_calls: list[dict] = []
```

After each `execute_tool` call, append:
```python
collected_tool_calls.append({"name": tc.name, "args": tc.arguments, "result": tool_result})
```

Return `tool_calls=collected_tool_calls` in the `LLMGatewayResult`. If no tools were used, this is an empty list `[]`.

### 3. `ChatSessionMessage` model — new column

**File:** `backend/app/models/chat_session.py`

Add one nullable JSON column:

```python
from sqlalchemy.dialects.postgresql import JSON, UUID

tool_calls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
```

### 4. Alembic migration

**File:** new file `backend/alembic/versions/<hash>_add_tool_calls_to_chat_session_messages.py`

```python
def upgrade() -> None:
    op.add_column(
        "chat_session_messages",
        sa.Column("tool_calls", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("chat_session_messages", "tool_calls")
```

### 5. `chat.py` API — save and return tool calls

**File:** `backend/app/api/chat.py`

**`ChatResponse`** — add field:
```python
tool_calls: list[dict]
```

**`MessageResponse`** — add field:
```python
tool_calls: Optional[list[dict]] = None
```

**`chat` endpoint** — save on the assistant message:
```python
assistant_msg = ChatSessionMessage(
    ...
    tool_calls=result.tool_calls or None,  # store None (not []) when unused
)
```

Return in `ChatResponse`:
```python
return ChatResponse(
    ...
    tool_calls=result.tool_calls,
)
```

**`get_session_messages` endpoint** — include in `MessageResponse`:
```python
MessageResponse(
    ...
    tool_calls=m.tool_calls,
)
```

### 6. Frontend — type and component

**File:** `frontend/lib/services/chat.ts` (or wherever `MessageResponse` is typed)

Add type:
```typescript
export interface ToolCallRecord {
  name: string;
  args: Record<string, unknown>;
  result: string;
}
```

Update `MessageResponse`:
```typescript
tool_calls?: ToolCallRecord[];
```

**Chat message component** — when `tool_calls` is present and non-empty on an assistant message:

- Render a collapsible toggle below the message text: `"Tools used (N)"`
- Default state: collapsed
- Each tool call row header: `tool_name(arg=value, ...)` — format args as `key=value` pairs, comma-separated
- Expand each row to reveal the full `result` string in a `<pre>` / monospace block
- Use CSS variables from `globals.css` only — no hardcoded colors

---

## Data Flow

```
User sends message
  └─► LLMGateway.complete_chat runs agentic loop
        └─► For each tool call: execute_tool → append {name, args, result}
        └─► Returns LLMGatewayResult(tool_calls=[...])
  └─► chat.py saves tool_calls on ChatSessionMessage
  └─► ChatResponse returned with tool_calls
  └─► Frontend renders message + collapsible tools panel
```

---

## Edge Cases

| Case | Behavior |
|------|----------|
| No tools called | `tool_calls = []` in result; `None` stored in DB; field absent in `MessageResponse` |
| User messages | `tool_calls` never set (only assistant messages have it) |
| History load | `MessageResponse.tool_calls` populated from DB JSON; old messages without the column return `None` |
| Very long tool result | Stored as-is; frontend truncates display with "show more" optional |

## Out of Scope

- Streaming tool call events in real time
- Filtering/searching chat history by tool used
- Showing tool calls for user messages
