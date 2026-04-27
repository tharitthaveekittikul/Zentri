import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.llm_service import (
    ClaudeProvider,
    OllamaProvider,
    OpenAIProvider,
    LLMResponse,
    _calc_cost,
)


def test_calc_cost_known_model():
    cost = _calc_cost("claude-sonnet-4-6", tokens_in=1_000_000, tokens_out=1_000_000)
    assert cost == pytest.approx(18.0)  # 3.0 + 15.0


def test_calc_cost_unknown_model_returns_zero():
    cost = _calc_cost("unknown-model-xyz", tokens_in=100, tokens_out=100)
    assert cost == 0.0


@pytest.mark.anyio
async def test_ollama_provider_complete():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "Hello"},
        "prompt_eval_count": 10,
        "eval_count": 5,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        provider = OllamaProvider(host="http://localhost:11434", model="llama3.2")
        result = await provider.complete([{"role": "user", "content": "Hi"}])

    assert isinstance(result, LLMResponse)
    assert result.content == "Hello"
    assert result.tokens_in == 10
    assert result.tokens_out == 5
    assert result.cost_usd == 0.0


@pytest.mark.anyio
async def test_claude_provider_complete():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="BUY signal")]
    mock_message.usage.input_tokens = 500
    mock_message.usage.output_tokens = 100

    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_cls.return_value = mock_client

        provider = ClaudeProvider(api_key="sk-ant-test", model="claude-sonnet-4-6")
        result = await provider.complete([
            {"role": "system", "content": "You are a financial analyst."},
            {"role": "user", "content": "Analyse AAPL"},
        ])

    assert result.content == "BUY signal"
    assert result.tokens_in == 500
    assert result.cost_usd > 0
