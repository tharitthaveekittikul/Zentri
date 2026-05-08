import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.llm_service import (
    ClaudeProvider,
    OllamaProvider,
    OpenAIProvider,
    LLMResponse,
    LLMQuotaExceededError,
)
from app.core.llm_pricing import calc_cost as _calc_cost


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


def test_llm_quota_exceeded_error_has_provider_and_url():
    err = LLMQuotaExceededError("gemini", "https://aistudio.google.com/billing")
    assert err.provider == "gemini"
    assert err.billing_url == "https://aistudio.google.com/billing"
    assert "gemini" in str(err)


@pytest.mark.asyncio
async def test_gemini_adapter_raises_quota_exceeded_on_resource_exhausted():
    from app.services.llm_gateway import GeminiAdapter
    adapter = GeminiAdapter.__new__(GeminiAdapter)
    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    adapter._genai = mock_genai

    from google.api_core.exceptions import ResourceExhausted

    async def raise_exhausted(*args, **kwargs):
        raise ResourceExhausted("Your prepayment credits are depleted.")

    with patch("asyncio.to_thread", side_effect=raise_exhausted):
        with pytest.raises(LLMQuotaExceededError) as exc_info:
            await adapter.complete("sys", "human", "gemini-2.0-flash")
    assert exc_info.value.provider == "gemini"


@pytest.mark.asyncio
async def test_openai_adapter_raises_quota_exceeded_on_rate_limit():
    from app.services.llm_gateway import OpenAIAdapter
    import openai

    adapter = OpenAIAdapter.__new__(OpenAIAdapter)
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = openai.RateLimitError(
        "Rate limit exceeded", response=MagicMock(status_code=429), body={}
    )
    adapter._client = mock_client

    with pytest.raises(LLMQuotaExceededError) as exc_info:
        await adapter.complete("sys", "human", "gpt-4o")
    assert exc_info.value.provider == "openai"


@pytest.mark.asyncio
async def test_anthropic_adapter_raises_quota_exceeded_on_rate_limit():
    from app.services.llm_gateway import AnthropicAdapter
    import anthropic

    adapter = AnthropicAdapter.__new__(AnthropicAdapter)
    mock_client = AsyncMock()
    mock_client.messages.create.side_effect = anthropic.RateLimitError(
        message="Rate limit exceeded", response=MagicMock(status_code=429), body={}
    )
    adapter._client = mock_client

    with pytest.raises(LLMQuotaExceededError) as exc_info:
        await adapter.complete("sys", "human", "claude-sonnet-4-6")
    assert exc_info.value.provider == "anthropic"
