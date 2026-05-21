import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

VALID_RESPONSE = json.dumps({
    "red_flags": [
        {
            "rank": 1,
            "title": "Gross margin compression",
            "severity": "high",
            "data_source": "yfinance",
            "evidence": "Gross margin fell from 52% to 47% over last 4 quarters.",
            "detail": "Sustained compression signals pricing pressure from NVDA.",
        },
        {
            "rank": 2,
            "title": "Customer concentration risk",
            "severity": "medium",
            "data_source": "llm_knowledge",
            "evidence": "Top hyperscaler customers account for ~30% of AI GPU revenue.",
            "detail": "Single hyperscaler capex cuts could meaningfully impact revenue.",
        },
        {
            "rank": 3,
            "title": "Elevated short interest",
            "severity": "low",
            "data_source": "yfinance",
            "evidence": "Short interest at 4.2% of float.",
            "detail": "Market skepticism around near-term execution.",
        },
    ],
    "summary": "Margin pressure and customer concentration are the two most credible bear theses.",
})


@pytest.mark.asyncio
async def test_run_bear_case_saves_analysis():
    from app.services.bear_case_analysis import run_bear_case
    from app.services.llm_gateway import LLMGatewayResult

    mock_db = AsyncMock()
    mock_asset = MagicMock()
    mock_asset.id = uuid.uuid4()
    mock_asset.name = "Advanced Micro Devices"
    mock_asset.symbol = "AMD"
    mock_asset.metadata_ = {"sector": "Technology"}
    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = mock_asset
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    gateway_result = LLMGatewayResult(
        content=VALID_RESPONSE, prompt="test",
        tokens_in=150, tokens_out=300, cost_usd=0.002,
        cost_thb=0.07, exchange_rate=35.0,
        model="claude-3-5-sonnet", provider="anthropic",
    )

    mock_yf_info = {
        "grossMargins": 0.512, "operatingMargins": 0.22,
        "revenueGrowth": 0.22, "debtToEquity": 12.5,
        "shortPercentOfFloat": 0.042,
    }
    mock_qf = MagicMock()
    mock_qf.index = []

    with patch("app.services.bear_case_analysis.LLMGateway") as MockGateway, \
         patch("app.services.bear_case_analysis.yf") as mock_yf:
        mock_gw = AsyncMock()
        mock_gw.complete = AsyncMock(return_value=gateway_result)
        MockGateway.return_value = mock_gw

        mock_ticker = MagicMock()
        mock_ticker.info = mock_yf_info
        mock_ticker.quarterly_financials = mock_qf
        mock_yf.Ticker.return_value = mock_ticker

        analysis = await run_bear_case("AMD", uuid.uuid4(), mock_db)

    assert len(analysis.red_flags) == 3
    assert analysis.red_flags[0]["rank"] == 1
    assert analysis.red_flags[0]["severity"] == "high"
    assert analysis.summary != ""
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_run_bear_case_raises_if_asset_not_found():
    from app.services.bear_case_analysis import run_bear_case

    mock_db = AsyncMock()
    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    with pytest.raises(ValueError, match="not found"):
        await run_bear_case("FAKE", uuid.uuid4(), mock_db)
