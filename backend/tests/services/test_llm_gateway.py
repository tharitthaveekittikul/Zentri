from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from app.services.llm_service import LLMResponse


@pytest.mark.asyncio
async def test_gateway_complete_logs_call():
    from app.services.llm_gateway import LLMGateway

    mock_db = AsyncMock()

    feature_config = MagicMock()
    feature_config.provider_config_id = uuid.uuid4()
    feature_config.system_prompt = "You are a test assistant."
    feature_config.model = "gemini-2.5-flash-lite"

    provider_config = MagicMock()
    provider_config.provider = "gemini"
    provider_config.encrypted_api_key = None
    provider_config.host_url = None
    provider_config.is_connected = True

    feature_result = MagicMock()
    feature_result.scalar_one_or_none.return_value = feature_config
    provider_result = MagicMock()
    provider_result.scalar_one_or_none.return_value = provider_config
    mock_db.execute = AsyncMock(side_effect=[feature_result, provider_result])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    fake_response = LLMResponse(content="answer", tokens_in=10, tokens_out=5, cost_usd=0.0)

    with patch("app.services.llm_gateway._build_adapter") as mock_build:
        mock_adapter = AsyncMock()
        mock_adapter.complete = AsyncMock(return_value=fake_response)
        mock_build.return_value = mock_adapter

        with patch("app.services.llm_gateway.get_current_usd_thb", return_value=Decimal("35.5")):
            gateway = LLMGateway(mock_db)
            result = await gateway.complete(
                "import_template_generator",
                uuid.uuid4(),
                {"file_format": "csv", "headers": "[]", "sample_rows": "[]"},
            )

    assert result == "answer"
    mock_db.add.assert_called_once()
    log_obj = mock_db.add.call_args[0][0]
    assert log_obj.tokens_in == 10
    assert log_obj.tokens_out == 5
    assert log_obj.feature_key == "import_template_generator"
