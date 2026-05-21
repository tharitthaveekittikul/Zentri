import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

VALID_RESPONSE = json.dumps({
    "verdict": "buy",
    "conviction": 7,
    "bull_thesis": "AMD is gaining AI GPU share with MI300X at a cheaper valuation than NVDA.",
    "bear_thesis": "Execution risk on next-gen GPU roadmap and NVDA ecosystem lock-in.",
    "key_risks": ["Customer concentration", "GPU supply chain constraints"],
    "reasoning": "Peer comparison shows best value/growth score. Bear case risks are manageable.",
    "based_on": ["top_down_analysis", "deep_dive", "peer_comparison", "bear_case"],
})


@pytest.mark.asyncio
async def test_run_combined_verdict_saves_result():
    from app.services.combined_verdict import run_combined_verdict
    from app.services.llm_gateway import LLMGatewayResult

    mock_db = AsyncMock()
    mock_asset = MagicMock()
    mock_asset.id = uuid.uuid4()
    mock_asset.name = "Advanced Micro Devices"
    mock_asset.symbol = "AMD"

    mock_top_down = MagicMock()
    mock_top_down.verdict = "BUY"
    mock_top_down.mega_trend = "AI compute buildout."
    mock_top_down.financial_health = "Strong balance sheet."

    mock_deep_dive = MagicMock()
    mock_deep_dive.business_model = "CPU/GPU chip designer."
    mock_deep_dive.moat_edge_type = "switching_cost"
    mock_deep_dive.moat_summary = "x86 lock-in."
    mock_deep_dive.asymmetry_verdict = "yes"

    mock_peer = MagicMock()
    mock_peer.sector_label = "AI Compute / CPU"
    mock_peer.ranked = [{"ticker": "AMD", "label": "BEST", "value_growth_score": 0.37}]

    mock_bear = MagicMock()
    mock_bear.red_flags = [{"rank": 1, "title": "Margin compression", "severity": "medium"}]
    mock_bear.summary = "Manageable risks."

    call_count = 0
    responses = [mock_asset, mock_top_down, mock_deep_dive, mock_peer, mock_bear]

    async def mock_execute(query):
        nonlocal call_count
        row = MagicMock()
        row.scalar_one_or_none.return_value = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return row

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    gateway_result = LLMGatewayResult(
        content=VALID_RESPONSE, prompt="test",
        tokens_in=500, tokens_out=300, cost_usd=0.005,
        cost_thb=0.175, exchange_rate=35.0,
        model="claude-3-5-sonnet", provider="anthropic",
    )

    with patch("app.services.combined_verdict.LLMGateway") as MockGateway:
        mock_gw = AsyncMock()
        mock_gw.complete = AsyncMock(return_value=gateway_result)
        MockGateway.return_value = mock_gw

        verdict = await run_combined_verdict("AMD", uuid.uuid4(), mock_db)

    assert verdict.verdict == "buy"
    assert verdict.conviction == 7
    assert "top_down_analysis" in verdict.based_on
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_run_combined_verdict_raises_if_no_analyses():
    from app.services.combined_verdict import run_combined_verdict

    mock_db = AsyncMock()
    mock_asset = MagicMock()
    mock_asset.id = uuid.uuid4()
    mock_asset.symbol = "AMD"

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        row = MagicMock()
        # First call returns asset, remaining calls return None (no analyses)
        row.scalar_one_or_none.return_value = mock_asset if call_count == 0 else None
        call_count += 1
        return row

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    with pytest.raises(ValueError, match="no analyses available"):
        await run_combined_verdict("AMD", uuid.uuid4(), mock_db)
