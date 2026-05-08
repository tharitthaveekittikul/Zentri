# Chat Tool-Calling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current simple chat LLM call with a tool-calling architecture where the LLM can fetch real portfolio data on demand, and enforce a finance-only scope guardrail with structured JSON output.

**Architecture:** Add `ToolCall`/`ToolLLMResponse` dataclasses and `complete_with_tools()` to `LLMAdapter`. Add `complete_chat()` to `LLMGateway` which runs the tool loop, executes tool calls against the DB, then returns a structured `{"type": "answer"|"out_of_scope", "message": "..."}` response with `data_used` populated server-side. Create `chat_tools.py` with 5 tool implementations. Update chat API endpoint to use the new method.

**Dependencies:** Plan 1 (Gateway + Prompts) must be complete — chat system prompt is defined there.

**Tech Stack:** Python, SQLAlchemy async, FastAPI, Anthropic SDK, OpenAI SDK, pytest

---

## File Map

| File | Change |
|---|---|
| `backend/app/services/llm_gateway.py` | Add ToolCall, ToolLLMResponse dataclasses; extend LLMAdapter ABC; implement in AnthropicAdapter + OpenAIAdapter + OllamaAdapter; add `complete_chat()` to LLMGateway |
| `backend/app/services/chat_tools.py` | NEW: 5 tool implementations |
| `backend/app/api/chat.py` | NEW or update: POST /chat endpoint |
| `backend/tests/test_chat_tools.py` | NEW |
| `backend/tests/test_llm_gateway.py` | Extend with tool-calling tests |

---

### Task 1: Add ToolCall and ToolLLMResponse dataclasses

**Files:**
- Modify: `backend/app/services/llm_gateway.py`
- Test: `backend/tests/test_llm_gateway.py`

- [ ] **Step 1: Write failing test**

```python
def test_tool_call_dataclass_importable():
    from app.services.llm_gateway import ToolCall, ToolLLMResponse
    tc = ToolCall(id="id1", name="get_portfolio_summary", input={})
    assert tc.name == "get_portfolio_summary"
    resp = ToolLLMResponse(content="hello", tool_calls=[], tokens_in=10, tokens_out=5, cost_usd=0.001)
    assert resp.content == "hello"
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py::test_tool_call_dataclass_importable -v
```

- [ ] **Step 3: Add dataclasses to llm_gateway.py**

Add after the existing `LLMGatewayResult` dataclass:

```python
@dataclass
class ToolCall:
    id: str
    name: str
    input: dict

@dataclass
class ToolLLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    tokens_in: int
    tokens_out: int
    cost_usd: float
```

- [ ] **Step 4: Run test**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py::test_tool_call_dataclass_importable -v
```
Expected: `PASSED`.

---

### Task 2: Extend LLMAdapter ABC and implement for Anthropic

**Files:**
- Modify: `backend/app/services/llm_gateway.py`

- [ ] **Step 1: Write failing test for Anthropic tool-calling**

```python
@pytest.mark.asyncio
async def test_anthropic_adapter_complete_with_tools_returns_tool_calls():
    from app.services.llm_gateway import AnthropicAdapter, ToolLLMResponse
    tools = [{"name": "get_portfolio_summary", "description": "Get portfolio summary", "input_schema": {"type": "object", "properties": {}}}]

    class FakeToolUse:
        type = "tool_use"
        id = "tool_1"
        name = "get_portfolio_summary"
        input = {}

    class FakeUsage:
        input_tokens = 50
        output_tokens = 10

    class FakeMsg:
        content = [FakeToolUse()]
        usage = FakeUsage()

    adapter = AnthropicAdapter(api_key="test")
    with patch.object(adapter._client.messages, "create", new=AsyncMock(return_value=FakeMsg())):
        result = await adapter.complete_with_tools("system", [], tools, "claude-haiku-3-5-20241022")
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "get_portfolio_summary"
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py::test_anthropic_adapter_complete_with_tools_returns_tool_calls -v
```

- [ ] **Step 3: Add abstract method to LLMAdapter + implement in AnthropicAdapter**

Add to `LLMAdapter` ABC:

```python
@abstractmethod
async def complete_with_tools(
    self, system: str, messages: list[dict], tools: list[dict], model: str
) -> ToolLLMResponse: ...
```

Add to `AnthropicAdapter`:

```python
async def complete_with_tools(
    self, system: str, messages: list[dict], tools: list[dict], model: str
) -> ToolLLMResponse:
    from app.services.llm_service import LLMQuotaExceededError
    # Convert to Anthropic tool format
    anthropic_tools = [
        {"name": t["name"], "description": t.get("description", ""), "input_schema": t.get("input_schema", {"type": "object", "properties": {}})}
        for t in tools
    ]
    try:
        msg = await self._client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            tools=anthropic_tools,
            messages=messages,
        )
    except Exception as exc:
        try:
            import anthropic
            if isinstance(exc, anthropic.RateLimitError):
                raise LLMQuotaExceededError("anthropic", "https://console.anthropic.com/settings/billing") from exc
        except ImportError:
            pass
        raise

    tool_calls = [
        ToolCall(id=b.id, name=b.name, input=b.input)
        for b in msg.content
        if hasattr(b, "type") and b.type == "tool_use"
    ]
    text_content = next(
        (b.text for b in msg.content if hasattr(b, "type") and b.type == "text"), None
    )
    tokens_in = msg.usage.input_tokens
    tokens_out = msg.usage.output_tokens
    return ToolLLMResponse(
        content=text_content,
        tool_calls=tool_calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=float(calc_cost(model, tokens_in, tokens_out)),
    )
```

- [ ] **Step 4: Run test**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py::test_anthropic_adapter_complete_with_tools_returns_tool_calls -v
```
Expected: `PASSED`.

---

### Task 3: Implement complete_with_tools for OpenAI and Ollama

**Files:**
- Modify: `backend/app/services/llm_gateway.py`

- [ ] **Step 1: Write failing test for OpenAI**

```python
@pytest.mark.asyncio
async def test_openai_adapter_complete_with_tools():
    import json
    from app.services.llm_gateway import OpenAIAdapter

    class FakeFunction:
        name = "get_cash_balance"
        arguments = json.dumps({})

    class FakeToolCall:
        id = "tc_1"
        function = FakeFunction()

    class FakeMessage:
        content = None
        tool_calls = [FakeToolCall()]

    class FakeUsage:
        prompt_tokens = 40
        completion_tokens = 8

    class FakeChoice:
        message = FakeMessage()

    class FakeResp:
        choices = [FakeChoice()]
        usage = FakeUsage()

    tools = [{"name": "get_cash_balance", "description": "Get cash", "input_schema": {"type": "object", "properties": {}}}]
    adapter = OpenAIAdapter(api_key="test")
    with patch.object(adapter._client.chat.completions, "create", new=AsyncMock(return_value=FakeResp())):
        result = await adapter.complete_with_tools("system", [], tools, "gpt-4o-mini")
    assert result.tool_calls[0].name == "get_cash_balance"
```

- [ ] **Step 2: Implement in OpenAIAdapter**

```python
async def complete_with_tools(
    self, system: str, messages: list[dict], tools: list[dict], model: str
) -> ToolLLMResponse:
    import json
    from app.services.llm_service import LLMQuotaExceededError
    openai_tools = [
        {"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("input_schema", {"type": "object", "properties": {}})}}
        for t in tools
    ]
    try:
        resp = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}] + messages,
            tools=openai_tools,
            tool_choice="auto",
        )
    except Exception as exc:
        try:
            import openai
            if isinstance(exc, openai.RateLimitError):
                raise LLMQuotaExceededError("openai", "https://platform.openai.com/settings/organization/billing") from exc
        except ImportError:
            pass
        raise

    msg = resp.choices[0].message
    tool_calls = [
        ToolCall(id=tc.id, name=tc.function.name, input=json.loads(tc.function.arguments))
        for tc in (msg.tool_calls or [])
    ]
    return ToolLLMResponse(
        content=msg.content,
        tool_calls=tool_calls,
        tokens_in=resp.usage.prompt_tokens,
        tokens_out=resp.usage.completion_tokens,
        cost_usd=float(calc_cost(model, resp.usage.prompt_tokens, resp.usage.completion_tokens)),
    )
```

- [ ] **Step 3: Add stub for OllamaAdapter**

Ollama tool-calling support varies by model. Add a stub that falls back to plain `complete()`:

```python
async def complete_with_tools(
    self, system: str, messages: list[dict], tools: list[dict], model: str
) -> ToolLLMResponse:
    # Ollama tool support is model-dependent; fall back to plain completion
    human = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    response = await self.complete(system, human, model)
    return ToolLLMResponse(
        content=response.content,
        tool_calls=[],
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=float(response.cost_usd),
    )
```

Add same stub to `OpenRouterAdapter`.

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py -k "tool" -v
```
Expected: `PASSED`.

---

### Task 4: Create chat_tools.py with 5 tool implementations

**Files:**
- Create: `backend/app/services/chat_tools.py`
- Test: `backend/tests/test_chat_tools.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_chat_tools.py`:

```python
import uuid
import pytest
from app.services.chat_tools import TOOL_DEFINITIONS, execute_tool

def test_tool_definitions_contains_all_tools():
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {"get_portfolio_summary", "get_holdings", "get_holding_detail", "get_cash_balance", "get_performance"}

@pytest.mark.asyncio
async def test_execute_tool_get_cash_balance(db_session, user_factory):
    user = await user_factory()
    result = await execute_tool("get_cash_balance", {}, user.id, db_session)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_execute_tool_unknown_raises(db_session, user_factory):
    user = await user_factory()
    with pytest.raises(ValueError, match="Unknown tool"):
        await execute_tool("nonexistent_tool", {}, user.id, db_session)
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_chat_tools.py -v
```

- [ ] **Step 3: Create chat_tools.py**

Create `backend/app/services/chat_tools.py`:

```python
from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services import overview as overview_svc

logger = get_logger(__name__)

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "get_portfolio_summary",
        "description": "Get the user's portfolio summary: total value, allocation breakdown, and overall health.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_holdings",
        "description": "Get the full list of the user's current holdings with current prices and P&L.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_holding_detail",
        "description": "Get detailed information about a specific holding by ticker symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_cash_balance",
        "description": "Get the user's cash balances across all currencies.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_performance",
        "description": "Get portfolio performance for a time range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "range": {
                    "type": "string",
                    "enum": ["1M", "3M", "YTD", "1Y"],
                    "description": "Time range",
                }
            },
        },
    },
]


async def execute_tool(name: str, input_: dict, user_id: uuid.UUID, db: AsyncSession) -> str:
    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    currency = getattr(user, "currency_primary", "USD") if user else "USD"

    if name == "get_portfolio_summary":
        summary = await overview_svc.get_summary(db, user_id, currency)
        return json.dumps({
            "total_value": getattr(summary, "total_value", 0),
            "currency": currency,
            "total_holdings": len(getattr(summary, "holdings", [])),
        })

    if name == "get_holdings":
        summary = await overview_svc.get_summary(db, user_id, currency)
        holdings = [
            {
                "symbol": getattr(h, "symbol", ""),
                "asset_type": getattr(h, "asset_type", ""),
                "quantity": getattr(h, "outstanding_shares", 0),
                "avg_cost": getattr(h, "cost_per_share", 0),
                "current_price": getattr(h, "current_price", None),
                "current_value": getattr(h, "current_value", 0),
                "allocation_pct": getattr(h, "allocation_pct", 0),
            }
            for h in getattr(summary, "holdings", [])
        ]
        return json.dumps(holdings)

    if name == "get_holding_detail":
        symbol = input_.get("symbol", "").upper()
        summary = await overview_svc.get_summary(db, user_id, currency)
        holding = next(
            (h for h in getattr(summary, "holdings", []) if getattr(h, "symbol", "") == symbol),
            None,
        )
        if not holding:
            return json.dumps({"error": f"No holding found for {symbol}"})
        return json.dumps({
            "symbol": symbol,
            "quantity": getattr(holding, "outstanding_shares", 0),
            "avg_cost": getattr(holding, "cost_per_share", 0),
            "current_price": getattr(holding, "current_price", None),
            "current_value": getattr(holding, "current_value", 0),
            "unrealized_pnl": getattr(holding, "unrealized_pnl", None),
            "allocation_pct": getattr(holding, "allocation_pct", 0),
        })

    if name == "get_cash_balance":
        summary = await overview_svc.get_summary(db, user_id, currency)
        cash = [
            {"currency": getattr(c, "currency", ""), "balance": getattr(c, "balance", 0)}
            for c in getattr(summary, "cash_accounts", [])
        ]
        return json.dumps(cash)

    if name == "get_performance":
        range_ = input_.get("range", "1M")
        perf = await overview_svc.get_performance(db, user_id, range_)
        return json.dumps({
            "range": range_,
            "change_pct": getattr(perf, "change_pct", 0),
            "change_value": getattr(perf, "change_value", 0),
        })

    raise ValueError(f"Unknown tool: {name}")
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_chat_tools.py -v
```
Expected: `PASSED`.

---

### Task 5: Add complete_chat() to LLMGateway

**Files:**
- Modify: `backend/app/services/llm_gateway.py`
- Test: `backend/tests/test_llm_gateway.py`

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_complete_chat_returns_answer_for_finance_question(mock_chat_gateway):
    gw, mock_adapter, _ = mock_chat_gateway
    # LLM returns no tool calls, just an answer
    mock_adapter.complete_with_tools.return_value = ToolLLMResponse(
        content='{"type": "answer", "message": "You have 5 holdings."}',
        tool_calls=[], tokens_in=50, tokens_out=20, cost_usd=0.001,
    )
    result = await gw.complete_chat(uuid.uuid4(), "How many holdings do I have?", [])
    assert result["type"] == "answer"
    assert "holdings" in result["message"]

@pytest.mark.asyncio
async def test_complete_chat_returns_out_of_scope_for_weather(mock_chat_gateway):
    gw, mock_adapter, _ = mock_chat_gateway
    mock_adapter.complete_with_tools.return_value = ToolLLMResponse(
        content='{"type": "out_of_scope", "message": "I can only help with finance topics."}',
        tool_calls=[], tokens_in=30, tokens_out=15, cost_usd=0.0005,
    )
    result = await gw.complete_chat(uuid.uuid4(), "What's the weather?", [])
    assert result["type"] == "out_of_scope"

@pytest.mark.asyncio
async def test_complete_chat_data_used_populated_server_side(mock_chat_gateway_with_tools):
    gw, mock_adapter, _ = mock_chat_gateway_with_tools
    # First call returns tool call, second call returns answer
    mock_adapter.complete_with_tools.side_effect = [
        ToolLLMResponse(content=None, tool_calls=[ToolCall(id="1", name="get_cash_balance", input={})], tokens_in=40, tokens_out=10, cost_usd=0.001),
        ToolLLMResponse(content='{"type": "answer", "message": "Your cash is 1000 USD."}', tool_calls=[], tokens_in=60, tokens_out=20, cost_usd=0.001),
    ]
    result = await gw.complete_chat(uuid.uuid4(), "What's my cash balance?", [])
    assert "get_cash_balance" in result["data_used"]
```

- [ ] **Step 2: Add complete_chat() to LLMGateway**

```python
async def complete_chat(
    self,
    user_id: uuid.UUID,
    message: str,
    history: list[dict],
) -> dict:
    from app.models.llm_call_log import LLMCallLog
    from app.services.chat_tools import TOOL_DEFINITIONS, execute_tool
    from datetime import datetime

    config = await self._get_feature_config("chat", user_id)
    provider = await self._get_provider(config.provider_config_id)
    api_key = decrypt(provider.encrypted_api_key) if provider.encrypted_api_key else None
    adapter = _build_adapter(provider.provider, api_key, provider.host_url)

    user_row = (await self._db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    age_ctx = get_user_age_context(user_row) if user_row and user_row.birth_date else None
    currency = getattr(user_row, "currency_primary", "USD") if user_row else "USD"

    age_prefix = f"{age_ctx['prompt']}\n\n" if age_ctx else ""
    current_date = datetime.now().strftime("%A, %Y-%m-%d")
    system = (
        f"Current date: {current_date}\n\n"
        + age_prefix
        + (config.system_prompt or DEFAULT_SYSTEM_PROMPTS.get("chat", ""))
    )

    messages = list(history) + [{"role": "user", "content": message}]
    tool_calls_made: list[str] = []
    total_tokens_in = 0
    total_tokens_out = 0
    total_cost = 0.0

    # Tool loop — max 5 iterations to prevent runaway calls
    for _ in range(5):
        response = await adapter.complete_with_tools(system, messages, TOOL_DEFINITIONS, config.model)
        total_tokens_in += response.tokens_in
        total_tokens_out += response.tokens_out
        total_cost += response.cost_usd

        if not response.tool_calls:
            break

        # Execute each tool call
        for tc in response.tool_calls:
            tool_calls_made.append(tc.name)
            logger.info("chat tool call: %s input=%s", tc.name, tc.input)
            tool_result = await execute_tool(tc.name, tc.input, user_id, self._db)

            # Append assistant tool use + tool result to messages (Anthropic format)
            messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}]})
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": tc.id, "content": tool_result}]})

    content = response.content or '{"type": "answer", "message": "Sorry, I could not generate a response."}'

    # Log to LLMCallLog
    usd_thb = await get_current_usd_thb(self._db)
    cost_thb = total_cost * float(usd_thb) if usd_thb else 0.0
    log = LLMCallLog(
        user_id=user_id,
        feature_key="chat",
        provider=provider.provider,
        model=config.model,
        prompt_in=f"SYSTEM: {system}\n\nUSER: {message}",
        response_out=content,
        tokens_in=total_tokens_in,
        tokens_out=total_tokens_out,
        cost_usd=total_cost,
        cost_thb=cost_thb,
        exchange_rate=float(usd_thb) if usd_thb else 0.0,
    )
    self._db.add(log)
    await self._db.flush()

    import json
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        parsed = {"type": "answer", "message": content}

    # Populate data_used server-side
    parsed["data_used"] = tool_calls_made
    return parsed
```

- [ ] **Step 3: Run tests**

```bash
cd backend && uv run pytest tests/test_llm_gateway.py -k "chat" -v
```
Expected: `PASSED`.

---

### Task 6: Create Chat API Endpoint

**Files:**
- Create or update: `backend/app/api/chat.py`

- [ ] **Step 1: Check if chat.py exists**

```bash
ls backend/app/api/chat.py 2>/dev/null && echo "exists" || echo "not found"
```

- [ ] **Step 2: Write failing test**

```python
@pytest.mark.asyncio
async def test_post_chat_returns_answer(client, auth_headers):
    with patch("app.api.chat.LLMGateway") as MockGW:
        MockGW.return_value.complete_chat = AsyncMock(return_value={
            "type": "answer", "message": "You have 5 holdings.", "data_used": []
        })
        resp = await client.post("/chat", json={"message": "How many holdings?", "history": []}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["type"] == "answer"

@pytest.mark.asyncio
async def test_post_chat_out_of_scope_returns_correct_type(client, auth_headers):
    with patch("app.api.chat.LLMGateway") as MockGW:
        MockGW.return_value.complete_chat = AsyncMock(return_value={
            "type": "out_of_scope",
            "message": "I can only help with finance topics.",
            "data_used": [],
        })
        resp = await client.post("/chat", json={"message": "What's the weather?", "history": []}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["type"] == "out_of_scope"
```

- [ ] **Step 3: Create/update chat.py**

Create `backend/app/api/chat.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User
from app.services.llm_gateway import LLMGateway

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@router.post("")
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gw = LLMGateway(db)
    result = await gw.complete_chat(current_user.id, body.message, body.history)
    logger.info("chat: user=%s type=%s tools=%s", current_user.id, result.get("type"), result.get("data_used"))
    return result
```

- [ ] **Step 4: Register router in main.py**

In `backend/app/main.py`, add:

```python
from app.api.chat import router as chat_router
app.include_router(chat_router)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_chat_api.py -v
```
Expected: `PASSED`.

---

### Task 7: Update Frontend Chat

**Files:**
- Find and modify the chat frontend component

- [ ] **Step 1: Locate chat component**

```bash
find frontend -name "*.tsx" | xargs grep -l "chat\|Chat" 2>/dev/null | grep -v node_modules | head -10
```

- [ ] **Step 2: Update API call to new schema**

Replace the existing chat API call with:

```typescript
// lib/api/chat.ts
export interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

export interface ChatResponse {
  type: "answer" | "out_of_scope"
  message: string
  data_used: string[]
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[]
): Promise<ChatResponse> {
  return apiFetch("/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  })
}
```

- [ ] **Step 3: Handle out_of_scope in UI**

In the chat component, add handling for `type === "out_of_scope"`:

```tsx
// When response comes back:
if (response.type === "out_of_scope") {
  // Render with a muted style and a redirect hint
  appendMessage({
    role: "assistant",
    content: response.message,
    isOutOfScope: true,  // add isOutOfScope flag to message type
  })
} else {
  appendMessage({ role: "assistant", content: response.message })
}

// In message render:
{message.isOutOfScope && (
  <div className="text-sm text-muted-foreground italic">{message.content}</div>
)}
```

- [ ] **Step 4: Show data_used badges**

Below each assistant message that has `data_used`, show small badges:

```tsx
{message.data_used && message.data_used.length > 0 && (
  <div className="flex gap-1 mt-1">
    {message.data_used.map((tool) => (
      <Badge key={tool} variant="outline" className="text-xs">{tool}</Badge>
    ))}
  </div>
)}
```

- [ ] **Step 5: Verify in browser**

```bash
cd frontend && npm run dev
```

Test:
- Finance question → shows answer + data_used badges
- "What's the weather?" → shows muted out_of_scope message
- Question needing portfolio data → LLM calls tools, answer includes real data
