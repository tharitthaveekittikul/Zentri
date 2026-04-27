# Phase 6 — AI/LLM Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a full AI analysis stack — LLM provider abstraction, RAG pipeline over uploaded PDFs, BUY/SELL/HOLD verdict engine, and supporting frontend pages.

**Architecture:** Sequential/Layered — each layer (encryption → LLM abstraction → ChromaDB/RAG → document pipeline → analysis engine → API → frontend) is complete before the next builds on it. New Docker service `chromadb` stores embeddings. Four new DB tables (`llm_settings`, `documents`, `ai_analyses`, `llm_conversations`) are created in a single Alembic migration.

**Tech Stack:** Python `cryptography` (AES-256-GCM), `anthropic`/`openai`/`google-generativeai` SDKs, `chromadb`, `sentence-transformers`, `pymupdf`, ARQ worker, Next.js 15 App Router, shadcn/ui, recharts.

---

## File Map

**New backend files:**

- `backend/app/core/encryption.py` — AES-256-GCM encrypt/decrypt
- `backend/app/models/llm_settings.py` — LLMSettings ORM model
- `backend/app/models/document.py` — Document ORM model
- `backend/app/models/ai_analysis.py` — AIAnalysis ORM model
- `backend/app/models/llm_conversation.py` — LLMConversation ORM model
- `backend/alembic/versions/004_phase6_ai_schema.py` — all 4 new tables + enum additions
- `backend/app/services/llm_service.py` — LLMProvider abstraction + 4 providers
- `backend/app/services/rag_service.py` — ChromaDB collection + chunk operations
- `backend/app/api/documents.py` — upload / list / delete / reingest endpoints
- `backend/app/api/analysis.py` — trigger / latest / history / conversation endpoints
- `backend/worker/jobs/ingest_document.py` — PDF → chunk → embed ARQ job
- `backend/worker/jobs/run_analysis.py` — RAG + LLM → verdict ARQ job
- `backend/tests/test_encryption.py`
- `backend/tests/test_llm_settings.py`
- `backend/tests/test_llm_service.py`
- `backend/tests/test_rag_service.py`
- `backend/tests/test_documents.py`
- `backend/tests/test_analysis.py`

**Modified backend files:**

- `backend/app/core/config.py` — add `CHROMA_HOST`, `CHROMA_PORT`, `OLLAMA_HOST`
- `backend/app/models/pipeline_log.py` — extend `JOB_TYPES` with new job types
- `backend/app/api/settings.py` — add LLM settings endpoints
- `backend/app/main.py` — register `documents` and `analysis` routers
- `backend/worker/main.py` — register `job_ingest_document` and `job_run_analysis`

**New frontend files:**

- `frontend/components/analysis/VerdictCard.tsx`
- `frontend/app/(auth)/documents/page.tsx`
- `frontend/app/(auth)/ai-usage/page.tsx`

**Modified frontend files:**

- `frontend/app/(auth)/portfolio/[symbol]/page.tsx` — embed VerdictCard

---

## Task 1: Encryption utility + Config additions

**Files:**

- Create: `backend/app/core/encryption.py`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_encryption.py`

- [x] **Step 1: Install cryptography package**

```bash
cd backend && uv pip install cryptography
```

- [x] **Step 2: Write failing test**

Create `backend/tests/test_encryption.py`:

```python
import pytest
from app.core.encryption import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    plaintext = "sk-ant-api03-secret-key-12345"
    token = encrypt(plaintext)
    assert token != plaintext
    assert decrypt(token) == plaintext


def test_different_plaintexts_produce_different_ciphertexts():
    a = encrypt("key-a")
    b = encrypt("key-b")
    assert a != b


def test_same_plaintext_produces_different_ciphertexts():
    # nonce is random — same input should not produce same output
    a = encrypt("same-key")
    b = encrypt("same-key")
    assert a != b
    assert decrypt(a) == decrypt(b) == "same-key"
```

- [x] **Step 3: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_encryption.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` on `app.core.encryption`.

- [x] **Step 4: Write implementation**

Create `backend/app/core/encryption.py`:

```python
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _get_key() -> bytes:
    return hashlib.sha256(settings.JWT_SECRET.encode()).digest()


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    aesgcm = AESGCM(_get_key())
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt(token: str) -> str:
    data = base64.b64decode(token.encode())
    nonce, ciphertext = data[:12], data[12:]
    aesgcm = AESGCM(_get_key())
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
```

- [x] **Step 5: Add config fields**

Edit `backend/app/core/config.py` — add three new fields to `Settings`:

```python
CHROMA_HOST: str = "localhost"
CHROMA_PORT: int = 8000
OLLAMA_HOST: str = "http://host.docker.internal:11434"
```

- [x] **Step 6: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_encryption.py -v
```

Expected: 3 tests PASS.

---

## Task 2: DB models + Alembic migration 004

**Files:**

- Create: `backend/app/models/llm_settings.py`
- Create: `backend/app/models/document.py`
- Create: `backend/app/models/ai_analysis.py`
- Create: `backend/app/models/llm_conversation.py`
- Modify: `backend/app/models/pipeline_log.py`
- Create: `backend/alembic/versions/004_phase6_ai_schema.py`

- [x] **Step 1: Create LLMSettings model**

Create `backend/app/models/llm_settings.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMSettings(Base):
    __tablename__ = "llm_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [x] **Step 2: Create Document model**

Create `backend/app/models/document.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(nullable=False)
    file_path: Mapped[str] = mapped_column(nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="pending")
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chroma_collection_id: Mapped[str | None] = mapped_column(nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [x] **Step 3: Create AIAnalysis model**

Create `backend/app/models/ai_analysis.py`:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[str | None] = mapped_column(nullable=True)
    verdict: Mapped[str] = mapped_column(nullable=False)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [x] **Step 4: Create LLMConversation model**

Create `backend/app/models/llm_conversation.py`:

```python
import uuid

from sqlalchemy import Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMConversation(Base):
    __tablename__ = "llm_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_order: Mapped[int] = mapped_column(Integer, nullable=False)
```

- [x] **Step 5: Extend JOB_TYPES in pipeline_log.py**

Edit `backend/app/models/pipeline_log.py` — update the `JOB_TYPES` tuple:

```python
JOB_TYPES = (
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "ingest_document", "run_analysis",
)
```

- [x] **Step 6: Write Alembic migration 004**

Create `backend/alembic/versions/004_phase6_ai_schema.py`:

```python
"""phase 6 AI/LLM analysis schema

Revision ID: 004
Revises: 003
Create Date: 2026-04-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend existing job_type_enum
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'ingest_document'")
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'run_analysis'")

    op.create_table(
        "llm_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=True),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("file_path", sa.String, nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("chroma_collection_id", sa.String, nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "ai_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("verdict", sa.String, nullable=False),
        sa.Column("target_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("tokens_in", sa.Integer, default=0),
        sa.Column("tokens_out", sa.Integer, default=0),
        sa.Column("cost_usd", sa.Numeric(10, 6), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "llm_conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_id", UUID(as_uuid=True), sa.ForeignKey("ai_analyses.id"), nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("message_order", sa.Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_conversations")
    op.drop_table("ai_analyses")
    op.drop_table("documents")
    op.drop_table("llm_settings")
```

- [x] **Step 7: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade 003 -> 004, phase 6 AI/LLM analysis schema`

---

## Task 3: LLM settings API endpoints

**Files:**

- Modify: `backend/app/api/settings.py`
- Create: `backend/tests/test_llm_settings.py`

- [x] **Step 1: Write failing tests**

Create `backend/tests/test_llm_settings.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_llm_settings_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/settings/llm")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_upsert_llm_settings_ollama(auth_client: AsyncClient):
    resp = await auth_client.put(
        "/api/v1/settings/llm",
        json={"provider": "ollama", "model": "llama3.2"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    settings = await auth_client.get("/api/v1/settings/llm")
    data = settings.json()
    assert len(data) == 1
    assert data[0]["provider"] == "ollama"
    assert data[0]["is_active"] is True
    assert data[0]["masked_key"] is None


@pytest.mark.anyio
async def test_upsert_llm_settings_claude_masks_key(auth_client: AsyncClient):
    resp = await auth_client.put(
        "/api/v1/settings/llm",
        json={"provider": "claude", "model": "claude-sonnet-4-6", "api_key": "sk-ant-api03-secretkey"},
    )
    assert resp.status_code == 200

    settings = await auth_client.get("/api/v1/settings/llm")
    data = settings.json()
    provider = next(d for d in data if d["provider"] == "claude")
    assert "sk-ant-a" in provider["masked_key"]
    assert "secretkey" not in provider["masked_key"]
    assert "****" in provider["masked_key"]


@pytest.mark.anyio
async def test_only_one_provider_active_at_a_time(auth_client: AsyncClient):
    await auth_client.put("/api/v1/settings/llm", json={"provider": "ollama", "model": "llama3.2"})
    await auth_client.put(
        "/api/v1/settings/llm",
        json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-openai-key"},
    )
    settings = await auth_client.get("/api/v1/settings/llm")
    active = [d for d in settings.json() if d["is_active"]]
    assert len(active) == 1
    assert active[0]["provider"] == "openai"
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_llm_settings.py -v
```

Expected: 404 errors (endpoints don't exist yet).

- [x] **Step 3: Add LLM endpoints to settings.py**

Replace full content of `backend/app/api/settings.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.encryption import decrypt, encrypt
from app.models.llm_settings import LLMSettings
from app.models.user import User
from app.services.hardware import detect_hardware

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/hardware")
async def hardware_info(_: User = Depends(get_current_user)):
    info = detect_hardware()
    return {
        "cpu_brand": info.cpu_brand,
        "ram_gb": round(info.ram_gb, 1),
        "is_apple_silicon": info.is_apple_silicon,
        "recommendation": info.recommendation,
    }


class LLMSettingsRequest(BaseModel):
    provider: str
    api_key: str | None = None
    model: str


class LLMSettingsResponse(BaseModel):
    id: str
    provider: str
    masked_key: str | None
    model: str
    is_active: bool


def _mask_key(plaintext: str | None) -> str | None:
    if not plaintext:
        return None
    return plaintext[:7] + "****"


@router.get("/llm", response_model=list[LLMSettingsResponse])
async def list_llm_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(LLMSettings))
    rows = result.scalars().all()
    return [
        LLMSettingsResponse(
            id=str(r.id),
            provider=r.provider,
            masked_key=_mask_key(decrypt(r.encrypted_api_key) if r.encrypted_api_key else None),
            model=r.model,
            is_active=r.is_active,
        )
        for r in rows
    ]


@router.put("/llm")
async def upsert_llm_settings(
    body: LLMSettingsRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await db.execute(update(LLMSettings).values(is_active=False))
    result = await db.execute(
        select(LLMSettings).where(LLMSettings.provider == body.provider)
    )
    existing = result.scalar_one_or_none()
    encrypted = encrypt(body.api_key) if body.api_key else None
    if existing:
        existing.model = body.model
        if encrypted:
            existing.encrypted_api_key = encrypted
        existing.is_active = True
    else:
        db.add(LLMSettings(
            provider=body.provider,
            encrypted_api_key=encrypted,
            model=body.model,
            is_active=True,
        ))
    await db.commit()
    return {"ok": True}


@router.post("/test-llm")
async def test_llm_connection(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    import time
    from app.services.llm_service import get_llm_provider
    provider = await get_llm_provider(db)
    start = time.monotonic()
    try:
        resp = await provider.complete([{"role": "user", "content": "Reply with the single word: OK"}])
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"ok": True, "latency_ms": latency_ms, "response": resp.content[:50]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_llm_settings.py -v
```

Expected: 4 tests PASS.

---

## Task 4: LLM provider abstraction service

**Files:**

- Create: `backend/app/services/llm_service.py`
- Create: `backend/tests/test_llm_service.py`

- [x] **Step 1: Install provider SDKs**

```bash
cd backend && uv pip install anthropic openai google-generativeai httpx
```

- [x] **Step 2: Write failing tests**

Create `backend/tests/test_llm_service.py`:

```python
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
```

- [x] **Step 3: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_llm_service.py -v
```

Expected: `ImportError` on `app.services.llm_service`.

- [x] **Step 4: Write implementation**

Create `backend/app/services/llm_service.py`:

```python
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
```

- [x] **Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_llm_service.py -v
```

Expected: 4 tests PASS.

---

## Task 5: ChromaDB Docker service + RAG service

**Files:**

- Modify: `docker-compose.yml`
- Create: `backend/app/services/rag_service.py`
- Create: `backend/tests/test_rag_service.py`

- [x] **Step 1: Install chromadb and sentence-transformers**

```bash
cd backend && uv pip install chromadb sentence-transformers pymupdf
```

- [x] **Step 2: Add chromadb to docker-compose.yml**

In `docker-compose.yml`, add the `chromadb` service under `services:` and add `chroma_data` under `volumes:`:

```yaml
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma
    environment:
      - IS_PERSISTENT=TRUE
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  chroma_data:
```

Also add `chromadb` to the `depends_on` list of the `worker` service.

Update `.env.example` to document the new config vars:

```
CHROMA_HOST=chromadb
CHROMA_PORT=8000
OLLAMA_HOST=http://host.docker.internal:11434
```

- [x] **Step 3: Write failing tests**

Create `backend/tests/test_rag_service.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_collection(count=0):
    col = MagicMock()
    col.count.return_value = count
    col.query.return_value = {"documents": [["chunk about AAPL earnings"]]}
    return col


def test_search_returns_empty_when_collection_empty():
    from app.services.rag_service import search
    col = _make_mock_collection(count=0)
    result = search(col, query="revenue growth")
    assert result == []
    col.query.assert_not_called()


def test_search_returns_chunks_when_collection_has_data():
    from app.services.rag_service import search
    col = _make_mock_collection(count=3)
    result = search(col, query="earnings forecast")
    assert result == ["chunk about AAPL earnings"]


def test_add_chunks_calls_upsert():
    from app.services.rag_service import add_chunks
    col = MagicMock()
    add_chunks(
        col,
        chunks=["text chunk 1", "text chunk 2"],
        metadatas=[{"doc_id": "abc", "chunk_index": 0}, {"doc_id": "abc", "chunk_index": 1}],
        ids=["abc_0", "abc_1"],
    )
    col.upsert.assert_called_once()


def test_get_or_create_collection_uses_global_for_none():
    from app.services.rag_service import get_or_create_collection
    mock_client = MagicMock()
    with patch("app.services.rag_service._get_client", return_value=mock_client):
        get_or_create_collection(None)
    mock_client.get_or_create_collection.assert_called_once_with(name="global")


def test_get_or_create_collection_normalises_symbol():
    from app.services.rag_service import get_or_create_collection
    mock_client = MagicMock()
    with patch("app.services.rag_service._get_client", return_value=mock_client):
        get_or_create_collection("BTC/USDT")
    mock_client.get_or_create_collection.assert_called_once_with(name="btc_usdt")
```

- [x] **Step 4: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_rag_service.py -v
```

Expected: `ImportError` on `app.services.rag_service`.

- [x] **Step 5: Write RAG service implementation**

Create `backend/app/services/rag_service.py`:

```python
import chromadb
from chromadb import Collection

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)


def get_or_create_collection(asset_symbol: str | None) -> Collection:
    name = (asset_symbol or "global").lower().replace("/", "_").replace("-", "_")
    client = _get_client()
    logger.info("rag get_or_create_collection name=%s", name)
    return client.get_or_create_collection(name=name)


def add_chunks(
    collection: Collection,
    chunks: list[str],
    metadatas: list[dict],
    ids: list[str],
) -> None:
    logger.info("rag add_chunks collection=%s count=%d", collection.name, len(chunks))
    collection.upsert(documents=chunks, metadatas=metadatas, ids=ids)


def search(collection: Collection, query: str, n_results: int = 5) -> list[str]:
    if collection.count() == 0:
        logger.info("rag search collection=%s is empty, skipping", collection.name)
        return []
    n = min(n_results, collection.count())
    results = collection.query(query_texts=[query], n_results=n)
    docs = results.get("documents", [[]])[0]
    logger.info("rag search collection=%s query=%r returned %d chunks", collection.name, query, len(docs))
    return docs
```

- [x] **Step 6: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_rag_service.py -v
```

Expected: 5 tests PASS.

- [x] **Step 7: Start ChromaDB locally for manual verification**

```bash
docker compose up chromadb -d
curl http://localhost:8001/api/v1/heartbeat
```

Expected: `{"nanosecond heartbeat": <timestamp>}`

---

## Task 6: Documents API + ingest_document ARQ job

**Files:**

- Create: `backend/app/api/documents.py`
- Modify: `backend/app/main.py`
- Create: `backend/worker/jobs/ingest_document.py`
- Modify: `backend/worker/main.py`
- Create: `backend/tests/test_documents.py`

- [x] **Step 1: Write failing tests**

Create `backend/tests/test_documents.py`:

```python
import io
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_documents_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/documents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_upload_document(auth_client: AsyncClient):
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    resp = await auth_client.post(
        "/api/v1/documents/upload",
        files={"file": ("test_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"doc_type": "annual_report"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "document_id" in body
    assert body["status"] == "pending"


@pytest.mark.anyio
async def test_list_documents_after_upload(auth_client: AsyncClient):
    pdf_bytes = b"%PDF-1.4 fake pdf"
    await auth_client.post(
        "/api/v1/documents/upload",
        files={"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"doc_type": "earnings"},
    )
    resp = await auth_client.get("/api/v1/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["filename"] == "report.pdf"
    assert docs[0]["status"] == "pending"


@pytest.mark.anyio
async def test_delete_document(auth_client: AsyncClient):
    pdf_bytes = b"%PDF-1.4 fake pdf"
    upload = await auth_client.post(
        "/api/v1/documents/upload",
        files={"file": ("del_me.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"doc_type": "research"},
    )
    doc_id = upload.json()["document_id"]
    del_resp = await auth_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200
    list_resp = await auth_client.get("/api/v1/documents")
    assert list_resp.json() == []
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_documents.py -v
```

Expected: 404 on `/api/v1/documents`.

- [x] **Step 3: Create documents API**

Create `backend/app/api/documents.py`:

```python
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.document import Document
from app.models.user import User

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(default="general"),
    asset_symbol: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    dest = UPLOAD_DIR / f"{doc_id}_{file.filename}"
    content = await file.read()
    dest.write_bytes(content)

    # Resolve asset_id from symbol if provided
    asset_id = None
    if asset_symbol:
        from app.models.asset import Asset
        result = await db.execute(select(Asset).where(Asset.symbol == asset_symbol.upper()))
        asset = result.scalar_one_or_none()
        if asset:
            asset_id = asset.id

    doc = Document(
        id=doc_id,
        filename=file.filename,
        file_path=str(dest),
        asset_id=asset_id,
        status="pending",
    )
    db.add(doc)
    await db.commit()

    # Enqueue ingest job
    from arq.connections import ArqRedis, RedisSettings, create_pool
    from app.core.config import settings
    redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    job = await redis.enqueue_job("job_ingest_document", str(doc_id))
    await redis.aclose()

    logger.info("document uploaded id=%s filename=%s", doc_id, file.filename)
    return {"document_id": str(doc_id), "status": "pending", "job_id": job.job_id if job else None}


@router.get("")
async def list_documents(
    asset: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Document).order_by(Document.created_at.desc())
    if asset:
        from app.models.asset import Asset
        result = await db.execute(select(Asset).where(Asset.symbol == asset.upper()))
        a = result.scalar_one_or_none()
        if a:
            query = query.where(Document.asset_id == a.id)
    result = await db.execute(query)
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "asset_id": str(d.asset_id) if d.asset_id else None,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "error_msg": d.error_msg,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.chroma_collection_id:
        try:
            from app.services.rag_service import _get_client
            client = _get_client()
            client.delete_collection(doc.chroma_collection_id)
        except Exception:
            pass

    if doc.file_path and Path(doc.file_path).exists():
        Path(doc.file_path).unlink()

    await db.delete(doc)
    await db.commit()
    logger.info("document deleted id=%s", doc_id)
    return {"ok": True}


@router.post("/{doc_id}/reingest", status_code=202)
async def reingest_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "pending"
    doc.error_msg = None
    await db.commit()

    from arq.connections import ArqRedis, RedisSettings, create_pool
    from app.core.config import settings
    redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    job = await redis.enqueue_job("job_ingest_document", str(doc_id))
    await redis.aclose()
    return {"ok": True, "job_id": job.job_id if job else None}
```

- [x] **Step 4: Register documents router in main.py**

Edit `backend/app/main.py`:

```python
from app.api import assets, auth, documents, health, overview, pipeline, platforms, portfolio, settings

# add after existing include_router calls:
app.include_router(documents.router, prefix="/api/v1")
```

- [x] **Step 5: Create ingest_document ARQ job**

Create `backend/worker/jobs/ingest_document.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.document import Document
from app.services.pipeline import create_log, finish_log
from app.services.rag_service import add_chunks, get_or_create_collection

logger = get_logger(__name__)


def _recursive_chunk(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


async def job_ingest_document(ctx: dict, document_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "ingest_document")
        doc_uuid = uuid.UUID(document_id)
        result = await db.execute(select(Document).where(Document.id == doc_uuid))
        doc = result.scalar_one_or_none()
        if not doc:
            await finish_log(db, log, success=False, error_message=f"Document {document_id} not found")
            return {"error": "not found"}
        try:
            doc.status = "processing"
            await db.commit()

            import fitz
            pdf = fitz.open(doc.file_path)
            full_text = "\n".join(page.get_text() for page in pdf)
            pdf.close()

            chunks = _recursive_chunk(full_text)

            # Resolve asset symbol for collection name
            asset_symbol = None
            if doc.asset_id:
                from app.models.asset import Asset
                a_result = await db.execute(select(Asset).where(Asset.id == doc.asset_id))
                asset = a_result.scalar_one_or_none()
                asset_symbol = asset.symbol if asset else None

            collection = get_or_create_collection(asset_symbol)
            metadatas = [
                {"document_id": document_id, "chunk_index": i, "asset_symbol": asset_symbol or "global"}
                for i in range(len(chunks))
            ]
            ids = [f"{document_id}_{i}" for i in range(len(chunks))]
            add_chunks(collection, chunks, metadatas, ids)

            doc.status = "done"
            doc.chunk_count = len(chunks)
            doc.chroma_collection_id = collection.name
            await db.commit()

            await finish_log(db, log, success=True)
            logger.info("ingest_document done id=%s chunks=%d", document_id, len(chunks))
            return {"chunks": len(chunks)}
        except Exception as e:
            logger.exception("ingest_document failed id=%s: %s", document_id, e)
            doc.status = "failed"
            doc.error_msg = str(e)
            await db.commit()
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [x] **Step 6: Register job in worker/main.py**

Edit `backend/worker/main.py`:

```python
from worker.jobs.ingest_document import job_ingest_document
# in WorkerSettings:
functions = [
    job_fetch_prices_us,
    job_fetch_prices_crypto,
    job_fetch_price_gold,
    job_fetch_benchmark_prices,
    job_ingest_document,
]
```

- [x] **Step 7: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_documents.py -v
```

Expected: 4 tests PASS.

---

## Task 7: run_analysis ARQ job + Analysis API

**Files:**

- Create: `backend/worker/jobs/run_analysis.py`
- Modify: `backend/worker/main.py`
- Create: `backend/app/api/analysis.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_analysis.py`

- [x] **Step 1: Write failing tests**

Create `backend/tests/test_analysis.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_trigger_analysis_unknown_symbol_returns_404(auth_client: AsyncClient):
    resp = await auth_client.post("/api/v1/analysis/UNKNOWN_XYZ")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_latest_verdict_no_analysis_returns_404(auth_client: AsyncClient):
    # Create asset first via portfolio
    await auth_client.post(
        "/api/v1/portfolio/holdings",
        json={"symbol": "AAPL", "asset_type": "stock", "platform_id": None,
              "quantity": 10, "avg_cost": 150.0, "currency": "USD"},
    )
    resp = await auth_client.get("/api/v1/analysis/AAPL/latest")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_trigger_analysis_returns_202(auth_client: AsyncClient):
    from unittest.mock import AsyncMock, patch
    await auth_client.post(
        "/api/v1/portfolio/holdings",
        json={"symbol": "AAPL", "asset_type": "stock", "platform_id": None,
              "quantity": 10, "avg_cost": 150.0, "currency": "USD"},
    )
    with patch("arq.connections.create_pool") as mock_pool:
        mock_redis = AsyncMock()
        mock_job = AsyncMock()
        mock_job.job_id = "test-job-123"
        mock_redis.enqueue_job = AsyncMock(return_value=mock_job)
        mock_redis.aclose = AsyncMock()
        mock_pool.return_value = mock_redis

        resp = await auth_client.post("/api/v1/analysis/AAPL")
    assert resp.status_code == 202
    assert "job_id" in resp.json()
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_analysis.py -v
```

Expected: 404 on `/api/v1/analysis/...`.

- [x] **Step 3: Create run_analysis ARQ job**

Create `backend/worker/jobs/run_analysis.py`:

````python
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.llm_conversation import LLMConversation
from app.services.llm_service import get_llm_provider
from app.services.pipeline import create_log, finish_log
from app.services.rag_service import get_or_create_collection, search

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a professional financial analyst. Analyse the provided portfolio position and market data.
Respond ONLY with valid JSON in this exact format:
{"verdict": "BUY" | "SELL" | "HOLD", "target_price": <number or null>, "reasoning": "<2-3 sentence explanation>"}
Do not include any text outside the JSON object."""

FORMAT_REMINDER = 'Your previous response was not valid JSON. Respond ONLY with the JSON object: {"verdict": "BUY"|"SELL"|"HOLD", "target_price": <number or null>, "reasoning": "<explanation>"}'


async def job_run_analysis(ctx: dict, symbol: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "run_analysis")
        try:
            from app.models.asset import Asset
            from app.models.holding import Holding
            from app.models.price import Price

            # Resolve asset
            a_result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
            asset = a_result.scalar_one_or_none()
            if not asset:
                raise ValueError(f"Asset {symbol} not found")

            # Holdings
            h_result = await db.execute(select(Holding).where(Holding.asset_id == asset.id))
            holdings = h_result.scalars().all()

            # 90-day price history
            since = datetime.now(timezone.utc) - timedelta(days=90)
            p_result = await db.execute(
                select(Price)
                .where(Price.asset_id == asset.id, Price.timestamp >= since)
                .order_by(desc(Price.timestamp))
                .limit(90)
            )
            prices = p_result.scalars().all()

            # RAG context
            collection = get_or_create_collection(symbol)
            rag_chunks = search(collection, query=f"{symbol} financial analysis earnings revenue")
            rag_context = "\n\n---\n\n".join(rag_chunks) if rag_chunks else "No documents available."

            # Build user prompt
            holdings_txt = "\n".join(
                f"- {h.quantity} units @ avg cost {h.avg_cost}" for h in holdings
            ) or "No current holdings."
            prices_txt = "\n".join(
                f"{p.timestamp.date()}: close={p.close}" for p in prices[:10]
            ) if prices else "No price history."

            user_prompt = f"""Asset: {symbol}

Holdings:
{holdings_txt}

Recent price history (last 10 days):
{prices_txt}

Research documents context:
{rag_context}

Provide your BUY/SELL/HOLD verdict as JSON."""

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            llm = await get_llm_provider(db)
            resp = await llm.complete(messages)
            parsed = _parse_verdict(resp.content)

            if parsed is None:
                # Retry once with format reminder
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": FORMAT_REMINDER})
                resp2 = await llm.complete(messages)
                parsed = _parse_verdict(resp2.content)
                if parsed is None:
                    raise ValueError(f"LLM returned malformed JSON after retry: {resp2.content[:200]}")
                resp = resp2

            analysis = AIAnalysis(
                asset_id=asset.id,
                job_id=str(log.id),
                verdict=parsed["verdict"],
                target_price=parsed.get("target_price"),
                reasoning=parsed["reasoning"],
                provider=type(llm).__name__.replace("Provider", "").lower(),
                model=getattr(llm, "model", "unknown"),
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                cost_usd=resp.cost_usd,
            )
            db.add(analysis)
            await db.flush()

            for i, msg in enumerate(messages + [{"role": "assistant", "content": resp.content}]):
                db.add(LLMConversation(
                    analysis_id=analysis.id,
                    role=msg["role"],
                    content=msg["content"],
                    message_order=i,
                ))

            await db.commit()
            await finish_log(db, log, success=True)
            logger.info("run_analysis done symbol=%s verdict=%s cost_usd=%.6f", symbol, parsed["verdict"], resp.cost_usd)
            return {"verdict": parsed["verdict"], "analysis_id": str(analysis.id)}
        except Exception as e:
            logger.exception("run_analysis failed symbol=%s: %s", symbol, e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


def _parse_verdict(text: str) -> dict | None:
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if data.get("verdict") not in ("BUY", "SELL", "HOLD"):
            return None
        return data
    except (json.JSONDecodeError, AttributeError):
        return None
````

- [x] **Step 4: Create analysis API**

Create `backend/app/api/analysis.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.asset import Asset
from app.models.llm_conversation import LLMConversation
from app.models.user import User

router = APIRouter(prefix="/analysis", tags=["analysis"])
logger = get_logger(__name__)


@router.post("/{symbol}", status_code=202)
async def trigger_analysis(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    from arq.connections import ArqRedis, RedisSettings, create_pool
    from app.core.config import settings
    redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    job = await redis.enqueue_job("job_run_analysis", symbol.upper())
    await redis.aclose()
    logger.info("analysis triggered symbol=%s job_id=%s", symbol, job.job_id if job else None)
    return {"symbol": symbol.upper(), "job_id": job.job_id if job else None}


@router.get("/{symbol}/latest")
async def get_latest_verdict(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    a_result = await db.execute(
        select(AIAnalysis)
        .where(AIAnalysis.asset_id == asset.id)
        .order_by(desc(AIAnalysis.created_at))
        .limit(1)
    )
    analysis = a_result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this asset")
    return _serialize(analysis)


@router.get("/{symbol}/history")
async def get_analysis_history(
    symbol: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    a_result = await db.execute(
        select(AIAnalysis)
        .where(AIAnalysis.asset_id == asset.id)
        .order_by(desc(AIAnalysis.created_at))
        .limit(limit)
    )
    return [_serialize(a) for a in a_result.scalars().all()]


@router.get("/conversation/{analysis_id}")
async def get_conversation(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LLMConversation)
        .where(LLMConversation.analysis_id == analysis_id)
        .order_by(LLMConversation.message_order)
    )
    msgs = result.scalars().all()
    if not msgs:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [{"role": m.role, "content": m.content, "order": m.message_order} for m in msgs]


def _serialize(a: AIAnalysis) -> dict:
    return {
        "id": str(a.id),
        "asset_id": str(a.asset_id),
        "verdict": a.verdict,
        "target_price": float(a.target_price) if a.target_price else None,
        "reasoning": a.reasoning,
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "created_at": a.created_at.isoformat(),
    }
```

- [x] **Step 5: Register analysis router and job**

Edit `backend/app/main.py`:

```python
from app.api import analysis, assets, auth, documents, health, overview, pipeline, platforms, portfolio, settings

app.include_router(analysis.router, prefix="/api/v1")
```

Edit `backend/worker/main.py`:

```python
from worker.jobs.run_analysis import job_run_analysis
# in WorkerSettings.functions:
functions = [
    job_fetch_prices_us,
    job_fetch_prices_crypto,
    job_fetch_price_gold,
    job_fetch_benchmark_prices,
    job_ingest_document,
    job_run_analysis,
]
```

- [x] **Step 6: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_analysis.py -v
```

Expected: 3 tests PASS.

---

## Task 8: VerdictCard frontend component

**Files:**

- Create: `frontend/components/analysis/VerdictCard.tsx`
- Modify: `frontend/app/(auth)/portfolio/[symbol]/page.tsx`

- [x] **Step 1: Create VerdictCard component**

Create `frontend/components/analysis/VerdictCard.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Analysis {
  id: string;
  verdict: "BUY" | "SELL" | "HOLD";
  target_price: number | null;
  reasoning: string;
  model: string;
  cost_usd: number;
  created_at: string;
}

interface VerdictCardProps {
  symbol: string;
  privacyMode?: boolean;
}

const VERDICT_COLORS = {
  BUY: "bg-green-500 text-white",
  SELL: "bg-red-500 text-white",
  HOLD: "bg-yellow-500 text-white",
};

export function VerdictCard({ symbol, privacyMode = false }: VerdictCardProps) {
  const [latest, setLatest] = useState<Analysis | null>(null);
  const [history, setHistory] = useState<Analysis[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [conversation, setConversation] = useState<
    { role: string; content: string }[]
  >([]);
  const [convOpen, setConvOpen] = useState(false);

  const displayed = history.find((a) => a.id === selectedId) ?? latest;

  async function fetchLatest() {
    const res = await fetch(`/api/v1/analysis/${symbol}/latest`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("token") ?? ""}`,
      },
    });
    if (res.ok) {
      const data = await res.json();
      setLatest(data);
      setSelectedId(data.id);
    }
  }

  async function fetchHistory() {
    const res = await fetch(`/api/v1/analysis/${symbol}/history`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("token") ?? ""}`,
      },
    });
    if (res.ok) setHistory(await res.json());
  }

  async function runAnalysis() {
    setLoading(true);
    const token = localStorage.getItem("token") ?? "";
    const res = await fetch(`/api/v1/analysis/${symbol}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setLoading(false);
      return;
    }

    // Poll SSE stream until done
    const source = new EventSource(`/api/v1/pipeline/stream?token=${token}`);
    source.onmessage = (e) => {
      const jobs = JSON.parse(e.data) as { job_type: string; status: string }[];
      const done = jobs.find(
        (j) => j.job_type === "run_analysis" && j.status === "done",
      );
      if (done) {
        source.close();
        fetchLatest().then(fetchHistory);
        setLoading(false);
      }
      const failed = jobs.find(
        (j) => j.job_type === "run_analysis" && j.status === "failed",
      );
      if (failed) {
        source.close();
        setLoading(false);
      }
    };
    source.onerror = () => {
      source.close();
      setLoading(false);
    };
  }

  async function loadConversation(id: string) {
    const res = await fetch(`/api/v1/analysis/conversation/${id}`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("token") ?? ""}`,
      },
    });
    if (res.ok) setConversation(await res.json());
  }

  // Load latest on first render
  useState(() => {
    fetchLatest().then(fetchHistory);
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">AI Analysis</CardTitle>
        <Button size="sm" onClick={runAnalysis} disabled={loading}>
          {loading ? "Analysing…" : "Run Analysis"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {displayed ? (
          <>
            <div className="flex items-center gap-3">
              <Badge className={VERDICT_COLORS[displayed.verdict]}>
                {displayed.verdict}
              </Badge>
              {displayed.target_price !== null && (
                <span className="text-sm text-muted-foreground">
                  Target:{" "}
                  {privacyMode
                    ? "••••"
                    : `$${displayed.target_price.toFixed(2)}`}
                </span>
              )}
            </div>
            <p className="text-sm">{displayed.reasoning}</p>
            <p className="text-xs text-muted-foreground">
              {displayed.model} · ${displayed.cost_usd.toFixed(4)} ·{" "}
              {new Date(displayed.created_at).toLocaleDateString()}
            </p>

            {history.length > 1 && (
              <Select
                value={selectedId ?? ""}
                onValueChange={(v) => {
                  setSelectedId(v);
                  setConvOpen(false);
                }}
              >
                <SelectTrigger className="h-7 text-xs">
                  <SelectValue placeholder="Past verdicts" />
                </SelectTrigger>
                <SelectContent>
                  {history.map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.verdict} —{" "}
                      {new Date(a.created_at).toLocaleDateString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            <Collapsible
              open={convOpen}
              onOpenChange={(o) => {
                setConvOpen(o);
                if (o && displayed) loadConversation(displayed.id);
              }}
            >
              <CollapsibleTrigger className="text-xs text-muted-foreground underline">
                {convOpen ? "Hide" : "View"} conversation
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 space-y-1 max-h-64 overflow-y-auto">
                {conversation.map((m, i) => (
                  <div key={i} className="text-xs rounded p-2 bg-muted">
                    <span className="font-semibold capitalize">{m.role}: </span>
                    {m.content}
                  </div>
                ))}
              </CollapsibleContent>
            </Collapsible>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            No analysis yet. Click Run Analysis.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
```

- [x] **Step 2: Add VerdictCard to asset detail page**

Edit `frontend/app/(auth)/portfolio/[symbol]/page.tsx` — import and render `VerdictCard`. Find the section where the price chart is rendered and add the card below it:

```tsx
import { VerdictCard } from "@/components/analysis/VerdictCard";

// In the JSX, after the chart section:
<VerdictCard symbol={symbol} privacyMode={privacyMode} />;
```

Where `privacyMode` is whatever state/context variable the page already uses for the privacy toggle.

- [x] **Step 3: Verify in browser**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000` → navigate to any asset detail page → confirm VerdictCard renders with "No analysis yet" state and Run Analysis button.

---

## Task 9: Document library page

**Files:**

- Create: `frontend/app/(auth)/documents/page.tsx`

- [x] **Step 1: Create page**

Create `frontend/app/(auth)/documents/page.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Document {
  id: string;
  filename: string;
  asset_id: string | null;
  status: "pending" | "processing" | "done" | "failed";
  chunk_count: number | null;
  error_msg: string | null;
  created_at: string;
}

const STATUS_BADGE: Record<Document["status"], string> = {
  pending: "bg-gray-400 text-white",
  processing: "bg-blue-500 text-white animate-pulse",
  done: "bg-green-500 text-white",
  failed: "bg-red-500 text-white",
};

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem("token") ?? ""}` };
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [filter, setFilter] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [assetSymbol, setAssetSymbol] = useState("");
  const [docType, setDocType] = useState("research");
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    const url = filter
      ? `/api/v1/documents?asset=${filter.toUpperCase()}`
      : "/api/v1/documents";
    const res = await fetch(url, { headers: authHeaders() });
    if (res.ok) setDocs(await res.json());
  }

  useEffect(() => {
    load();
  }, [filter]);

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);
    if (assetSymbol) form.append("asset_symbol", assetSymbol.toUpperCase());
    await fetch("/api/v1/documents/upload", {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
    setUploading(false);
    setUploadOpen(false);
    load();
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this document?")) return;
    await fetch(`/api/v1/documents/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    load();
  }

  async function handleReingest(id: string) {
    await fetch(`/api/v1/documents/${id}/reingest`, {
      method: "POST",
      headers: authHeaders(),
    });
    load();
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Document Library</h1>
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogTrigger asChild>
            <Button>Upload PDF</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Upload Research Document</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div>
                <Label>Asset Symbol (optional)</Label>
                <Input
                  placeholder="e.g. AAPL"
                  value={assetSymbol}
                  onChange={(e) => setAssetSymbol(e.target.value)}
                />
              </div>
              <div>
                <Label>Document Type</Label>
                <Select value={docType} onValueChange={setDocType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[
                      "research",
                      "annual_report",
                      "earnings",
                      "news",
                      "general",
                    ].map((t) => (
                      <SelectItem key={t} value={t}>
                        {t}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>PDF File</Label>
                <Input type="file" accept=".pdf" ref={fileRef} />
              </div>
              <Button
                onClick={handleUpload}
                disabled={uploading}
                className="w-full"
              >
                {uploading ? "Uploading…" : "Upload"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Input
        placeholder="Filter by asset symbol…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="max-w-xs"
      />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Filename</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Chunks</TableHead>
            <TableHead>Uploaded</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {docs.map((doc) => (
            <TableRow key={doc.id}>
              <TableCell className="font-mono text-sm">
                {doc.filename}
              </TableCell>
              <TableCell>
                <Badge className={STATUS_BADGE[doc.status]}>{doc.status}</Badge>
                {doc.error_msg && (
                  <p className="text-xs text-red-500 mt-1">{doc.error_msg}</p>
                )}
              </TableCell>
              <TableCell>{doc.chunk_count ?? "—"}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {new Date(doc.created_at).toLocaleDateString()}
              </TableCell>
              <TableCell className="flex gap-2">
                {doc.status === "failed" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleReingest(doc.id)}
                  >
                    Re-ingest
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => handleDelete(doc.id)}
                >
                  Delete
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {docs.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={5}
                className="text-center text-muted-foreground py-8"
              >
                No documents yet. Upload a PDF to get started.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [x] **Step 2: Verify in browser**

```bash
cd frontend && npm run dev
```

Navigate to `http://localhost:3000/documents` → confirm empty state renders, Upload dialog opens, filter input works.

---

## Task 10: AI usage page

**Files:**

- Create: `frontend/app/(auth)/ai-usage/page.tsx`

- [x] **Step 1: Add usage endpoint to analysis router**

Edit `backend/app/api/analysis.py` — add two new routes at the bottom:

```python
@router.get("/usage/summary")
async def get_usage_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy import func
    total = await db.execute(select(func.sum(AIAnalysis.cost_usd)))
    total_cost = float(total.scalar() or 0)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly = await db.execute(
        select(func.sum(AIAnalysis.cost_usd)).where(AIAnalysis.created_at >= month_start)
    )
    monthly_cost = float(monthly.scalar() or 0)

    count = await db.execute(select(func.count(AIAnalysis.id)))
    total_analyses = int(count.scalar() or 0)

    by_provider = await db.execute(
        select(AIAnalysis.provider, func.sum(AIAnalysis.cost_usd).label("cost"))
        .group_by(AIAnalysis.provider)
    )
    return {
        "total_cost_usd": total_cost,
        "monthly_cost_usd": monthly_cost,
        "total_analyses": total_analyses,
        "by_provider": [{"provider": r.provider, "cost_usd": float(r.cost)} for r in by_provider],
    }


@router.get("/usage/logs")
async def get_usage_logs(
    limit: int = 100,
    provider: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(AIAnalysis).order_by(desc(AIAnalysis.created_at)).limit(limit)
    if provider:
        query = query.where(AIAnalysis.provider == provider)
    result = await db.execute(query)
    return [_serialize(a) for a in result.scalars().all()]
```

- [x] **Step 2: Create AI usage page**

Create `frontend/app/(auth)/ai-usage/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Summary {
  total_cost_usd: number;
  monthly_cost_usd: number;
  total_analyses: number;
  by_provider: { provider: string; cost_usd: number }[];
}

interface Analysis {
  id: string;
  verdict: string;
  model: string;
  provider: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  created_at: string;
  asset_id: string;
}

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem("token") ?? ""}` };
}

export default function AIUsagePage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [logs, setLogs] = useState<Analysis[]>([]);
  const [filterProvider, setFilterProvider] = useState("all");
  const [conversations, setConversations] = useState<
    Record<string, { role: string; content: string }[]>
  >({});
  const [openRows, setOpenRows] = useState<Set<string>>(new Set());

  async function load() {
    const [sRes, lRes] = await Promise.all([
      fetch("/api/v1/analysis/usage/summary", { headers: authHeaders() }),
      fetch(
        filterProvider === "all"
          ? "/api/v1/analysis/usage/logs"
          : `/api/v1/analysis/usage/logs?provider=${filterProvider}`,
        { headers: authHeaders() },
      ),
    ]);
    if (sRes.ok) setSummary(await sRes.json());
    if (lRes.ok) setLogs(await lRes.json());
  }

  useEffect(() => {
    load();
  }, [filterProvider]);

  async function toggleConversation(id: string) {
    const next = new Set(openRows);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
      if (!conversations[id]) {
        const res = await fetch(`/api/v1/analysis/conversation/${id}`, {
          headers: authHeaders(),
        });
        if (res.ok)
          setConversations((prev) => ({ ...prev, [id]: await res.json() }));
      }
    }
    setOpenRows(next);
  }

  const providers = summary
    ? ["all", ...summary.by_provider.map((p) => p.provider)]
    : ["all"];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-semibold">AI Usage</h1>

      {summary && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm">Total Spend</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">
                  ${summary.total_cost_usd.toFixed(4)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm">This Month</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">
                  ${summary.monthly_cost_usd.toFixed(4)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm">Total Analyses</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{summary.total_analyses}</p>
              </CardContent>
            </Card>
          </div>

          {summary.by_provider.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Cost by Provider</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={summary.by_provider}>
                    <XAxis dataKey="provider" />
                    <YAxis tickFormatter={(v) => `$${v}`} />
                    <Tooltip
                      formatter={(v: number) => [`$${v.toFixed(6)}`, "Cost"]}
                    />
                    <Bar dataKey="cost_usd" fill="#6366f1" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </>
      )}

      <div className="flex items-center gap-3">
        <Select value={filterProvider} onValueChange={setFilterProvider}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {providers.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Verdict</TableHead>
            <TableHead>Model</TableHead>
            <TableHead>Tokens In</TableHead>
            <TableHead>Tokens Out</TableHead>
            <TableHead>Cost</TableHead>
            <TableHead>Date</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((a) => (
            <>
              <TableRow key={a.id}>
                <TableCell>
                  <span
                    className={
                      a.verdict === "BUY"
                        ? "text-green-500"
                        : a.verdict === "SELL"
                          ? "text-red-500"
                          : "text-yellow-500"
                    }
                  >
                    {a.verdict}
                  </span>
                </TableCell>
                <TableCell className="text-sm">{a.model}</TableCell>
                <TableCell>{a.tokens_in.toLocaleString()}</TableCell>
                <TableCell>{a.tokens_out.toLocaleString()}</TableCell>
                <TableCell>${a.cost_usd.toFixed(6)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(a.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <button
                    className="text-xs text-muted-foreground underline"
                    onClick={() => toggleConversation(a.id)}
                  >
                    {openRows.has(a.id) ? "Hide" : "View"} log
                  </button>
                </TableCell>
              </TableRow>
              {openRows.has(a.id) && (
                <TableRow key={`${a.id}-conv`}>
                  <TableCell colSpan={7}>
                    <div className="space-y-1 max-h-48 overflow-y-auto py-1">
                      {(conversations[a.id] ?? []).map((m, i) => (
                        <div key={i} className="text-xs bg-muted rounded p-2">
                          <span className="font-semibold capitalize">
                            {m.role}:{" "}
                          </span>
                          {m.content}
                        </div>
                      ))}
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </>
          ))}
          {logs.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={7}
                className="text-center text-muted-foreground py-8"
              >
                No analyses yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [x] **Step 3: Verify in browser**

```bash
cd frontend && npm run dev
```

Navigate to `http://localhost:3000/ai-usage` → confirm summary cards, empty table, provider filter render correctly.

---

## Self-Review Checklist

**Spec coverage:**

- ✅ AES-256-GCM encryption — Task 1
- ✅ LLM provider abstraction (Ollama/OpenAI/Claude/Gemini) — Task 4
- ✅ ChromaDB Docker + RAG service — Task 5
- ✅ DB migration (llm_settings, documents, ai_analyses, llm_conversations) — Task 2
- ✅ LLM settings API (GET/PUT/test-llm) — Task 3
- ✅ ingest_document ARQ job — Task 6
- ✅ Documents API (upload/list/delete/reingest) — Task 6
- ✅ run_analysis ARQ job — Task 7
- ✅ Analysis API (trigger/latest/history/conversation) — Task 7
- ✅ VerdictCard with BUY/SELL/HOLD badge + privacy mode + SSE — Task 8
- ✅ Document library page — Task 9
- ✅ AI usage page with cost summary + bar chart + conversation logs — Task 10
- ✅ Error handling: malformed JSON retry, empty RAG, ChromaDB failure, invalid key — run_analysis + ingest_document jobs

**Type consistency:** `LLMResponse` defined in Task 4, used in Tasks 7. `get_llm_provider(db)` defined in Task 4, called in Tasks 3 and 7. `get_or_create_collection`/`search`/`add_chunks` defined in Task 5, called in Tasks 6 and 7. All consistent.

**No placeholders:** All steps contain complete runnable code.
