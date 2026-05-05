# Import Simplification & Portfolio Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the platform/template import wizard with a simple canonical-check → LLM-fallback pipeline, redesign the portfolio table with computed columns and correct currency display, and remove Broker Platforms from Settings.

**Architecture:** DB migration first removes dead tables and alters Transaction/Holding; backend services are simplified in sequence (models → services → API); frontend changes consume the new API shapes. Each task is independently testable.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic (backend), Next.js 14 App Router/TypeScript/TanStack Table/shadcn-ui (frontend), PostgreSQL 16 / TimescaleDB.

---

## File Map

**Backend — Create:**
- `backend/alembic/versions/007_simplify_import_remove_platforms.py`
- `backend/app/schemas/import_pipeline.py` (replaces import_template.py)

**Backend — Modify:**
- `backend/app/models/transaction.py`
- `backend/app/models/holding.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/holding.py`
- `backend/app/services/import_pipeline.py`
- `backend/app/services/llm_gateway.py`
- `backend/app/services/portfolio.py`
- `backend/app/api/import_pipeline.py`
- `backend/app/api/portfolio.py`
- `backend/app/main.py`

**Backend — Delete:**
- `backend/app/models/platform.py`
- `backend/app/models/import_template.py`
- `backend/app/models/import_profile.py`
- `backend/app/services/platform.py`
- `backend/app/services/csv_import.py`
- `backend/app/schemas/platform.py`
- `backend/app/schemas/csv_import.py`
- `backend/app/schemas/import_template.py`
- `backend/app/api/platforms.py`
- `backend/tests/test_platforms.py`
- `backend/tests/test_csv_import.py`

**Frontend — Create:**
- `frontend/components/import/ReviewTable.tsx`

**Frontend — Modify:**
- `frontend/lib/services/import-pipeline.ts`
- `frontend/lib/services/portfolio.ts`
- `frontend/app/(auth)/import/page.tsx`
- `frontend/components/portfolio/HoldingsTable.tsx`
- `frontend/components/portfolio/AddHoldingDialog.tsx`
- `frontend/app/(auth)/portfolio/page.tsx`
- `frontend/app/(auth)/settings/page.tsx`

**Frontend — Delete:**
- `frontend/components/portfolio/ImportDrawer.tsx`
- `frontend/components/settings/PlatformsManager.tsx`
- `frontend/lib/services/platforms.ts`

---

## Task 1: Database Migration

**Files:**
- Create: `backend/alembic/versions/007_simplify_import_remove_platforms.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/alembic/versions/007_simplify_import_remove_platforms.py
"""simplify_import_remove_platforms

Revision ID: 007
Revises: 006
Create Date: 2026-05-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop import_templates (has FK to platforms — must go before platforms)
    op.drop_table('import_templates')

    # 2. Drop import_profiles
    op.execute("DROP TABLE IF EXISTS import_profiles")

    # 3. Drop platform_id FK + column from transactions
    op.drop_constraint('transactions_platform_id_fkey', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'platform_id')

    # 4. Add platform text column to transactions
    op.add_column('transactions', sa.Column('platform', sa.String(100), nullable=True))

    # 5. Extend transaction_type_enum (pg16 supports ADD VALUE in transaction)
    op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'reward'")
    op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'fee'")
    op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'transfer'")

    # 6. Add purchased_at to holdings
    op.add_column('holdings', sa.Column('purchased_at', sa.Date(), nullable=True))

    # 7. Drop platforms table (all FKs to it are now gone)
    op.drop_table('platforms')


def downgrade() -> None:
    op.create_table(
        'platforms',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('asset_types_supported', postgresql.JSONB(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.drop_column('holdings', 'purchased_at')
    op.drop_column('transactions', 'platform')
    op.add_column('transactions', sa.Column('platform_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'transactions_platform_id_fkey', 'transactions', 'platforms', ['platform_id'], ['id']
    )
```

- [ ] **Step 2: Run the migration**

```bash
cd backend
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 006 -> 007, simplify_import_remove_platforms`

- [ ] **Step 3: Verify columns in DB**

```bash
docker compose exec db psql -U zentri -d zentri -c "\d transactions"
docker compose exec db psql -U zentri -d zentri -c "\d holdings"
docker compose exec db psql -U zentri -d zentri -c "\dt" | grep -E "platform|import"
```

Expected: `transactions` has `platform varchar(100)`, no `platform_id`. `holdings` has `purchased_at date`. No `platforms` or `import_templates` tables.

---

## Task 2: Backend Models & Schemas

**Files:**
- Modify: `backend/app/models/transaction.py`
- Modify: `backend/app/models/holding.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/holding.py`
- Delete: `backend/app/models/platform.py`, `import_template.py`, `import_profile.py`
- Delete: `backend/app/schemas/platform.py`, `csv_import.py`, `import_template.py`

- [ ] **Step 1: Update Transaction model**

Replace `backend/app/models/transaction.py` entirely:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

TRANSACTION_TYPES = ("buy", "sell", "dividend", "reward", "fee", "transfer")
TRANSACTION_SOURCES = ("manual", "csv_import")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    type: Mapped[str] = mapped_column(
        Enum(*TRANSACTION_TYPES, name="transaction_type_enum"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=Decimal("0"))
    source: Mapped[str] = mapped_column(
        Enum(*TRANSACTION_SOURCES, name="transaction_source_enum"), nullable=False, default="manual"
    )
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Update Holding model**

Replace `backend/app/models/holding.py` entirely:

```python
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    avg_cost_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="THB")
    purchased_at: Mapped[date | None] = mapped_column(Date(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 3: Update models/__init__.py**

Replace `backend/app/models/__init__.py`:

```python
from app.models.asset import Asset  # noqa: F401
from app.models.benchmark import Benchmark, BenchmarkPrice  # noqa: F401
from app.models.cash_balance import CashBalance  # noqa: F401
from app.models.feature_llm_config import FeatureLLMConfig  # noqa: F401
from app.models.holding import Holding  # noqa: F401
from app.models.pipeline_log import PipelineLog  # noqa: F401
from app.models.price import Price  # noqa: F401
from app.models.provider_config import ProviderConfig  # noqa: F401
from app.models.transaction import Transaction  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.llm_call_log import LLMCallLog  # noqa: F401
from app.models.exchange_rate_cache import ExchangeRateCache  # noqa: F401

__all__ = [
    "User", "Asset", "Holding", "Transaction",
    "Price", "PipelineLog", "Benchmark", "BenchmarkPrice",
    "ProviderConfig", "FeatureLLMConfig", "CashBalance",
    "LLMCallLog", "ExchangeRateCache",
]
```

- [ ] **Step 4: Delete dead model files**

```bash
rm backend/app/models/platform.py
rm backend/app/models/import_template.py
rm backend/app/models/import_profile.py
```

- [ ] **Step 5: Update Holding schema**

Replace `backend/app/schemas/holding.py`:

```python
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class HoldingCreate(BaseModel):
    symbol: str
    asset_type: str = "us_stock"
    purchased_at: date | None = None
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str = "THB"


class HoldingRow(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    asset_type: str
    currency: str
    purchased_at: date | None
    outstanding_shares: Decimal
    cost_per_share: Decimal
    total_cost: Decimal
    current_price: Decimal | None = None
    holding_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    price_1d_change: Decimal | None = None

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    holdings_count: int
    total_cost: Decimal
    primary_currency: str
```

- [ ] **Step 6: Delete dead schema files**

```bash
rm backend/app/schemas/platform.py
rm backend/app/schemas/csv_import.py
rm backend/app/schemas/import_template.py
```

- [ ] **Step 7: Create new import pipeline schema**

Create `backend/app/schemas/import_pipeline.py`:

```python
from pydantic import BaseModel


class UploadResponse(BaseModel):
    rows: list[dict]
    method: str  # "direct" | "llm_translated"
    total: int


class ConfirmRequest(BaseModel):
    rows: list[dict]


class ConfirmResponse(BaseModel):
    imported: int
    errors: list[dict]
```

- [ ] **Step 8: Delete dead test files**

```bash
rm backend/tests/test_platforms.py
rm backend/tests/test_csv_import.py
```

- [ ] **Step 9: Verify imports compile**

```bash
cd backend
docker compose exec backend python -c "from app.models import Holding, Transaction, Asset, User; print('OK')"
```

Expected: `OK`

---

## Task 3: Backend — Delete Dead Service & API Files, Clean main.py

**Files:**
- Delete: `backend/app/services/platform.py`, `csv_import.py`
- Delete: `backend/app/api/platforms.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Delete dead service and API files**

```bash
rm backend/app/services/platform.py
rm backend/app/services/csv_import.py
rm backend/app/api/platforms.py
```

- [ ] **Step 2: Update main.py**

Replace `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    analysis, assets, auth, cash_balance, documents,
    feature_llm_config, health, import_pipeline, llm_usage,
    overview, pipeline, portfolio, provider_config, settings,
)
from app.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Zentri API", version="0.1.0")
logger.info("Zentri API starting up")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(overview.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(provider_config.router, prefix="/api/v1")
app.include_router(feature_llm_config.router, prefix="/api/v1")
app.include_router(cash_balance.router, prefix="/api/v1")
app.include_router(import_pipeline.router, prefix="/api/v1")
app.include_router(llm_usage.router, prefix="/api/v1")
```

- [ ] **Step 3: Verify app starts**

```bash
docker compose exec backend python -c "from app.main import app; print('OK')"
```

Expected: `OK`

---

## Task 4: Backend — Import Pipeline Service & LLM Gateway

**Files:**
- Modify: `backend/app/services/llm_gateway.py`
- Modify: `backend/app/services/import_pipeline.py`

- [ ] **Step 1: Write failing test for canonical check**

Create `backend/tests/test_import_upload.py`:

```python
import pytest
from app.services.import_pipeline import is_canonical, apply_mapping, parse_all_rows

def test_is_canonical_exact_match():
    headers = ["trade_date", "type", "symbol", "unit", "price", "currency"]
    assert is_canonical(headers) is True

def test_is_canonical_unknown_header():
    headers = ["Date", "Ticker", "Qty", "Amount"]
    assert is_canonical(headers) is False

def test_is_canonical_empty():
    assert is_canonical([]) is True

def test_apply_mapping_basic():
    mapping = {
        "field_map": {"Date": "trade_date", "Ticker": "symbol", "Qty": "unit", "Action": "type"},
        "type_map": {"Buy": "BUY", "Sell": "SELL"},
        "currency_default": "USD",
        "asset_type_default": "us_stock",
    }
    row = {"Date": "2024-01-15", "Ticker": "AAPL", "Qty": "10", "Action": "Buy"}
    result = apply_mapping(row, mapping)
    assert result["trade_date"] == "2024-01-15"
    assert result["symbol"] == "AAPL"
    assert result["unit"] == "10"
    assert result["type"] == "BUY"
    assert result["currency"] == "USD"

def test_apply_mapping_type_passthrough():
    mapping = {"field_map": {"type": "type"}, "type_map": {}, "currency_default": "THB", "asset_type_default": "thai_stock"}
    row = {"type": "BUY"}
    result = apply_mapping(row, mapping)
    assert result["type"] == "BUY"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend
docker compose exec backend pytest tests/test_import_upload.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` — functions don't exist yet.

- [ ] **Step 3: Add `import_translator` feature to LLM gateway**

In `backend/app/services/llm_gateway.py`, update `FEATURE_KEYS` and add prompts.

Find the line:
```python
FEATURE_KEYS = (
    "import_template_generator",
    "transaction_classifier",
    "portfolio_analysis",
    "chat",
)
```

Replace with:
```python
FEATURE_KEYS = (
    "import_translator",
    "transaction_classifier",
    "portfolio_analysis",
    "chat",
)
```

Find the `"import_template_generator"` entry in `DEFAULT_SYSTEM_PROMPTS` and replace with:
```python
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
```

Find the `"import_template_generator"` entry in `DEFAULT_HUMAN_PROMPTS` and replace with:
```python
    "import_translator": "Headers: {headers}\n\nSample rows:\n{sample_rows}",
```

- [ ] **Step 4: Rewrite import_pipeline.py service**

**First:** Read `backend/app/services/llm_gateway.py` and confirm the signature of `LLMGateway.call()` — specifically what keyword arguments it accepts (`feature_key`, `user_id`, `prompt_vars`, etc.) and what it returns. Adjust `translate_via_llm` below to match the actual signature if it differs.

Replace `backend/app/services/import_pipeline.py` entirely:

```python
from __future__ import annotations

import csv
import io
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.canonical import CANONICAL_FIELDS
from app.core.logging import get_logger
from app.services.llm_gateway import LLMGateway

logger = get_logger(__name__)

CANONICAL_SET = set(CANONICAL_FIELDS)


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


def parse_all_rows(file_format: str, content: bytes) -> list[dict]:
    if file_format == "csv":
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        return [dict(r) for r in reader]
    data = json.loads(content)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
    return []


def is_canonical(headers: list[str]) -> bool:
    return all(h in CANONICAL_SET for h in headers)


def apply_mapping(row: dict, mapping: dict) -> dict:
    field_map: dict[str, str] = mapping.get("field_map", {})
    type_map: dict[str, str] = mapping.get("type_map", {})
    currency_default: str = mapping.get("currency_default", "THB")
    asset_type_default: str = mapping.get("asset_type_default", "us_stock")

    result: dict[str, Any] = {f: None for f in CANONICAL_FIELDS}

    for src_col, canonical_field in field_map.items():
        if canonical_field in CANONICAL_SET and src_col in row:
            result[canonical_field] = row[src_col] if row[src_col] != "" else None

    if result.get("type") and type_map:
        result["type"] = type_map.get(str(result["type"]), result["type"])

    if not result.get("currency"):
        result["currency"] = currency_default
    if not result.get("asset_type"):
        result["asset_type"] = asset_type_default

    return result


async def translate_via_llm(
    db: AsyncSession,
    user_id: Any,
    headers: list[str],
    sample_rows: list[dict],
) -> dict:
    gw = LLMGateway(db)
    human = f"Headers: {headers}\n\nSample rows:\n{json.dumps(sample_rows[:5], ensure_ascii=False, indent=2)}"
    response = await gw.call(
        feature_key="import_translator",
        user_id=user_id,
        prompt_vars={"headers": str(headers), "sample_rows": json.dumps(sample_rows[:5])},
    )
    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    mapping = json.loads(raw)
    logger.info("LLM translation mapping produced: %s", mapping)
    return mapping


async def process_file(
    db: AsyncSession,
    user_id: Any,
    file_format: str,
    content: bytes,
) -> tuple[list[dict], str]:
    rows = parse_all_rows(file_format, content)
    if not rows:
        return [], "direct"
    headers = list(rows[0].keys())
    if is_canonical(headers):
        logger.info("File is canonical — direct import, %d rows", len(rows))
        return rows, "direct"
    logger.info("Non-canonical headers %s — calling LLM translator", headers)
    mapping = await translate_via_llm(db, user_id, headers, rows)
    canonical_rows = [apply_mapping(r, mapping) for r in rows]
    return canonical_rows, "llm_translated"
```

- [ ] **Step 5: Run the tests**

```bash
cd backend
docker compose exec backend pytest tests/test_import_upload.py -v
```

Expected: all 4 tests pass.

---

## Task 5: Backend — New Import & Portfolio API Endpoints

**Files:**
- Modify: `backend/app/api/import_pipeline.py`
- Modify: `backend/app/services/portfolio.py`
- Modify: `backend/app/api/portfolio.py`

- [ ] **Step 1: Write failing test for import upload endpoint**

Add to `backend/tests/test_import_upload.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.anyio
async def test_upload_canonical_csv(auth_headers):
    csv_content = b"trade_date,type,symbol,unit,price,currency\n2024-01-15,BUY,AAPL,10,150.00,USD\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/v1/import/upload",
            files={"file": ("trades.csv", csv_content, "text/csv")},
            headers=auth_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "direct"
    assert body["total"] == 1
    assert body["rows"][0]["symbol"] == "AAPL"

@pytest.mark.anyio
async def test_confirm_import(auth_headers):
    rows = [{"trade_date": "2024-01-15", "type": "buy", "symbol": "AAPL",
             "unit": "10", "price": "150.00", "currency": "USD",
             "asset_type": "us_stock", "exchange": None, "gross_amount": None,
             "fee": None, "gross_thb": None, "fee_thb": None,
             "exchange_rate": None, "platform": None, "notes": None}]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/v1/import/confirm",
            json={"rows": rows},
            headers=auth_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 1
    assert body["errors"] == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec backend pytest tests/test_import_upload.py::test_upload_canonical_csv -v
```

Expected: `404 Not Found` — endpoint doesn't exist yet.

- [ ] **Step 3: Rewrite import_pipeline.py API**

Replace `backend/app/api/import_pipeline.py` entirely:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.import_pipeline import ConfirmRequest, ConfirmResponse, UploadResponse
from app.services import import_pipeline as pipeline_svc

logger = get_logger(__name__)
router = APIRouter(prefix="/import", tags=["import"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    file_format = pipeline_svc.detect_file_format(file.filename or "", content)
    rows, method = await pipeline_svc.process_file(db, current_user.id, file_format, content)
    logger.info("Upload: method=%s rows=%d user=%s", method, len(rows), current_user.id)
    return UploadResponse(rows=rows, method=method, total=len(rows))


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_import(
    body: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    imported = 0
    errors: list[dict] = []

    for row in body.rows:
        try:
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                raise ValueError("symbol is required")

            asset_type = str(row.get("asset_type") or "us_stock")
            currency = str(row.get("currency") or "THB")
            platform = row.get("platform") or None

            def to_decimal(val: object) -> Decimal:
                if val is None or val == "":
                    return Decimal("0")
                return Decimal(str(val))

            quantity = to_decimal(row.get("unit"))
            price = to_decimal(row.get("price"))
            fee = to_decimal(row.get("fee_thb") or row.get("fee"))

            raw_date = row.get("trade_date") or ""
            try:
                from dateutil import parser as dp
                executed_at = dp.parse(str(raw_date)).replace(tzinfo=timezone.utc)
            except Exception:
                executed_at = datetime.now(timezone.utc)

            tx_type = str(row.get("type") or "buy").lower()

            # Upsert asset
            result = await db.execute(
                select(Asset).where(Asset.user_id == current_user.id, Asset.symbol == symbol)
            )
            asset = result.scalar_one_or_none()
            if asset is None:
                asset = Asset(
                    id=uuid.uuid4(), user_id=current_user.id, symbol=symbol,
                    asset_type=asset_type, name=symbol, currency=currency, metadata_={},
                )
                db.add(asset)
                await db.flush()

            # Record transaction
            tx = Transaction(
                id=uuid.uuid4(), user_id=current_user.id, asset_id=asset.id,
                platform=str(platform) if platform else None,
                type=tx_type, quantity=quantity, price=price, fee=fee,
                source="csv_import", executed_at=executed_at,
            )
            db.add(tx)
            await db.flush()

            # Upsert holding
            h_result = await db.execute(
                select(Holding).where(Holding.asset_id == asset.id, Holding.user_id == current_user.id)
            )
            holding = h_result.scalar_one_or_none()

            if tx_type == "buy":
                if holding is None:
                    holding = Holding(
                        id=uuid.uuid4(), user_id=current_user.id, asset_id=asset.id,
                        quantity=quantity, avg_cost_price=price, currency=currency,
                        updated_at=datetime.now(timezone.utc),
                    )
                    db.add(holding)
                else:
                    total_qty = holding.quantity + quantity
                    if total_qty > 0:
                        holding.avg_cost_price = (
                            holding.quantity * holding.avg_cost_price + quantity * price
                        ) / total_qty
                    holding.quantity = total_qty
                    holding.updated_at = datetime.now(timezone.utc)

            elif tx_type == "sell" and holding is not None:
                holding.quantity -= quantity
                holding.updated_at = datetime.now(timezone.utc)
                if holding.quantity <= 0:
                    await db.delete(holding)

            elif tx_type == "reward":
                if holding is None:
                    holding = Holding(
                        id=uuid.uuid4(), user_id=current_user.id, asset_id=asset.id,
                        quantity=quantity, avg_cost_price=Decimal("0"), currency=currency,
                        updated_at=datetime.now(timezone.utc),
                    )
                    db.add(holding)
                else:
                    holding.quantity += quantity
                    holding.updated_at = datetime.now(timezone.utc)

            await db.flush()
            imported += 1

        except Exception as exc:
            errors.append({"row": row, "error": str(exc)})

    await db.commit()
    logger.info("Import confirm: imported=%d errors=%d user=%s", imported, len(errors), current_user.id)
    return ConfirmResponse(imported=imported, errors=errors)
```

- [ ] **Step 4: Update portfolio service**

Replace `backend/app/services/portfolio.py` entirely:

```python
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.transaction import Transaction

logger = get_logger(__name__)


async def add_holding(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str,
    asset_type: str,
    quantity: Decimal,
    avg_cost_price: Decimal,
    currency: str,
    purchased_at: date | None = None,
) -> tuple[Holding, Asset]:
    symbol = symbol.strip().upper()
    result = await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.symbol == symbol)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        asset = Asset(
            id=uuid.uuid4(), user_id=user_id, symbol=symbol,
            asset_type=asset_type, name=symbol, currency=currency, metadata_={},
        )
        db.add(asset)
        await db.flush()

    holding = Holding(
        id=uuid.uuid4(), user_id=user_id, asset_id=asset.id,
        quantity=quantity, avg_cost_price=avg_cost_price,
        currency=currency, purchased_at=purchased_at,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    logger.info("Holding added: symbol=%s qty=%s user=%s", symbol, quantity, user_id)
    return holding, asset


async def list_holdings_with_assets(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(Holding, Asset)
        .join(Asset, Asset.id == Holding.asset_id)
        .where(Holding.user_id == user_id)
    )
    rows = []
    for holding, asset in result.all():
        total_cost = holding.quantity * holding.avg_cost_price
        rows.append({
            "id": holding.id,
            "asset_id": holding.asset_id,
            "symbol": asset.symbol,
            "asset_type": asset.asset_type,
            "currency": holding.currency,
            "purchased_at": holding.purchased_at,
            "outstanding_shares": holding.quantity,
            "cost_per_share": holding.avg_cost_price,
            "total_cost": total_cost,
            "current_price": None,
            "holding_value": None,
            "unrealized_pnl": None,
            "price_1d_change": None,
        })
    return rows


async def get_holding(db: AsyncSession, user_id: uuid.UUID, holding_id: uuid.UUID) -> Holding | None:
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_holding(db: AsyncSession, holding: Holding) -> None:
    logger.info("Holding deleted: id=%s user=%s", holding.id, holding.user_id)
    await db.delete(holding)
    await db.commit()


async def add_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    type_: str,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal,
    executed_at: datetime,
    platform: str | None = None,
    source: str = "manual",
) -> Transaction:
    tx = Transaction(
        id=uuid.uuid4(), user_id=user_id, asset_id=asset_id,
        platform=platform, type=type_, quantity=quantity,
        price=price, fee=fee, source=source, executed_at=executed_at,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    logger.info("Transaction added: type=%s asset=%s user=%s", type_, asset_id, user_id)
    return tx


async def list_transactions(
    db: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID | None = None
) -> list[Transaction]:
    q = select(Transaction).where(Transaction.user_id == user_id)
    if asset_id:
        q = q.where(Transaction.asset_id == asset_id)
    result = await db.execute(q.order_by(Transaction.executed_at.desc()))
    return list(result.scalars().all())


async def get_portfolio_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    rows = await list_holdings_with_assets(db, user_id)
    total_cost = sum(r["total_cost"] for r in rows)
    return {"holdings_count": len(rows), "total_cost": total_cost, "primary_currency": "THB"}
```

- [ ] **Step 5: Update portfolio API**

**First:** Read `backend/app/api/portfolio.py` and copy the full body of the `/export` endpoint (it produces a streaming CSV). Include it unchanged at the bottom of the new file.

Replace `backend/app/api/portfolio.py` with the following skeleton (keeping only the needed endpoints, removing old CSV import routes, and appending the copied `/export` endpoint):

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.asset import Asset
from app.models.user import User
from app.schemas.holding import HoldingCreate, HoldingRow, PortfolioSummary
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.services import portfolio as portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/holdings", response_model=HoldingRow, status_code=201)
async def add_holding(
    body: HoldingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holding, asset = await portfolio_service.add_holding(
        db, current_user.id, body.symbol, body.asset_type,
        body.quantity, body.avg_cost_price, body.currency, body.purchased_at,
    )
    total_cost = holding.quantity * holding.avg_cost_price
    return HoldingRow(
        id=holding.id, asset_id=holding.asset_id,
        symbol=asset.symbol, asset_type=asset.asset_type,
        currency=holding.currency, purchased_at=holding.purchased_at,
        outstanding_shares=holding.quantity, cost_per_share=holding.avg_cost_price,
        total_cost=total_cost,
    )


@router.get("/holdings", response_model=list[HoldingRow])
async def list_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await portfolio_service.list_holdings_with_assets(db, current_user.id)
    return [HoldingRow(**r) for r in rows]


@router.delete("/holdings/{holding_id}", status_code=204)
async def delete_holding(
    holding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holding = await portfolio_service.get_holding(db, current_user.id, holding_id)
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    await portfolio_service.delete_holding(db, holding)
    return Response(status_code=204)


@router.post("/transactions", response_model=TransactionResponse, status_code=201)
async def add_transaction(
    body: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.add_transaction(
        db, current_user.id, body.asset_id, body.type,
        body.quantity, body.price, body.fee, body.executed_at, body.platform,
    )


@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    asset_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.list_transactions(db, current_user.id, asset_id)


@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.get_portfolio_summary(db, current_user.id)
```

- [ ] **Step 6: Update TransactionCreate schema**

Open `backend/app/schemas/transaction.py` and replace `platform_id: uuid.UUID | None = None` with `platform: str | None = None`. Also ensure `TransactionResponse` doesn't reference `platform_id`.

The updated `TransactionCreate`:
```python
class TransactionCreate(BaseModel):
    asset_id: uuid.UUID
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal = Decimal("0")
    executed_at: datetime
    platform: str | None = None
```

The updated `TransactionResponse` (remove `platform_id`, add `platform`):
```python
class TransactionResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    platform: str | None
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    source: str
    executed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 7: Run all import/portfolio tests**

```bash
docker compose exec backend pytest tests/test_import_upload.py tests/test_portfolio.py -v
```

Expected: all tests pass. Fix any failures before continuing.

---

## Task 6: Frontend — Import Service & Page

**Files:**
- Modify: `frontend/lib/services/import-pipeline.ts`
- Create: `frontend/components/import/ReviewTable.tsx`
- Modify: `frontend/app/(auth)/import/page.tsx`

- [ ] **Step 1: Replace import-pipeline.ts**

Replace `frontend/lib/services/import-pipeline.ts` entirely:

```typescript
export interface CanonicalRow {
  trade_date: string | null;
  type: string | null;
  symbol: string | null;
  unit: string | null;
  price: string | null;
  currency: string | null;
  exchange: string | null;
  gross_amount: string | null;
  fee: string | null;
  gross_thb: string | null;
  fee_thb: string | null;
  exchange_rate: string | null;
  asset_type: string | null;
  platform: string | null;
  notes: string | null;
  [key: string]: unknown;
}

export interface UploadResponse {
  rows: CanonicalRow[];
  method: "direct" | "llm_translated";
  total: number;
}

function authHeader(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
  return { Authorization: `Bearer ${token}` };
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch("/api/v1/import/upload", {
    method: "POST",
    headers: authHeader(),
    body: form,
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Upload failed");
  }
  return r.json();
}

export async function confirmImport(
  rows: CanonicalRow[]
): Promise<{ imported: number; errors: unknown[] }> {
  const r = await fetch("/api/v1/import/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({ rows }),
  });
  if (!r.ok) throw new Error("Confirm failed");
  return r.json();
}
```

- [ ] **Step 2: Create ReviewTable component**

Create `frontend/components/import/ReviewTable.tsx`:

```tsx
"use client";

import { CanonicalRow } from "@/lib/services/import-pipeline";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const REQUIRED_FIELDS = ["trade_date", "type", "symbol", "unit"] as const;
const VISIBLE_FIELDS = [
  "trade_date", "type", "symbol", "unit", "price",
  "currency", "asset_type", "platform", "fee", "notes",
] as const;

interface Props {
  rows: CanonicalRow[];
  onChange: (rows: CanonicalRow[]) => void;
}

export function ReviewTable({ rows, onChange }: Props) {
  function handleChange(rowIdx: number, field: string, value: string) {
    const updated = rows.map((r, i) =>
      i === rowIdx ? { ...r, [field]: value || null } : r
    );
    onChange(updated);
  }

  function isMissing(row: CanonicalRow, field: string): boolean {
    return (REQUIRED_FIELDS as readonly string[]).includes(field) && !row[field];
  }

  return (
    <div className="overflow-auto max-h-[60vh] rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            {VISIBLE_FIELDS.map((f) => (
              <TableHead key={f} className="whitespace-nowrap text-xs">
                {f}{(REQUIRED_FIELDS as readonly string[]).includes(f) ? " *" : ""}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
              {VISIBLE_FIELDS.map((f) => (
                <TableCell key={f} className="p-1">
                  <Input
                    className={`h-7 text-xs min-w-[80px] ${isMissing(row, f) ? "border-destructive" : ""}`}
                    value={(row[f] as string) ?? ""}
                    onChange={(e) => handleChange(i, f, e.target.value)}
                  />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [ ] **Step 3: Replace import page**

Replace `frontend/app/(auth)/import/page.tsx` entirely:

```tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { CheckCircle, Upload } from "lucide-react";
import { ReviewTable } from "@/components/import/ReviewTable";
import {
  CanonicalRow,
  confirmImport,
  uploadFile,
} from "@/lib/services/import-pipeline";

type Step = "idle" | "uploading" | "review" | "confirming" | "done";

export default function ImportPage() {
  const [step, setStep] = useState<Step>("idle");
  const [rows, setRows] = useState<CanonicalRow[]>([]);
  const [method, setMethod] = useState<"direct" | "llm_translated">("direct");
  const [result, setResult] = useState<{ imported: number; errors: unknown[] } | null>(null);

  async function handleFile(file: File) {
    setStep("uploading");
    try {
      const res = await uploadFile(file);
      setRows(res.rows);
      setMethod(res.method);
      setStep("review");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
      setStep("idle");
    }
  }

  async function handleConfirm() {
    setStep("confirming");
    try {
      const res = await confirmImport(rows);
      setResult(res);
      setStep("done");
      toast.success(`Imported ${res.imported} transactions`);
    } catch {
      toast.error("Import failed");
      setStep("review");
    }
  }

  function reset() {
    setStep("idle");
    setRows([]);
    setResult(null);
  }

  if (step === "done" && result) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16">
        <CheckCircle className="h-12 w-12 text-green-500" />
        <p className="text-xl font-semibold">Import complete</p>
        <p className="text-muted-foreground">{result.imported} transactions imported</p>
        {(result.errors as unknown[]).length > 0 && (
          <p className="text-destructive text-sm">
            {(result.errors as unknown[]).length} rows had errors
          </p>
        )}
        <Button onClick={reset}>Import another file</Button>
      </div>
    );
  }

  if (step === "review" || step === "confirming") {
    return (
      <div className="space-y-4 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">
              Review {rows.length} transactions
            </h2>
            {method === "llm_translated" && (
              <p className="text-sm text-muted-foreground">
                Fields were translated by AI — please verify before importing.
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={reset} disabled={step === "confirming"}>
              Cancel
            </Button>
            <Button onClick={handleConfirm} disabled={step === "confirming"}>
              {step === "confirming" ? "Importing…" : "Confirm Import"}
            </Button>
          </div>
        </div>
        <ReviewTable rows={rows} onChange={setRows} />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-6 py-16 px-6">
      <h1 className="text-2xl font-bold">Import Transactions</h1>
      <p className="text-muted-foreground text-center max-w-md">
        Upload a CSV or JSON file. If the headers match the canonical format they
        import directly. Other formats are translated by AI.
      </p>
      <div
        className="border-2 border-dashed rounded-xl p-12 flex flex-col items-center gap-4
                   cursor-pointer hover:border-primary transition-colors w-full max-w-md"
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files[0];
          if (f) handleFile(f);
        }}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <Upload className="h-10 w-10 text-muted-foreground" />
        <p className="text-sm text-muted-foreground text-center">
          {step === "uploading"
            ? "Processing…"
            : "Drop CSV or JSON here, or click to browse"}
        </p>
        <input
          id="file-input"
          type="file"
          accept=".csv,.json"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Canonical fields: trade_date · type · symbol · unit · price · currency ·
        asset_type · platform · fee · notes · …
      </p>
    </div>
  );
}
```

---

## Task 7: Frontend — Portfolio Table, Currency Fix & Add Holding

**Files:**
- Modify: `frontend/lib/services/portfolio.ts`
- Modify: `frontend/components/portfolio/HoldingsTable.tsx`
- Modify: `frontend/components/portfolio/AddHoldingDialog.tsx`
- Modify: `frontend/app/(auth)/portfolio/page.tsx`
- Delete: `frontend/components/portfolio/ImportDrawer.tsx`

- [ ] **Step 1: Update portfolio.ts types and remove old CSV import functions**

Replace `frontend/lib/services/portfolio.ts` entirely:

```typescript
import { api } from "@/lib/api";

export interface HoldingRow {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  currency: string;
  purchased_at: string | null;
  outstanding_shares: string;
  cost_per_share: string;
  total_cost: string;
  current_price: string | null;
  holding_value: string | null;
  unrealized_pnl: string | null;
  price_1d_change: string | null;
}

export interface Transaction {
  id: string;
  asset_id: string;
  platform: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  created_at: string;
}

export interface PortfolioSummary {
  holdings_count: number;
  total_cost: string;
  primary_currency: string;
}

export async function fetchHoldings(): Promise<HoldingRow[]> {
  const res = await api.get("/api/v1/portfolio/holdings");
  if (!res.ok) throw new Error("Failed to fetch holdings");
  return res.json();
}

export async function addHolding(body: {
  symbol: string;
  asset_type: string;
  purchased_at: string | null;
  quantity: string;
  avg_cost_price: string;
  currency: string;
}): Promise<HoldingRow> {
  const res = await api.post("/api/v1/portfolio/holdings", body);
  if (!res.ok) throw new Error("Failed to add holding");
  return res.json();
}

export async function deleteHolding(id: string): Promise<void> {
  await api.delete(`/api/v1/portfolio/holdings/${id}`);
}

export async function fetchSummary(): Promise<PortfolioSummary> {
  const res = await api.get("/api/v1/portfolio/summary");
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}
```

- [ ] **Step 2: Replace HoldingsTable.tsx**

Replace `frontend/components/portfolio/HoldingsTable.tsx` entirely:

```tsx
"use client";

import {
  ColumnDef, flexRender, getCoreRowModel, useReactTable,
} from "@tanstack/react-table";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import { HoldingRow } from "@/lib/services/portfolio";
import { PrivacyValue } from "@/components/ui/PrivacyValue";

interface Props {
  holdings: HoldingRow[];
  primaryCurrency: string;
  onDelete: (id: string) => void;
}

export function HoldingsTable({ holdings, primaryCurrency, onDelete }: Props) {
  function fmtMoney(val: string | null | undefined): string {
    if (val == null) return "—";
    return `${primaryCurrency} ${Number(val).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  const columns: ColumnDef<HoldingRow>[] = [
    {
      accessorKey: "symbol",
      header: "Symbol / Fund Code",
    },
    {
      accessorKey: "outstanding_shares",
      header: "Outstanding Shares",
      cell: ({ row }) => Number(row.original.outstanding_shares).toLocaleString(),
    },
    {
      accessorKey: "cost_per_share",
      header: "Cost per Share",
      cell: ({ row }) => <PrivacyValue value={fmtMoney(row.original.cost_per_share)} />,
    },
    {
      accessorKey: "total_cost",
      header: "Total Cost",
      cell: ({ row }) => <PrivacyValue value={fmtMoney(row.original.total_cost)} />,
    },
    {
      accessorKey: "current_price",
      header: "Current Price",
      cell: ({ row }) =>
        row.original.current_price ? fmtMoney(row.original.current_price) : "—",
    },
    {
      accessorKey: "price_1d_change",
      header: "Price & 1D Change",
      cell: () => "—",
    },
    {
      accessorKey: "holding_value",
      header: "Holding Value",
      cell: ({ row }) =>
        row.original.holding_value
          ? <PrivacyValue value={fmtMoney(row.original.holding_value)} />
          : "—",
    },
    {
      accessorKey: "unrealized_pnl",
      header: "Unrealized P/L",
      cell: ({ row }) =>
        row.original.unrealized_pnl
          ? <PrivacyValue value={fmtMoney(row.original.unrealized_pnl)} />
          : "—",
    },
    {
      id: "actions",
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onDelete(row.original.id)}
        >
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      ),
    },
  ];

  const table = useReactTable({
    data: holdings,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((hg) => (
            <TableRow key={hg.id}>
              {hg.headers.map((h) => (
                <TableHead key={h.id}>
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                className="text-center text-muted-foreground py-8"
              >
                No holdings. Add one or import from the Import page.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [ ] **Step 3: Replace AddHoldingDialog.tsx**

Replace `frontend/components/portfolio/AddHoldingDialog.tsx` entirely:

```tsx
"use client";

import { useMemo, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { addHolding } from "@/lib/services/portfolio";
import { Plus } from "lucide-react";

const ASSET_TYPES = [
  "us_stock", "thai_stock", "th_fund", "etf", "crypto", "gold", "cash",
];

interface Props {
  primaryCurrency: string;
  onAdded: () => void;
}

export function AddHoldingDialog({ primaryCurrency, onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [assetType, setAssetType] = useState("us_stock");
  const [purchasedAt, setPurchasedAt] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [currency, setCurrency] = useState(primaryCurrency);
  const [loading, setLoading] = useState(false);

  const totalCost = useMemo(() => {
    const q = parseFloat(quantity);
    const c = parseFloat(avgCost);
    if (!isNaN(q) && !isNaN(c)) return (q * c).toLocaleString(undefined, { minimumFractionDigits: 2 });
    return "—";
  }, [quantity, avgCost]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await addHolding({
        symbol,
        asset_type: assetType,
        purchased_at: purchasedAt || null,
        quantity,
        avg_cost_price: avgCost,
        currency,
      });
      toast.success(`Added ${symbol} to portfolio`);
      setOpen(false);
      setSymbol(""); setQuantity(""); setAvgCost(""); setPurchasedAt("");
      onAdded();
    } catch {
      toast.error("Failed to add holding");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="h-4 w-4 mr-1" />
          Add Holding
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Holding</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Symbol</Label>
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="AAPL"
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Asset Type</Label>
              <Select value={assetType} onValueChange={setAssetType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ASSET_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>First Purchase Date (optional)</Label>
            <Input
              type="date"
              value={purchasedAt}
              onChange={(e) => setPurchasedAt(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Outstanding Shares</Label>
              <Input
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="10"
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Cost per Share</Label>
              <Input
                value={avgCost}
                onChange={(e) => setAvgCost(e.target.value)}
                placeholder="150.00"
                required
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Currency</Label>
            <Input
              value={currency}
              onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              placeholder="THB"
            />
          </div>
          <div className="rounded-md bg-muted px-3 py-2 text-sm flex justify-between">
            <span className="text-muted-foreground">Total Cost</span>
            <span className="font-medium">{currency} {totalCost}</span>
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Adding…" : "Add Holding"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Update portfolio page**

Open `frontend/app/(auth)/portfolio/page.tsx`. Read the file first, then make these targeted changes:

  a. Remove the import for `ImportDrawer` and any `previewImport`/`confirmImport` imports from portfolio service.

  b. Remove the "Import CSV" button and `<ImportDrawer />` element.

  c. Add `primaryCurrency` state fetched from `GET /api/v1/settings/display`. Add at the top:
  ```tsx
  const [primaryCurrency, setPrimaryCurrency] = useState("THB");

  useEffect(() => {
    api.get("/api/v1/settings/display")
      .then((r) => r.json())
      .then((d) => setPrimaryCurrency(d.currency_primary))
      .catch(() => {});
  }, []);
  ```

  d. Pass `primaryCurrency` to `HoldingsTable` and `AddHoldingDialog`:
  ```tsx
  <HoldingsTable holdings={holdings} primaryCurrency={primaryCurrency} onDelete={handleDelete} />
  <AddHoldingDialog primaryCurrency={primaryCurrency} onAdded={loadHoldings} />
  ```

  e. Remove `assetMap` prop from `HoldingsTable` (it now has `symbol` directly on each row).

- [ ] **Step 5: Delete ImportDrawer**

```bash
rm frontend/components/portfolio/ImportDrawer.tsx
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd frontend
npm run build 2>&1 | tail -20
```

Expected: no TypeScript errors. Fix any type errors before continuing.

---

## Task 8: Frontend — Settings Page Cleanup & Save Button Fix

**Files:**
- Delete: `frontend/components/settings/PlatformsManager.tsx`
- Delete: `frontend/lib/services/platforms.ts`
- Modify: `frontend/app/(auth)/settings/page.tsx`

- [ ] **Step 1: Delete PlatformsManager and platforms service**

```bash
rm frontend/components/settings/PlatformsManager.tsx
rm frontend/lib/services/platforms.ts
```

- [ ] **Step 2: Read settings page to understand current structure**

Run: `cat "frontend/app/(auth)/settings/page.tsx"`

Then make these changes:

  a. Remove the import for `PlatformsManager` and any import from `platforms` service.

  b. Remove the `<PlatformsManager />` JSX element and its surrounding section/card.

  c. Find the Display Currency Save button. It likely looks like:
  ```tsx
  <Button onClick={handleSave}>Save</Button>
  ```
  Replace with a button that has hover feedback and calls the save handler with toast:

  ```tsx
  <Button
    onClick={async () => {
      try {
        await api.patch("/api/v1/settings/display", {
          currency_primary: primaryCurrency,
          currency_secondary: secondaryCurrency,
        });
        toast.success("Display settings saved");
      } catch {
        toast.error("Failed to save settings");
      }
    }}
    className="hover:bg-primary/90 active:scale-95 transition-all cursor-pointer"
  >
    Save
  </Button>
  ```

  If the page uses a different `handleSave` function, wrap the existing call with `toast.success` / `toast.error` instead of inlining.

  d. Ensure `import { toast } from "sonner"` is present at the top.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend
npm run build 2>&1 | tail -20
```

Expected: no errors referencing PlatformsManager or platforms service.

- [ ] **Step 4: Manual smoke test**

Start the dev stack and verify:

1. Settings page → Display Currency section: hover Save button shows visual feedback, clicking shows toast.
2. Portfolio page: table shows Symbol, Outstanding Shares, Cost per Share, Total Cost columns; monetary values show THB (not $); no "Import CSV" button.
3. Add Holding dialog: fields are Symbol, Asset Type, First Purchase Date, Outstanding Shares, Cost per Share, Currency; Total Cost auto-calculates.
4. Import page: drag-drop zone with no platform selector; uploading a canonical CSV shows Review table; uploading a non-canonical file triggers LLM then shows Review table.
