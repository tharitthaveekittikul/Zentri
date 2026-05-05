# Dividend Cluster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dividend fetch worker (yfinance, weekly+on-demand), a dividend calendar page (grid + list + mark-as-received flow), and a transactions management page (edit + delete).

**Architecture:** An ARQ job calls `dividend_feed.fetch_all_dividends()` which upserts into a new `dividend_events` table. A FastAPI router exposes calendar, upcoming list, on-demand refresh, and confirm endpoints. Two new Next.js pages — `/dividends` and `/transactions` — consume these APIs using the existing `lib/api.ts` fetch pattern.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy async / ARQ / yfinance / PostgreSQL / Next.js 15 / shadcn/ui / Tailwind

---

## File Map

**Create (backend):**
- `backend/alembic/versions/013_dividend_events.py` — migration
- `backend/app/models/dividend_event.py` — DividendEvent SQLAlchemy model
- `backend/app/schemas/dividend.py` — Pydantic schemas for dividend API
- `backend/app/services/dividend_feed.py` — fetch + upsert + calendar query service
- `backend/app/api/dividends.py` — FastAPI router (/dividends/*)
- `backend/worker/jobs/dividend_fetch.py` — ARQ job wrapper
- `backend/tests/test_dividend_feed.py` — unit tests for dividend_feed service
- `backend/tests/test_dividends_api.py` — API integration tests

**Modify (backend):**
- `backend/app/models/__init__.py` — import DividendEvent
- `backend/app/schemas/transaction.py` — add TransactionRow + TransactionUpdate schemas
- `backend/app/services/portfolio.py` — add get_transaction, update_transaction, delete_transaction, list_transactions_with_assets
- `backend/app/api/portfolio.py` — add PATCH/DELETE /transactions/{id}, update GET /transactions to return TransactionRow
- `backend/app/main.py` — register dividends router
- `backend/worker/main.py` — register job_fetch_dividends + weekly cron

**Create (frontend):**
- `frontend/app/(auth)/transactions/page.tsx` — transactions management page
- `frontend/app/(auth)/dividends/page.tsx` — dividend calendar page

**Modify (frontend):**
- `frontend/components/layout/Sidebar.tsx` — add /transactions nav link (note: /dividends already exists)

---

## Task 1: Alembic Migration + DividendEvent Model

**Files:**
- Create: `backend/alembic/versions/013_dividend_events.py`
- Create: `backend/app/models/dividend_event.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/013_dividend_events.py
"""add dividend events table

Revision ID: 013
Revises: 012
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dividend_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("pay_date", sa.Date(), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("amount_per_share", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("frequency", sa.String(20), nullable=True),
        sa.Column(
            "status",
            sa.Enum("upcoming", "payable", "paid", name="dividend_event_status_enum"),
            nullable=False,
        ),
        sa.Column("source", sa.String(20), nullable=False, server_default="yfinance"),
        sa.Column("confirmed_transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_dividend_events_asset_ex_date", "dividend_events", ["asset_id", "ex_date"])
    op.create_unique_constraint("uq_dividend_events_asset_ex_date", "dividend_events", ["asset_id", "ex_date"])


def downgrade() -> None:
    op.drop_constraint("uq_dividend_events_asset_ex_date", "dividend_events", type_="unique")
    op.drop_index("ix_dividend_events_asset_ex_date", "dividend_events")
    op.drop_table("dividend_events")
    op.execute("DROP TYPE IF EXISTS dividend_event_status_enum")
```

- [ ] **Step 2: Create DividendEvent model**

```python
# backend/app/models/dividend_event.py
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

DIVIDEND_EVENT_STATUSES = ("upcoming", "payable", "paid")


class DividendEvent(Base):
    __tablename__ = "dividend_events"
    __table_args__ = (UniqueConstraint("asset_id", "ex_date", name="uq_dividend_events_asset_ex_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    pay_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    record_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_per_share: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*DIVIDEND_EVENT_STATUSES, name="dividend_event_status_enum"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="yfinance")
    confirmed_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 3: Register DividendEvent in models/__init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.dividend_event import DividendEvent  # noqa: F401
```

Add `"DividendEvent"` to `__all__`.

- [ ] **Step 4: Run migration**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 012 -> 013, add dividend events table`

---

## Task 2: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/dividend.py`
- Modify: `backend/app/schemas/transaction.py`

- [ ] **Step 1: Create dividend schemas**

```python
# backend/app/schemas/dividend.py
import uuid
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel


class DividendEventOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    ex_date: date
    pay_date: Optional[date] = None
    record_date: Optional[date] = None
    amount_per_share: Decimal
    currency: str
    frequency: Optional[str] = None
    status: str
    source: str
    quantity_held: Decimal
    projected_total_usd: Decimal
    projected_total_secondary: Optional[Decimal] = None

    model_config = {"from_attributes": False}


class DividendMonthGroup(BaseModel):
    year: int
    month: int
    total_projected_usd: Decimal
    events: list[DividendEventOut]


class DividendCalendarResponse(BaseModel):
    months: list[DividendMonthGroup]


class DividendConfirmRequest(BaseModel):
    quantity: Decimal
    executed_at: date
```

- [ ] **Step 2: Add TransactionRow and TransactionUpdate to transaction.py**

Open `backend/app/schemas/transaction.py` and append:

```python
class TransactionRow(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    asset_type: str
    platform: str | None
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    source: str
    executed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": False}


class TransactionUpdate(BaseModel):
    type: Literal["buy", "sell", "dividend", "reward", "fee", "transfer"] | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    fee: Decimal | None = None
    executed_at: datetime | None = None
    platform: str | None = None
```

---

## Task 3: dividend_feed Service

**Files:**
- Create: `backend/app/services/dividend_feed.py`
- Create: `backend/tests/test_dividend_feed.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_dividend_feed.py
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.services.dividend_feed import _build_rows_for_asset, _compute_status


def _make_asset(symbol: str = "AAPL", currency: str = "USD"):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.symbol = symbol
    a.currency = currency
    return a


def test_compute_status_upcoming():
    future = date(2099, 1, 1)
    assert _compute_status(future, date.today()) == "upcoming"


def test_compute_status_payable():
    past = date(2020, 1, 1)
    assert _compute_status(past, date.today()) == "payable"


def test_build_rows_for_asset_extracts_historical():
    asset = _make_asset()
    ts = pd.Timestamp("2025-01-15")
    divs = pd.Series([0.25], index=[ts])
    cal = {}
    rows = _build_rows_for_asset(asset, divs, cal, date(2026, 1, 1))
    assert len(rows) == 1
    assert rows[0]["asset_id"] == asset.id
    assert rows[0]["amount_per_share"] == Decimal("0.25")
    assert rows[0]["status"] == "payable"


def test_build_rows_for_asset_skips_zero_dividends():
    asset = _make_asset()
    ts = pd.Timestamp("2025-01-15")
    divs = pd.Series([0.0], index=[ts])
    rows = _build_rows_for_asset(asset, divs, {}, date(2026, 1, 1))
    assert len(rows) == 0


def test_build_rows_for_asset_adds_upcoming_from_calendar():
    asset = _make_asset()
    divs = pd.Series([0.25], index=[pd.Timestamp("2025-01-15")])
    cal = {
        "Ex-Dividend Date": pd.Timestamp("2099-06-01"),
        "Dividend Date": pd.Timestamp("2099-06-15"),
    }
    rows = _build_rows_for_asset(asset, divs, cal, date(2026, 1, 1))
    upcoming = [r for r in rows if r["ex_date"] == date(2099, 6, 1)]
    assert len(upcoming) == 1
    assert upcoming[0]["status"] == "upcoming"
    assert upcoming[0]["pay_date"] == date(2099, 6, 15)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
python -m pytest tests/test_dividend_feed.py -v 2>&1 | head -30
```

Expected: ImportError or ModuleNotFoundError for `dividend_feed`

- [ ] **Step 3: Implement dividend_feed service**

```python
# backend/app/services/dividend_feed.py
import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import sqlalchemy as sa
import yfinance as yf
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.dividend_event import DividendEvent
from app.models.holding import Holding
from app.services.exchange_rate import get_rate

logger = get_logger(__name__)

FETCHABLE_ASSET_TYPES = {"us_stock", "etf"}


def _compute_status(ex_date: date, today: date) -> str:
    return "upcoming" if ex_date > today else "payable"


def _build_rows_for_asset(asset, divs, cal: dict, today: date) -> list[dict]:
    rows = []

    for ts, amount in divs.items():
        if not amount or float(amount) <= 0:
            continue
        ex_dt = ts.date() if hasattr(ts, "date") else ts
        rows.append({
            "asset_id": asset.id,
            "ex_date": ex_dt,
            "pay_date": None,
            "record_date": None,
            "amount_per_share": Decimal(str(float(amount))),
            "currency": asset.currency,
            "frequency": None,
            "status": _compute_status(ex_dt, today),
            "source": "yfinance",
        })

    if cal and isinstance(cal, dict):
        cal_ex = cal.get("Ex-Dividend Date")
        cal_pay = cal.get("Dividend Date")
        if cal_ex is not None:
            cal_ex_date = cal_ex.date() if hasattr(cal_ex, "date") else cal_ex
            if cal_ex_date > today:
                last_amount = Decimal(str(float(divs.iloc[-1]))) if len(divs) > 0 else None
                if last_amount and last_amount > 0:
                    pay_date = cal_pay.date() if cal_pay and hasattr(cal_pay, "date") else None
                    rows.append({
                        "asset_id": asset.id,
                        "ex_date": cal_ex_date,
                        "pay_date": pay_date,
                        "record_date": None,
                        "amount_per_share": last_amount,
                        "currency": asset.currency,
                        "frequency": None,
                        "status": "upcoming",
                        "source": "yfinance",
                    })

    return rows


async def fetch_all_dividends(db: AsyncSession) -> int:
    result = await db.execute(
        select(Asset).where(Asset.asset_type.in_(FETCHABLE_ASSET_TYPES))
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_all_dividends: no fetchable assets found")
        return 0

    today = date.today()
    all_rows: list[dict] = []

    def _fetch(symbol: str):
        ticker = yf.Ticker(symbol)
        return ticker.dividends, ticker.calendar

    for asset in assets:
        try:
            divs, cal = await asyncio.get_event_loop().run_in_executor(None, _fetch, asset.symbol)
            rows = _build_rows_for_asset(asset, divs, cal or {}, today)
            all_rows.extend(rows)
        except Exception as e:
            logger.warning("fetch_all_dividends: failed for %s: %s", asset.symbol, e)

    if not all_rows:
        logger.info("fetch_all_dividends: no rows to upsert")
        return 0

    stmt = pg_insert(DividendEvent).values(all_rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_dividend_events_asset_ex_date",
        set_={
            "amount_per_share": stmt.excluded.amount_per_share,
            "pay_date": stmt.excluded.pay_date,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    await db.execute(stmt)

    await db.execute(
        update(DividendEvent)
        .where(
            DividendEvent.ex_date <= today,
            DividendEvent.status == "upcoming",
            DividendEvent.confirmed_transaction_id.is_(None),
        )
        .values(status="payable", updated_at=datetime.now(timezone.utc))
    )
    await db.commit()

    logger.info("fetch_all_dividends: upserted %d rows", len(all_rows))
    return len(all_rows)


async def get_event(db: AsyncSession, event_id: uuid.UUID) -> DividendEvent | None:
    result = await db.execute(select(DividendEvent).where(DividendEvent.id == event_id))
    return result.scalar_one_or_none()


async def get_calendar(
    db: AsyncSession,
    user_id: uuid.UUID,
    months: int,
    secondary_currency: str,
) -> dict:
    today = date.today()
    start_date = today - timedelta(days=30)
    end_date = today + timedelta(days=months * 31)

    result = await db.execute(
        select(DividendEvent, Asset, Holding)
        .join(Asset, DividendEvent.asset_id == Asset.id)
        .outerjoin(
            Holding,
            sa.and_(Holding.asset_id == DividendEvent.asset_id, Holding.user_id == user_id),
        )
        .where(DividendEvent.ex_date >= start_date, DividendEvent.ex_date <= end_date)
        .order_by(DividendEvent.ex_date)
    )
    rows = result.all()

    rate = await get_rate(db, "USD", secondary_currency)
    months_dict: dict[tuple, dict] = {}

    for event, asset, holding in rows:
        qty = holding.quantity if holding else Decimal("0")
        projected_usd = qty * event.amount_per_share
        projected_secondary = projected_usd * rate if rate else None

        key = (event.ex_date.year, event.ex_date.month)
        if key not in months_dict:
            months_dict[key] = {
                "year": key[0],
                "month": key[1],
                "total_projected_usd": Decimal("0"),
                "events": [],
            }

        months_dict[key]["events"].append({
            "id": event.id,
            "asset_id": event.asset_id,
            "symbol": asset.symbol,
            "ex_date": event.ex_date,
            "pay_date": event.pay_date,
            "record_date": event.record_date,
            "amount_per_share": event.amount_per_share,
            "currency": event.currency,
            "frequency": event.frequency,
            "status": event.status,
            "source": event.source,
            "quantity_held": qty,
            "projected_total_usd": projected_usd,
            "projected_total_secondary": projected_secondary,
        })
        months_dict[key]["total_projected_usd"] += projected_usd

    return {"months": list(months_dict.values())}


async def get_upcoming(
    db: AsyncSession,
    user_id: uuid.UUID,
    secondary_currency: str,
) -> list[dict]:
    today = date.today()

    result = await db.execute(
        select(DividendEvent, Asset, Holding)
        .join(Asset, DividendEvent.asset_id == Asset.id)
        .outerjoin(
            Holding,
            sa.and_(Holding.asset_id == DividendEvent.asset_id, Holding.user_id == user_id),
        )
        .where(DividendEvent.status.in_(["upcoming", "payable"]))
        .order_by(DividendEvent.ex_date)
    )
    rows = result.all()

    rate = await get_rate(db, "USD", secondary_currency)
    events = []
    for event, asset, holding in rows:
        qty = holding.quantity if holding else Decimal("0")
        projected_usd = qty * event.amount_per_share
        events.append({
            "id": event.id,
            "asset_id": event.asset_id,
            "symbol": asset.symbol,
            "ex_date": event.ex_date,
            "pay_date": event.pay_date,
            "record_date": event.record_date,
            "amount_per_share": event.amount_per_share,
            "currency": event.currency,
            "frequency": event.frequency,
            "status": event.status,
            "source": event.source,
            "quantity_held": qty,
            "projected_total_usd": projected_usd,
            "projected_total_secondary": projected_usd * rate if rate else None,
        })
    return events
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
python -m pytest tests/test_dividend_feed.py -v 2>&1 | tail -15
```

Expected: 5 passed

---

## Task 4: ARQ Job + Worker Registration

**Files:**
- Create: `backend/worker/jobs/dividend_fetch.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Create the ARQ job**

```python
# backend/worker/jobs/dividend_fetch.py
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.pipeline import create_log, finish_log
from app.services.dividend_feed import fetch_all_dividends

logger = get_logger(__name__)


async def job_fetch_dividends(ctx: dict) -> dict:
    """ARQ job: fetch dividend events for all us_stock/etf assets via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "dividend_fetch")
        try:
            count = await fetch_all_dividends(db)
            await finish_log(db, log, success=True)
            return {"upserted": count}
        except Exception as e:
            logger.exception("job_fetch_dividends failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 2: Register job and cron in worker/main.py**

In `backend/worker/main.py`, add the import:

```python
from worker.jobs.dividend_fetch import job_fetch_dividends
```

Add to `functions` list:
```python
job_fetch_dividends,
```

Add to `cron_jobs` list:
```python
cron(job_fetch_dividends, weekday=0, hour=2, minute=0),  # Every Monday 02:00
```

- [ ] **Step 3: Verify worker starts without import errors**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
docker compose restart worker
docker compose logs worker --tail=20
```

Expected: `ARQ worker started — DB pool ready` with no import errors

---

## Task 5: Dividends API Router

**Files:**
- Create: `backend/app/api/dividends.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_dividends_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
# backend/tests/test_dividends_api.py
import pytest


@pytest.mark.asyncio
async def test_get_calendar_empty(auth_client):
    response = await auth_client.get("/api/v1/dividends/calendar")
    assert response.status_code == 200
    assert response.json() == {"months": []}


@pytest.mark.asyncio
async def test_get_upcoming_empty(auth_client):
    response = await auth_client.get("/api/v1/dividends/upcoming")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_confirm_nonexistent_event(auth_client):
    import uuid
    fake_id = str(uuid.uuid4())
    response = await auth_client.post(
        f"/api/v1/dividends/{fake_id}/confirm",
        json={"quantity": "10.0", "executed_at": "2026-05-15"},
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
python -m pytest tests/test_dividends_api.py -v 2>&1 | head -20
```

Expected: 404 for `/api/v1/dividends/calendar` (router not registered yet)

- [ ] **Step 3: Implement the dividends router**

```python
# backend/app/api/dividends.py
import uuid
from datetime import datetime, time, timezone
from decimal import Decimal

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.asset import Asset
from app.models.user import User
from app.schemas.dividend import (
    DividendCalendarResponse,
    DividendConfirmRequest,
    DividendEventOut,
)
from app.schemas.transaction import TransactionResponse
from app.services import dividend_feed, portfolio as portfolio_service

router = APIRouter(prefix="/dividends", tags=["dividends"])


@router.get("/calendar", response_model=DividendCalendarResponse)
async def get_calendar(
    months: int = 3,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if months < 1 or months > 12:
        raise HTTPException(status_code=400, detail="months must be between 1 and 12")
    result = await dividend_feed.get_calendar(
        db, current_user.id, months, current_user.currency_secondary
    )
    return result


@router.get("/upcoming", response_model=list[DividendEventOut])
async def get_upcoming(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dividend_feed.get_upcoming(db, current_user.id, current_user.currency_secondary)


@router.post("/refresh", status_code=202)
async def refresh_dividends():
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await redis.enqueue_job("job_fetch_dividends")
    await redis.aclose()
    return {"status": "queued"}


@router.post("/{event_id}/confirm", response_model=TransactionResponse)
async def confirm_dividend(
    event_id: uuid.UUID,
    body: DividendConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await dividend_feed.get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Dividend event not found")
    if event.status == "paid":
        raise HTTPException(status_code=400, detail="Dividend already confirmed")

    result = await db.execute(select(Asset).where(Asset.id == event.asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    executed_dt = datetime.combine(body.executed_at, time.min).replace(tzinfo=timezone.utc)
    tx = await portfolio_service.add_transaction(
        db,
        current_user.id,
        event.asset_id,
        "dividend",
        body.quantity,
        event.amount_per_share,
        Decimal("0"),
        executed_dt,
        platform=None,
        source="manual",
    )

    event.confirmed_transaction_id = tx.id
    event.status = "paid"
    event.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return tx
```

- [ ] **Step 4: Register the router in app/main.py**

In `backend/app/main.py`, add import:
```python
from app.api import dividends
```

Add router registration after existing routers:
```python
app.include_router(dividends.router, prefix="/api/v1")
```

- [ ] **Step 5: Run the API tests**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
python -m pytest tests/test_dividends_api.py -v 2>&1 | tail -15
```

Expected: 3 passed

---

## Task 6: Portfolio Service Additions + PATCH/DELETE Transactions API

**Files:**
- Modify: `backend/app/services/portfolio.py`
- Modify: `backend/app/api/portfolio.py`
- Modify: `backend/tests/test_portfolio.py`

- [ ] **Step 1: Write failing tests for PATCH/DELETE transactions**

Append to `backend/tests/test_portfolio.py`:

```python
@pytest.mark.asyncio
async def test_patch_transaction(auth_client, asset_id):
    create_res = await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id,
        "type": "buy",
        "quantity": "5",
        "price": "155.00",
        "fee": "1.00",
        "executed_at": "2026-01-15T10:00:00Z",
    })
    tx_id = create_res.json()["id"]

    patch_res = await auth_client.patch(
        f"/api/v1/portfolio/transactions/{tx_id}",
        json={"price": "160.00", "fee": "0.50"},
    )
    assert patch_res.status_code == 200
    assert float(patch_res.json()["price"]) == 160.00
    assert float(patch_res.json()["fee"]) == 0.50


@pytest.mark.asyncio
async def test_delete_transaction(auth_client, asset_id):
    create_res = await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id,
        "type": "buy",
        "quantity": "5",
        "price": "155.00",
        "fee": "1.00",
        "executed_at": "2026-01-15T10:00:00Z",
    })
    tx_id = create_res.json()["id"]

    delete_res = await auth_client.delete(f"/api/v1/portfolio/transactions/{tx_id}")
    assert delete_res.status_code == 204

    list_res = await auth_client.get("/api/v1/portfolio/transactions")
    assert all(t["id"] != tx_id for t in list_res.json())


@pytest.mark.asyncio
async def test_delete_transaction_not_found(auth_client):
    import uuid
    fake_id = str(uuid.uuid4())
    res = await auth_client.delete(f"/api/v1/portfolio/transactions/{fake_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_transactions_includes_symbol(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id, "type": "buy", "quantity": "5",
        "price": "155", "fee": "1", "executed_at": "2026-01-15T10:00:00Z"
    })
    res = await auth_client.get("/api/v1/portfolio/transactions")
    assert res.status_code == 200
    assert res.json()[0]["symbol"] == "AAPL"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
python -m pytest tests/test_portfolio.py::test_patch_transaction tests/test_portfolio.py::test_delete_transaction tests/test_portfolio.py::test_delete_transaction_not_found tests/test_portfolio.py::test_list_transactions_includes_symbol -v 2>&1 | tail -20
```

Expected: 4 failed (405 Method Not Allowed / KeyError on symbol)

- [ ] **Step 3: Add service functions to portfolio.py**

Append to `backend/app/services/portfolio.py`:

```python
async def get_transaction(
    db: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
) -> Transaction | None:
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_transaction(db: AsyncSession, tx: Transaction, data: dict) -> Transaction:
    for field, value in data.items():
        if value is not None:
            setattr(tx, field, value)
    await db.commit()
    await db.refresh(tx)
    logger.info("Transaction updated: id=%s", tx.id)
    return tx


async def delete_transaction(db: AsyncSession, tx: Transaction) -> None:
    logger.info("Transaction deleted: id=%s user=%s", tx.id, tx.user_id)
    await db.delete(tx)
    await db.commit()


async def list_transactions_with_assets(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID | None = None,
) -> list[dict]:
    q = (
        select(Transaction, Asset)
        .join(Asset, Asset.id == Transaction.asset_id)
        .where(Transaction.user_id == user_id)
    )
    if asset_id:
        q = q.where(Transaction.asset_id == asset_id)
    result = await db.execute(q.order_by(Transaction.executed_at.desc()))
    rows = []
    for tx, asset in result.all():
        rows.append({
            "id": tx.id,
            "asset_id": tx.asset_id,
            "symbol": asset.symbol,
            "asset_type": asset.asset_type,
            "platform": tx.platform,
            "type": tx.type,
            "quantity": tx.quantity,
            "price": tx.price,
            "fee": tx.fee,
            "source": tx.source,
            "executed_at": tx.executed_at,
            "created_at": tx.created_at,
        })
    return rows
```

- [ ] **Step 4: Add PATCH/DELETE endpoints and update GET /transactions in portfolio.py API**

Open `backend/app/api/portfolio.py`. Add imports at the top:
```python
from app.schemas.transaction import (
    ManualTransactionCreate, TransactionCreate, TransactionResponse,
    TransactionRow, TransactionUpdate,
)
```

Replace the existing `list_transactions` endpoint:
```python
@router.get("/transactions", response_model=list[TransactionRow])
async def list_transactions(
    asset_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await portfolio_service.list_transactions_with_assets(db, current_user.id, asset_id)
    return rows
```

Append the two new endpoints after the existing `/transactions` endpoints:
```python
@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID,
    body: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tx = await portfolio_service.get_transaction(db, current_user.id, transaction_id)
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return await portfolio_service.update_transaction(db, tx, body.model_dump(exclude_none=True))


@router.delete("/transactions/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tx = await portfolio_service.get_transaction(db, current_user.id, transaction_id)
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    await portfolio_service.delete_transaction(db, tx)
    return Response(status_code=204)
```

- [ ] **Step 5: Run all portfolio tests**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
python -m pytest tests/test_portfolio.py -v 2>&1 | tail -20
```

Expected: all tests pass

---

## Task 7: Frontend Transactions Page + Sidebar

**Files:**
- Create: `frontend/app/(auth)/transactions/page.tsx`
- Modify: `frontend/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add /transactions to Sidebar**

In `frontend/components/layout/Sidebar.tsx`, the `navItems` array already has `/dividends`. Add `/transactions` after it. Also add `Receipt` to the lucide import:

```tsx
import {
  LayoutDashboard,
  Briefcase,
  Star,
  TrendingUp,
  CalendarDays,
  Receipt,
  FileText,
  Activity,
  Bot,
  Settings,
  Upload,
} from "lucide-react";
```

In `navItems`:
```tsx
{ href: "/dividends", label: "Dividends", icon: CalendarDays },
{ href: "/transactions", label: "Transactions", icon: Receipt },
```

- [ ] **Step 2: Create transactions page**

```tsx
// frontend/app/(auth)/transactions/page.tsx
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Pencil, Trash2 } from "lucide-react";

type TransactionRow = {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  platform: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  created_at: string;
};

const TYPE_COLORS: Record<string, string> = {
  buy: "bg-green-100 text-green-800",
  sell: "bg-red-100 text-red-800",
  dividend: "bg-blue-100 text-blue-800",
  reward: "bg-purple-100 text-purple-800",
  fee: "bg-yellow-100 text-yellow-800",
  transfer: "bg-gray-100 text-gray-800",
};

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [editTarget, setEditTarget] = useState<TransactionRow | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TransactionRow | null>(null);
  const [editForm, setEditForm] = useState<Partial<TransactionRow>>({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const fetchTransactions = async () => {
    setLoading(true);
    const res = await api.get("/api/v1/portfolio/transactions");
    if (res.ok) setTransactions(await res.json());
    setLoading(false);
  };

  useEffect(() => { fetchTransactions(); }, []);

  const openEdit = (tx: TransactionRow) => {
    setEditTarget(tx);
    setEditForm({
      type: tx.type,
      quantity: tx.quantity,
      price: tx.price,
      fee: tx.fee,
      executed_at: tx.executed_at.slice(0, 16),
      platform: tx.platform ?? "",
    });
  };

  const saveEdit = async () => {
    if (!editTarget) return;
    setSaving(true);
    const res = await api.patch(`/api/v1/portfolio/transactions/${editTarget.id}`, {
      type: editForm.type,
      quantity: editForm.quantity ? parseFloat(editForm.quantity) : undefined,
      price: editForm.price ? parseFloat(editForm.price) : undefined,
      fee: editForm.fee ? parseFloat(editForm.fee) : undefined,
      executed_at: editForm.executed_at ? new Date(editForm.executed_at).toISOString() : undefined,
      platform: editForm.platform || null,
    });
    setSaving(false);
    if (res.ok) {
      setEditTarget(null);
      fetchTransactions();
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    await api.delete(`/api/v1/portfolio/transactions/${deleteTarget.id}`);
    setDeleting(false);
    setDeleteTarget(null);
    fetchTransactions();
  };

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Transactions</h1>

      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Asset</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Quantity</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">Fee</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                    No transactions yet
                  </TableCell>
                </TableRow>
              )}
              {transactions.map((tx) => (
                <TableRow key={tx.id}>
                  <TableCell className="text-sm">
                    {new Date(tx.executed_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="font-medium">{tx.symbol}</TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[tx.type] ?? "bg-gray-100 text-gray-800"}`}>
                      {tx.type}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">{parseFloat(tx.quantity).toLocaleString()}</TableCell>
                  <TableCell className="text-right">{parseFloat(tx.price).toFixed(2)}</TableCell>
                  <TableCell className="text-right">{parseFloat(tx.fee).toFixed(2)}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">{tx.platform ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(tx)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(tx)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={!!editTarget} onOpenChange={(open) => !open && setEditTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Transaction — {editTarget?.symbol}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label>Type</Label>
              <Select value={editForm.type} onValueChange={(v) => setEditForm((f) => ({ ...f, type: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["buy", "sell", "dividend", "reward", "fee", "transfer"].map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Quantity</Label>
                <Input value={editForm.quantity ?? ""} onChange={(e) => setEditForm((f) => ({ ...f, quantity: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label>Price</Label>
                <Input value={editForm.price ?? ""} onChange={(e) => setEditForm((f) => ({ ...f, price: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label>Fee</Label>
                <Input value={editForm.fee ?? ""} onChange={(e) => setEditForm((f) => ({ ...f, fee: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <Label>Platform</Label>
                <Input value={editForm.platform ?? ""} onChange={(e) => setEditForm((f) => ({ ...f, platform: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-1">
              <Label>Executed At</Label>
              <Input type="datetime-local" value={editForm.executed_at ?? ""} onChange={(e) => setEditForm((f) => ({ ...f, executed_at: e.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTarget(null)}>Cancel</Button>
            <Button onClick={saveEdit} disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete transaction?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This will permanently delete the <strong>{deleteTarget?.type}</strong> transaction for <strong>{deleteTarget?.symbol}</strong>. This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>
              {deleting ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
```

- [ ] **Step 3: Verify in browser**

Start or confirm frontend is running:
```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npm run dev
```

Open `http://localhost:3000/transactions`. Verify:
- Sidebar shows "Transactions" link
- Table loads (empty state shows "No transactions yet")
- Edit dialog opens on pencil click
- Delete confirm dialog appears on trash click

---

## Task 8: Frontend Dividends Page

**Files:**
- Create: `frontend/app/(auth)/dividends/page.tsx`

- [ ] **Step 1: Create dividends page**

```tsx
// frontend/app/(auth)/dividends/page.tsx
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, CheckCircle2 } from "lucide-react";

type DividendEvent = {
  id: string;
  symbol: string;
  ex_date: string;
  pay_date: string | null;
  amount_per_share: string;
  currency: string;
  frequency: string | null;
  status: "upcoming" | "payable" | "paid";
  quantity_held: string;
  projected_total_usd: string;
  projected_total_secondary: string | null;
};

type MonthGroup = {
  year: number;
  month: number;
  total_projected_usd: string;
  events: DividendEvent[];
};

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const STATUS_BADGE: Record<string, string> = {
  upcoming: "bg-blue-100 text-blue-800",
  payable: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
};

function CalendarGrid({ events, onConfirm }: { events: DividendEvent[]; onConfirm: (e: DividendEvent) => void }) {
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDay = new Date(year, month, 1).getDay();

  const byDay: Record<number, DividendEvent[]> = {};
  for (const ev of events) {
    const d = new Date(ev.ex_date);
    if (d.getFullYear() === year && d.getMonth() === month) {
      const day = d.getDate();
      if (!byDay[day]) byDay[day] = [];
      byDay[day].push(ev);
    }
  }

  const cells: (number | null)[] = Array(firstDay).fill(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <div className="border rounded-lg p-4">
      <h2 className="font-semibold mb-3">
        {MONTH_NAMES[month]} {year}
      </h2>
      <div className="grid grid-cols-7 gap-1 text-xs text-center text-muted-foreground mb-1">
        {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((d) => (
          <div key={d} className="py-1 font-medium">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, i) => (
          <div
            key={i}
            className={`min-h-[56px] rounded p-1 text-xs ${day ? "bg-card border" : ""} ${day && day === today.getDate() ? "border-primary" : ""}`}
          >
            {day && (
              <>
                <div className="font-medium text-muted-foreground mb-1">{day}</div>
                {(byDay[day] ?? []).map((ev) => (
                  <div
                    key={ev.id}
                    className={`rounded px-1 py-0.5 mb-0.5 cursor-pointer truncate ${STATUS_BADGE[ev.status]}`}
                    title={`${ev.symbol} – $${parseFloat(ev.amount_per_share).toFixed(4)}/share`}
                    onClick={() => ev.status === "payable" && onConfirm(ev)}
                  >
                    {ev.symbol}
                  </div>
                ))}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DividendsPage() {
  const [calendar, setCalendar] = useState<{ months: MonthGroup[] }>({ months: [] });
  const [upcoming, setUpcoming] = useState<DividendEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState<DividendEvent | null>(null);
  const [confirmQty, setConfirmQty] = useState("");
  const [confirmDate, setConfirmDate] = useState("");
  const [confirming, setConfirming] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    const [calRes, upRes] = await Promise.all([
      api.get("/api/v1/dividends/calendar?months=3"),
      api.get("/api/v1/dividends/upcoming"),
    ]);
    if (calRes.ok) setCalendar(await calRes.json());
    if (upRes.ok) setUpcoming(await upRes.json());
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await api.post("/api/v1/dividends/refresh", {});
    setRefreshing(false);
    setTimeout(fetchData, 2000);
  };

  const openConfirm = (ev: DividendEvent) => {
    setConfirmTarget(ev);
    setConfirmQty(parseFloat(ev.quantity_held).toString());
    setConfirmDate(ev.pay_date ?? new Date().toISOString().slice(0, 10));
  };

  const submitConfirm = async () => {
    if (!confirmTarget) return;
    setConfirming(true);
    const res = await api.post(`/api/v1/dividends/${confirmTarget.id}/confirm`, {
      quantity: parseFloat(confirmQty),
      executed_at: confirmDate,
    });
    setConfirming(false);
    if (res.ok) {
      setConfirmTarget(null);
      fetchData();
    }
  };

  const allEvents = calendar.months.flatMap((m) => m.events);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dividend Calendar</h1>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <>
          <CalendarGrid events={allEvents} onConfirm={openConfirm} />

          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Upcoming Dividends</h2>
            {upcoming.length === 0 ? (
              <p className="text-muted-foreground text-sm">No upcoming dividends. Click Refresh to fetch data.</p>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ticker</TableHead>
                      <TableHead>Ex-Date</TableHead>
                      <TableHead>Pay-Date</TableHead>
                      <TableHead className="text-right">Per Share</TableHead>
                      <TableHead className="text-right">Projected (USD)</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {upcoming.map((ev) => (
                      <TableRow key={ev.id}>
                        <TableCell className="font-medium">{ev.symbol}</TableCell>
                        <TableCell>{ev.ex_date}</TableCell>
                        <TableCell>{ev.pay_date ?? "—"}</TableCell>
                        <TableCell className="text-right">
                          {parseFloat(ev.amount_per_share).toFixed(4)} {ev.currency}
                        </TableCell>
                        <TableCell className="text-right">
                          <div>${parseFloat(ev.projected_total_usd).toFixed(2)}</div>
                          {ev.projected_total_secondary && (
                            <div className="text-muted-foreground text-xs">
                              ≈ {parseFloat(ev.projected_total_secondary).toFixed(0)}
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[ev.status]}`}>
                            {ev.status}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          {ev.status === "payable" && (
                            <Button size="sm" variant="outline" onClick={() => openConfirm(ev)}>
                              <CheckCircle2 className="h-4 w-4 mr-1" />
                              Mark Received
                            </Button>
                          )}
                          {ev.status === "paid" && (
                            <span className="text-xs text-green-600 font-medium">✓ Confirmed</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Mark as Received Dialog */}
      <Dialog open={!!confirmTarget} onOpenChange={(open) => !open && setConfirmTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Dividend — {confirmTarget?.symbol}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Amount per share</span>
              <span className="font-medium">
                {confirmTarget ? parseFloat(confirmTarget.amount_per_share).toFixed(4) : "—"} {confirmTarget?.currency}
              </span>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Quantity received</label>
              <input
                className="w-full border rounded px-3 py-2 text-sm"
                value={confirmQty}
                onChange={(e) => setConfirmQty(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Date received</label>
              <input
                type="date"
                className="w-full border rounded px-3 py-2 text-sm"
                value={confirmDate}
                onChange={(e) => setConfirmDate(e.target.value)}
              />
            </div>
            {confirmQty && confirmTarget && (
              <div className="flex justify-between font-semibold border-t pt-2">
                <span>Total income</span>
                <span>
                  ${(parseFloat(confirmQty) * parseFloat(confirmTarget.amount_per_share)).toFixed(2)} {confirmTarget.currency}
                </span>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmTarget(null)}>Cancel</Button>
            <Button onClick={submitConfirm} disabled={confirming || !confirmQty || !confirmDate}>
              {confirming ? "Saving…" : "Confirm & Record"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Open `http://localhost:3000/dividends`. Verify:
- Sidebar highlights "Dividends" correctly
- Calendar grid renders current month
- Upcoming table shows (empty if no data fetched yet)
- Refresh button triggers job and shows spinner
- After refresh + 2s delay, data appears if holdings have dividends
- Clicking a yellow "payable" event opens Mark as Received dialog
- Confirming creates a transaction (verify in `/transactions` page)

---

## Self-Review Checklist

- [x] Migration 013 creates `dividend_events` table with all columns from spec
- [x] `DividendEvent` model matches migration exactly
- [x] `_build_rows_for_asset` and `_compute_status` are pure functions — unit-testable without DB
- [x] `fetch_all_dividends` upserts without overwriting `paid` status (on_conflict only updates amount + pay_date)
- [x] `get_calendar` and `get_upcoming` join holdings for user-specific projected income
- [x] Worker registers job + weekly cron
- [x] `POST /dividends/refresh` enqueues on-demand via arq `create_pool`
- [x] `POST /dividends/{id}/confirm` creates `type=dividend` transaction + links event
- [x] Portfolio service: `get_transaction`, `update_transaction`, `delete_transaction`, `list_transactions_with_assets` all follow existing `get/update/delete_holding` pattern
- [x] `GET /portfolio/transactions` now returns `TransactionRow` (includes symbol)
- [x] `PATCH /portfolio/transactions/{id}` and `DELETE /portfolio/transactions/{id}` added
- [x] Sidebar: `/dividends` already existed, only `/transactions` added
- [x] Transactions page: edit + delete with confirmation dialogs
- [x] Dividends page: calendar grid + upcoming list + mark-as-received dialog
- [x] All type names consistent: `DividendEventOut`, `DividendCalendarResponse`, `DividendConfirmRequest`, `TransactionRow`, `TransactionUpdate`
