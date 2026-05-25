# Chat Symbol Analysis Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `get_symbol_analysis` tool to `chat_tools.py` so the chat agent can retrieve stored `CombinedVerdict` (or `AIAnalysis` fallback) for any ticker the user asks about.

**Architecture:** Single file change — add one new entry to `TOOL_DEFINITIONS`, one dispatch branch in `execute_tool`, and one new `_get_symbol_analysis` function in `backend/app/services/chat_tools.py`. No other files change. The existing agentic tool loop in `llm_gateway.py` already handles multi-tool turns.

**Tech Stack:** Python, SQLAlchemy async, pytest-asyncio, unittest.mock (AsyncMock/MagicMock)

---

## File Map

| Action | Path |
|--------|------|
| Modify | `backend/app/services/chat_tools.py` |
| Create | `backend/tests/test_chat_tools.py` |

---

## Task 1: Write failing tests for `_get_symbol_analysis`

**Files:**
- Create: `backend/tests/test_chat_tools.py`

- [ ] **Step 1: Create the test file**

```python
# backend/tests/test_chat_tools.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_get_symbol_analysis_returns_combined_verdict():
    from app.services.chat_tools import _get_symbol_analysis

    user_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    mock_asset = MagicMock()
    mock_asset.id = asset_id

    mock_verdict = MagicMock()
    mock_verdict.verdict = "BUY"
    mock_verdict.conviction = 8
    mock_verdict.entry_price = Decimal("180.00")
    mock_verdict.target_price = Decimal("220.00")
    mock_verdict.stop_loss = Decimal("165.00")
    mock_verdict.risk_reward = Decimal("2.7")
    mock_verdict.bull_thesis = "Strong AI revenue growth."
    mock_verdict.bear_thesis = "Valuation stretched."
    mock_verdict.key_risks = ["Regulation", "Competition"]
    mock_verdict.reasoning = "Net positive outlook."
    mock_verdict.based_on = ["deep_dive", "peer_comparison"]
    mock_verdict.created_at = datetime(2026, 5, 20, tzinfo=timezone.utc)

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        row = MagicMock()
        row.scalar_one_or_none.return_value = mock_asset if call_count == 0 else mock_verdict
        call_count += 1
        return row

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    result = await _get_symbol_analysis(mock_db, "AAPL", user_id)

    assert "BUY" in result
    assert "conviction: 8/10" in result
    assert "Strong AI revenue growth." in result
    assert "Valuation stretched." in result
    assert "Regulation" in result
    assert "Net positive outlook." in result
    assert "deep_dive" in result
    assert "2026-05-20" in result


@pytest.mark.asyncio
async def test_get_symbol_analysis_omits_prices_when_none():
    from app.services.chat_tools import _get_symbol_analysis

    user_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    mock_asset = MagicMock()
    mock_asset.id = asset_id

    mock_verdict = MagicMock()
    mock_verdict.verdict = "HOLD"
    mock_verdict.conviction = 5
    mock_verdict.entry_price = None
    mock_verdict.target_price = None
    mock_verdict.stop_loss = None
    mock_verdict.risk_reward = None
    mock_verdict.bull_thesis = "Steady state."
    mock_verdict.bear_thesis = "Low growth."
    mock_verdict.key_risks = []
    mock_verdict.reasoning = "Neutral."
    mock_verdict.based_on = []
    mock_verdict.created_at = datetime(2026, 5, 20, tzinfo=timezone.utc)

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        row = MagicMock()
        row.scalar_one_or_none.return_value = mock_asset if call_count == 0 else mock_verdict
        call_count += 1
        return row

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    result = await _get_symbol_analysis(mock_db, "SCB", user_id)

    assert "HOLD" in result
    assert "Entry" not in result
    assert "Key risks" not in result


@pytest.mark.asyncio
async def test_get_symbol_analysis_falls_back_to_ai_analysis():
    from app.services.chat_tools import _get_symbol_analysis

    user_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    mock_asset = MagicMock()
    mock_asset.id = asset_id

    mock_analysis = MagicMock()
    mock_analysis.verdict = "SELL"
    mock_analysis.target_price = Decimal("50.00")
    mock_analysis.reasoning = "Deteriorating fundamentals."
    mock_analysis.created_at = datetime(2026, 5, 18, tzinfo=timezone.utc)

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        row = MagicMock()
        if call_count == 0:
            row.scalar_one_or_none.return_value = mock_asset
        elif call_count == 1:
            row.scalar_one_or_none.return_value = None   # no CombinedVerdict
        else:
            row.scalar_one_or_none.return_value = mock_analysis
        call_count += 1
        return row

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    result = await _get_symbol_analysis(mock_db, "XYZ", user_id)

    assert "SELL" in result
    assert "no combined verdict" in result
    assert "Deteriorating fundamentals." in result
    assert "50.00" in result


@pytest.mark.asyncio
async def test_get_symbol_analysis_returns_not_found_when_no_asset():
    from app.services.chat_tools import _get_symbol_analysis

    user_id = uuid.uuid4()
    mock_db = AsyncMock()
    row = MagicMock()
    row.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=row)

    result = await _get_symbol_analysis(mock_db, "FAKE", user_id)

    assert result == "No analysis found for FAKE."


@pytest.mark.asyncio
async def test_get_symbol_analysis_returns_not_found_when_no_analyses():
    from app.services.chat_tools import _get_symbol_analysis

    user_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    mock_asset = MagicMock()
    mock_asset.id = asset_id

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        row = MagicMock()
        row.scalar_one_or_none.return_value = mock_asset if call_count == 0 else None
        call_count += 1
        return row

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    result = await _get_symbol_analysis(mock_db, "EMPTY", user_id)

    assert result == "No analysis found for EMPTY."


@pytest.mark.asyncio
async def test_get_symbol_analysis_returns_not_found_for_empty_symbol():
    from app.services.chat_tools import _get_symbol_analysis

    result = await _get_symbol_analysis(AsyncMock(), "", uuid.uuid4())

    assert result == "Symbol is required."
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri
docker compose exec backend pytest tests/test_chat_tools.py -v 2>&1 | tail -20
```

Expected: All 6 tests fail with `ImportError` or `cannot import name '_get_symbol_analysis'`

---

## Task 2: Implement `_get_symbol_analysis` in `chat_tools.py`

**Files:**
- Modify: `backend/app/services/chat_tools.py`

- [ ] **Step 3: Add imports at the top of `chat_tools.py`**

In `backend/app/services/chat_tools.py`, add two imports after the existing model imports (after line 14 `from app.models.watchlist_item import WatchlistItem`):

```python
from app.models.ai_analysis import AIAnalysis
from app.models.combined_verdict import CombinedVerdict
```

- [ ] **Step 4: Add `_get_symbol_analysis` function at the bottom of `chat_tools.py`**

Append this function after the existing `_get_asset_price` function:

```python
async def _get_symbol_analysis(db: AsyncSession, symbol: str, user_id: uuid.UUID) -> str:
    if not symbol:
        return "Symbol is required."
    sym = symbol.upper()
    asset = (await db.execute(
        select(Asset).where(Asset.symbol == sym, Asset.user_id == user_id)
    )).scalar_one_or_none()
    if not asset:
        return f"No analysis found for {sym}."

    verdict = (await db.execute(
        select(CombinedVerdict)
        .where(CombinedVerdict.asset_id == asset.id)
        .order_by(desc(CombinedVerdict.created_at))
        .limit(1)
    )).scalar_one_or_none()

    if verdict:
        lines = [
            f"{sym} — {verdict.verdict.upper()} (conviction: {verdict.conviction}/10)",
            f"As of: {verdict.created_at.strftime('%Y-%m-%d')}",
            "",
        ]
        price_parts = []
        if verdict.entry_price:
            price_parts.append(f"Entry: {float(verdict.entry_price):.2f}")
        if verdict.target_price:
            price_parts.append(f"Target: {float(verdict.target_price):.2f}")
        if verdict.stop_loss:
            price_parts.append(f"Stop: {float(verdict.stop_loss):.2f}")
        if verdict.risk_reward:
            price_parts.append(f"R/R: {float(verdict.risk_reward):.1f}x")
        if price_parts:
            lines.append(" | ".join(price_parts))
            lines.append("")
        lines += [
            "Bull thesis:",
            verdict.bull_thesis,
            "",
            "Bear thesis:",
            verdict.bear_thesis,
            "",
        ]
        if verdict.key_risks:
            lines.append("Key risks:")
            for risk in verdict.key_risks:
                lines.append(f"- {risk}")
            lines.append("")
        lines += ["Reasoning:", verdict.reasoning]
        if verdict.based_on:
            lines += ["", f"Based on: {', '.join(verdict.based_on)}"]
        return "\n".join(lines)

    analysis = (await db.execute(
        select(AIAnalysis)
        .where(AIAnalysis.asset_id == asset.id)
        .order_by(desc(AIAnalysis.created_at))
        .limit(1)
    )).scalar_one_or_none()

    if analysis:
        lines = [f"{sym} — {analysis.verdict.upper()} (AI analysis, no combined verdict)"]
        if analysis.target_price:
            lines.append(f"Target price: {float(analysis.target_price):.2f}")
        lines += ["Reasoning:", analysis.reasoning, f"As of: {analysis.created_at.strftime('%Y-%m-%d')}"]
        return "\n".join(lines)

    return f"No analysis found for {sym}."
```

- [ ] **Step 5: Run tests to verify they all pass**

```bash
docker compose exec backend pytest tests/test_chat_tools.py -v 2>&1 | tail -20
```

Expected: All 6 tests PASS

---

## Task 3: Wire into `TOOL_DEFINITIONS` and `execute_tool`

**Files:**
- Modify: `backend/app/services/chat_tools.py`

- [ ] **Step 6: Add tool definition to `TOOL_DEFINITIONS`**

In `backend/app/services/chat_tools.py`, append this entry to the `TOOL_DEFINITIONS` list (after the `search_news` entry, before the closing `]`):

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
    },
```

- [ ] **Step 7: Add dispatch branch in `execute_tool`**

In `execute_tool`, add this branch before the final `return f"Unknown tool: {name}"` line:

```python
        if name == "get_symbol_analysis":
            return await _get_symbol_analysis(db, arguments.get("symbol", ""), user_id)
```

- [ ] **Step 8: Run the full test suite to check for regressions**

```bash
docker compose exec backend pytest tests/test_chat_tools.py tests/test_chat_sessions.py tests/test_llm_gateway.py -v 2>&1 | tail -30
```

Expected: All tests PASS, no regressions
