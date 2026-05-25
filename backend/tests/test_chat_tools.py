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
    mock_asset.currency = "USD"

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
    assert "USD" in result


@pytest.mark.asyncio
async def test_get_symbol_analysis_omits_prices_when_none():
    from app.services.chat_tools import _get_symbol_analysis

    user_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    mock_asset = MagicMock()
    mock_asset.id = asset_id
    mock_asset.currency = "THB"

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
    mock_asset.currency = "USD"

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
    assert "50.00 USD" in result


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
