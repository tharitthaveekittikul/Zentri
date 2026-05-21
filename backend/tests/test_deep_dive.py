import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


VALID_RESPONSE = json.dumps({
    "business_model": "AMD designs CPUs and GPUs, licensing IP and selling chips.",
    "moat": {
        "edge_type": "switching_cost",
        "summary": "x86 architecture lock-in across enterprise.",
        "competitors": ["NVDA", "INTC", "QCOM"],
    },
    "catalysts": [
        {"title": "MI300X ramp", "timeframe": "H1 2025", "impact": "high"}
    ],
    "asymmetry": {
        "verdict": "yes",
        "floor": "CPU segment provides downside protection at ~5x P/S",
        "ceiling": "AI GPU TAM expansion to $400B by 2027",
        "reasoning": "Asymmetric upside from data center GPU share gains.",
    },
})


@pytest.mark.asyncio
async def test_run_deep_dive_saves_analysis():
    from app.services.deep_dive_analysis import run_deep_dive
    from app.services.llm_gateway import LLMGatewayResult

    mock_db = AsyncMock()
    mock_asset = MagicMock()
    mock_asset.id = uuid.uuid4()
    mock_asset.name = "Advanced Micro Devices"
    mock_asset.metadata_ = {"sector": "Technology"}

    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = mock_asset
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    gateway_result = LLMGatewayResult(
        content=VALID_RESPONSE,
        prompt="test",
        tokens_in=100,
        tokens_out=200,
        cost_usd=0.001,
        cost_thb=0.035,
        exchange_rate=35.0,
        model="claude-3-5-sonnet",
        provider="anthropic",
    )

    with patch("app.services.deep_dive_analysis.LLMGateway") as MockGateway:
        mock_gw = AsyncMock()
        mock_gw.complete = AsyncMock(return_value=gateway_result)
        MockGateway.return_value = mock_gw

        analysis = await run_deep_dive("AMD", uuid.uuid4(), mock_db)

    assert analysis.business_model == "AMD designs CPUs and GPUs, licensing IP and selling chips."
    assert analysis.moat_edge_type == "switching_cost"
    assert analysis.moat_competitors == ["NVDA", "INTC", "QCOM"]
    assert analysis.asymmetry_verdict == "yes"
    assert analysis.provider == "anthropic"
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_run_deep_dive_raises_if_asset_not_found():
    from app.services.deep_dive_analysis import run_deep_dive

    mock_db = AsyncMock()
    mock_result_row = MagicMock()
    mock_result_row.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result_row)

    with pytest.raises(ValueError, match="not found"):
        await run_deep_dive("FAKE", uuid.uuid4(), mock_db)
