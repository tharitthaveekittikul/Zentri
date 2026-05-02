from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.feature_llm_config import FeatureLLMConfig
from app.models.provider_config import ProviderConfig
from sqlalchemy import select

logger = get_logger(__name__)

FEATURE_KEYS = (
    "import_template_generator",
    "transaction_classifier",
    "portfolio_analysis",
    "chat",
)

DEFAULT_SYSTEM_PROMPTS: dict[str, str] = {
    "import_template_generator": (
        "You are a data normalization expert. Given a financial transaction file structure, "
        "produce a JSON mapping template that maps source fields to the canonical schema. "
        "Canonical fields: symbol, date, type, units, price, currency, total_thb, fee_thb, asset_type, notes. "
        "Also produce asset_type_rules (list of {field, values/pattern, asset_type}) and asset_type_fallback. "
        "Respond with valid JSON only. No explanation."
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
    "import_template_generator": (
        "File format: {file_format}\n"
        "Headers/keys: {headers}\n"
        "Sample rows (first 3):\n{sample_rows}\n\n"
        "Return a JSON object with keys: file_format, json_path, field_map, asset_type_rules, asset_type_fallback, currency_default."
    ),
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
    async def complete(self, system: str, human: str, model: str) -> str: ...

    @abstractmethod
    async def fetch_models(self) -> list[str]: ...


class AnthropicAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, system: str, human: str, model: str) -> str:
        msg = await self._client.messages.create(
            model=model, max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": human}],
        )
        return msg.content[0].text

    async def fetch_models(self) -> list[str]:
        result = await self._client.models.list()
        return [m.id for m in result.data]


class OpenAIAdapter(LLMAdapter):
    def __init__(self, api_key: str, base_url: str | None = None):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def complete(self, system: str, human: str, model: str) -> str:
        resp = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": human}],
        )
        return resp.choices[0].message.content or ""

    async def fetch_models(self) -> list[str]:
        models = await self._client.models.list()
        return [m.id for m in models.data if m.id.startswith(("gpt-", "o1", "o3"))]


class GeminiAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai

    async def complete(self, system: str, human: str, model: str) -> str:
        import asyncio
        m = self._genai.GenerativeModel(model_name=model, system_instruction=system)
        resp = await asyncio.to_thread(m.generate_content, human)
        return resp.text

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

    async def complete(self, system: str, human: str, model: str) -> str:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(f"{self._host}/api/chat", json={
                "model": model, "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": human},
                ],
            })
            resp.raise_for_status()
            return resp.json()["message"]["content"]

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

    async def complete(self, system: str, human: str, model: str) -> str:
        resp = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": human}],
        )
        return resp.choices[0].message.content or ""

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
        config = await self._get_feature_config(feature_key, user_id)
        provider = await self._get_provider(config.provider_config_id)
        api_key = decrypt(provider.encrypted_api_key) if provider.encrypted_api_key else None
        adapter = _build_adapter(provider.provider, api_key, provider.host_url)
        system = config.system_prompt
        human = HUMAN_PROMPTS[feature_key].format(**variables)
        logger.info("LLM call: feature=%s provider=%s model=%s", feature_key, provider.provider, config.model)
        return await adapter.complete(system, human, config.model)

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
