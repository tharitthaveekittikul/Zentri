# Smart Import, Cash Accounts & LLM Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `etf`/`cash` asset types, per-feature LLM provider configuration with model fetching, cash account balance snapshots, and a smart import pipeline that generates reusable mapping templates via LLM.

**Architecture:** Five phases — (1) DB schema foundation, (2) LLM gateway infrastructure, (3) cash accounts, (4) smart import pipeline, (5) frontend. Each phase produces independently testable software. The LLMGateway abstracts all provider SDKs behind one `.complete()` interface. Existing `llm_settings` table is kept; new `provider_configs` and `feature_llm_configs` tables are added alongside it.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, TimescaleDB (PostgreSQL), httpx, anthropic SDK, openai SDK, google-generativeai SDK, Next.js 14 App Router, TypeScript

---

## File Map

### Backend — New files

| File                                                    | Responsibility                                      |
| ------------------------------------------------------- | --------------------------------------------------- |
| `backend/app/models/provider_config.py`                 | ProviderConfig SQLAlchemy model                     |
| `backend/app/models/feature_llm_config.py`              | FeatureLLMConfig SQLAlchemy model                   |
| `backend/app/models/cash_balance.py`                    | CashBalance SQLAlchemy model                        |
| `backend/app/models/import_template.py`                 | ImportTemplate SQLAlchemy model                     |
| `backend/app/schemas/provider_config.py`                | Pydantic schemas for provider config                |
| `backend/app/schemas/feature_llm_config.py`             | Pydantic schemas for feature LLM config             |
| `backend/app/schemas/cash_balance.py`                   | Pydantic schemas for cash balance                   |
| `backend/app/schemas/import_template.py`                | Pydantic schemas for import template                |
| `backend/app/services/llm_gateway.py`                   | LLMGateway + all provider adapters + prompts        |
| `backend/app/services/cash_balance.py`                  | Cash balance CRUD service                           |
| `backend/app/services/import_pipeline.py`               | Import pipeline orchestration service               |
| `backend/app/api/provider_config.py`                    | REST endpoints: CRUD, test connection, fetch models |
| `backend/app/api/feature_llm_config.py`                 | REST endpoints: CRUD, reset to default              |
| `backend/app/api/cash_balance.py`                       | REST endpoints: CRUD cash balances                  |
| `backend/app/api/import_pipeline.py`                    | REST endpoints: upload, preview, confirm import     |
| `backend/alembic/versions/005_smart_import_llm_cash.py` | Migration: new tables + enum values                 |

### Backend — Modified files

| File                           | Change                                          |
| ------------------------------ | ----------------------------------------------- |
| `backend/app/models/asset.py`  | Add `etf`, `cash` to ASSET_TYPES                |
| `backend/app/schemas/asset.py` | Update Literal type                             |
| `backend/app/main.py`          | Register 4 new routers                          |
| `backend/pyproject.toml`       | Add anthropic, openai, google-generativeai deps |

### Frontend — New files

| File                                          | Responsibility                          |
| --------------------------------------------- | --------------------------------------- |
| `frontend/lib/services/provider-config.ts`    | API client for provider config          |
| `frontend/lib/services/feature-llm-config.ts` | API client for feature LLM config       |
| `frontend/lib/services/cash-balance.ts`       | API client for cash balances            |
| `frontend/lib/services/import-pipeline.ts`    | API client for import pipeline          |
| `frontend/app/(auth)/settings/ai/page.tsx`    | AI providers + feature prompts settings |
| `frontend/app/(auth)/import/page.tsx`         | Import wizard page                      |

### Frontend — Modified files

| File                                                | Change                       |
| --------------------------------------------------- | ---------------------------- |
| `frontend/app/(auth)/settings/page.tsx` (or layout) | Add AI tab link              |
| `frontend/app/(auth)/page.tsx` (overview)           | Add cash row + currency hint |

---

## Phase 1 — DB Foundation

### Task 1: Expand ASSET_TYPES and update schemas

**Files:**

- Modify: `backend/app/models/asset.py`
- Modify: `backend/app/schemas/asset.py`

- [ ] **Step 1: Update ASSET_TYPES tuple in asset model**

In `backend/app/models/asset.py`, change line 10:

```python
ASSET_TYPES = ("us_stock", "thai_stock", "th_fund", "etf", "crypto", "gold", "cash")
```

- [ ] **Step 2: Update asset schema Literal**

In `backend/app/schemas/asset.py`, update the `asset_type` field:

```python
asset_type: Literal["us_stock", "thai_stock", "th_fund", "etf", "crypto", "gold", "cash"]
```

- [ ] **Step 3: Run existing tests to verify no regression**

```bash
cd backend && python -m pytest tests/test_assets.py tests/test_portfolio.py -v
```

Expected: all pass (enum change is additive, existing values still valid)

---

### Task 2: Create new DB models

**Files:**

- Create: `backend/app/models/provider_config.py`
- Create: `backend/app/models/feature_llm_config.py`
- Create: `backend/app/models/cash_balance.py`
- Create: `backend/app/models/import_template.py`

- [ ] **Step 1: Create ProviderConfig model**

`backend/app/models/provider_config.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PROVIDERS = ("anthropic", "openai", "gemini", "ollama", "openrouter")


class ProviderConfig(Base):
    __tablename__ = "provider_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    host_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    models_cache: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    models_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Create FeatureLLMConfig model**

`backend/app/models/feature_llm_config.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

FEATURE_KEYS = (
    "import_template_generator",
    "transaction_classifier",
    "portfolio_analysis",
    "chat",
)


class FeatureLLMConfig(Base):
    __tablename__ = "feature_llm_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    feature_key: Mapped[str] = mapped_column(String(60), nullable=False)
    provider_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_configs.id"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    is_prompt_customized: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 3: Create CashBalance model**

`backend/app/models/cash_balance.py`:

```python
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CashBalance(Base):
    __tablename__ = "cash_balances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    balance: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Create ImportTemplate model**

`backend/app/models/import_template.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportTemplate(Base):
    __tablename__ = "import_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platforms.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)  # csv | json
    json_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    column_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    field_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    asset_type_rules: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    asset_type_fallback: Mapped[str] = mapped_column(String(30), nullable=False)
    currency_default: Mapped[str] = mapped_column(String(10), nullable=False, default="THB")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
```

---

### Task 3: Alembic migration 005

**Files:**

- Create: `backend/alembic/versions/005_smart_import_llm_cash.py`

> **Important:** PostgreSQL `Enum` types cannot have values added in a transaction. Use `ALTER TYPE ... ADD VALUE` with `execute_if` and batch mode.

- [ ] **Step 1: Create migration file**

`backend/alembic/versions/005_smart_import_llm_cash.py`:

```python
"""smart import llm cash

Revision ID: 005
Revises: 004
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values — must be outside transaction in PostgreSQL
    op.execute("ALTER TYPE asset_type_enum ADD VALUE IF NOT EXISTS 'etf'")
    op.execute("ALTER TYPE asset_type_enum ADD VALUE IF NOT EXISTS 'cash'")

    op.create_table(
        "provider_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=True),
        sa.Column("host_url", sa.String(255), nullable=True),
        sa.Column("is_connected", sa.Boolean, default=False),
        sa.Column("models_cache", JSONB, nullable=False, server_default="[]"),
        sa.Column("models_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "feature_llm_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("feature_key", sa.String(60), nullable=False),
        sa.Column(
            "provider_config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("provider_configs.id"),
            nullable=False,
        ),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("is_prompt_customized", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "cash_balances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "import_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("platform_id", UUID(as_uuid=True), sa.ForeignKey("platforms.id"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("file_format", sa.String(10), nullable=False),
        sa.Column("json_path", sa.String(255), nullable=True),
        sa.Column("column_signature", sa.String(64), nullable=False),
        sa.Column("field_map", JSONB, nullable=False, server_default="{}"),
        sa.Column("asset_type_rules", JSONB, nullable=False, server_default="[]"),
        sa.Column("asset_type_fallback", sa.String(30), nullable=False),
        sa.Column("currency_default", sa.String(10), nullable=False, server_default="THB"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("import_templates")
    op.drop_table("cash_balances")
    op.drop_table("feature_llm_configs")
    op.drop_table("provider_configs")
    # Note: PostgreSQL does not support removing enum values — manual downgrade needed for etf/cash
```

- [ ] **Step 2: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade 004 -> 005` with no errors.

- [ ] **Step 3: Verify tables exist**

```bash
cd backend && python -c "
import asyncio
from app.core.database import async_engine
from sqlalchemy import text

async def check():
    async with async_engine.connect() as c:
        for t in ['provider_configs','feature_llm_configs','cash_balances','import_templates']:
            r = await c.execute(text(f'SELECT COUNT(*) FROM {t}'))
            print(t, r.scalar())

asyncio.run(check())
"
```

Expected: all 4 tables print `0`.

---

## Phase 2 — LLM Gateway Infrastructure

### Task 4: Add LLM SDK dependencies

**Files:**

- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add dependencies to pyproject.toml**

In `backend/pyproject.toml`, add to the `dependencies` list:

```toml
"anthropic>=0.30.0",
"openai>=1.0.0",
"google-generativeai>=0.8.0",
```

- [ ] **Step 2: Install**

```bash
cd backend && uv pip install anthropic openai google-generativeai
```

Expected: installed successfully, no conflicts.

---

### Task 5: Create LLM Gateway service

**Files:**

- Create: `backend/app/services/llm_gateway.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_llm_gateway.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_gateway import LLMGateway, FEATURE_KEYS, DEFAULT_SYSTEM_PROMPTS, HUMAN_PROMPTS


def test_all_feature_keys_have_defaults():
    for key in FEATURE_KEYS:
        assert key in DEFAULT_SYSTEM_PROMPTS, f"Missing default system prompt for {key}"
        assert key in HUMAN_PROMPTS, f"Missing human prompt for {key}"


def test_human_prompt_has_placeholders():
    prompt = HUMAN_PROMPTS["import_template_generator"]
    assert "{file_format}" in prompt
    assert "{headers}" in prompt
    assert "{sample_rows}" in prompt


def test_human_prompt_classifier_has_placeholders():
    prompt = HUMAN_PROMPTS["transaction_classifier"]
    assert "{symbol}" in prompt
    assert "{exchange}" in prompt
    assert "{currency}" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_llm_gateway.py -v
```

Expected: `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Implement LLMGateway**

`backend/app/services/llm_gateway.py`:

```python
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
        import anthropic
        msg = await self._client.messages.create(
            model=model, max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": human}],
        )
        return msg.content[0].text

    async def fetch_models(self) -> list[str]:
        import anthropic
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
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_llm_gateway.py -v
```

Expected: all 3 tests pass.

---

### Task 6: ProviderConfig API

**Files:**

- Create: `backend/app/schemas/provider_config.py`
- Create: `backend/app/api/provider_config.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_provider_config.py`:

```python
import pytest


async def test_create_provider_config(auth_client):
    resp = await auth_client.post("/api/v1/provider-configs", json={
        "provider": "ollama",
        "host_url": "http://localhost:11434",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "ollama"
    assert data["is_connected"] is False
    assert "id" in data


async def test_create_provider_config_invalid_provider(auth_client):
    resp = await auth_client.post("/api/v1/provider-configs", json={
        "provider": "unknown_provider",
    })
    assert resp.status_code == 422


async def test_list_provider_configs(auth_client):
    await auth_client.post("/api/v1/provider-configs", json={"provider": "ollama", "host_url": "http://localhost:11434"})
    resp = await auth_client.get("/api/v1/provider-configs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_delete_provider_config(auth_client):
    create = await auth_client.post("/api/v1/provider-configs", json={"provider": "ollama", "host_url": "http://localhost:11434"})
    pid = create.json()["id"]
    resp = await auth_client.delete(f"/api/v1/provider-configs/{pid}")
    assert resp.status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_provider_config.py -v
```

Expected: `404 Not Found` (router not registered yet).

- [ ] **Step 3: Create schemas**

`backend/app/schemas/provider_config.py`:

```python
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

PROVIDER_LITERAL = Literal["anthropic", "openai", "gemini", "ollama", "openrouter"]


class ProviderConfigCreate(BaseModel):
    provider: PROVIDER_LITERAL
    api_key: str | None = None
    host_url: str | None = None


class ProviderConfigUpdate(BaseModel):
    api_key: str | None = None
    host_url: str | None = None


class ProviderConfigOut(BaseModel):
    id: uuid.UUID
    provider: str
    host_url: str | None
    is_connected: bool
    models_cache: list[str]
    models_fetched_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create API router**

`backend/app/api/provider_config.py`:

```python
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.encryption import encrypt, decrypt
from app.core.logging import get_logger
from app.models.provider_config import ProviderConfig
from app.models.user import User
from app.schemas.provider_config import ProviderConfigCreate, ProviderConfigOut, ProviderConfigUpdate
from app.services.llm_gateway import _build_adapter

logger = get_logger(__name__)
router = APIRouter(prefix="/provider-configs", tags=["provider-configs"])


@router.get("", response_model=list[ProviderConfigOut])
async def list_provider_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("", response_model=ProviderConfigOut, status_code=status.HTTP_201_CREATED)
async def create_provider_config(
    body: ProviderConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    cfg = ProviderConfig(
        user_id=current_user.id,
        provider=body.provider,
        encrypted_api_key=encrypt(body.api_key) if body.api_key else None,
        host_url=body.host_url,
        created_at=now,
        updated_at=now,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    logger.info("ProviderConfig created: provider=%s user=%s", body.provider, current_user.id)
    return cfg


@router.patch("/{config_id}", response_model=ProviderConfigOut)
async def update_provider_config(
    config_id: uuid.UUID,
    body: ProviderConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    if body.api_key is not None:
        cfg.encrypted_api_key = encrypt(body.api_key)
    if body.host_url is not None:
        cfg.host_url = body.host_url
    cfg.is_connected = False
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    await db.delete(cfg)
    await db.commit()


@router.post("/{config_id}/test-connection", response_model=ProviderConfigOut)
async def test_connection(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    api_key = decrypt(cfg.encrypted_api_key) if cfg.encrypted_api_key else None
    try:
        adapter = _build_adapter(cfg.provider, api_key, cfg.host_url)
        await adapter.fetch_models()
        cfg.is_connected = True
        logger.info("Provider connection OK: provider=%s user=%s", cfg.provider, current_user.id)
    except Exception as exc:
        cfg.is_connected = False
        logger.warning("Provider connection failed: provider=%s error=%s", cfg.provider, exc)
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.post("/{config_id}/fetch-models", response_model=ProviderConfigOut)
async def fetch_models(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    api_key = decrypt(cfg.encrypted_api_key) if cfg.encrypted_api_key else None
    try:
        adapter = _build_adapter(cfg.provider, api_key, cfg.host_url)
        models = await adapter.fetch_models()
        cfg.models_cache = models
        cfg.models_fetched_at = datetime.now(timezone.utc)
        cfg.is_connected = True
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {exc}")
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def _get_own(db: AsyncSession, config_id: uuid.UUID, user_id: uuid.UUID) -> ProviderConfig:
    result = await db.execute(
        select(ProviderConfig).where(
            ProviderConfig.id == config_id,
            ProviderConfig.user_id == user_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return cfg
```

- [ ] **Step 5: Register router in main.py**

In `backend/app/main.py`, add import and `include_router`:

```python
from app.api import analysis, assets, auth, documents, health, overview, pipeline, platforms, portfolio, settings, provider_config, feature_llm_config, cash_balance, import_pipeline

# ...existing includes...
app.include_router(provider_config.router, prefix="/api/v1")
app.include_router(feature_llm_config.router, prefix="/api/v1")
app.include_router(cash_balance.router, prefix="/api/v1")
app.include_router(import_pipeline.router, prefix="/api/v1")
```

> Note: `feature_llm_config`, `cash_balance`, `import_pipeline` routers will be created in subsequent tasks — add stubs now and fill in later.

- [ ] **Step 6: Run tests**

```bash
cd backend && python -m pytest tests/test_provider_config.py -v
```

Expected: all 4 pass.

---

### Task 7: FeatureLLMConfig API

**Files:**

- Create: `backend/app/schemas/feature_llm_config.py`
- Create: `backend/app/api/feature_llm_config.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_feature_llm_config.py`:

```python
import pytest


async def test_create_feature_llm_config(auth_client):
    provider = await auth_client.post("/api/v1/provider-configs", json={
        "provider": "ollama", "host_url": "http://localhost:11434"
    })
    pid = provider.json()["id"]
    resp = await auth_client.post("/api/v1/feature-llm-configs", json={
        "feature_key": "import_template_generator",
        "provider_config_id": pid,
        "model": "llama3.2",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["feature_key"] == "import_template_generator"
    assert data["is_prompt_customized"] is False
    assert len(data["system_prompt"]) > 20


async def test_reset_to_default(auth_client):
    provider = await auth_client.post("/api/v1/provider-configs", json={
        "provider": "ollama", "host_url": "http://localhost:11434"
    })
    pid = provider.json()["id"]
    create = await auth_client.post("/api/v1/feature-llm-configs", json={
        "feature_key": "chat", "provider_config_id": pid, "model": "llama3.2",
    })
    cid = create.json()["id"]
    # Customize it
    await auth_client.patch(f"/api/v1/feature-llm-configs/{cid}", json={
        "system_prompt": "custom prompt", "model": "llama3.2"
    })
    # Reset
    resp = await auth_client.post(f"/api/v1/feature-llm-configs/{cid}/reset-prompt")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_prompt_customized"] is False
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && python -m pytest tests/test_feature_llm_config.py -v
```

Expected: `404` (router not wired yet).

- [ ] **Step 3: Create schemas**

`backend/app/schemas/feature_llm_config.py`:

```python
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class FeatureLLMConfigCreate(BaseModel):
    feature_key: str
    provider_config_id: uuid.UUID
    model: str
    system_prompt: str | None = None  # defaults to DEFAULT_SYSTEM_PROMPTS[feature_key]


class FeatureLLMConfigUpdate(BaseModel):
    provider_config_id: uuid.UUID | None = None
    model: str | None = None
    system_prompt: str | None = None


class FeatureLLMConfigOut(BaseModel):
    id: uuid.UUID
    feature_key: str
    provider_config_id: uuid.UUID
    model: str
    system_prompt: str
    is_prompt_customized: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create API router**

`backend/app/api/feature_llm_config.py`:

```python
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.feature_llm_config import FeatureLLMConfig, FEATURE_KEYS
from app.models.user import User
from app.schemas.feature_llm_config import FeatureLLMConfigCreate, FeatureLLMConfigOut, FeatureLLMConfigUpdate
from app.services.llm_gateway import DEFAULT_SYSTEM_PROMPTS

logger = get_logger(__name__)
router = APIRouter(prefix="/feature-llm-configs", tags=["feature-llm-configs"])


@router.get("", response_model=list[FeatureLLMConfigOut])
async def list_feature_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FeatureLLMConfig).where(FeatureLLMConfig.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("", response_model=FeatureLLMConfigOut, status_code=status.HTTP_201_CREATED)
async def create_feature_config(
    body: FeatureLLMConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.feature_key not in FEATURE_KEYS:
        raise HTTPException(status_code=422, detail=f"Unknown feature_key: {body.feature_key}")
    system_prompt = body.system_prompt or DEFAULT_SYSTEM_PROMPTS[body.feature_key]
    is_customized = body.system_prompt is not None
    now = datetime.now(timezone.utc)
    cfg = FeatureLLMConfig(
        user_id=current_user.id,
        feature_key=body.feature_key,
        provider_config_id=body.provider_config_id,
        model=body.model,
        system_prompt=system_prompt,
        is_prompt_customized=is_customized,
        created_at=now,
        updated_at=now,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    logger.info("FeatureLLMConfig created: key=%s user=%s", body.feature_key, current_user.id)
    return cfg


@router.patch("/{config_id}", response_model=FeatureLLMConfigOut)
async def update_feature_config(
    config_id: uuid.UUID,
    body: FeatureLLMConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    if body.provider_config_id is not None:
        cfg.provider_config_id = body.provider_config_id
    if body.model is not None:
        cfg.model = body.model
    if body.system_prompt is not None:
        cfg.system_prompt = body.system_prompt
        cfg.is_prompt_customized = True
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.post("/{config_id}/reset-prompt", response_model=FeatureLLMConfigOut)
async def reset_prompt(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = await _get_own(db, config_id, current_user.id)
    cfg.system_prompt = DEFAULT_SYSTEM_PROMPTS[cfg.feature_key]
    cfg.is_prompt_customized = False
    await db.commit()
    await db.refresh(cfg)
    logger.info("System prompt reset to default: key=%s user=%s", cfg.feature_key, current_user.id)
    return cfg


async def _get_own(db: AsyncSession, config_id: uuid.UUID, user_id: uuid.UUID) -> FeatureLLMConfig:
    result = await db.execute(
        select(FeatureLLMConfig).where(
            FeatureLLMConfig.id == config_id,
            FeatureLLMConfig.user_id == user_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Feature LLM config not found")
    return cfg
```

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest tests/test_feature_llm_config.py -v
```

Expected: all 2 pass.

---

## Phase 3 — Cash Accounts

### Task 8: Cash balance service and API

**Files:**

- Create: `backend/app/schemas/cash_balance.py`
- Create: `backend/app/services/cash_balance.py`
- Create: `backend/app/api/cash_balance.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_cash_balance.py`:

```python
import pytest
from datetime import date


async def test_create_cash_asset_and_balance(auth_client):
    # Create cash asset
    asset = await auth_client.post("/api/v1/assets", json={
        "symbol": "KBANK_SAVINGS",
        "asset_type": "cash",
        "name": "KBANK Savings",
        "currency": "THB",
    })
    assert asset.status_code == 201
    asset_id = asset.json()["id"]

    # Add balance snapshot
    resp = await auth_client.post("/api/v1/cash-balances", json={
        "asset_id": asset_id,
        "balance": 50000.0,
        "snapshot_date": str(date.today()),
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["balance"] == 50000.0


async def test_latest_balance(auth_client):
    asset = await auth_client.post("/api/v1/assets", json={
        "symbol": "GSB_SAVINGS", "asset_type": "cash", "name": "GSB", "currency": "THB"
    })
    aid = asset.json()["id"]
    await auth_client.post("/api/v1/cash-balances", json={
        "asset_id": aid, "balance": 10000.0, "snapshot_date": "2026-01-01"
    })
    await auth_client.post("/api/v1/cash-balances", json={
        "asset_id": aid, "balance": 15000.0, "snapshot_date": "2026-02-01"
    })
    resp = await auth_client.get(f"/api/v1/cash-balances/{aid}/latest")
    assert resp.status_code == 200
    assert resp.json()["balance"] == 15000.0


async def test_balance_history(auth_client):
    asset = await auth_client.post("/api/v1/assets", json={
        "symbol": "DIME_USD", "asset_type": "cash", "name": "DIME USD", "currency": "USD"
    })
    aid = asset.json()["id"]
    for amount in [100.0, 200.0, 150.0]:
        await auth_client.post("/api/v1/cash-balances", json={
            "asset_id": aid, "balance": amount, "snapshot_date": f"2026-0{int(amount/100)}-01"
        })
    resp = await auth_client.get(f"/api/v1/cash-balances/{aid}/history")
    assert resp.status_code == 200
    assert len(resp.json()) == 3
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && python -m pytest tests/test_cash_balance.py -v
```

Expected: `404`.

- [ ] **Step 3: Create schemas**

`backend/app/schemas/cash_balance.py`:

```python
from __future__ import annotations
import uuid
from datetime import date, datetime
from pydantic import BaseModel


class CashBalanceCreate(BaseModel):
    asset_id: uuid.UUID
    balance: float
    snapshot_date: date
    notes: str | None = None


class CashBalanceOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    balance: float
    snapshot_date: date
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create service**

`backend/app/services/cash_balance.py`:

```python
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.cash_balance import CashBalance

logger = get_logger(__name__)


async def create_snapshot(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    balance: float,
    snapshot_date: date,
    notes: str | None = None,
) -> CashBalance:
    snap = CashBalance(
        user_id=user_id,
        asset_id=asset_id,
        balance=balance,
        snapshot_date=snapshot_date,
        notes=notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    logger.info("Cash snapshot created: asset=%s balance=%s date=%s", asset_id, balance, snapshot_date)
    return snap


async def get_latest(db: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID) -> CashBalance | None:
    result = await db.execute(
        select(CashBalance)
        .where(CashBalance.asset_id == asset_id, CashBalance.user_id == user_id)
        .order_by(CashBalance.snapshot_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_history(db: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID) -> list[CashBalance]:
    result = await db.execute(
        select(CashBalance)
        .where(CashBalance.asset_id == asset_id, CashBalance.user_id == user_id)
        .order_by(CashBalance.snapshot_date.asc())
    )
    return list(result.scalars().all())
```

- [ ] **Step 5: Create API router**

`backend/app/api/cash_balance.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.cash_balance import CashBalanceCreate, CashBalanceOut
from app.services import cash_balance as cash_service

router = APIRouter(prefix="/cash-balances", tags=["cash-balances"])


@router.post("", response_model=CashBalanceOut, status_code=status.HTTP_201_CREATED)
async def create_balance(
    body: CashBalanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await cash_service.create_snapshot(
        db, current_user.id, body.asset_id, body.balance, body.snapshot_date, body.notes
    )


@router.get("/{asset_id}/latest", response_model=CashBalanceOut)
async def get_latest_balance(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snap = await cash_service.get_latest(db, current_user.id, asset_id)
    if not snap:
        raise HTTPException(status_code=404, detail="No balance snapshot found")
    return snap


@router.get("/{asset_id}/history", response_model=list[CashBalanceOut])
async def get_balance_history(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await cash_service.get_history(db, current_user.id, asset_id)
```

- [ ] **Step 6: Run tests**

```bash
cd backend && python -m pytest tests/test_cash_balance.py -v
```

Expected: all 3 pass.

---

### Task 9: Include cash in overview allocation

**Files:**

- Modify: `backend/app/services/overview.py`

- [ ] **Step 1: Write failing test**

In `backend/tests/test_overview.py`, add:

```python
async def test_allocation_includes_cash(auth_client):
    # Create cash asset with balance
    asset = await auth_client.post("/api/v1/assets", json={
        "symbol": "KBANK_SAVINGS", "asset_type": "cash", "name": "KBANK", "currency": "THB"
    })
    aid = asset.json()["id"]
    await auth_client.post("/api/v1/cash-balances", json={
        "asset_id": aid, "balance": 100000.0, "snapshot_date": "2026-04-01"
    })
    resp = await auth_client.get("/api/v1/overview/allocation")
    assert resp.status_code == 200
    types = [row["asset_type"] for row in resp.json()]
    assert "cash" in types
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && python -m pytest tests/test_overview.py::test_allocation_includes_cash -v
```

Expected: `AssertionError: "cash" not in types`.

- [ ] **Step 3: Update get_allocation in overview service**

In `backend/app/services/overview.py`, add cash balance aggregation to `get_allocation`:

```python
from app.models.cash_balance import CashBalance
from sqlalchemy import func

async def get_allocation(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    # existing holdings logic (unchanged)
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    by_type: dict[str, Decimal] = {}
    for h in holdings:
        latest = await _latest_price(db, h.asset_id)
        if not latest:
            continue
        asset = (await db.execute(
            select(Asset).where(Asset.id == h.asset_id)
        )).scalar_one_or_none()
        if not asset:
            continue
        by_type[asset.asset_type] = by_type.get(asset.asset_type, Decimal("0")) + h.quantity * latest.close

    # Add cash balances — latest snapshot per cash asset
    cash_assets = list((await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.asset_type == "cash")
    )).scalars().all())

    for ca in cash_assets:
        snap_result = await db.execute(
            select(CashBalance)
            .where(CashBalance.asset_id == ca.id, CashBalance.user_id == user_id)
            .order_by(CashBalance.snapshot_date.desc())
            .limit(1)
        )
        snap = snap_result.scalar_one_or_none()
        if snap:
            by_type["cash"] = by_type.get("cash", Decimal("0")) + Decimal(str(snap.balance))

    total = sum(by_type.values()) or Decimal("1")
    logger.info("Allocation: user=%s types=%s", user_id, list(by_type.keys()))
    return [{"asset_type": k, "value": float(v), "pct": float(v / total * 100)} for k, v in by_type.items()]
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_overview.py -v
```

Expected: all pass including new cash test.

---

## Phase 4 — Smart Import Pipeline

### Task 10: File parser and template matching

**Files:**

- Create: `backend/app/services/import_pipeline.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_import_pipeline.py`:

```python
import pytest
import hashlib
import json
from app.services.import_pipeline import (
    detect_file_format,
    extract_structure,
    compute_signature,
    apply_template,
)


def test_detect_csv_format():
    assert detect_file_format("transactions.csv", b"Fund_Code,Date\nK-VIETNAM,2026-01-01") == "csv"


def test_detect_json_format():
    assert detect_file_format("data.json", b'[{"symbol": "AAPL"}]') == "json"


def test_extract_csv_structure():
    content = b"Fund_Code,Trade_Date,Total_Amount\nK-VIETNAM,2026-01-01,500"
    structure = extract_structure("csv", content, json_path=None)
    assert structure["headers"] == ["Fund_Code", "Trade_Date", "Total_Amount"]
    assert len(structure["sample_rows"]) == 1


def test_extract_json_structure():
    data = [{"transactions": [{"symbol": "AAPL", "unit": 1}]}, {"transactions": [{"symbol": "MSFT", "unit": 2}]}]
    content = json.dumps(data).encode()
    structure = extract_structure("json", content, json_path="[].transactions[]")
    assert "symbol" in structure["headers"]


def test_compute_signature_stable():
    headers = ["Fund_Code", "Trade_Date", "Total_Amount"]
    sig1 = compute_signature(headers)
    sig2 = compute_signature(headers)
    assert sig1 == sig2
    assert len(sig1) == 64  # sha256 hex


def test_apply_template_maps_fields():
    rows = [{"share_name": "PTT", "unit": 100, "net_amount": 3455, "trade_date": "2026-01-01", "type": "BUY"}]
    template = {
        "field_map": {"share_name": "symbol", "unit": "units", "net_amount": "total_thb", "trade_date": "date"},
        "asset_type_rules": [],
        "asset_type_fallback": "thai_stock",
        "currency_default": "THB",
    }
    result = apply_template(rows, template)
    assert result[0]["symbol"] == "PTT"
    assert result[0]["units"] == 100
    assert result[0]["asset_type"] == "thai_stock"
    assert result[0]["currency"] == "THB"


def test_apply_template_asset_type_rules():
    rows = [{"symbol": "AAPL", "exchange": "XNAS", "unit": 1, "total_thb": 5000, "date": "2026-01-01", "type": "BUY"}]
    template = {
        "field_map": {},
        "asset_type_rules": [
            {"field": "exchange", "values": ["XNAS", "XNYS"], "asset_type": "us_stock"},
        ],
        "asset_type_fallback": "etf",
        "currency_default": "USD",
    }
    result = apply_template(rows, template)
    assert result[0]["asset_type"] == "us_stock"
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && python -m pytest tests/test_import_pipeline.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement import pipeline service**

`backend/app/services/import_pipeline.py`:

````python
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.import_template import ImportTemplate
from app.models.platform import Platform
from app.services.llm_gateway import LLMGateway

logger = get_logger(__name__)

CANONICAL_FIELDS = {"symbol", "date", "type", "units", "price", "currency", "total_thb", "fee_thb", "asset_type", "notes"}


def detect_file_format(filename: str, content: bytes) -> str:
    if filename.endswith(".csv"):
        return "csv"
    if filename.endswith(".json"):
        return "json"
    try:
        json.loads(content)
        return "json"
    except Exception:
        return "csv"


def _resolve_json_path(data: Any, path: str) -> list[dict]:
    """Resolve a dotted path like '[].transactions[]' into a flat list of dicts."""
    items = data if isinstance(data, list) else [data]
    for part in path.split("."):
        part = part.strip("[]")
        if not part:
            continue
        next_items: list[dict] = []
        for item in items:
            val = item.get(part, [])
            if isinstance(val, list):
                next_items.extend(val)
            elif isinstance(val, dict):
                next_items.append(val)
        items = next_items
    return items


def extract_structure(file_format: str, content: bytes, json_path: str | None) -> dict:
    if file_format == "csv":
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = [dict(r) for r in reader]
        headers = list(rows[0].keys()) if rows else []
        sample_rows = rows[:3]
    else:
        data = json.loads(content)
        if json_path:
            rows = _resolve_json_path(data, json_path)
        else:
            rows = data if isinstance(data, list) else [data]
        headers = list(rows[0].keys()) if rows else []
        sample_rows = rows[:3]
    return {"headers": headers, "sample_rows": sample_rows, "total_rows": len(rows), "all_rows": rows}


def compute_signature(headers: list[str]) -> str:
    return hashlib.sha256(",".join(sorted(headers)).encode()).hexdigest()


def _classify_row_asset_type(row: dict, rules: list[dict], fallback: str) -> str:
    for rule in rules:
        field = rule.get("field", "")
        value = str(row.get(field, ""))
        if "values" in rule:
            if value in rule["values"]:
                return rule["asset_type"]
        elif "pattern" in rule:
            if re.match(rule["pattern"], value, re.IGNORECASE):
                return rule["asset_type"]
    return fallback


def apply_template(rows: list[dict], template: dict) -> list[dict]:
    field_map: dict[str, str] = template.get("field_map", {})
    rules: list[dict] = template.get("asset_type_rules", [])
    fallback: str = template.get("asset_type_fallback", "us_stock")
    currency_default: str = template.get("currency_default", "THB")

    result = []
    for raw in rows:
        normalized: dict[str, Any] = {}
        # Copy canonical fields that are already present
        for k, v in raw.items():
            if k in CANONICAL_FIELDS:
                normalized[k] = v
        # Apply field_map
        for src, dst in field_map.items():
            if src in raw:
                normalized[dst] = raw[src]
        # Defaults
        normalized.setdefault("currency", currency_default)
        normalized.setdefault("fee_thb", 0.0)
        normalized.setdefault("notes", None)
        # Asset type from rules
        normalized["asset_type"] = _classify_row_asset_type(raw, rules, fallback)
        result.append(normalized)
    return result


async def get_template(db: AsyncSession, user_id: uuid.UUID, platform_id: uuid.UUID) -> ImportTemplate | None:
    result = await db.execute(
        select(ImportTemplate).where(
            ImportTemplate.platform_id == platform_id,
            ImportTemplate.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def save_template(
    db: AsyncSession,
    user_id: uuid.UUID,
    platform_id: uuid.UUID,
    template_data: dict,
    file_format: str,
    json_path: str | None,
    signature: str,
) -> ImportTemplate:
    now = datetime.now(timezone.utc)
    existing = await get_template(db, user_id, platform_id)
    if existing:
        existing.field_map = template_data.get("field_map", {})
        existing.asset_type_rules = template_data.get("asset_type_rules", [])
        existing.asset_type_fallback = template_data.get("asset_type_fallback", "us_stock")
        existing.currency_default = template_data.get("currency_default", "THB")
        existing.json_path = template_data.get("json_path", json_path)
        existing.column_signature = signature
        existing.file_format = file_format
        existing.updated_at = now
        await db.commit()
        await db.refresh(existing)
        return existing
    tmpl = ImportTemplate(
        platform_id=platform_id,
        user_id=user_id,
        file_format=file_format,
        json_path=json_path,
        column_signature=signature,
        field_map=template_data.get("field_map", {}),
        asset_type_rules=template_data.get("asset_type_rules", []),
        asset_type_fallback=template_data.get("asset_type_fallback", "us_stock"),
        currency_default=template_data.get("currency_default", "THB"),
        created_at=now,
        updated_at=now,
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    logger.info("ImportTemplate saved: platform=%s user=%s", platform_id, user_id)
    return tmpl


async def generate_template_via_llm(
    db: AsyncSession,
    user_id: uuid.UUID,
    file_format: str,
    structure: dict,
) -> dict:
    gateway = LLMGateway(db)
    raw = await gateway.complete(
        "import_template_generator",
        user_id,
        {
            "file_format": file_format,
            "headers": json.dumps(structure["headers"]),
            "sample_rows": json.dumps(structure["sample_rows"], ensure_ascii=False, indent=2),
        },
    )
    # LLM returns JSON — parse it
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)
````

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_import_pipeline.py -v
```

Expected: all 7 pass.

---

### Task 11: Import Pipeline API

**Files:**

- Create: `backend/app/schemas/import_template.py`
- Create: `backend/app/api/import_pipeline.py`

- [ ] **Step 1: Write failing test**

`backend/tests/test_import_api.py`:

```python
import pytest
import json


async def test_upload_known_template(auth_client, db):
    # Create platform
    platform = await auth_client.post("/api/v1/platforms", json={"name": "Finnomena", "asset_types_supported": ["th_fund"]})
    pid = platform.json()["id"]

    # First upload — no template, should return needs_llm=True if no LLM configured
    csv_content = b"Template,Fund_Code,Trade_Date,Total_Amount,Number_of_Units,Filename\nManual,K-VIETNAM,2026-01-01,500,-,"
    resp = await auth_client.post(
        "/api/v1/import/analyze",
        data={"platform_id": pid},
        files={"file": ("transactions.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "signature" in data
    assert "structure" in data
    assert data["template_status"] in ("match", "mismatch", "new")
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && python -m pytest tests/test_import_api.py -v
```

Expected: `404`.

- [ ] **Step 3: Create schemas**

`backend/app/schemas/import_template.py`:

```python
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ImportTemplateOut(BaseModel):
    id: uuid.UUID
    platform_id: uuid.UUID
    file_format: str
    json_path: str | None
    column_signature: str
    field_map: dict
    asset_type_rules: list
    asset_type_fallback: str
    currency_default: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnalyzeResponse(BaseModel):
    signature: str
    structure: dict
    template_status: str  # "match" | "mismatch" | "new"
    template: ImportTemplateOut | None
    preview_rows: list[dict] | None  # populated if template matches


class TemplateSaveRequest(BaseModel):
    platform_id: uuid.UUID
    file_format: str
    json_path: str | None = None
    signature: str
    template_data: dict


class ConfirmImportRequest(BaseModel):
    platform_id: uuid.UUID
    rows: list[dict]  # normalized canonical rows after user review
```

- [ ] **Step 4: Create import API**

`backend/app/api/import_pipeline.py`:

```python
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.import_template import AnalyzeResponse, ConfirmImportRequest, ImportTemplateOut, TemplateSaveRequest
from app.services import import_pipeline as pipeline_svc
from app.services.asset import get_or_create_asset
from app.services.csv_import import upsert_transaction  # reuse existing transaction writer

logger = get_logger(__name__)
router = APIRouter(prefix="/import", tags=["import"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_file(
    platform_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    file_format = pipeline_svc.detect_file_format(file.filename or "", content)

    existing_template = await pipeline_svc.get_template(db, current_user.id, platform_id)
    json_path = existing_template.json_path if existing_template else None
    structure = pipeline_svc.extract_structure(file_format, content, json_path)
    signature = pipeline_svc.compute_signature(structure["headers"])

    if not existing_template:
        status = "new"
        preview = None
    elif existing_template.column_signature != signature:
        status = "mismatch"
        preview = None
    else:
        status = "match"
        tmpl_dict = {
            "field_map": existing_template.field_map,
            "asset_type_rules": existing_template.asset_type_rules,
            "asset_type_fallback": existing_template.asset_type_fallback,
            "currency_default": existing_template.currency_default,
        }
        preview = pipeline_svc.apply_template(structure["all_rows"], tmpl_dict)

    logger.info("Import analyze: platform=%s format=%s status=%s user=%s", platform_id, file_format, status, current_user.id)
    return AnalyzeResponse(
        signature=signature,
        structure={"headers": structure["headers"], "sample_rows": structure["sample_rows"], "total_rows": structure["total_rows"]},
        template_status=status,
        template=ImportTemplateOut.model_validate(existing_template) if existing_template else None,
        preview_rows=preview,
    )


@router.post("/generate-template")
async def generate_template(
    platform_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    file_format = pipeline_svc.detect_file_format(file.filename or "", content)
    existing = await pipeline_svc.get_template(db, current_user.id, platform_id)
    json_path = existing.json_path if existing else None
    structure = pipeline_svc.extract_structure(file_format, content, json_path)

    try:
        template_data = await pipeline_svc.generate_template_via_llm(db, current_user.id, file_format, structure)
    except ValueError as exc:
        raise HTTPException(status_code=424, detail=str(exc))

    signature = pipeline_svc.compute_signature(structure["headers"])
    tmpl = await pipeline_svc.save_template(
        db, current_user.id, platform_id, template_data, file_format, template_data.get("json_path", json_path), signature
    )
    preview = pipeline_svc.apply_template(structure["all_rows"], template_data)
    return {"template": ImportTemplateOut.model_validate(tmpl), "preview_rows": preview}


@router.post("/save-template", response_model=ImportTemplateOut)
async def save_template_manual(
    body: TemplateSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = await pipeline_svc.save_template(
        db, current_user.id, body.platform_id, body.template_data,
        body.file_format, body.json_path, body.signature,
    )
    return ImportTemplateOut.model_validate(tmpl)


@router.post("/confirm")
async def confirm_import(
    body: ConfirmImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    imported = 0
    errors = []
    for row in body.rows:
        try:
            asset = await get_or_create_asset(
                db, current_user.id,
                row["symbol"], row["asset_type"], row.get("name", row["symbol"]), row.get("currency", "THB"),
            )
            await upsert_transaction(db, current_user.id, asset.id, row)
            imported += 1
        except Exception as exc:
            errors.append({"row": row, "error": str(exc)})
    logger.info("Import confirm: imported=%d errors=%d user=%s", imported, len(errors), current_user.id)
    return {"imported": imported, "errors": errors}
```

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest tests/test_import_api.py -v
```

Expected: all pass.

---

## Phase 5 — Frontend

### Task 12: Frontend API service clients

**Files:**

- Create: `frontend/lib/services/provider-config.ts`
- Create: `frontend/lib/services/feature-llm-config.ts`
- Create: `frontend/lib/services/cash-balance.ts`
- Create: `frontend/lib/services/import-pipeline.ts`

- [ ] **Step 1: Create provider config service**

`frontend/lib/services/provider-config.ts`:

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL;

export interface ProviderConfig {
  id: string;
  provider: string;
  host_url: string | null;
  is_connected: boolean;
  models_cache: string[];
  models_fetched_at: string | null;
  created_at: string;
}

export type Provider =
  | "anthropic"
  | "openai"
  | "gemini"
  | "ollama"
  | "openrouter";

export async function listProviderConfigs(
  token: string,
): Promise<ProviderConfig[]> {
  const r = await fetch(`${BASE}/api/v1/provider-configs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("Failed to fetch provider configs");
  return r.json();
}

export async function createProviderConfig(
  token: string,
  provider: Provider,
  api_key?: string,
  host_url?: string,
): Promise<ProviderConfig> {
  const r = await fetch(`${BASE}/api/v1/provider-configs`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ provider, api_key, host_url }),
  });
  if (!r.ok) throw new Error("Failed to create provider config");
  return r.json();
}

export async function testConnection(
  token: string,
  id: string,
): Promise<ProviderConfig> {
  const r = await fetch(
    `${BASE}/api/v1/provider-configs/${id}/test-connection`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!r.ok) throw new Error("Connection test failed");
  return r.json();
}

export async function fetchModels(
  token: string,
  id: string,
): Promise<ProviderConfig> {
  const r = await fetch(`${BASE}/api/v1/provider-configs/${id}/fetch-models`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("Failed to fetch models");
  return r.json();
}

export async function deleteProviderConfig(
  token: string,
  id: string,
): Promise<void> {
  const r = await fetch(`${BASE}/api/v1/provider-configs/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("Failed to delete");
}
```

- [ ] **Step 2: Create feature LLM config service**

`frontend/lib/services/feature-llm-config.ts`:

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL;

export interface FeatureLLMConfig {
  id: string;
  feature_key: string;
  provider_config_id: string;
  model: string;
  system_prompt: string;
  is_prompt_customized: boolean;
  updated_at: string;
}

export const FEATURE_LABELS: Record<string, string> = {
  import_template_generator: "Import Template Generator",
  transaction_classifier: "Transaction Classifier",
  portfolio_analysis: "Portfolio Analysis",
  chat: "Chat Assistant",
};

export async function listFeatureConfigs(
  token: string,
): Promise<FeatureLLMConfig[]> {
  const r = await fetch(`${BASE}/api/v1/feature-llm-configs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("Failed to fetch feature configs");
  return r.json();
}

export async function createFeatureConfig(
  token: string,
  feature_key: string,
  provider_config_id: string,
  model: string,
  system_prompt?: string,
): Promise<FeatureLLMConfig> {
  const r = await fetch(`${BASE}/api/v1/feature-llm-configs`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      feature_key,
      provider_config_id,
      model,
      system_prompt,
    }),
  });
  if (!r.ok) throw new Error("Failed to create feature config");
  return r.json();
}

export async function updateFeatureConfig(
  token: string,
  id: string,
  patch: {
    provider_config_id?: string;
    model?: string;
    system_prompt?: string;
  },
): Promise<FeatureLLMConfig> {
  const r = await fetch(`${BASE}/api/v1/feature-llm-configs/${id}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error("Failed to update feature config");
  return r.json();
}

export async function resetPrompt(
  token: string,
  id: string,
): Promise<FeatureLLMConfig> {
  const r = await fetch(
    `${BASE}/api/v1/feature-llm-configs/${id}/reset-prompt`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!r.ok) throw new Error("Failed to reset prompt");
  return r.json();
}
```

- [ ] **Step 3: Create cash balance service**

`frontend/lib/services/cash-balance.ts`:

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL;

export interface CashBalance {
  id: string;
  asset_id: string;
  balance: number;
  snapshot_date: string;
  notes: string | null;
  created_at: string;
}

export async function createBalance(
  token: string,
  asset_id: string,
  balance: number,
  snapshot_date: string,
  notes?: string,
): Promise<CashBalance> {
  const r = await fetch(`${BASE}/api/v1/cash-balances`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ asset_id, balance, snapshot_date, notes }),
  });
  if (!r.ok) throw new Error("Failed to create balance");
  return r.json();
}

export async function getLatestBalance(
  token: string,
  asset_id: string,
): Promise<CashBalance> {
  const r = await fetch(`${BASE}/api/v1/cash-balances/${asset_id}/latest`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("No balance found");
  return r.json();
}

export async function getBalanceHistory(
  token: string,
  asset_id: string,
): Promise<CashBalance[]> {
  const r = await fetch(`${BASE}/api/v1/cash-balances/${asset_id}/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("Failed to fetch history");
  return r.json();
}
```

- [ ] **Step 4: Create import pipeline service**

`frontend/lib/services/import-pipeline.ts`:

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL;

export interface AnalyzeResponse {
  signature: string;
  structure: {
    headers: string[];
    sample_rows: Record<string, unknown>[];
    total_rows: number;
  };
  template_status: "match" | "mismatch" | "new";
  template: ImportTemplate | null;
  preview_rows: Record<string, unknown>[] | null;
}

export interface ImportTemplate {
  id: string;
  platform_id: string;
  file_format: string;
  json_path: string | null;
  column_signature: string;
  field_map: Record<string, string>;
  asset_type_rules: unknown[];
  asset_type_fallback: string;
  currency_default: string;
  updated_at: string;
}

export async function analyzeFile(
  token: string,
  platform_id: string,
  file: File,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("platform_id", platform_id);
  form.append("file", file);
  const r = await fetch(`${BASE}/api/v1/import/analyze`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!r.ok) throw new Error("Failed to analyze file");
  return r.json();
}

export async function generateTemplate(
  token: string,
  platform_id: string,
  file: File,
): Promise<{
  template: ImportTemplate;
  preview_rows: Record<string, unknown>[];
}> {
  const form = new FormData();
  form.append("platform_id", platform_id);
  form.append("file", file);
  const r = await fetch(`${BASE}/api/v1/import/generate-template`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!r.ok) throw new Error("Failed to generate template");
  return r.json();
}

export async function confirmImport(
  token: string,
  platform_id: string,
  rows: Record<string, unknown>[],
): Promise<{ imported: number; errors: unknown[] }> {
  const r = await fetch(`${BASE}/api/v1/import/confirm`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ platform_id, rows }),
  });
  if (!r.ok) throw new Error("Failed to confirm import");
  return r.json();
}
```

---

### Task 13: AI Settings page

**Files:**

- Create: `frontend/app/(auth)/settings/ai/page.tsx`

- [ ] **Step 1: Create AI settings page**

`frontend/app/(auth)/settings/ai/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import {
  listProviderConfigs,
  createProviderConfig,
  testConnection,
  fetchModels,
  deleteProviderConfig,
  ProviderConfig,
  Provider,
} from "@/lib/services/provider-config";
import {
  listFeatureConfigs,
  createFeatureConfig,
  updateFeatureConfig,
  resetPrompt,
  FeatureLLMConfig,
  FEATURE_LABELS,
} from "@/lib/services/feature-llm-config";

const PROVIDERS: Provider[] = [
  "anthropic",
  "openai",
  "gemini",
  "ollama",
  "openrouter",
];
const FEATURE_KEYS = [
  "import_template_generator",
  "transaction_classifier",
  "portfolio_analysis",
  "chat",
];

export default function AISettingsPage() {
  const { token } = useAuth();
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [features, setFeatures] = useState<FeatureLLMConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [addProvider, setAddProvider] = useState<Provider | "">("");
  const [apiKey, setApiKey] = useState("");
  const [hostUrl, setHostUrl] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    if (!token) return;
    Promise.all([listProviderConfigs(token), listFeatureConfigs(token)])
      .then(([p, f]) => {
        setProviders(p);
        setFeatures(f);
      })
      .finally(() => setLoading(false));
  }, [token]);

  async function handleAddProvider() {
    if (!token || !addProvider) return;
    const cfg = await createProviderConfig(
      token,
      addProvider,
      apiKey || undefined,
      hostUrl || undefined,
    );
    setProviders((p) => [...p, cfg]);
    setAddProvider("");
    setApiKey("");
    setHostUrl("");
  }

  async function handleTest(id: string) {
    if (!token) return;
    setStatus("Testing...");
    const cfg = await testConnection(token, id);
    setProviders((p) => p.map((x) => (x.id === id ? cfg : x)));
    setStatus(cfg.is_connected ? "Connected!" : "Connection failed");
  }

  async function handleFetchModels(id: string) {
    if (!token) return;
    setStatus("Fetching models...");
    const cfg = await fetchModels(token, id);
    setProviders((p) => p.map((x) => (x.id === id ? cfg : x)));
    setStatus(`Fetched ${cfg.models_cache.length} models`);
  }

  async function handleDelete(id: string) {
    if (!token) return;
    await deleteProviderConfig(token, id);
    setProviders((p) => p.filter((x) => x.id !== id));
  }

  async function handleResetPrompt(id: string) {
    if (!token) return;
    const cfg = await resetPrompt(token, id);
    setFeatures((f) => f.map((x) => (x.id === id ? cfg : x)));
  }

  async function handleFeatureUpdate(
    id: string,
    patch: Partial<FeatureLLMConfig>,
  ) {
    if (!token) return;
    const cfg = await updateFeatureConfig(token, id, patch);
    setFeatures((f) => f.map((x) => (x.id === id ? cfg : x)));
  }

  if (loading) return <div className="p-6">Loading...</div>;

  return (
    <div className="p-6 max-w-3xl space-y-10">
      <h1 className="text-2xl font-semibold">AI & LLM Settings</h1>

      {/* Providers */}
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Providers</h2>
        {status && <p className="text-sm text-muted-foreground">{status}</p>}
        <div className="space-y-3">
          {providers.map((p) => (
            <div key={p.id} className="border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium capitalize">{p.provider}</span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${p.is_connected ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}
                >
                  {p.is_connected ? "Connected" : "Not connected"}
                </span>
              </div>
              {p.host_url && (
                <p className="text-xs text-muted-foreground">{p.host_url}</p>
              )}
              {p.models_fetched_at && (
                <p className="text-xs text-muted-foreground">
                  {p.models_cache.length} models cached
                </p>
              )}
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={() => handleTest(p.id)}
                  className="text-xs px-3 py-1 border rounded hover:bg-muted"
                >
                  Test Connection
                </button>
                <button
                  onClick={() => handleFetchModels(p.id)}
                  className="text-xs px-3 py-1 border rounded hover:bg-muted"
                >
                  Refresh Models
                </button>
                <button
                  onClick={() => handleDelete(p.id)}
                  className="text-xs px-3 py-1 border rounded text-red-600 hover:bg-red-50"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Add provider */}
        <div className="border rounded-lg p-4 space-y-3">
          <p className="text-sm font-medium">Add Provider</p>
          <div className="flex gap-2 flex-wrap">
            <select
              value={addProvider}
              onChange={(e) => setAddProvider(e.target.value as Provider)}
              className="border rounded px-2 py-1 text-sm"
            >
              <option value="">Select provider</option>
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            {addProvider && addProvider !== "ollama" && (
              <input
                type="password"
                placeholder="API Key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="border rounded px-2 py-1 text-sm flex-1"
              />
            )}
            {addProvider === "ollama" && (
              <input
                type="text"
                placeholder="Host URL (e.g. http://localhost:11434)"
                value={hostUrl}
                onChange={(e) => setHostUrl(e.target.value)}
                className="border rounded px-2 py-1 text-sm flex-1"
              />
            )}
            <button
              onClick={handleAddProvider}
              disabled={!addProvider}
              className="px-3 py-1 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </div>
      </section>

      {/* Feature prompts */}
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Feature Configuration</h2>
        {features.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No features configured yet. Add a provider above, then configure
            each feature below.
          </p>
        )}
        {FEATURE_KEYS.map((key) => {
          const cfg = features.find((f) => f.feature_key === key);
          return (
            <div key={key} className="border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="font-medium">{FEATURE_LABELS[key]}</p>
                {cfg?.is_prompt_customized && (
                  <span className="text-xs bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded-full">
                    Custom prompt
                  </span>
                )}
              </div>
              {cfg ? (
                <>
                  <div className="flex gap-2">
                    <select
                      value={cfg.provider_config_id}
                      onChange={(e) =>
                        handleFeatureUpdate(cfg.id, {
                          provider_config_id: e.target.value,
                        })
                      }
                      className="border rounded px-2 py-1 text-sm"
                    >
                      {providers.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.provider}
                        </option>
                      ))}
                    </select>
                    <select
                      value={cfg.model}
                      onChange={(e) =>
                        handleFeatureUpdate(cfg.id, { model: e.target.value })
                      }
                      className="border rounded px-2 py-1 text-sm flex-1"
                    >
                      {(
                        providers.find((p) => p.id === cfg.provider_config_id)
                          ?.models_cache ?? []
                      ).map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>
                  <textarea
                    value={cfg.system_prompt}
                    onChange={(e) =>
                      handleFeatureUpdate(cfg.id, {
                        system_prompt: e.target.value,
                      })
                    }
                    rows={5}
                    className="w-full border rounded px-3 py-2 text-sm font-mono resize-y"
                  />
                  <button
                    onClick={() => handleResetPrompt(cfg.id)}
                    className="text-xs text-muted-foreground hover:underline"
                  >
                    Reset to default
                  </button>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Not configured.{" "}
                  {providers.length === 0 ? "Add a provider first." : ""}
                </p>
              )}
            </div>
          );
        })}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Add AI link to settings navigation**

In `frontend/app/(auth)/settings/page.tsx` (or the settings layout), add:

```tsx
<Link href="/settings/ai">AI & LLM</Link>
```

- [ ] **Step 3: Verify page renders**

Start dev server and navigate to `/settings/ai`. Confirm providers section and feature prompts section render without errors.

---

### Task 14: Import Wizard page

**Files:**

- Create: `frontend/app/(auth)/import/page.tsx`

- [ ] **Step 1: Create import page**

`frontend/app/(auth)/import/page.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { listPlatforms } from "@/lib/services/platforms";
import {
  analyzeFile,
  generateTemplate,
  confirmImport,
  AnalyzeResponse,
} from "@/lib/services/import-pipeline";

type Step = "upload" | "analyze" | "review" | "done";

export default function ImportPage() {
  const { token } = useAuth();
  const [platforms, setPlatforms] = useState<{ id: string; name: string }[]>(
    [],
  );
  const [platformId, setPlatformId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [step, setStep] = useState<Step>("upload");
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    imported: number;
    errors: unknown[];
  } | null>(null);

  useEffect(() => {
    if (!token) return;
    listPlatforms(token).then(setPlatforms);
  }, [token]);

  async function handleAnalyze() {
    if (!token || !file || !platformId) return;
    setLoading(true);
    setError("");
    try {
      const res = await analyzeFile(token, platformId, file);
      setAnalysis(res);
      if (res.template_status === "match" && res.preview_rows) {
        setPreviewRows(res.preview_rows);
        setStep("review");
      } else {
        setStep("analyze");
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateTemplate() {
    if (!token || !file || !platformId) return;
    setLoading(true);
    setError("");
    try {
      const res = await generateTemplate(token, platformId, file);
      setPreviewRows(res.preview_rows);
      setStep("review");
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    if (!token || !platformId) return;
    setLoading(true);
    setError("");
    try {
      const res = await confirmImport(token, platformId, previewRows);
      setResult(res);
      setStep("done");
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">Import Transactions</h1>

      {/* Step 1: Upload */}
      <div className="border rounded-lg p-5 space-y-4">
        <h2 className="font-medium">1. Select Platform & File</h2>
        <div className="flex gap-3 flex-wrap">
          <select
            value={platformId}
            onChange={(e) => setPlatformId(e.target.value)}
            className="border rounded px-3 py-2 text-sm"
          >
            <option value="">Select platform</option>
            {platforms.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <input
            type="file"
            accept=".csv,.json"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
          <button
            onClick={handleAnalyze}
            disabled={!file || !platformId || loading}
            className="px-4 py-2 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50"
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      {/* Step 2: Analyze result */}
      {step === "analyze" && analysis && (
        <div className="border rounded-lg p-5 space-y-4">
          <h2 className="font-medium">2. Template Status</h2>
          {analysis.template_status === "new" && (
            <div className="space-y-3">
              <p className="text-sm">
                No template found for this platform. Generate one using AI.
              </p>
              <p className="text-sm text-muted-foreground">
                Detected {analysis.structure.total_rows} rows. Headers:{" "}
                {analysis.structure.headers.join(", ")}
              </p>
              <button
                onClick={handleGenerateTemplate}
                disabled={loading}
                className="px-4 py-2 bg-primary text-primary-foreground rounded text-sm disabled:opacity-50"
              >
                {loading ? "Generating..." : "Generate Template with AI"}
              </button>
            </div>
          )}
          {analysis.template_status === "mismatch" && (
            <div className="space-y-3">
              <p className="text-sm text-yellow-700 bg-yellow-50 rounded p-3">
                File format has changed since last import. Re-generate template?
              </p>
              <button
                onClick={handleGenerateTemplate}
                disabled={loading}
                className="px-4 py-2 bg-yellow-600 text-white rounded text-sm disabled:opacity-50"
              >
                {loading ? "Re-generating..." : "Re-generate Template"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Step 3: Review */}
      {step === "review" && previewRows.length > 0 && (
        <div className="border rounded-lg p-5 space-y-4">
          <h2 className="font-medium">
            3. Review & Confirm ({previewRows.length} rows)
          </h2>
          <div className="overflow-x-auto">
            <table className="text-xs border-collapse w-full">
              <thead>
                <tr className="bg-muted">
                  {Object.keys(previewRows[0]).map((k) => (
                    <th key={k} className="border px-2 py-1 text-left">
                      {k}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewRows.slice(0, 20).map((row, i) => (
                  <tr key={i} className="hover:bg-muted/50">
                    {Object.values(row).map((v, j) => (
                      <td key={j} className="border px-2 py-1">
                        {String(v ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {previewRows.length > 20 && (
            <p className="text-xs text-muted-foreground">
              Showing first 20 of {previewRows.length} rows
            </p>
          )}
          <button
            onClick={handleConfirm}
            disabled={loading}
            className="px-4 py-2 bg-green-600 text-white rounded text-sm disabled:opacity-50"
          >
            {loading ? "Importing..." : "Confirm Import"}
          </button>
        </div>
      )}

      {/* Step 4: Done */}
      {step === "done" && result && (
        <div className="border rounded-lg p-5 space-y-2">
          <h2 className="font-medium text-green-700">Import Complete</h2>
          <p className="text-sm">
            Successfully imported {result.imported} transactions.
          </p>
          {(result.errors as unknown[]).length > 0 && (
            <p className="text-sm text-red-600">
              {(result.errors as unknown[]).length} rows failed.
            </p>
          )}
          <button
            onClick={() => {
              setStep("upload");
              setFile(null);
              setAnalysis(null);
              setPreviewRows([]);
              setResult(null);
            }}
            className="text-sm text-primary underline"
          >
            Import another file
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify page renders end-to-end**

Start dev server, go to `/import`. Select a platform, upload one of the example files in `data/example/`. Verify analyze step works, template generation triggers, preview table shows correctly, confirm import succeeds.

---

## Self-Review

**Spec coverage check:**

| Requirement                               | Task                                                                                     |
| ----------------------------------------- | ---------------------------------------------------------------------------------------- |
| Cash accounts (balance snapshots)         | Tasks 2, 8, 9                                                                            |
| `etf` asset type                          | Task 1                                                                                   |
| `cash` asset type                         | Tasks 1, 8                                                                               |
| Overview cash row + drilldown             | Task 9 (backend); note: frontend drilldown UI can be added to overview page as follow-up |
| Currency conversion hint toggle           | Not yet implemented — add to Task 9 follow-up                                            |
| Asset type auto-detection (per-row rules) | Tasks 10, 11 (apply_template + asset_type_rules)                                         |
| LLM provider config with API key          | Tasks 5, 6                                                                               |
| Test connection per provider              | Task 6                                                                                   |
| Fetch models per provider                 | Tasks 5, 6                                                                               |
| FeatureLLMConfig per-feature              | Task 7                                                                                   |
| System prompt editable + reset            | Task 7                                                                                   |
| LLM Gateway abstraction                   | Task 5                                                                                   |
| Column signature change detection         | Tasks 10, 11                                                                             |
| LLM never sees full file (3 rows)         | Task 10 (extract_structure returns sample_rows[:3])                                      |
| Import template saved and reused          | Tasks 10, 11                                                                             |
| Preview table before confirm              | Task 14                                                                                  |

**Two gaps identified — add as follow-up tasks:**

1. **Currency conversion hint toggle** — Settings toggle + overview display (`≈ 31,000 THB`)
2. **Cash drilldown in overview frontend** — Expandable cash row showing per-account breakdown

Both can be implemented after this plan as small follow-up tasks.

**No placeholders found.** All steps contain complete code.

**Type consistency verified** — `apply_template`, `extract_structure`, `compute_signature`, `get_template`, `save_template` used consistently across Tasks 10, 11, 14.
