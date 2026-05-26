def test_llm_call_log_has_tool_rounds_column():
    from app.models.llm_call_log import LLMCallLog
    from sqlalchemy import inspect as sa_inspect
    cols = {c.key for c in sa_inspect(LLMCallLog).mapper.column_attrs}
    assert "tool_rounds" in cols


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

    log_arg = mock_db.add.call_args[0][0]
    assert log_arg.tool_rounds is not None
    assert len(log_arg.tool_rounds) == 2


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
