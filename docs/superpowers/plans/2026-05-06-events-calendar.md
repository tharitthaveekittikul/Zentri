# Events Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the Dividends page into a unified Events Calendar showing dividends + IPOs with color-coded dots, watchlist integration, and on-demand LLM analysis for IPOs.

**Architecture:** Unified `GET /api/v1/events/calendar` endpoint returns both event types as a typed union. A new `IpoEvent` model stores IPO data seeded from watchlist tickers via yfinance. LLM analysis uses the existing `LLMGateway` with a new `ipo_analysis` feature key assignable in Settings → AI & LLM.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, yfinance, Next.js 14 App Router, shadcn/ui, TypeScript

---

## File Map

### New Files
- `backend/app/models/ipo_event.py` — IpoEvent SQLAlchemy model
- `backend/app/schemas/ipo.py` — IpoEvent Pydantic schemas
- `backend/app/schemas/events.py` — Unified calendar response schema
- `backend/app/services/ipo_feed.py` — yfinance IPO data fetching + DB upsert
- `backend/app/services/events_calendar.py` — Merges dividends + IPOs by month
- `backend/app/api/events.py` — GET /events/calendar router
- `backend/app/api/ipos.py` — POST /ipos/{id}/analyze router
- `backend/alembic/versions/018_ipo_events_and_ai_analysis_update.py` — Migration
- `backend/tests/services/test_ipo_feed.py` — ipo_feed service tests
- `backend/tests/api/test_events.py` — events API tests
- `backend/tests/api/test_ipos.py` — IPO analyze endpoint tests
- `frontend/app/(auth)/events/page.tsx` — New unified Events page
- `frontend/lib/services/events.ts` — Frontend API client for events

### Modified Files
- `backend/app/services/llm_gateway.py` — Add `ipo_analysis` to FEATURE_KEYS, DEFAULT_SYSTEM_PROMPTS, HUMAN_PROMPTS
- `backend/app/models/feature_llm_config.py` — Add `"ipo_analysis"` to FEATURE_KEYS tuple
- `backend/app/models/ai_analysis.py` — Make `asset_id` nullable, add `ipo_event_id` FK
- `backend/app/main.py` — Register events + ipos routers
- `frontend/app/(auth)/dividends/page.tsx` — Replace with redirect to /events
- `frontend/app/(auth)/layout.tsx` — Update nav link "Dividends" → "Events"

---

## Task 1: Add `ipo_analysis` feature key and prompts

**Files:**
- Modify: `backend/app/models/feature_llm_config.py`
- Modify: `backend/app/services/llm_gateway.py`

- [ ] **Step 1: Add to FEATURE_KEYS in feature_llm_config.py**

Open `backend/app/models/feature_llm_config.py`. Find the `FEATURE_KEYS` tuple and add `"ipo_analysis"`:

```python
FEATURE_KEYS = (
    "import_translator",
    "portfolio_analysis",
    "chat",
    "watchlist_scan",
    "watchlist_discovery",
    "ipo_analysis",
)
```

- [ ] **Step 2: Add to FEATURE_KEYS in llm_gateway.py**

Open `backend/app/services/llm_gateway.py`. Find the `FEATURE_KEYS` tuple near the top and add `"ipo_analysis"`:

```python
FEATURE_KEYS = (
    "import_translator",
    "portfolio_analysis",
    "chat",
    "watchlist_scan",
    "watchlist_discovery",
    "ipo_analysis",
)
```

- [ ] **Step 3: Add to DEFAULT_SYSTEM_PROMPTS in llm_gateway.py**

In `llm_gateway.py`, find `DEFAULT_SYSTEM_PROMPTS` dict and add:

```python
    "ipo_analysis": (
        "You are a financial analyst specializing in IPO evaluations. "
        "Given IPO data, assess whether to Buy, Watch, or Skip this offering. "
        "Provide a suggested entry price and concise reasoning. "
        "Respond ONLY with valid JSON in this exact format:\n"
        "{\"verdict\": \"BUY\" | \"WATCH\" | \"SKIP\", \"suggested_price\": <number or null>, "
        "\"reasoning\": \"<2-3 sentence explanation>\"}\n"
        "Do not include any text outside the JSON object."
    ),
```

- [ ] **Step 4: Add to HUMAN_PROMPTS in llm_gateway.py**

In `llm_gateway.py`, find `HUMAN_PROMPTS` dict and add:

```python
    "ipo_analysis": (
        "Analyze this upcoming IPO and provide an investment recommendation.\n\n"
        "Symbol: {symbol}\n"
        "Company: {company_name}\n"
        "Sector: {sector}\n"
        "IPO Date: {ipo_date}\n"
        "Expected Price Range: {price_low} - {price_high} USD\n"
        "Business Description: {description}\n"
        "Market Cap: {market_cap}\n"
        "Trailing P/E: {pe_ratio}"
    ),
```

- [ ] **Step 5: Verify no import errors**

```bash
cd backend && python -c "from app.services.llm_gateway import DEFAULT_SYSTEM_PROMPTS, HUMAN_PROMPTS; print('ipo_analysis' in DEFAULT_SYSTEM_PROMPTS, 'ipo_analysis' in HUMAN_PROMPTS)"
```

Expected: `True True`

---

## Task 2: Create IpoEvent model

**Files:**
- Create: `backend/app/models/ipo_event.py`
- Modify: `backend/app/models/__init__.py` (add import so Alembic sees the model)

- [ ] **Step 1: Create the model**

Create `backend/app/models/ipo_event.py`:

```python
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

IPO_EVENT_STATUSES = ("upcoming", "priced", "listed")


class IpoEvent(Base):
    __tablename__ = "ipo_events"
    __table_args__ = (UniqueConstraint("symbol", "ipo_date", name="uq_ipo_events_symbol_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ipo_date: Mapped[date] = mapped_column(Date, nullable=False)
    price_low: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    price_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*IPO_EVENT_STATUSES, name="ipo_event_status_enum"), nullable=False, default="upcoming"
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="yfinance")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Register in models __init__.py**

Open `backend/app/models/__init__.py`. Add `IpoEvent` alongside other model imports so Alembic auto-detects it. Follow the existing import pattern in that file.

- [ ] **Step 3: Verify model imports cleanly**

```bash
cd backend && python -c "from app.models.ipo_event import IpoEvent; print(IpoEvent.__tablename__)"
```

Expected: `ipo_events`

---

## Task 3: Update AIAnalysis model

**Files:**
- Modify: `backend/app/models/ai_analysis.py`

Current `asset_id` is non-nullable UUID. IPO analyses have no portfolio asset, so we must make it nullable and add an `ipo_event_id` FK.

- [ ] **Step 1: Update the model**

Open `backend/app/models/ai_analysis.py`. Replace the file content with:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ipo_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ipo_events.id"), nullable=True
    )
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

- [ ] **Step 2: Verify imports cleanly**

```bash
cd backend && python -c "from app.models.ai_analysis import AIAnalysis; print('ok')"
```

Expected: `ok`

---

## Task 4: Write and run the Alembic migration

**Files:**
- Create: `backend/alembic/versions/018_ipo_events_and_ai_analysis_update.py`

- [ ] **Step 1: Verify migration number**

```bash
ls backend/alembic/versions/ | grep -v __pycache__ | sort | tail -3
```

If the latest is not `017_*`, adjust the filename prefix to be one higher than the current latest.

- [ ] **Step 2: Generate migration**

```bash
cd backend && alembic revision --autogenerate -m "ipo_events_and_ai_analysis_update"
```

This creates a new file in `alembic/versions/`. Rename it to start with `018_` if needed.

- [ ] **Step 3: Verify generated migration**

Open the generated file. It should contain:
- `op.create_table("ipo_events", ...)` — creates the IpoEvent table with all columns
- `op.create_unique_constraint("uq_ipo_events_symbol_date", "ipo_events", ["symbol", "ipo_date"])`
- `op.alter_column("ai_analyses", "asset_id", nullable=True)`
- `op.add_column("ai_analyses", sa.Column("ipo_event_id", ...))`

If autogenerate missed any of these, add them manually following SQLAlchemy Alembic op patterns.

- [ ] **Step 4: Run the migration**

```bash
cd backend && alembic upgrade head
```

Expected: Migration runs without errors.

- [ ] **Step 5: Verify tables exist**

```bash
cd backend && python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        r = await conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_name IN ('ipo_events')\"))
        print(r.fetchall())

asyncio.run(check())
"
```

Expected: `[('ipo_events',)]`

---

## Task 5: Create IPO and Events schemas

**Files:**
- Create: `backend/app/schemas/ipo.py`
- Create: `backend/app/schemas/events.py`

- [ ] **Step 1: Create ipo.py**

Create `backend/app/schemas/ipo.py`:

```python
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class IpoEventOut(BaseModel):
    id: uuid.UUID
    symbol: str
    company_name: Optional[str] = None
    ipo_date: date
    price_low: Optional[Decimal] = None
    price_high: Optional[Decimal] = None
    sector: Optional[str] = None
    status: str
    source: str
    is_in_watchlist: bool = False

    model_config = {"from_attributes": False}


class IpoAnalysisResult(BaseModel):
    verdict: str
    suggested_price: Optional[Decimal] = None
    reasoning: str
    provider: str
    model: str
    cached: bool = False
```

- [ ] **Step 2: Create events.py**

Create `backend/app/schemas/events.py`:

```python
from datetime import date
from decimal import Decimal
from typing import Literal, Optional, Union
import uuid

from pydantic import BaseModel


class DividendCalendarEvent(BaseModel):
    event_type: Literal["dividend"] = "dividend"
    id: uuid.UUID
    symbol: str
    asset_id: uuid.UUID
    event_date: date
    pay_date: Optional[date] = None
    amount_per_share: Decimal
    currency: str
    status: str
    projected_total_usd: Decimal
    quantity_held: Decimal
    is_in_watchlist: bool = False


class IpoCalendarEvent(BaseModel):
    event_type: Literal["ipo"] = "ipo"
    id: uuid.UUID
    symbol: str
    event_date: date
    company_name: Optional[str] = None
    price_low: Optional[Decimal] = None
    price_high: Optional[Decimal] = None
    sector: Optional[str] = None
    status: str
    is_in_watchlist: bool = False


CalendarEvent = Union[DividendCalendarEvent, IpoCalendarEvent]


class EventsMonthGroup(BaseModel):
    year: int
    month: int
    events: list[CalendarEvent]


class EventsCalendarResponse(BaseModel):
    months: list[EventsMonthGroup]
```

- [ ] **Step 3: Verify schemas import cleanly**

```bash
cd backend && python -c "from app.schemas.events import EventsCalendarResponse; from app.schemas.ipo import IpoEventOut, IpoAnalysisResult; print('ok')"
```

Expected: `ok`

---

## Task 6: Create ipo_feed service

**Files:**
- Create: `backend/app/services/ipo_feed.py`
- Create: `backend/tests/services/test_ipo_feed.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/test_ipo_feed.py`:

```python
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ipo_feed import extract_ipo_info


def test_extract_ipo_info_with_valid_data():
    info = {
        "ipoDate": "2026-06-15",
        "longName": "Acme Corp",
        "sector": "Technology",
        "fiftyTwoWeekLow": 10.0,
        "fiftyTwoWeekHigh": 15.0,
    }
    result = extract_ipo_info("ACME", info)
    assert result is not None
    assert result["symbol"] == "ACME"
    assert result["company_name"] == "Acme Corp"
    assert result["ipo_date"] == date(2026, 6, 15)
    assert result["sector"] == "Technology"


def test_extract_ipo_info_with_no_ipo_date():
    info = {"longName": "No Date Corp"}
    result = extract_ipo_info("NDC", info)
    assert result is None


def test_extract_ipo_info_with_past_ipo_date():
    info = {"ipoDate": "2020-01-01", "longName": "Old Corp"}
    result = extract_ipo_info("OLD", info)
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/services/test_ipo_feed.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — service doesn't exist yet.

- [ ] **Step 3: Implement ipo_feed.py**

Create `backend/app/services/ipo_feed.py`:

```python
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ipo_event import IpoEvent
from app.models.watchlist_item import WatchlistItem

logger = get_logger(__name__)


def extract_ipo_info(symbol: str, info: dict) -> Optional[dict]:
    raw_date = info.get("ipoDate")
    if not raw_date:
        return None
    try:
        ipo_date = date.fromisoformat(raw_date)
    except (ValueError, TypeError):
        return None
    cutoff = date.today() - timedelta(days=90)
    if ipo_date < cutoff:
        return None
    return {
        "symbol": symbol,
        "company_name": info.get("longName") or info.get("shortName"),
        "ipo_date": ipo_date,
        "price_low": Decimal(str(info["fiftyTwoWeekLow"])) if info.get("fiftyTwoWeekLow") else None,
        "price_high": Decimal(str(info["fiftyTwoWeekHigh"])) if info.get("fiftyTwoWeekHigh") else None,
        "sector": info.get("sector"),
        "status": "upcoming" if ipo_date >= date.today() else "listed",
        "source": "yfinance",
    }


async def refresh_ipos_from_watchlist(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(WatchlistItem.symbol).where(WatchlistItem.user_id == user_id)
    )
    symbols = [row[0] for row in result.fetchall()]
    if not symbols:
        return 0

    upserted = 0
    for symbol in symbols:
        try:
            info = yf.Ticker(symbol).info
            data = extract_ipo_info(symbol, info)
            if not data:
                continue
            stmt = (
                pg_insert(IpoEvent)
                .values(id=uuid.uuid4(), **data)
                .on_conflict_do_update(
                    constraint="uq_ipo_events_symbol_date",
                    set_={k: v for k, v in data.items() if k not in ("symbol", "ipo_date")},
                )
            )
            await db.execute(stmt)
            upserted += 1
        except Exception as exc:
            logger.warning("Failed to fetch IPO data for %s: %s", symbol, exc)
    await db.commit()
    logger.info("refresh_ipos_from_watchlist: upserted %d rows for user %s", upserted, user_id)
    return upserted


async def get_ipo_events(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> list[dict]:
    result = await db.execute(
        select(IpoEvent).where(
            IpoEvent.ipo_date >= start_date,
            IpoEvent.ipo_date <= end_date,
        )
    )
    events = result.scalars().all()

    watchlist_result = await db.execute(
        select(WatchlistItem.symbol).where(WatchlistItem.user_id == user_id)
    )
    watchlist_symbols = {row[0] for row in watchlist_result.fetchall()}

    return [
        {
            "id": ev.id,
            "symbol": ev.symbol,
            "company_name": ev.company_name,
            "ipo_date": ev.ipo_date,
            "price_low": ev.price_low,
            "price_high": ev.price_high,
            "sector": ev.sector,
            "status": ev.status,
            "source": ev.source,
            "is_in_watchlist": ev.symbol in watchlist_symbols,
        }
        for ev in events
    ]


async def get_event(db: AsyncSession, event_id: uuid.UUID) -> IpoEvent | None:
    result = await db.execute(select(IpoEvent).where(IpoEvent.id == event_id))
    return result.scalar_one_or_none()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/services/test_ipo_feed.py -v
```

Expected: All 3 tests PASS.

---

## Task 7: Create events_calendar service

**Files:**
- Create: `backend/app/services/events_calendar.py`

- [ ] **Step 1: Create the service**

Create `backend/app/services/events_calendar.py`:

```python
import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services import dividend_feed, ipo_feed

logger = get_logger(__name__)


async def get_calendar(
    db: AsyncSession,
    user_id: uuid.UUID,
    months: int,
    secondary_currency: str,
) -> dict:
    today = date.today()
    start_date = today - timedelta(days=30)
    end_date = today + timedelta(days=months * 31)

    dividend_events_raw, ipo_events_raw = await _fetch_both(
        db, user_id, start_date, end_date, secondary_currency
    )

    dividend_events = [
        {
            "event_type": "dividend",
            "id": e["id"],
            "symbol": e["symbol"],
            "asset_id": e["asset_id"],
            "event_date": e["ex_date"],
            "pay_date": e.get("pay_date"),
            "amount_per_share": e["amount_per_share"],
            "currency": e["currency"],
            "status": e["status"],
            "projected_total_usd": e["projected_total_usd"],
            "quantity_held": e["quantity_held"],
            "is_in_watchlist": False,
        }
        for e in dividend_events_raw
    ]

    ipo_events = [
        {
            "event_type": "ipo",
            "id": e["id"],
            "symbol": e["symbol"],
            "event_date": e["ipo_date"],
            "company_name": e.get("company_name"),
            "price_low": e.get("price_low"),
            "price_high": e.get("price_high"),
            "sector": e.get("sector"),
            "status": e["status"],
            "is_in_watchlist": e["is_in_watchlist"],
        }
        for e in ipo_events_raw
    ]

    all_events = dividend_events + ipo_events
    return _group_by_month(all_events, start_date, end_date)


async def _fetch_both(db, user_id, start_date, end_date, secondary_currency):
    import asyncio
    dividend_task = asyncio.create_task(
        dividend_feed.get_calendar(db, user_id, 3, secondary_currency)
    )
    ipo_task = asyncio.create_task(
        ipo_feed.get_ipo_events(db, user_id, start_date, end_date)
    )
    dividend_result, ipo_result = await asyncio.gather(dividend_task, ipo_task)
    dividend_raw = []
    if isinstance(dividend_result, dict):
        for month in dividend_result.get("months", []):
            dividend_raw.extend(month.get("events", []))
    return dividend_raw, ipo_result


def _group_by_month(events: list[dict], start_date: date, end_date: date) -> dict:
    months: dict[tuple[int, int], list] = {}
    current = start_date.replace(day=1)
    while current <= end_date:
        months[(current.year, current.month)] = []
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    for event in events:
        d = event["event_date"]
        key = (d.year, d.month)
        if key in months:
            months[key].append(event)

    return {
        "months": [
            {"year": y, "month": m, "events": evts}
            for (y, m), evts in sorted(months.items())
        ]
    }
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from app.services.events_calendar import get_calendar; print('ok')"
```

Expected: `ok`

---

## Task 8: Create events API router

**Files:**
- Create: `backend/app/api/events.py`
- Create: `backend/tests/api/test_events.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_events.py`:

```python
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_events_calendar_returns_200(auth_client: AsyncClient):
    mock_result = {"months": []}
    with patch(
        "app.api.events.events_calendar.get_calendar",
        new=AsyncMock(return_value=mock_result),
    ):
        response = await auth_client.get("/api/v1/events/calendar?months=3")
    assert response.status_code == 200
    data = response.json()
    assert "months" in data


@pytest.mark.asyncio
async def test_get_events_calendar_validates_months(auth_client: AsyncClient):
    response = await auth_client.get("/api/v1/events/calendar?months=0")
    assert response.status_code == 400

    response = await auth_client.get("/api/v1/events/calendar?months=13")
    assert response.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/api/test_events.py -v
```

Expected: FAIL — router not registered yet.

- [ ] **Step 3: Create the router**

Create `backend/app/api/events.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.events import EventsCalendarResponse
from app.services import events_calendar

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/calendar", response_model=EventsCalendarResponse)
async def get_calendar(
    months: int = 3,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if months < 1 or months > 12:
        raise HTTPException(status_code=400, detail="months must be between 1 and 12")
    result = await events_calendar.get_calendar(
        db, current_user.id, months, current_user.currency_secondary
    )
    return result
```

- [ ] **Step 4: Register router in main.py**

Open `backend/app/main.py`. In the import block, add `events` and `ipos` to the `from app.api import (...)` statement. Then add two lines after the dividends router:

```python
app.include_router(events.router, prefix="/api/v1")
app.include_router(ipos.router, prefix="/api/v1")
```

(Create `app/api/ipos.py` as an empty router stub first so the import doesn't fail — see Task 9.)

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/api/test_events.py -v
```

Expected: PASS

---

## Task 9: Create IPO analyze endpoint

**Files:**
- Create: `backend/app/api/ipos.py`
- Create: `backend/tests/api/test_ipos.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_ipos.py`:

```python
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_analyze_ipo_not_found(auth_client: AsyncClient):
    fake_id = str(uuid.uuid4())
    with patch("app.api.ipos.ipo_feed.get_event", new=AsyncMock(return_value=None)):
        response = await auth_client.post(f"/api/v1/ipos/{fake_id}/analyze")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyze_ipo_llm_not_configured(auth_client: AsyncClient):
    fake_event = MagicMock()
    fake_event.id = uuid.uuid4()
    fake_event.symbol = "ACME"
    fake_event.company_name = "Acme Corp"
    fake_event.sector = "Technology"
    fake_event.ipo_date = date(2026, 7, 1)
    fake_event.price_low = None
    fake_event.price_high = None

    with (
        patch("app.api.ipos.ipo_feed.get_event", new=AsyncMock(return_value=fake_event)),
        patch("app.api.ipos._get_cached_analysis", new=AsyncMock(return_value=None)),
        patch(
            "app.api.ipos.LLMGateway.complete",
            side_effect=ValueError("No LLM config for feature 'ipo_analysis'"),
        ),
    ):
        response = await auth_client.post(f"/api/v1/ipos/{fake_event.id}/analyze")
    assert response.status_code == 400
    assert "Settings" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/api/test_ipos.py -v
```

Expected: FAIL — router not yet fully implemented.

- [ ] **Step 3: Implement the router**

Create `backend/app/api/ipos.py`:

```python
import json
import uuid
from datetime import date, datetime, timezone

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.user import User
from app.schemas.ipo import IpoAnalysisResult
from app.services import ipo_feed
from app.services.llm_gateway import LLMGateway

logger = get_logger(__name__)
router = APIRouter(prefix="/ipos", tags=["ipos"])


async def _get_cached_analysis(db: AsyncSession, ipo_event_id: uuid.UUID) -> AIAnalysis | None:
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    result = await db.execute(
        select(AIAnalysis).where(
            AIAnalysis.ipo_event_id == ipo_event_id,
            AIAnalysis.created_at >= today_start,
        )
    )
    return result.scalar_one_or_none()


@router.post("/{event_id}/analyze", response_model=IpoAnalysisResult)
async def analyze_ipo(
    event_id: uuid.UUID,
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await ipo_feed.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="IPO event not found")

    if not force:
        cached = await _get_cached_analysis(db, event_id)
        if cached:
            return IpoAnalysisResult(
                verdict=cached.verdict,
                suggested_price=cached.target_price,
                reasoning=cached.reasoning,
                provider=cached.provider,
                model=cached.model,
                cached=True,
            )

    try:
        info = yf.Ticker(event.symbol).info
    except Exception:
        info = {}

    variables = {
        "symbol": event.symbol,
        "company_name": event.company_name or "N/A",
        "sector": event.sector or "N/A",
        "ipo_date": str(event.ipo_date),
        "price_low": str(event.price_low) if event.price_low else "N/A",
        "price_high": str(event.price_high) if event.price_high else "N/A",
        "description": (info.get("longBusinessSummary", "N/A") or "N/A")[:500],
        "market_cap": str(info.get("marketCap", "N/A")),
        "pe_ratio": str(info.get("trailingPE", "N/A")),
    }

    try:
        gateway = LLMGateway(db)
        result = await gateway.complete("ipo_analysis", current_user.id, variables)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"LLM not configured for IPO analysis. Please assign a model in Settings → AI & LLM.",
        ) from exc

    try:
        parsed = json.loads(result.content)
        verdict = parsed.get("verdict", "WATCH")
        suggested_price = parsed.get("suggested_price")
        reasoning = parsed.get("reasoning", result.content)
    except (json.JSONDecodeError, AttributeError):
        verdict = "WATCH"
        suggested_price = None
        reasoning = result.content

    analysis = AIAnalysis(
        ipo_event_id=event_id,
        verdict=verdict,
        target_price=suggested_price,
        reasoning=reasoning,
        provider=result.provider,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
    )
    db.add(analysis)
    await db.commit()
    logger.info("IPO analysis stored: event=%s verdict=%s", event_id, verdict)

    return IpoAnalysisResult(
        verdict=verdict,
        suggested_price=suggested_price,
        reasoning=reasoning,
        provider=result.provider,
        model=result.model,
        cached=False,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/api/test_ipos.py -v
```

Expected: PASS

- [ ] **Step 5: Smoke test the full backend starts**

```bash
cd backend && python -c "from app.main import app; print('app loads ok')"
```

Expected: `app loads ok`

---

## Task 10: Create frontend events service

**Files:**
- Create: `frontend/lib/services/events.ts`

- [ ] **Step 1: Create the service**

Create `frontend/lib/services/events.ts`:

```typescript
import { api } from "@/lib/api";

export type DividendCalendarEvent = {
  event_type: "dividend";
  id: string;
  symbol: string;
  asset_id: string;
  event_date: string;
  pay_date: string | null;
  amount_per_share: string;
  currency: string;
  status: "upcoming" | "payable" | "paid";
  projected_total_usd: string;
  quantity_held: string;
  is_in_watchlist: boolean;
};

export type IpoCalendarEvent = {
  event_type: "ipo";
  id: string;
  symbol: string;
  event_date: string;
  company_name: string | null;
  price_low: string | null;
  price_high: string | null;
  sector: string | null;
  status: "upcoming" | "priced" | "listed";
  is_in_watchlist: boolean;
};

export type CalendarEvent = DividendCalendarEvent | IpoCalendarEvent;

export type EventsMonthGroup = {
  year: number;
  month: number;
  events: CalendarEvent[];
};

export type EventsCalendarResponse = {
  months: EventsMonthGroup[];
};

export type IpoAnalysisResult = {
  verdict: "BUY" | "WATCH" | "SKIP";
  suggested_price: string | null;
  reasoning: string;
  provider: string;
  model: string;
  cached: boolean;
};

export async function fetchEventsCalendar(months = 3): Promise<EventsCalendarResponse> {
  const res = await api.get(`/api/v1/events/calendar?months=${months}`);
  if (!res.ok) throw new Error("Failed to fetch events calendar");
  return res.json();
}

export async function analyzeIpo(
  eventId: string,
  force = false
): Promise<IpoAnalysisResult> {
  const res = await api.post(
    `/api/v1/ipos/${eventId}/analyze${force ? "?force=true" : ""}`,
    {}
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Analysis failed" }));
    throw new Error(err.detail || "Analysis failed");
  }
  return res.json();
}
```

---

## Task 11: Create Events page

**Files:**
- Create: `frontend/app/(auth)/events/page.tsx`

This replaces the dividends page with a unified calendar. The CalendarGrid component is reproduced here (do not import from dividends page — it will be replaced).

- [ ] **Step 1: Create the page**

Create `frontend/app/(auth)/events/page.tsx`:

```typescript
"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
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
import { api } from "@/lib/api";
import {
  fetchEventsCalendar,
  analyzeIpo,
  CalendarEvent,
  DividendCalendarEvent,
  IpoCalendarEvent,
  IpoAnalysisResult,
} from "@/lib/services/events";

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

type FilterType = "all" | "dividend" | "ipo" | "watchlist";

const VERDICT_STYLE: Record<string, string> = {
  BUY: "bg-green-100 text-green-800",
  WATCH: "bg-yellow-100 text-yellow-800",
  SKIP: "bg-red-100 text-red-800",
};

const STATUS_BADGE: Record<string, string> = {
  upcoming: "bg-blue-100 text-blue-800",
  payable: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
  priced: "bg-purple-100 text-purple-800",
  listed: "bg-gray-100 text-gray-800",
};

function filterEvents(events: CalendarEvent[], filter: FilterType): CalendarEvent[] {
  if (filter === "all") return events;
  if (filter === "dividend") return events.filter((e) => e.event_type === "dividend");
  if (filter === "ipo") return events.filter((e) => e.event_type === "ipo");
  if (filter === "watchlist") return events.filter((e) => e.is_in_watchlist);
  return events;
}

function CalendarGrid({
  events,
  onSelectDividend,
  onSelectIpo,
}: {
  events: CalendarEvent[];
  onSelectDividend: (e: DividendCalendarEvent) => void;
  onSelectIpo: (e: IpoCalendarEvent) => void;
}) {
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstDay = new Date(viewYear, viewMonth, 1).getDay();
  const isCurrentMonth = viewYear === today.getFullYear() && viewMonth === today.getMonth();

  const prev = () => {
    if (viewMonth === 0) { setViewYear((y) => y - 1); setViewMonth(11); }
    else setViewMonth((m) => m - 1);
  };
  const next = () => {
    if (viewMonth === 11) { setViewYear((y) => y + 1); setViewMonth(0); }
    else setViewMonth((m) => m + 1);
  };

  const byDay: Record<number, CalendarEvent[]> = {};
  for (const ev of events) {
    const d = new Date(ev.event_date);
    if (d.getFullYear() === viewYear && d.getMonth() === viewMonth) {
      const day = d.getDate();
      if (!byDay[day]) byDay[day] = [];
      byDay[day].push(ev);
    }
  }

  const cells: (number | null)[] = Array(firstDay).fill(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
        <Button variant="ghost" size="icon" onClick={prev}><ChevronLeft className="h-4 w-4" /></Button>
        <span className="font-semibold text-sm">
          {MONTH_NAMES[viewMonth]} {viewYear}
          {isCurrentMonth && <span className="ml-2 text-xs text-muted-foreground">(current)</span>}
        </span>
        <Button variant="ghost" size="icon" onClick={next}><ChevronRight className="h-4 w-4" /></Button>
      </div>
      <div className="grid grid-cols-7 text-xs text-center text-muted-foreground border-b">
        {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((d) => (
          <div key={d} className="py-1">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {cells.map((day, i) => (
          <div
            key={i}
            className={`min-h-[72px] border-b border-r p-1 text-xs ${!day ? "bg-muted/10" : ""} ${
              day === today.getDate() && isCurrentMonth ? "bg-blue-50" : ""
            }`}
          >
            {day && (
              <>
                <div className="text-muted-foreground mb-1">{day}</div>
                {(byDay[day] || []).map((ev) => (
                  <div
                    key={ev.id}
                    onClick={() =>
                      ev.event_type === "dividend"
                        ? onSelectDividend(ev as DividendCalendarEvent)
                        : onSelectIpo(ev as IpoCalendarEvent)
                    }
                    className={`truncate rounded px-1 py-0.5 mb-0.5 cursor-pointer text-[10px] font-medium flex items-center gap-0.5 ${
                      ev.event_type === "dividend"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-orange-100 text-orange-800"
                    }`}
                  >
                    {ev.is_in_watchlist && <span>★</span>}
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

function IpoPanel({
  event,
  onClose,
}: {
  event: IpoCalendarEvent;
  onClose: () => void;
}) {
  const [analysis, setAnalysis] = useState<IpoAnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const runAnalysis = async (force = false) => {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const result = await analyzeIpo(event.id, force);
      setAnalysis(result);
    } catch (err: unknown) {
      setAnalyzeError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded text-xs bg-orange-100 text-orange-800 font-medium">IPO</span>
            {event.symbol}
            {event.company_name && <span className="text-sm font-normal text-muted-foreground">— {event.company_name}</span>}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">IPO Date</span>
            <span>{event.event_date}</span>
          </div>
          {event.sector && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Sector</span>
              <span>{event.sector}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-muted-foreground">Price Range</span>
            <span>
              {event.price_low && event.price_high
                ? `$${event.price_low} – $${event.price_high}`
                : "N/A"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Status</span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[event.status] || ""}`}>
              {event.status}
            </span>
          </div>
          {event.is_in_watchlist && (
            <div className="text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded px-2 py-1">
              ★ In your watchlist
            </div>
          )}
        </div>

        <div className="border-t pt-3 space-y-3">
          {!analysis && !analyzing && (
            <Button onClick={() => runAnalysis(false)} className="w-full" disabled={analyzing}>
              Analyze with AI
            </Button>
          )}
          {analyzing && (
            <div className="text-center text-sm text-muted-foreground">Analyzing…</div>
          )}
          {analyzeError && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {analyzeError.includes("Settings") ? (
                <>LLM not configured. <a href="/settings" className="underline">Set up in Settings →</a></>
              ) : analyzeError}
            </div>
          )}
          {analysis && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className={`px-3 py-1 rounded-full text-sm font-bold ${VERDICT_STYLE[analysis.verdict] || ""}`}>
                  {analysis.verdict}
                </span>
                {analysis.suggested_price && (
                  <span className="text-sm font-medium">Target: ${analysis.suggested_price}</span>
                )}
                {analysis.cached && <span className="text-xs text-muted-foreground">cached</span>}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{analysis.reasoning}</p>
              <Button variant="ghost" size="sm" onClick={() => runAnalysis(true)} disabled={analyzing}>
                Re-analyze
              </Button>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function EventsPage() {
  const [allEvents, setAllEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedDividend, setSelectedDividend] = useState<DividendCalendarEvent | null>(null);
  const [selectedIpo, setSelectedIpo] = useState<IpoCalendarEvent | null>(null);
  const [confirmQty, setConfirmQty] = useState("");
  const [confirmDate, setConfirmDate] = useState("");
  const [confirming, setConfirming] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const data = await fetchEventsCalendar(3);
      setAllEvents(data.months.flatMap((m) => m.events));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await api.post("/api/v1/dividends/refresh", {});
    setRefreshing(false);
    setTimeout(fetchData, 2000);
  };

  const openDividend = (ev: DividendCalendarEvent) => {
    if (ev.status !== "payable") return;
    setSelectedDividend(ev);
    setConfirmQty(parseFloat(ev.quantity_held).toString());
    setConfirmDate(ev.pay_date ?? new Date().toISOString().slice(0, 10));
  };

  const submitConfirm = async () => {
    if (!selectedDividend) return;
    setConfirming(true);
    const res = await api.post(`/api/v1/dividends/${selectedDividend.id}/confirm`, {
      quantity: parseFloat(confirmQty),
      executed_at: confirmDate,
    });
    setConfirming(false);
    if (res.ok) { setSelectedDividend(null); fetchData(); }
  };

  const filtered = filterEvents(allEvents, filter);

  const FILTERS: { key: FilterType; label: string }[] = [
    { key: "all", label: "All" },
    { key: "dividend", label: "Dividends" },
    { key: "ipo", label: "IPOs" },
    { key: "watchlist", label: "Watchlist only" },
  ];

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Events</h1>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw className={`h-4 w-4 mr-1 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <div className="flex gap-2 flex-wrap">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-3 py-1 rounded-full text-sm font-medium border transition-colors ${
              filter === key
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-background border-border text-muted-foreground hover:border-primary"
            }`}
          >
            {label}
          </button>
        ))}
        <div className="flex items-center gap-3 ml-auto text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-200 inline-block" /> Dividend</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-200 inline-block" /> IPO</span>
          <span>★ Watchlist</span>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-muted-foreground">Loading…</div>
      ) : (
        <CalendarGrid
          events={filtered}
          onSelectDividend={openDividend}
          onSelectIpo={setSelectedIpo}
        />
      )}

      <div>
        <h2 className="text-lg font-semibold mb-2">Upcoming Events</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Symbol</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Details</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered
              .filter((e) => e.status !== "paid" && e.status !== "listed")
              .sort((a, b) => a.event_date.localeCompare(b.event_date))
              .map((ev) => (
                <TableRow key={ev.id}>
                  <TableCell className="font-medium">
                    {ev.is_in_watchlist && <span className="text-yellow-500 mr-1">★</span>}
                    {ev.symbol}
                  </TableCell>
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      ev.event_type === "dividend" ? "bg-blue-100 text-blue-800" : "bg-orange-100 text-orange-800"
                    }`}>
                      {ev.event_type === "dividend" ? "Dividend" : "IPO"}
                    </span>
                  </TableCell>
                  <TableCell>{ev.event_date}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {ev.event_type === "dividend"
                      ? `$${parseFloat((ev as DividendCalendarEvent).amount_per_share).toFixed(4)}/sh`
                      : (ev as IpoCalendarEvent).price_low
                      ? `$${(ev as IpoCalendarEvent).price_low}–$${(ev as IpoCalendarEvent).price_high}`
                      : "N/A"}
                  </TableCell>
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[ev.status] || ""}`}>
                      {ev.status}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>

      {selectedIpo && (
        <IpoPanel event={selectedIpo} onClose={() => setSelectedIpo(null)} />
      )}

      <Dialog open={!!selectedDividend} onOpenChange={(open) => !open && setSelectedDividend(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Dividend — {selectedDividend?.symbol}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Amount per share</span>
              <span className="font-medium">
                {selectedDividend ? parseFloat(selectedDividend.amount_per_share).toFixed(4) : "—"} {selectedDividend?.currency}
              </span>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Quantity received</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={confirmQty} onChange={(e) => setConfirmQty(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Date received</label>
              <input type="date" className="w-full border rounded px-3 py-2 text-sm" value={confirmDate} onChange={(e) => setConfirmDate(e.target.value)} />
            </div>
            {confirmQty && selectedDividend && (
              <div className="flex justify-between font-semibold border-t pt-2">
                <span>Total income</span>
                <span>${(parseFloat(confirmQty) * parseFloat(selectedDividend.amount_per_share)).toFixed(2)} {selectedDividend.currency}</span>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedDividend(null)}>Cancel</Button>
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

---

## Task 12: Update navigation and add redirect

**Files:**
- Modify: `frontend/app/(auth)/layout.tsx` — update nav link
- Modify: `frontend/app/(auth)/dividends/page.tsx` — replace with redirect

- [ ] **Step 1: Update nav link in layout.tsx**

Open `frontend/app/(auth)/layout.tsx`. Find the nav link for "Dividends" (look for `/dividends` in the href). Change it to point to `/events` and update the label to "Events".

The exact change will look something like:
```tsx
// Before
{ href: "/dividends", label: "Dividends", icon: ... }
// After
{ href: "/events", label: "Events", icon: ... }
```

- [ ] **Step 2: Replace dividends page with redirect**

Open `frontend/app/(auth)/dividends/page.tsx`. Replace the entire file content with:

```typescript
import { redirect } from "next/navigation";

export default function DividendsRedirect() {
  redirect("/events");
}
```

- [ ] **Step 3: Verify build has no TypeScript errors**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors (or only pre-existing errors unrelated to this feature).

- [ ] **Step 4: Start dev server and verify the page loads**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/events` — should show the Events calendar page.
Open `http://localhost:3000/dividends` — should redirect to `/events`.

---

## Task 13: Add `ipo_analysis` to Settings AI tab

The Settings page AI tab renders `<AISettings />`. The `ipo_analysis` feature key is now in `FEATURE_KEYS`, so the settings API will accept it. Verify the AI settings UI already dynamically lists all configured feature keys — if so, no frontend change is needed.

- [ ] **Step 1: Check if AISettings auto-discovers feature keys**

Open the `AISettings` component (find it by searching the frontend for `AISettings`):

```bash
grep -rn "AISettings\|feature_key\|ipo_analysis" frontend/app --include="*.tsx" | grep -v node_modules | head -20
```

- [ ] **Step 2a: If AISettings fetches feature keys from the API**

No change needed — `ipo_analysis` will appear automatically once the backend ships it in `FEATURE_KEYS`.

- [ ] **Step 2b: If AISettings has a hardcoded list of feature keys**

Add `"ipo_analysis"` to the list and add a display label:

```typescript
{ key: "ipo_analysis", label: "IPO Analysis" }
```

---

## Post-Implementation Checklist

- [ ] All backend tests pass: `cd backend && python -m pytest tests/ -v`
- [ ] Frontend builds without TypeScript errors: `cd frontend && npx tsc --noEmit`
- [ ] `/events` page loads in browser
- [ ] `/dividends` redirects to `/events`
- [ ] Dividend dots appear blue, IPO dots appear orange on calendar
- [ ] Filter chips correctly show/hide event types
- [ ] Clicking a dividend opens the confirm dialog
- [ ] Clicking an IPO opens the detail panel
- [ ] "Analyze with AI" button shows error if no LLM configured
- [ ] Settings → AI & LLM shows `ipo_analysis` feature for assignment
- [ ] After assigning a model, "Analyze with AI" returns a verdict
