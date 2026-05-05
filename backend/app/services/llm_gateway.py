from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.feature_llm_config import FeatureLLMConfig
from app.models.provider_config import ProviderConfig
from app.services.exchange_rate import get_current_usd_thb
from app.services.llm_service import LLMResponse, calc_cost
from sqlalchemy import select

logger = get_logger(__name__)

FEATURE_KEYS = (
    "import_translator",
    "transaction_classifier",
    "portfolio_analysis",
    "chat",
)

DEFAULT_SYSTEM_PROMPTS: dict[str, str] = {
    "import_translator": (
        "You are a financial data normalization expert. Given headers and sample rows from a "
        "broker export file, produce a JSON mapping to translate them to canonical fields.\n\n"
        "Canonical fields: trade_date, type (BUY|SELL|DIVIDEND|REWARD|FEE|TRANSFER), symbol, "
        "unit (number of units), price, currency (ISO code), exchange, gross_amount, fee, "
        "gross_thb, fee_thb, exchange_rate, asset_type (us_stock|thai_stock|th_fund|etf|crypto|gold|cash), "
        "platform, notes.\n\n"
        "Return ONLY valid JSON with this structure (no explanation):\n"
        "{\n"
        "  \"field_map\": {\"SourceCol\": \"canonical_field\", ...},\n"
        "  \"type_map\": {\"SourceValue\": \"CANONICAL_TYPE\", ...},\n"
        "  \"currency_default\": \"THB\",\n"
        "  \"asset_type_default\": \"us_stock\"\n"
        "}"
    ),
    "transaction_classifier": (
        "You are a financial asset classifier. Given a symbol, exchange, and currency, "
        "return the most appropriate asset_type from: us_stock, thai_stock, th_fund, etf, crypto, gold, cash. "
        "Respond with a single word only."
    ),
    "portfolio_analysis": (
        "You are a portfolio analyst. Analyze the user's portfolio allocation, performance, and risk. "
        "Provide concise, actionable insights. Be specific with numbers. Use Thai Baht (THB) as base currency."
    ),
    "chat": (
        "You are a personal finance assistant for Zentri portfolio tracker. "
        "Answer questions about the user's portfolio clearly and concisely. "
        "When you don't know something, say so."
    ),
}

HUMAN_PROMPTS: dict[str, str] = {
    "import_translator": "Headers: {headers}\n\nSample rows:\n{sample_rows}",
    "transaction_classifier": (
        "Symbol: {symbol}\nExchange: {exchange}\nCurrency: {currency}\n"
        "What is the asset_type?"
    ),
    "portfolio_analysis": (
        "Portfolio summary:\n{summary}\n\nAllocation:\n{allocation}\n\n"
        "Provide 3-5 key insights."
    ),
    "chat": "{message}",
}


class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, system: str, human: str, model: str) -> LLMResponse: ...

    @abstractmethod
    async def fetch_models(self) -> list[str]: ...


class AnthropicAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        from app.services.llm_service import LLMQuotaExceededError
        try:
            msg = await self._client.messages.create(
                model=model, max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": human}],
            )
        except Exception as exc:
            try:
                import anthropic
                if isinstance(exc, anthropic.RateLimitError):
                    raise LLMQuotaExceededError("anthropic", "https://console.anthropic.com/settings/billing") from exc
            except ImportError:
                pass
            raise
        tokens_in = msg.usage.input_tokens
        tokens_out = msg.usage.output_tokens
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=msg.content[0].text, tokens_in=tokens_in,
                           tokens_out=tokens_out, cost_usd=cost_usd)

    async def fetch_models(self) -> list[str]:
        result = await self._client.models.list()
        return [m.id for m in result.data]


class OpenAIAdapter(LLMAdapter):
    def __init__(self, api_key: str, base_url: str | None = None):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        from app.services.llm_service import LLMQuotaExceededError
        try:
            resp = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": human}],
            )
        except Exception as exc:
            try:
                import openai
                if isinstance(exc, openai.RateLimitError):
                    raise LLMQuotaExceededError("openai", "https://platform.openai.com/settings/organization/billing") from exc
            except ImportError:
                pass
            raise
        tokens_in = resp.usage.prompt_tokens
        tokens_out = resp.usage.completion_tokens
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=resp.choices[0].message.content or "",
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd)

    async def fetch_models(self) -> list[str]:
        models = await self._client.models.list()
        return [m.id for m in models.data if m.id.startswith(("gpt-", "o1", "o3"))]


class GeminiAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        import asyncio
        from app.services.llm_service import LLMQuotaExceededError
        m = self._genai.GenerativeModel(model_name=model, system_instruction=system)
        try:
            response = await asyncio.to_thread(m.generate_content, human)
        except Exception as exc:
            try:
                from google.api_core.exceptions import ResourceExhausted
                if isinstance(exc, ResourceExhausted):
                    raise LLMQuotaExceededError("gemini", "https://aistudio.google.com/billing") from exc
            except ImportError:
                pass
            raise
        tokens_in = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        tokens_out = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=response.text, tokens_in=tokens_in,
                           tokens_out=tokens_out, cost_usd=cost_usd)

    async def fetch_models(self) -> list[str]:
        import asyncio
        models = await asyncio.to_thread(self._genai.list_models)
        return [
            m.name.replace("models/", "")
            for m in models
            if "generateContent" in (m.supported_generation_methods or [])
        ]


class OllamaAdapter(LLMAdapter):
    def __init__(self, host_url: str):
        self._host = host_url.rstrip("/")

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(f"{self._host}/api/chat", json={
                "model": model, "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": human},
                ],
            })
            resp.raise_for_status()
            data = resp.json()
        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)
        return LLMResponse(content=data["message"]["content"],
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=0.0)

    async def fetch_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(f"{self._host}/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]


class OpenRouterAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    async def complete(self, system: str, human: str, model: str) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": human}],
        )
        usage = resp.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        cost_usd = calc_cost(model, tokens_in, tokens_out)
        return LLMResponse(content=resp.choices[0].message.content or "",
                           tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd)

    async def fetch_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            return [m["id"] for m in resp.json().get("data", [])]


def _build_adapter(provider: str, api_key: str | None, host_url: str | None) -> LLMAdapter:
    if provider == "anthropic":
        return AnthropicAdapter(api_key or "")
    if provider == "openai":
        return OpenAIAdapter(api_key or "")
    if provider == "gemini":
        return GeminiAdapter(api_key or "")
    if provider == "ollama":
        return OllamaAdapter(host_url or "http://localhost:11434")
    if provider == "openrouter":
        return OpenRouterAdapter(api_key or "")
    raise ValueError(f"Unknown provider: {provider}")


class LLMGateway:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def complete(self, feature_key: str, user_id: uuid.UUID, variables: dict) -> str:
        from app.models.llm_call_log import LLMCallLog

        config = await self._get_feature_config(feature_key, user_id)
        provider = await self._get_provider(config.provider_config_id)
        api_key = decrypt(provider.encrypted_api_key) if provider.encrypted_api_key else None
        adapter = _build_adapter(provider.provider, api_key, provider.host_url)
        system = config.system_prompt or DEFAULT_SYSTEM_PROMPTS.get(feature_key, "")
        human = HUMAN_PROMPTS[feature_key].format(**variables)
        logger.info("LLM call: feature=%s provider=%s model=%s", feature_key, provider.provider, config.model)

        response: LLMResponse = await adapter.complete(system, human, config.model)

        usd_thb = await get_current_usd_thb(self._db)
        cost_thb = float(response.cost_usd) * float(usd_thb) if usd_thb else 0.0

        log = LLMCallLog(
            user_id=user_id,
            feature_key=feature_key,
            provider=provider.provider,
            model=config.model,
            prompt_in=f"SYSTEM: {system}\n\nHUMAN: {human}",
            response_out=response.content,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=response.cost_usd,
            cost_thb=cost_thb,
            exchange_rate=float(usd_thb) if usd_thb else 0.0,
        )
        self._db.add(log)
        await self._db.flush()

        logger.info("LLM logged: tokens_in=%d tokens_out=%d cost_usd=%.6f",
                    response.tokens_in, response.tokens_out, response.cost_usd)
        return response.content

    async def _get_feature_config(self, feature_key: str, user_id: uuid.UUID) -> FeatureLLMConfig:
        result = await self._db.execute(
            select(FeatureLLMConfig).where(
                FeatureLLMConfig.feature_key == feature_key,
                FeatureLLMConfig.user_id == user_id,
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            raise ValueError(f"No LLM config for feature '{feature_key}'. Configure it in Settings → AI.")
        return config

    async def _get_provider(self, provider_config_id: uuid.UUID) -> ProviderConfig:
        result = await self._db.execute(
            select(ProviderConfig).where(ProviderConfig.id == provider_config_id)
        )
        provider = result.scalar_one_or_none()
        if not provider:
            raise ValueError("Provider config not found")
        if not provider.is_connected:
            raise ValueError(f"Provider '{provider.provider}' is not connected. Test connection in Settings → AI.")
        return provider
