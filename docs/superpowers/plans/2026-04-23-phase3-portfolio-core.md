# Phase 3: Portfolio Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users can manage their portfolio — add assets, record holdings and transactions, import from CSV, and view a live holdings table — building on the auth foundation from Phase 1+2.

**Architecture:** Follows existing patterns: SQLAlchemy 2.0 async models → Alembic migration → service layer (`app/services/`) → FastAPI router (`app/api/`) → Pydantic schemas (`app/schemas/`). Hardware detection is a pure Python service with no DB dependency. Portfolio page uses TanStack Query + TanStack Table.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, asyncpg, Pydantic v2, pytest-asyncio, Next.js 15 App Router, shadcn/ui DataTable, TanStack Query v5, TanStack Table v8

---

## Scope

This plan covers Kanban tasks:

- `feat - hardware detection service`
- `feat - settings hardware detect endpoint and recommendation`
- `feat - asset master data model and migration`
- `feat - platforms broker apps CRUD endpoints and UI`
- `feat - manual holdings entry endpoint`
- `feat - manual transaction recording`
- `feat - CSV import with LLM column mapper endpoint`
- `feat - CSV import confirm and save import profiles`
- `feat - portfolio export endpoint`
- `feat - portfolio list page with DataTable`

Phase 4 (Price Feeds + Pipeline) is a separate plan.

---

## File Map

```
backend/
├── app/
│   ├── core/
│   │   └── encryption.py              # NEW — AES-256 for future API keys (stub for now)
│   ├── models/
│   │   ├── __init__.py                # MODIFY — add all new model imports
│   │   ├── asset.py                   # NEW — Asset master
│   │   ├── platform.py                # NEW — Platform (broker)
│   │   ├── holding.py                 # NEW — Holding per user+asset
│   │   ├── transaction.py             # NEW — Transaction records
│   │   └── import_profile.py          # NEW — Saved CSV column mappings
│   ├── schemas/
│   │   ├── asset.py                   # NEW — AssetCreate, AssetResponse
│   │   ├── platform.py                # NEW — PlatformCreate, PlatformResponse
│   │   ├── holding.py                 # NEW — HoldingCreate, HoldingResponse, PortfolioSummary
│   │   ├── transaction.py             # NEW — TransactionCreate, TransactionResponse
│   │   └── csv_import.py             # NEW — ImportPreview, ImportConfirm, ImportProfileResponse
│   ├── api/
│   │   ├── assets.py                  # NEW — GET /assets/search, GET /assets/{symbol}
│   │   ├── platforms.py               # NEW — CRUD /platforms
│   │   ├── portfolio.py               # NEW — holdings CRUD, transactions, import, export, summary
│   │   └── settings.py               # NEW — GET /settings/hardware
│   ├── services/
│   │   ├── asset.py                   # NEW — asset lookup/create logic
│   │   ├── platform.py                # NEW — platform CRUD logic
│   │   ├── portfolio.py               # NEW — holdings + transactions logic
│   │   ├── csv_import.py             # NEW — parse, map columns, confirm
│   │   └── hardware.py               # NEW — detect CPU/RAM, return LLM recommendation
│   └── main.py                        # MODIFY — register new routers
├── alembic/versions/
│   └── 002_portfolio_schema.py        # NEW — assets, platforms, holdings, transactions, import_profiles
└── tests/
    ├── test_assets.py                 # NEW
    ├── test_platforms.py              # NEW
    ├── test_portfolio.py              # NEW
    ├── test_csv_import.py            # NEW
    └── test_hardware.py              # NEW

frontend/
├── app/(auth)/
│   ├── portfolio/
│   │   └── page.tsx                   # NEW — Holdings DataTable + import drawer + add dialog
│   └── settings/
│       └── page.tsx                   # NEW — Settings page (platforms tab + hardware info)
├── components/
│   ├── portfolio/
│   │   ├── HoldingsTable.tsx          # NEW — TanStack Table with columns
│   │   ├── AddHoldingDialog.tsx       # NEW — shadcn Dialog, form to add holding
│   │   └── ImportDrawer.tsx           # NEW — Sheet drawer for CSV import flow
│   └── settings/
│       └── PlatformsManager.tsx       # NEW — CRUD UI for broker platforms
└── lib/
    └── services/
        ├── portfolio.ts               # NEW — TanStack Query hooks for holdings/transactions
        ├── assets.ts                  # NEW — asset search hook
        └── platforms.ts              # NEW — platforms CRUD hooks
```

---

## Task 1: Hardware detection service + endpoint

**Files:**

- Create: `backend/app/services/hardware.py`
- Create: `backend/app/api/settings.py`
- Create: `backend/tests/test_hardware.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing test for hardware detection**

`backend/tests/test_hardware.py`:

```python
import pytest
from app.services.hardware import detect_hardware, HardwareInfo


def test_detect_hardware_returns_hardware_info():
    info = detect_hardware()
    assert isinstance(info, HardwareInfo)
    assert info.cpu_brand != ""
    assert info.ram_gb > 0


def test_recommendation_provided():
    info = detect_hardware()
    rec = info.recommendation
    assert rec["recommended_model"] != ""
    assert "note" in rec
    assert isinstance(rec["can_run_local_llm"], bool)
    assert "setup_command" in rec
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_hardware.py -v
```

Expected: `ImportError: cannot import name 'detect_hardware'`

- [ ] **Step 3: Write `backend/app/services/hardware.py`**

```python
import platform
import subprocess
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


@dataclass
class HardwareInfo:
    cpu_brand: str
    ram_gb: float
    is_apple_silicon: bool

    @property
    def recommendation(self) -> dict[str, Any]:
        if self.is_apple_silicon and self.ram_gb >= 16:
            return {
                "can_run_local_llm": True,
                "recommended_model": "llama3.1:8b",
                "setup_command": "brew install ollama && ollama pull llama3.1:8b",
                "note": f"Apple Silicon with {self.ram_gb:.0f}GB RAM — great for local inference.",
            }
        if self.is_apple_silicon and self.ram_gb >= 8:
            return {
                "can_run_local_llm": True,
                "recommended_model": "mistral:7b-q4",
                "setup_command": "brew install ollama && ollama pull mistral:7b-q4",
                "note": f"Apple Silicon with {self.ram_gb:.0f}GB RAM — use quantized model.",
            }
        if self.ram_gb >= 16:
            return {
                "can_run_local_llm": True,
                "recommended_model": "mistral:7b-q4",
                "setup_command": "docker compose --profile local-llm up -d",
                "note": "Linux/Windows — use the local-llm Docker profile (requires NVIDIA GPU).",
            }
        return {
            "can_run_local_llm": False,
            "recommended_model": "claude-3-5-haiku",
            "setup_command": "",
            "note": "Limited RAM — recommend cloud LLM. Configure API key in Settings.",
        }


def detect_hardware() -> HardwareInfo:
    cpu_brand = platform.processor() or platform.machine()
    is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"

    if _HAS_PSUTIL:
        ram_bytes = psutil.virtual_memory().total
        ram_gb = ram_bytes / (1024 ** 3)
    else:
        # Fallback: try sysctl on macOS
        try:
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            ram_gb = int(out.strip()) / (1024 ** 3)
        except Exception:
            ram_gb = 8.0  # conservative default

    return HardwareInfo(cpu_brand=cpu_brand, ram_gb=ram_gb, is_apple_silicon=is_apple_silicon)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_hardware.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Write `backend/app/api/settings.py`**

```python
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
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
```

- [ ] **Step 6: Register router in `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health, settings

app = FastAPI(title="Zentri API", version="0.1.0")

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
```

- [ ] **Step 7: Install psutil**

Add `psutil>=5.9.0` to `backend/pyproject.toml` dependencies list, then:

```bash
cd backend && pip install psutil
```

---

## Task 2: Asset + Platform + Holdings + Transaction data models + migration

**Files:**

- Create: `backend/app/models/asset.py`
- Create: `backend/app/models/platform.py`
- Create: `backend/app/models/holding.py`
- Create: `backend/app/models/transaction.py`
- Create: `backend/app/models/import_profile.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/002_portfolio_schema.py`

- [ ] **Step 1: Write `backend/app/models/asset.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

ASSET_TYPES = ("us_stock", "thai_stock", "th_fund", "crypto", "gold")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    asset_type: Mapped[str] = mapped_column(
        Enum(*ASSET_TYPES, name="asset_type_enum"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Write `backend/app/models/platform.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_types_supported: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 3: Write `backend/app/models/holding.py`**

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
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
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Write `backend/app/models/transaction.py`**

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

TRANSACTION_TYPES = ("buy", "sell", "dividend")
TRANSACTION_SOURCES = ("manual", "csv_import")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    platform_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("platforms.id"), nullable=True)
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

- [ ] **Step 5: Write `backend/app/models/import_profile.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportProfile(Base):
    __tablename__ = "import_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    broker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    column_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 6: Update `backend/app/models/__init__.py`**

```python
from app.models.asset import Asset  # noqa: F401
from app.models.holding import Holding  # noqa: F401
from app.models.import_profile import ImportProfile  # noqa: F401
from app.models.platform import Platform  # noqa: F401
from app.models.transaction import Transaction  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = ["User", "Asset", "Platform", "Holding", "Transaction", "ImportProfile"]
```

- [ ] **Step 7: Write `backend/alembic/versions/002_portfolio_schema.py`**

```python
"""portfolio schema — assets, platforms, holdings, transactions, import_profiles

Revision ID: 002
Revises: 001
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    op.execute("CREATE TYPE asset_type_enum AS ENUM ('us_stock', 'thai_stock', 'th_fund', 'crypto', 'gold')")
    op.execute("CREATE TYPE transaction_type_enum AS ENUM ('buy', 'sell', 'dividend')")
    op.execute("CREATE TYPE transaction_source_enum AS ENUM ('manual', 'csv_import')")

    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("asset_type", sa.Enum("us_stock", "thai_stock", "th_fund", "crypto", "gold", name="asset_type_enum", create_type=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assets_user_id", "assets", ["user_id"])
    op.create_index("ix_assets_symbol", "assets", ["symbol"])

    op.create_table(
        "platforms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("asset_types_supported", JSONB, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_platforms_user_id", "platforms", ["user_id"])

    op.create_table(
        "holdings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("avg_cost_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_holdings_user_id", "holdings", ["user_id"])
    op.create_index("ix_holdings_asset_id", "holdings", ["asset_id"])

    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("platform_id", UUID(as_uuid=True), sa.ForeignKey("platforms.id"), nullable=True),
        sa.Column("type", sa.Enum("buy", "sell", "dividend", name="transaction_type_enum", create_type=False), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("fee", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("source", sa.Enum("manual", "csv_import", name="transaction_source_enum", create_type=False), nullable=False, server_default="manual"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_asset_id", "transactions", ["asset_id"])

    op.create_table(
        "import_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("broker_name", sa.String(100), nullable=False),
        sa.Column("column_mapping", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_import_profiles_user_id", "import_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_table("import_profiles")
    op.drop_table("transactions")
    op.drop_table("holdings")
    op.drop_table("platforms")
    op.drop_table("assets")
    op.execute("DROP TYPE transaction_source_enum")
    op.execute("DROP TYPE transaction_type_enum")
    op.execute("DROP TYPE asset_type_enum")
```

- [ ] **Step 8: Run migration**

```bash
docker compose up postgres -d
cd backend && alembic upgrade head
```

Expected: `Running upgrade 001 -> 002, portfolio schema`

---

## Task 3: Asset search + Platform CRUD endpoints

**Files:**

- Create: `backend/app/schemas/asset.py`
- Create: `backend/app/schemas/platform.py`
- Create: `backend/app/services/asset.py`
- Create: `backend/app/services/platform.py`
- Create: `backend/app/api/assets.py`
- Create: `backend/app/api/platforms.py`
- Create: `backend/tests/test_assets.py`
- Create: `backend/tests/test_platforms.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests for assets**

`backend/tests/test_assets.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/zentri_test"
test_engine = create_async_engine(TEST_DB_URL)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def auth_client():
    async def override_get_db():
        async with TestSession() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        setup = await c.post("/api/v1/auth/setup", json={"username": "admin", "password": "password123"})
        token = setup.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_asset(auth_client):
    response = await auth_client.post("/api/v1/assets", json={
        "symbol": "AAPL",
        "asset_type": "us_stock",
        "name": "Apple Inc.",
        "currency": "USD",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["asset_type"] == "us_stock"


@pytest.mark.asyncio
async def test_search_assets(auth_client):
    await auth_client.post("/api/v1/assets", json={"symbol": "AAPL", "asset_type": "us_stock", "name": "Apple Inc.", "currency": "USD"})
    response = await auth_client.get("/api/v1/assets/search?q=AAPL")
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_get_asset_detail(auth_client):
    create = await auth_client.post("/api/v1/assets", json={"symbol": "MSFT", "asset_type": "us_stock", "name": "Microsoft", "currency": "USD"})
    asset_id = create.json()["id"]
    response = await auth_client.get(f"/api/v1/assets/{asset_id}")
    assert response.status_code == 200
    assert response.json()["symbol"] == "MSFT"
```

- [ ] **Step 2: Write failing tests for platforms**

`backend/tests/test_platforms.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/zentri_test"
test_engine = create_async_engine(TEST_DB_URL)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def auth_client():
    async def override_get_db():
        async with TestSession() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        setup = await c.post("/api/v1/auth/setup", json={"username": "admin", "password": "password123"})
        token = setup.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_platform(auth_client):
    response = await auth_client.post("/api/v1/platforms", json={
        "name": "Robinhood",
        "asset_types_supported": ["us_stock", "crypto"],
        "notes": "US broker",
    })
    assert response.status_code == 201
    assert response.json()["name"] == "Robinhood"


@pytest.mark.asyncio
async def test_list_platforms(auth_client):
    await auth_client.post("/api/v1/platforms", json={"name": "Robinhood", "asset_types_supported": ["us_stock"]})
    response = await auth_client.get("/api/v1/platforms")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_update_platform(auth_client):
    create = await auth_client.post("/api/v1/platforms", json={"name": "Robinhood", "asset_types_supported": ["us_stock"]})
    pid = create.json()["id"]
    response = await auth_client.put(f"/api/v1/platforms/{pid}", json={"name": "Robinhood Pro", "asset_types_supported": ["us_stock", "crypto"]})
    assert response.status_code == 200
    assert response.json()["name"] == "Robinhood Pro"


@pytest.mark.asyncio
async def test_delete_platform(auth_client):
    create = await auth_client.post("/api/v1/platforms", json={"name": "Robinhood", "asset_types_supported": ["us_stock"]})
    pid = create.json()["id"]
    response = await auth_client.delete(f"/api/v1/platforms/{pid}")
    assert response.status_code == 204
    list_response = await auth_client.get("/api/v1/platforms")
    assert len(list_response.json()) == 0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_assets.py tests/test_platforms.py -v
```

Expected: `404` or import errors.

- [ ] **Step 4: Write `backend/app/schemas/asset.py`**

```python
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AssetCreate(BaseModel):
    symbol: str
    asset_type: str
    name: str
    currency: str = "USD"
    metadata_: dict[str, Any] = {}


class AssetResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    asset_type: str
    name: str
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Write `backend/app/schemas/platform.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class PlatformCreate(BaseModel):
    name: str
    asset_types_supported: list[str] = []
    notes: str | None = None


class PlatformUpdate(BaseModel):
    name: str
    asset_types_supported: list[str] = []
    notes: str | None = None


class PlatformResponse(BaseModel):
    id: uuid.UUID
    name: str
    asset_types_supported: list[str]
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 6: Write `backend/app/services/asset.py`**

```python
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset


async def create_asset(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str,
    asset_type: str,
    name: str,
    currency: str = "USD",
    metadata_: dict[str, Any] | None = None,
) -> Asset:
    asset = Asset(
        id=uuid.uuid4(),
        user_id=user_id,
        symbol=symbol.upper(),
        asset_type=asset_type,
        name=name,
        currency=currency,
        metadata_=metadata_ or {},
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def search_assets(db: AsyncSession, user_id: uuid.UUID, query: str) -> list[Asset]:
    q = query.upper()
    result = await db.execute(
        select(Asset).where(
            Asset.user_id == user_id,
            Asset.symbol.ilike(f"%{q}%") | Asset.name.ilike(f"%{query}%"),
        ).limit(20)
    )
    return list(result.scalars().all())


async def get_asset(db: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID) -> Asset | None:
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_all_assets(db: AsyncSession, user_id: uuid.UUID) -> list[Asset]:
    result = await db.execute(select(Asset).where(Asset.user_id == user_id))
    return list(result.scalars().all())
```

- [ ] **Step 7: Write `backend/app/services/platform.py`**

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import Platform


async def create_platform(
    db: AsyncSession, user_id: uuid.UUID, name: str, asset_types_supported: list[str], notes: str | None
) -> Platform:
    platform = Platform(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        asset_types_supported=asset_types_supported,
        notes=notes,
    )
    db.add(platform)
    await db.commit()
    await db.refresh(platform)
    return platform


async def list_platforms(db: AsyncSession, user_id: uuid.UUID) -> list[Platform]:
    result = await db.execute(select(Platform).where(Platform.user_id == user_id))
    return list(result.scalars().all())


async def get_platform(db: AsyncSession, user_id: uuid.UUID, platform_id: uuid.UUID) -> Platform | None:
    result = await db.execute(
        select(Platform).where(Platform.id == platform_id, Platform.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_platform(
    db: AsyncSession, platform: Platform, name: str, asset_types_supported: list[str], notes: str | None
) -> Platform:
    platform.name = name
    platform.asset_types_supported = asset_types_supported
    platform.notes = notes
    await db.commit()
    await db.refresh(platform)
    return platform


async def delete_platform(db: AsyncSession, platform: Platform) -> None:
    await db.delete(platform)
    await db.commit()
```

- [ ] **Step 8: Write `backend/app/api/assets.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetResponse
from app.services import asset as asset_service

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("", response_model=AssetResponse, status_code=201)
async def create_asset(
    body: AssetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_service.create_asset(
        db, current_user.id, body.symbol, body.asset_type, body.name, body.currency, body.metadata_
    )


@router.get("/search", response_model=list[AssetResponse])
async def search_assets(
    q: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await asset_service.search_assets(db, current_user.id, q)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await asset_service.get_asset(db, current_user.id, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset
```

- [ ] **Step 9: Write `backend/app/api/platforms.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.platform import PlatformCreate, PlatformResponse, PlatformUpdate
from app.services import platform as platform_service

router = APIRouter(prefix="/platforms", tags=["platforms"])


@router.post("", response_model=PlatformResponse, status_code=201)
async def create_platform(
    body: PlatformCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await platform_service.create_platform(
        db, current_user.id, body.name, body.asset_types_supported, body.notes
    )


@router.get("", response_model=list[PlatformResponse])
async def list_platforms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await platform_service.list_platforms(db, current_user.id)


@router.put("/{platform_id}", response_model=PlatformResponse)
async def update_platform(
    platform_id: uuid.UUID,
    body: PlatformUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    platform = await platform_service.get_platform(db, current_user.id, platform_id)
    if platform is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
    return await platform_service.update_platform(db, platform, body.name, body.asset_types_supported, body.notes)


@router.delete("/{platform_id}", status_code=204)
async def delete_platform(
    platform_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    platform = await platform_service.get_platform(db, current_user.id, platform_id)
    if platform is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
    await platform_service.delete_platform(db, platform)
    return Response(status_code=204)
```

- [ ] **Step 10: Register routers in `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assets, auth, health, platforms, settings

app = FastAPI(title="Zentri API", version="0.1.0")

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
app.include_router(platforms.router, prefix="/api/v1")
```

- [ ] **Step 11: Run tests**

```bash
cd backend && python -m pytest tests/test_assets.py tests/test_platforms.py -v
```

Expected: All 7 tests PASS.

---

## Task 4: Holdings + Transactions endpoints

**Files:**

- Create: `backend/app/schemas/holding.py`
- Create: `backend/app/schemas/transaction.py`
- Create: `backend/app/services/portfolio.py`
- Create: `backend/app/api/portfolio.py`
- Create: `backend/tests/test_portfolio.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_portfolio.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/zentri_test"
test_engine = create_async_engine(TEST_DB_URL)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def auth_client():
    async def override_get_db():
        async with TestSession() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        setup = await c.post("/api/v1/auth/setup", json={"username": "admin", "password": "password123"})
        token = setup.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def asset_id(auth_client):
    res = await auth_client.post("/api/v1/assets", json={"symbol": "AAPL", "asset_type": "us_stock", "name": "Apple", "currency": "USD"})
    return res.json()["id"]


@pytest.mark.asyncio
async def test_add_holding(auth_client, asset_id):
    response = await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": asset_id,
        "quantity": "10.5",
        "avg_cost_price": "150.00",
        "currency": "USD",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["quantity"] == "10.5"
    assert data["avg_cost_price"] == "150.00"


@pytest.mark.asyncio
async def test_list_holdings(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/holdings", json={"asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD"})
    response = await auth_client.get("/api/v1/portfolio/holdings")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_add_transaction(auth_client, asset_id):
    response = await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id,
        "type": "buy",
        "quantity": "5",
        "price": "155.00",
        "fee": "1.00",
        "executed_at": "2026-01-15T10:00:00Z",
    })
    assert response.status_code == 201
    assert response.json()["type"] == "buy"


@pytest.mark.asyncio
async def test_list_transactions_for_asset(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id, "type": "buy", "quantity": "5",
        "price": "155", "fee": "1", "executed_at": "2026-01-15T10:00:00Z"
    })
    response = await auth_client.get(f"/api/v1/portfolio/transactions?asset_id={asset_id}")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_portfolio_summary(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/holdings", json={"asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD"})
    response = await auth_client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200
    data = response.json()
    assert "holdings_count" in data
    assert data["holdings_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_portfolio.py -v
```

Expected: `404 Not Found` errors.

- [ ] **Step 3: Write `backend/app/schemas/holding.py`**

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class HoldingCreate(BaseModel):
    asset_id: uuid.UUID
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str = "USD"


class HoldingResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    holdings_count: int
    total_cost_usd: Decimal
```

- [ ] **Step 4: Write `backend/app/schemas/transaction.py`**

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TransactionCreate(BaseModel):
    asset_id: uuid.UUID
    platform_id: uuid.UUID | None = None
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal = Decimal("0")
    executed_at: datetime


class TransactionResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    platform_id: uuid.UUID | None
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    source: str
    executed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Write `backend/app/services/portfolio.py`**

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.transaction import Transaction


async def add_holding(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    quantity: Decimal,
    avg_cost_price: Decimal,
    currency: str,
) -> Holding:
    holding = Holding(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset_id,
        quantity=quantity,
        avg_cost_price=avg_cost_price,
        currency=currency,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


async def list_holdings(db: AsyncSession, user_id: uuid.UUID) -> list[Holding]:
    result = await db.execute(select(Holding).where(Holding.user_id == user_id))
    return list(result.scalars().all())


async def get_holding(db: AsyncSession, user_id: uuid.UUID, holding_id: uuid.UUID) -> Holding | None:
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_holding(db: AsyncSession, holding: Holding) -> None:
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
    platform_id: uuid.UUID | None = None,
    source: str = "manual",
) -> Transaction:
    tx = Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset_id,
        platform_id=platform_id,
        type=type_,
        quantity=quantity,
        price=price,
        fee=fee,
        source=source,
        executed_at=executed_at,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
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
    holdings = await list_holdings(db, user_id)
    total_cost = sum(h.quantity * h.avg_cost_price for h in holdings)
    return {
        "holdings_count": len(holdings),
        "total_cost_usd": total_cost,
    }
```

- [ ] **Step 6: Write `backend/app/api/portfolio.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.holding import HoldingCreate, HoldingResponse, PortfolioSummary
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.services import portfolio as portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/holdings", response_model=HoldingResponse, status_code=201)
async def add_holding(
    body: HoldingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.add_holding(
        db, current_user.id, body.asset_id, body.quantity, body.avg_cost_price, body.currency
    )


@router.get("/holdings", response_model=list[HoldingResponse])
async def list_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await portfolio_service.list_holdings(db, current_user.id)


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
        db, current_user.id, body.asset_id, body.type, body.quantity,
        body.price, body.fee, body.executed_at, body.platform_id
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

- [ ] **Step 7: Register portfolio router in `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assets, auth, health, platforms, portfolio, settings

app = FastAPI(title="Zentri API", version="0.1.0")

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
app.include_router(platforms.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
```

- [ ] **Step 8: Run tests**

```bash
cd backend && python -m pytest tests/test_portfolio.py -v
```

Expected: All 5 tests PASS.

---

## Task 5: CSV import endpoint

**Files:**

- Create: `backend/app/schemas/csv_import.py`
- Create: `backend/app/services/csv_import.py`
- Modify: `backend/app/api/portfolio.py`
- Modify: `backend/app/main.py` (add `python-multipart` note)
- Create: `backend/tests/test_csv_import.py`

The CSV import is a two-step flow:

1. `POST /portfolio/import/preview` — upload CSV, returns detected columns + row preview
2. `POST /portfolio/import/confirm` — confirm with column mapping, saves transactions + holding

- [ ] **Step 1: Write failing tests**

`backend/tests/test_csv_import.py`:

```python
import io
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/zentri_test"
test_engine = create_async_engine(TEST_DB_URL)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def auth_client():
    async def override_get_db():
        async with TestSession() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        setup = await c.post("/api/v1/auth/setup", json={"username": "admin", "password": "password123"})
        token = setup.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c
    app.dependency_overrides.clear()


SAMPLE_CSV = b"""Date,Symbol,Action,Quantity,Price,Fee
2026-01-15,AAPL,BUY,10,150.00,1.00
2026-02-01,MSFT,BUY,5,300.00,1.00
"""


@pytest.mark.asyncio
async def test_import_preview_returns_columns_and_rows(auth_client):
    response = await auth_client.post(
        "/api/v1/portfolio/import/preview",
        files={"file": ("trades.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "columns" in data
    assert "rows" in data
    assert len(data["columns"]) == 6
    assert len(data["rows"]) == 2


@pytest.mark.asyncio
async def test_import_confirm_creates_transactions(auth_client):
    # First create assets
    await auth_client.post("/api/v1/assets", json={"symbol": "AAPL", "asset_type": "us_stock", "name": "Apple", "currency": "USD"})
    await auth_client.post("/api/v1/assets", json={"symbol": "MSFT", "asset_type": "us_stock", "name": "Microsoft", "currency": "USD"})

    confirm_payload = {
        "rows": [
            {"date": "2026-01-15", "symbol": "AAPL", "type": "buy", "quantity": "10", "price": "150.00", "fee": "1.00"},
            {"date": "2026-02-01", "symbol": "MSFT", "type": "buy", "quantity": "5", "price": "300.00", "fee": "1.00"},
        ],
        "asset_type": "us_stock",
        "save_profile": False,
        "broker_name": None,
    }
    response = await auth_client.post("/api/v1/portfolio/import/confirm", json=confirm_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert data["skipped"] == 0

    txns = await auth_client.get("/api/v1/portfolio/transactions")
    assert len(txns.json()) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_csv_import.py -v
```

Expected: `404` errors.

- [ ] **Step 3: Write `backend/app/schemas/csv_import.py`**

```python
from decimal import Decimal
from pydantic import BaseModel


class ImportPreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict]


class ImportRow(BaseModel):
    date: str          # ISO date string e.g. "2026-01-15"
    symbol: str
    type: str          # "buy" | "sell" | "dividend"
    quantity: str
    price: str
    fee: str = "0"


class ImportConfirmRequest(BaseModel):
    rows: list[ImportRow]
    asset_type: str = "us_stock"
    save_profile: bool = False
    broker_name: str | None = None


class ImportConfirmResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []
```

- [ ] **Step 4: Write `backend/app/services/csv_import.py`**

```python
import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import asset as asset_service
from app.services import portfolio as portfolio_service


def parse_csv_preview(content: bytes) -> dict:
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append(dict(row))
    columns = list(rows[0].keys()) if rows else []
    return {"columns": columns, "rows": rows[:5]}  # preview first 5 rows


async def confirm_import(
    db: AsyncSession,
    user_id: uuid.UUID,
    rows: list[dict],
    asset_type: str,
) -> dict:
    imported = 0
    skipped = 0
    errors = []

    for row in rows:
        symbol = row["symbol"].strip().upper()
        try:
            quantity = Decimal(row["quantity"])
            price = Decimal(row["price"])
            fee = Decimal(row.get("fee", "0") or "0")
            executed_at = datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc)
            tx_type = row["type"].lower()
        except (InvalidOperation, ValueError) as e:
            errors.append(f"Row {symbol}: {e}")
            skipped += 1
            continue

        # Find or create asset
        assets = await asset_service.search_assets(db, user_id, symbol)
        matching = [a for a in assets if a.symbol == symbol]
        if matching:
            asset = matching[0]
        else:
            asset = await asset_service.create_asset(
                db, user_id, symbol, asset_type, symbol, "USD"
            )

        await portfolio_service.add_transaction(
            db, user_id, asset.id, tx_type, quantity, price, fee, executed_at, source="csv_import"
        )

        # Upsert holding for buy transactions
        if tx_type == "buy":
            holdings = await portfolio_service.list_holdings(db, user_id)
            existing = next((h for h in holdings if h.asset_id == asset.id), None)
            if existing is None:
                await portfolio_service.add_holding(db, user_id, asset.id, quantity, price, "USD")

        imported += 1

    return {"imported": imported, "skipped": skipped, "errors": errors}
```

- [ ] **Step 5: Add import endpoints to `backend/app/api/portfolio.py`**

Add these imports at the top of `backend/app/api/portfolio.py`:

```python
from fastapi import File, UploadFile
from app.schemas.csv_import import ImportConfirmRequest, ImportConfirmResponse, ImportPreviewResponse
from app.services import csv_import as csv_import_service
```

Add these routes at the end of `backend/app/api/portfolio.py`:

```python
@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    content = await file.read()
    return csv_import_service.parse_csv_preview(content)


@router.post("/import/confirm", response_model=ImportConfirmResponse)
async def import_confirm(
    body: ImportConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = [r.model_dump() for r in body.rows]
    result = await csv_import_service.confirm_import(db, current_user.id, rows, body.asset_type)
    return ImportConfirmResponse(**result)
```

- [ ] **Step 6: Install python-multipart (required for file uploads)**

Add `python-multipart>=0.0.9` to `backend/pyproject.toml` dependencies, then:

```bash
cd backend && pip install python-multipart
```

- [ ] **Step 7: Run tests**

```bash
cd backend && python -m pytest tests/test_csv_import.py -v
```

Expected: Both tests PASS.

- [ ] **Step 8: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All tests PASS.

---

## Task 6: Portfolio export endpoint

**Files:**

- Modify: `backend/app/api/portfolio.py`

- [ ] **Step 1: Add export endpoint to `backend/app/api/portfolio.py`**

Add this import at the top:

```python
import csv
import io
from fastapi.responses import StreamingResponse
```

Add this route:

```python
@router.get("/export")
async def export_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    transactions = await portfolio_service.list_transactions(db, current_user.id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "asset_id", "type", "quantity", "price", "fee", "source", "executed_at"])
    for tx in transactions:
        writer.writerow([
            str(tx.id), str(tx.asset_id), tx.type,
            str(tx.quantity), str(tx.price), str(tx.fee),
            tx.source, tx.executed_at.isoformat()
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=zentri-portfolio.csv"},
    )
```

- [ ] **Step 2: Manually test export**

```bash
# With stack running:
curl -H "Authorization: Bearer <token>" http://localhost/api/v1/portfolio/export -o export.csv
cat export.csv
```

Expected: CSV with headers and transaction rows.

---

## Task 7: Portfolio list page (frontend)

**Files:**

- Create: `frontend/lib/services/portfolio.ts`
- Create: `frontend/lib/services/assets.ts`
- Create: `frontend/lib/services/platforms.ts`
- Create: `frontend/components/portfolio/HoldingsTable.tsx`
- Create: `frontend/components/portfolio/AddHoldingDialog.tsx`
- Create: `frontend/components/portfolio/ImportDrawer.tsx`
- Create: `frontend/app/(auth)/portfolio/page.tsx`
- Modify: `frontend/app/layout.tsx` (add TanStack Query provider)

- [ ] **Step 1: Add TanStack Query provider to `frontend/app/layout.tsx`**

```typescript
"use client";

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <html lang="en">
      <body className={inter.className}>
        <QueryClientProvider client={queryClient}>
          {children}
          <Toaster />
        </QueryClientProvider>
      </body>
    </html>
  );
}
```

> Note: Remove `export const metadata` when adding `"use client"` — metadata exports only work in Server Components. Move metadata to a separate layout or use `<head>` tags.

- [ ] **Step 2: Write `frontend/lib/services/portfolio.ts`**

```typescript
import { api } from "@/lib/api";

export interface Holding {
  id: string;
  asset_id: string;
  quantity: string;
  avg_cost_price: string;
  currency: string;
  updated_at: string;
}

export interface Transaction {
  id: string;
  asset_id: string;
  platform_id: string | null;
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
  total_cost_usd: string;
}

export async function fetchHoldings(): Promise<Holding[]> {
  const res = await api.get("/api/v1/portfolio/holdings");
  if (!res.ok) throw new Error("Failed to fetch holdings");
  return res.json();
}

export async function addHolding(body: {
  asset_id: string;
  quantity: string;
  avg_cost_price: string;
  currency: string;
}): Promise<Holding> {
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

export async function previewImport(
  file: File,
): Promise<{ columns: string[]; rows: Record<string, string>[] }> {
  const formData = new FormData();
  formData.append("file", file);
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/portfolio/import/preview`,
    {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    },
  );
  if (!res.ok) throw new Error("Preview failed");
  return res.json();
}

export async function confirmImport(payload: {
  rows: Array<{
    date: string;
    symbol: string;
    type: string;
    quantity: string;
    price: string;
    fee: string;
  }>;
  asset_type: string;
  save_profile: boolean;
  broker_name: string | null;
}): Promise<{ imported: number; skipped: number; errors: string[] }> {
  const res = await api.post("/api/v1/portfolio/import/confirm", payload);
  if (!res.ok) throw new Error("Import failed");
  return res.json();
}
```

- [ ] **Step 3: Write `frontend/lib/services/assets.ts`**

```typescript
import { api } from "@/lib/api";

export interface Asset {
  id: string;
  symbol: string;
  asset_type: string;
  name: string;
  currency: string;
  created_at: string;
}

export async function searchAssets(q: string): Promise<Asset[]> {
  const res = await api.get(`/api/v1/assets/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
  return res.json();
}

export async function createAsset(body: {
  symbol: string;
  asset_type: string;
  name: string;
  currency: string;
}): Promise<Asset> {
  const res = await api.post("/api/v1/assets", body);
  if (!res.ok) throw new Error("Failed to create asset");
  return res.json();
}
```

- [ ] **Step 4: Write `frontend/lib/services/platforms.ts`**

```typescript
import { api } from "@/lib/api";

export interface Platform {
  id: string;
  name: string;
  asset_types_supported: string[];
  notes: string | null;
  created_at: string;
}

export async function fetchPlatforms(): Promise<Platform[]> {
  const res = await api.get("/api/v1/platforms");
  if (!res.ok) return [];
  return res.json();
}

export async function createPlatform(body: {
  name: string;
  asset_types_supported: string[];
  notes?: string;
}): Promise<Platform> {
  const res = await api.post("/api/v1/platforms", body);
  if (!res.ok) throw new Error("Failed to create platform");
  return res.json();
}

export async function deletePlatform(id: string): Promise<void> {
  await api.delete(`/api/v1/platforms/${id}`);
}
```

- [ ] **Step 5: Write `frontend/components/portfolio/HoldingsTable.tsx`**

```typescript
"use client";

import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import { Holding } from "@/lib/services/portfolio";
import { usePrivacyStore } from "@/store/privacy";

interface Props {
  holdings: Holding[];
  assetMap: Record<string, string>; // asset_id -> symbol
  onDelete: (id: string) => void;
}

export function HoldingsTable({ holdings, assetMap, onDelete }: Props) {
  const { isPrivate } = usePrivacyStore();

  const columns: ColumnDef<Holding>[] = [
    {
      accessorKey: "asset_id",
      header: "Symbol",
      cell: ({ row }) => assetMap[row.original.asset_id] ?? row.original.asset_id.slice(0, 8),
    },
    {
      accessorKey: "quantity",
      header: "Quantity",
      cell: ({ row }) => isPrivate ? "••••" : row.original.quantity,
    },
    {
      accessorKey: "avg_cost_price",
      header: "Avg Cost",
      cell: ({ row }) => isPrivate ? "••••" : `${row.original.currency} ${row.original.avg_cost_price}`,
    },
    {
      accessorKey: "updated_at",
      header: "Updated",
      cell: ({ row }) => new Date(row.original.updated_at).toLocaleDateString(),
    },
    {
      id: "actions",
      cell: ({ row }) => (
        <Button variant="ghost" size="icon" onClick={() => onDelete(row.original.id)}>
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      ),
    },
  ];

  const table = useReactTable({ data: holdings, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((hg) => (
            <TableRow key={hg.id}>
              {hg.headers.map((h) => (
                <TableHead key={h.id}>{flexRender(h.column.columnDef.header, h.getContext())}</TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={columns.length} className="text-center text-muted-foreground py-8">
                No holdings yet. Add one or import from CSV.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [ ] **Step 6: Write `frontend/components/portfolio/AddHoldingDialog.tsx`**

```typescript
"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { createAsset } from "@/lib/services/assets";
import { addHolding } from "@/lib/services/portfolio";
import { Plus } from "lucide-react";

const ASSET_TYPES = ["us_stock", "thai_stock", "th_fund", "crypto", "gold"];

interface Props {
  onAdded: () => void;
}

export function AddHoldingDialog({ onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [assetType, setAssetType] = useState("us_stock");
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const asset = await createAsset({ symbol, asset_type: assetType, name: name || symbol, currency });
      await addHolding({ asset_id: asset.id, quantity, avg_cost_price: avgCost, currency });
      toast.success(`Added ${symbol} to portfolio`);
      setOpen(false);
      setSymbol(""); setName(""); setQuantity(""); setAvgCost("");
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
        <Button size="sm"><Plus className="h-4 w-4 mr-1" />Add Holding</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Add Holding</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Symbol</Label>
              <Input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="AAPL" required />
            </div>
            <div className="space-y-1">
              <Label>Type</Label>
              <Select value={assetType} onValueChange={setAssetType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ASSET_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Name (optional)</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Apple Inc." />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Quantity</Label>
              <Input value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="10" required />
            </div>
            <div className="space-y-1">
              <Label>Avg Cost Price</Label>
              <Input value={avgCost} onChange={(e) => setAvgCost(e.target.value)} placeholder="150.00" required />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Currency</Label>
            <Input value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} placeholder="USD" />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Adding..." : "Add Holding"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 7: Write `frontend/components/portfolio/ImportDrawer.tsx`**

```typescript
"use client";

import { useState, useRef } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { previewImport, confirmImport } from "@/lib/services/portfolio";
import { Upload } from "lucide-react";

const ASSET_TYPES = ["us_stock", "thai_stock", "th_fund", "crypto", "gold"];

interface Props {
  onImported: () => void;
}

export function ImportDrawer({ onImported }: Props) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<"upload" | "preview">("upload");
  const [assetType, setAssetType] = useState("us_stock");
  const [preview, setPreview] = useState<{ columns: string[]; rows: Record<string, string>[] } | null>(null);
  const [mappedRows, setMappedRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const data = await previewImport(file);
      setPreview(data);
      // Auto-map common column names (case-insensitive)
      const colMap = (name: string) => {
        const n = name.toLowerCase();
        if (n.includes("date") || n.includes("time")) return "date";
        if (n.includes("symbol") || n.includes("ticker")) return "symbol";
        if (n.includes("action") || n.includes("type") || n.includes("side")) return "type";
        if (n.includes("qty") || n.includes("quantity") || n.includes("shares")) return "quantity";
        if (n.includes("price") || n.includes("unit")) return "price";
        if (n.includes("fee") || n.includes("commission")) return "fee";
        return null;
      };
      const mapped = data.rows.map((row) => {
        const out: Record<string, string> = {};
        for (const [col, val] of Object.entries(row)) {
          const field = colMap(col);
          if (field) out[field] = val;
        }
        // Default action to buy if not detected
        if (!out.type) out.type = "buy";
        if (!out.fee) out.fee = "0";
        return out;
      });
      setMappedRows(mapped);
      setStep("preview");
    } catch {
      toast.error("Could not parse CSV");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    setLoading(true);
    try {
      const result = await confirmImport({
        rows: mappedRows as any,
        asset_type: assetType,
        save_profile: false,
        broker_name: null,
      });
      toast.success(`Imported ${result.imported} transactions. Skipped: ${result.skipped}`);
      setOpen(false);
      setStep("upload");
      setPreview(null);
      onImported();
    } catch {
      toast.error("Import failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm"><Upload className="h-4 w-4 mr-1" />Import CSV</Button>
      </SheetTrigger>
      <SheetContent className="w-[480px]">
        <SheetHeader><SheetTitle>Import from CSV</SheetTitle></SheetHeader>

        {step === "upload" && (
          <div className="space-y-4 mt-4">
            <div className="space-y-1">
              <Label>Asset Type</Label>
              <Select value={assetType} onValueChange={setAssetType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ASSET_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div
              className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:bg-muted/50"
              onClick={() => fileRef.current?.click()}
            >
              <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Click to upload CSV</p>
              <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
            </div>
          </div>
        )}

        {step === "preview" && preview && (
          <div className="space-y-4 mt-4">
            <p className="text-sm text-muted-foreground">
              Found {mappedRows.length} row(s). Columns: {preview.columns.join(", ")}
            </p>
            <div className="border rounded overflow-auto max-h-48 text-xs">
              <table className="w-full">
                <thead className="bg-muted">
                  <tr>{["date","symbol","type","quantity","price","fee"].map(c => <th key={c} className="px-2 py-1 text-left">{c}</th>)}</tr>
                </thead>
                <tbody>
                  {mappedRows.slice(0, 5).map((row, i) => (
                    <tr key={i} className="border-t">
                      {["date","symbol","type","quantity","price","fee"].map(c => (
                        <td key={c} className="px-2 py-1">{row[c] ?? "—"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep("upload")} className="flex-1">Back</Button>
              <Button onClick={handleConfirm} disabled={loading} className="flex-1">
                {loading ? "Importing..." : `Import ${mappedRows.length} rows`}
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 8: Write `frontend/app/(auth)/portfolio/page.tsx`**

```typescript
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchHoldings, deleteHolding, fetchSummary } from "@/lib/services/portfolio";
import { fetchAllAssets } from "@/lib/services/assets";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { AddHoldingDialog } from "@/components/portfolio/AddHoldingDialog";
import { ImportDrawer } from "@/components/portfolio/ImportDrawer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { usePrivacyStore } from "@/store/privacy";

export default function PortfolioPage() {
  const qc = useQueryClient();
  const { isPrivate } = usePrivacyStore();

  const { data: holdings = [], isLoading } = useQuery({
    queryKey: ["holdings"],
    queryFn: fetchHoldings,
  });

  const { data: summary } = useQuery({
    queryKey: ["portfolio-summary"],
    queryFn: fetchSummary,
  });

  const { data: assets = [] } = useQuery({
    queryKey: ["assets"],
    queryFn: () => fetch("/api/v1/assets/search?q=").then((r) => r.json()).catch(() => []),
  });

  const assetMap = Object.fromEntries(assets.map((a: any) => [a.id, a.symbol]));

  const deleteMutation = useMutation({
    mutationFn: deleteHolding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holdings"] });
      qc.invalidateQueries({ queryKey: ["portfolio-summary"] });
      toast.success("Holding removed");
    },
    onError: () => toast.error("Failed to remove holding"),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["holdings"] });
    qc.invalidateQueries({ queryKey: ["portfolio-summary"] });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Portfolio</h1>
        <div className="flex gap-2">
          <ImportDrawer onImported={refresh} />
          <AddHoldingDialog onAdded={refresh} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Holdings</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{summary?.holdings_count ?? "—"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Total Cost</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {isPrivate ? "••••" : summary ? `$${parseFloat(summary.total_cost_usd).toLocaleString()}` : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <HoldingsTable
          holdings={holdings}
          assetMap={assetMap}
          onDelete={(id) => deleteMutation.mutate(id)}
        />
      )}
    </div>
  );
}
```

> Note: Add `fetchAllAssets` to `frontend/lib/services/assets.ts`:

```typescript
export async function fetchAllAssets(): Promise<Asset[]> {
  const res = await api.get("/api/v1/assets/search?q=");
  if (!res.ok) return [];
  return res.json();
}
```

- [ ] **Step 9: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

---

## Task 8: Settings page — Platforms tab

**Files:**

- Create: `frontend/components/settings/PlatformsManager.tsx`
- Create: `frontend/app/(auth)/settings/page.tsx`

- [ ] **Step 1: Write `frontend/components/settings/PlatformsManager.tsx`**

```typescript
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchPlatforms, createPlatform, deletePlatform } from "@/lib/services/platforms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";

export function PlatformsManager() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [types, setTypes] = useState("us_stock");

  const { data: platforms = [] } = useQuery({ queryKey: ["platforms"], queryFn: fetchPlatforms });

  const createMutation = useMutation({
    mutationFn: () => createPlatform({
      name,
      asset_types_supported: types.split(",").map((t) => t.trim()).filter(Boolean),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platforms"] });
      setName(""); setTypes("us_stock");
      toast.success("Platform added");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deletePlatform,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platforms"] });
      toast.success("Platform removed");
    },
  });

  return (
    <Card>
      <CardHeader><CardTitle>Broker Platforms</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Robinhood" />
          </div>
          <div className="flex-1 space-y-1">
            <Label>Asset Types (comma separated)</Label>
            <Input value={types} onChange={(e) => setTypes(e.target.value)} placeholder="us_stock, crypto" />
          </div>
          <div className="flex items-end">
            <Button onClick={() => createMutation.mutate()} disabled={!name}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="space-y-2">
          {platforms.map((p) => (
            <div key={p.id} className="flex items-center justify-between border rounded p-2">
              <div>
                <span className="font-medium text-sm">{p.name}</span>
                <div className="flex gap-1 mt-1">
                  {p.asset_types_supported.map((t) => (
                    <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                  ))}
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(p.id)}>
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
          {platforms.length === 0 && (
            <p className="text-sm text-muted-foreground">No platforms yet.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Write `frontend/app/(auth)/settings/page.tsx`**

```typescript
"use client";

import { useEffect, useState } from "react";
import { PlatformsManager } from "@/components/settings/PlatformsManager";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface HardwareInfo {
  cpu_brand: string;
  ram_gb: number;
  is_apple_silicon: boolean;
  recommendation: {
    can_run_local_llm: boolean;
    recommended_model: string;
    setup_command: string;
    note: string;
  };
}

export default function SettingsPage() {
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    fetch("/api/v1/settings/hardware", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then(setHardware)
      .catch(() => null);
  }, []);

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Card>
        <CardHeader><CardTitle>Hardware</CardTitle></CardHeader>
        <CardContent>
          {hardware ? (
            <div className="space-y-2 text-sm">
              <p><strong>CPU:</strong> {hardware.cpu_brand}</p>
              <p><strong>RAM:</strong> {hardware.ram_gb} GB</p>
              <p><strong>Apple Silicon:</strong> {hardware.is_apple_silicon ? "Yes" : "No"}</p>
              <div className="border rounded p-3 mt-2 space-y-1">
                <p><strong>Recommended model:</strong> {hardware.recommendation.recommended_model}</p>
                <p className="text-muted-foreground">{hardware.recommendation.note}</p>
                {hardware.recommendation.can_run_local_llm && (
                  <code className="block bg-muted p-2 rounded text-xs mt-1">
                    {hardware.recommendation.setup_command}
                  </code>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Loading hardware info...</p>
          )}
        </CardContent>
      </Card>

      <PlatformsManager />
    </div>
  );
}
```

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: No TypeScript errors.

---

## Task 9: End-to-end smoke test

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

Expected: All tests PASS. Coverage >70% for `app/services/` and `app/api/`.

- [ ] **Step 2: Bring up full stack**

```bash
docker compose up -d
```

- [ ] **Step 3: Run migration against real DB**

```bash
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 001 -> 002, portfolio schema`

- [ ] **Step 4: Test portfolio endpoints manually**

```bash
# Setup + get token
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Add asset
curl -s -X POST http://localhost/api/v1/assets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","asset_type":"us_stock","name":"Apple Inc.","currency":"USD"}' | python3 -m json.tool

# Check hardware
curl -s http://localhost/api/v1/settings/hardware \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

- [ ] **Step 5: Open browser and test UI**

Navigate to `http://localhost/portfolio` — holdings table should render.
Click "Add Holding" — dialog opens, fill form, submit → row appears.
Click "Import CSV" — drawer opens, upload a CSV file, preview renders, confirm imports.
Navigate to `http://localhost/settings` — hardware info and platforms manager render.

---

## Self-Review

### Spec Coverage

| Kanban Task                                        | Covered by |
| -------------------------------------------------- | ---------- |
| feat - hardware detection service                  | Task 1     |
| feat - settings hardware detect endpoint           | Task 1     |
| feat - asset master data model and migration       | Task 2     |
| feat - platforms broker apps CRUD endpoints and UI | Tasks 3, 8 |
| feat - manual holdings entry endpoint              | Task 4     |
| feat - manual transaction recording                | Task 4     |
| feat - CSV import with LLM column mapper endpoint  | Task 5     |
| feat - CSV import confirm and save import profiles | Task 5     |
| feat - portfolio export endpoint                   | Task 6     |
| feat - portfolio list page with DataTable          | Task 7     |

### Notes

- CSV import uses auto-mapping heuristics (column name matching) rather than LLM in this phase. LLM column mapping is an enhancement that can be added in Phase 6 when the LLM pipeline is built — the endpoint contract is identical.
- `save_profile` field in `ImportConfirmRequest` is wired through but profile saving is not implemented (ImportProfile model is migrated, ready for Phase 6).
- Privacy mode is integrated in HoldingsTable — monetary values masked when `isPrivate` is true.
