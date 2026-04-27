from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)

PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-7": (15.0, 75.0),
    "claude-haiku-4-5-20251001": (0.8, 4.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-1.5-flash": (0.075, 0.3),
}


def _calc_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    if model not in PRICING:
        return 0.0
    in_rate, out_rate = PRICING[model]
    return (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000


@dataclass
class LLMResponse:
    content: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict]) -> LLMResponse: ...


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, model: str):
        self.host = host
        self.model = model

    async def complete(self, messages: list[dict]) -> LLMResponse:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.host}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False},
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
        content = data["message"]["content"]
        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)
        logger.info("ollama complete model=%s tokens_in=%d tokens_out=%d", self.model, tokens_in, tokens_out)
        return LLMResponse(content=content, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=0.0)


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def complete(self, messages: list[dict]) -> LLMResponse:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key)
        resp = await client.chat.completions.create(model=self.model, messages=messages)
        content = resp.choices[0].message.content
        tokens_in = resp.usage.prompt_tokens
        tokens_out = resp.usage.completion_tokens
        cost = _calc_cost(self.model, tokens_in, tokens_out)
        logger.info("openai complete model=%s cost_usd=%.6f", self.model, cost)
        return LLMResponse(content=content, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost)


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def complete(self, messages: list[dict]) -> LLMResponse:
        import anthropic
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] != "system"]
        system = "\n\n".join(system_parts) if system_parts else anthropic.NOT_GIVEN
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        resp = await client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=user_msgs,
        )
        content = resp.content[0].text
        tokens_in = resp.usage.input_tokens
        tokens_out = resp.usage.output_tokens
        cost = _calc_cost(self.model, tokens_in, tokens_out)
        logger.info("claude complete model=%s cost_usd=%.6f", self.model, cost)
        return LLMResponse(content=content, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost)


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def complete(self, messages: list[dict]) -> LLMResponse:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        prompt = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        response = await model.generate_content_async(prompt)
        content = response.text
        logger.info("gemini complete model=%s", self.model)
        return LLMResponse(content=content, tokens_in=0, tokens_out=0, cost_usd=0.0)


async def get_llm_provider(db) -> LLMProvider:
    from sqlalchemy import select
    from app.core.config import settings as app_settings
    from app.core.encryption import decrypt
    from app.models.llm_settings import LLMSettings

    result = await db.execute(select(LLMSettings).where(LLMSettings.is_active == True))
    row = result.scalar_one_or_none()
    if not row:
        return OllamaProvider(host=app_settings.OLLAMA_HOST, model="llama3.2")

    api_key = decrypt(row.encrypted_api_key) if row.encrypted_api_key else None
    if row.provider == "ollama":
        return OllamaProvider(host=app_settings.OLLAMA_HOST, model=row.model)
    elif row.provider == "openai":
        return OpenAIProvider(api_key=api_key, model=row.model)
    elif row.provider == "claude":
        return ClaudeProvider(api_key=api_key, model=row.model)
    elif row.provider == "gemini":
        return GeminiProvider(api_key=api_key, model=row.model)
    else:
        raise ValueError(f"Unknown LLM provider: {row.provider}")
