import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PEER_DISCOVERY_RESPONSE = json.dumps(["NVDA", "INTC", "QCOM"])

MAIN_ANALYSIS_RESPONSE = json.dumps({
    "sector_label": "AI Compute / CPU",
    "methodology_note": "Value/Growth Score = P/S TTM / YoY Revenue Growth %",
    "ranked": [
        {
            "ticker": "AMD", "company_name": "Advanced Micro Devices",
            "ps_ttm": 8.1, "ps_forward": 7.4, "ev_ebitda": 34.0,
            "gross_margin_pct": 51.2, "yoy_revenue_growth_pct": 22.0,
            "revenue_trend": "Reaccelerating", "value_growth_score": 0.37,
            "label": "BEST", "notes": "Best value/growth ratio in sector.",
        },
        {
            "ticker": "NVDA", "company_name": "NVIDIA Corp",
            "ps_ttm": 27.2, "ps_forward": 19.8, "ev_ebitda": 44.0,
            "gross_margin_pct": 74.1, "yoy_revenue_growth_pct": 64.0,
            "revenue_trend": "Decelerating", "value_growth_score": 0.42,
            "label": "FAIR", "notes": "Premium valuation.",
        },
        {
            "ticker": "INTC", "company_name": "Intel Corp",
            "ps_ttm": 1.9, "ps_forward": 1.8, "ev_ebitda": None,
            "gross_margin_pct": 37.4, "yoy_revenue_growth_pct": 3.0,
            "revenue_trend": "Stagnant", "value_growth_score": 0.63,
            "label": "AVOID", "notes": "Low growth.",
        },
    ],
})


@pytest.mark.asyncio
async def test_run_peer_comparison_saves_analysis():
    from app.services.peer_comparison_analysis import run_peer_comparison
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

    main_result = LLMGatewayResult(
        content=MAIN_ANALYSIS_RESPONSE, prompt="test",
        tokens_in=200, tokens_out=400, cost_usd=0.003,
        cost_thb=0.1, exchange_rate=35.0,
        model="claude-3-5-sonnet", provider="anthropic",
    )

    mock_yf_data = {
        "AMD": {"ps_ttm": 8.1, "ps_forward": 7.4, "ev_ebitda": 34.0, "gross_margin_pct": 51.2, "yoy_revenue_growth_pct": 22.0},
        "NVDA": {"ps_ttm": 27.2, "ps_forward": 19.8, "ev_ebitda": 44.0, "gross_margin_pct": 74.1, "yoy_revenue_growth_pct": 64.0},
        "INTC": {"ps_ttm": 1.9, "ps_forward": 1.8, "ev_ebitda": None, "gross_margin_pct": 37.4, "yoy_revenue_growth_pct": 3.0},
    }

    with patch("app.services.peer_comparison_analysis.LLMGateway") as MockGateway, \
         patch("app.services.peer_comparison_analysis._fetch_yfinance_metrics") as mock_yf, \
         patch("app.services.peer_comparison_analysis._discover_peers") as mock_discover:

        mock_gw = AsyncMock()
        mock_gw.complete = AsyncMock(return_value=main_result)
        MockGateway.return_value = mock_gw

        discovery_result = MagicMock()
        mock_discover.return_value = (["NVDA", "INTC", "QCOM"], discovery_result)
        mock_yf.return_value = mock_yf_data

        analysis = await run_peer_comparison("AMD", uuid.uuid4(), mock_db)

    assert analysis.sector_label == "AI Compute / CPU"
    assert len(analysis.ranked) == 3
    assert analysis.ranked[0]["label"] == "BEST"
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_run_peer_comparison_raises_if_asset_not_found():
    from app.services.peer_comparison_analysis import run_peer_comparison

    mock_db = AsyncMock()
    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    with pytest.raises(ValueError, match="not found"):
        await run_peer_comparison("FAKE", uuid.uuid4(), mock_db)
