# Dividend Telegram Alert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send a Telegram notification at 13:00 Bangkok (06:00 UTC) on each stock's ex-dividend date, only for stocks the user actually holds, showing projected total income in USD and secondary currency.

**Architecture:** Add `dividend_notified_at` to `DividendEvent` for deduplication. New `dividend_alert` service queries events where `ex_date = today`, `holding.quantity > 0`, `dividend_notified_at IS NULL`, sends Telegram, stamps the column. ARQ job + daily cron at 06:00 UTC mirrors `watchlist_alert` pattern exactly.

**Tech Stack:** Python 3.12, SQLAlchemy async, ARQ, httpx (Telegram), pytest-asyncio, unittest.mock

---

### Task 1: Migration 029 — add `dividend_notified_at` column

**Files:**
- Create: `backend/alembic/versions/029_add_dividend_notified_at.py`

- [ ] **Step 1: Create the migration file**

```python
"""add dividend_notified_at to dividend_events

Revision ID: 029
Revises: 028
Create Date: 2026-05-08
"""
import sqlalchemy as sa
from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dividend_events",
        sa.Column("dividend_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dividend_events", "dividend_notified_at")
```

- [ ] **Step 2: Apply migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected output: `Running upgrade 028 -> 029, add dividend_notified_at to dividend_events`

---

### Task 2: Migration 030 — add `dividend_alert` to `job_type_enum`

**Files:**
- Create: `backend/alembic/versions/030_add_dividend_alert_job_type.py`

- [ ] **Step 1: Create the migration file**

```python
"""add dividend_alert to job_type_enum

Revision ID: 030
Revises: 029
Create Date: 2026-05-08
"""
from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'dividend_alert'")


def downgrade() -> None:
    pass
```

- [ ] **Step 2: Apply migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected output: `Running upgrade 029 -> 030, add dividend_alert to job_type_enum`

---

### Task 3: Update `DividendEvent` model

**Files:**
- Modify: `backend/app/models/dividend_event.py`

- [ ] **Step 1: Add `dividend_notified_at` column after `updated_at`**

The file currently ends at `updated_at`. Add the new field:

```python
# After the existing updated_at field, add:
    dividend_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
```

Full file after change:

```python
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
    dividend_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
```

- [ ] **Step 2: Verify no import errors**

```bash
docker compose exec backend python -c "from app.models.dividend_event import DividendEvent; print('OK')"
```

Expected: `OK`

---

### Task 4: Update `JOB_TYPES` in pipeline_log model

**Files:**
- Modify: `backend/app/models/pipeline_log.py`

- [ ] **Step 1: Add `"dividend_alert"` to the `JOB_TYPES` tuple**

Change:
```python
    "watchlist_discovery", "watchlist_scan",
    "dividend_fetch", "ipo_fetch",
)
```

To:
```python
    "watchlist_discovery", "watchlist_scan",
    "dividend_fetch", "ipo_fetch", "dividend_alert",
)
```

- [ ] **Step 2: Verify**

```bash
docker compose exec backend python -c "from app.models.pipeline_log import JOB_TYPES; assert 'dividend_alert' in JOB_TYPES; print('OK')"
```

Expected: `OK`

---

### Task 5: Write tests for `dividend_alert` service

**Files:**
- Create: `backend/tests/services/test_dividend_alert.py`

- [ ] **Step 1: Write the test file**

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.encryption import encrypt
from app.services.dividend_alert import check_and_notify


def _event(notified_at=None, amount=Decimal("0.26"), currency="USD"):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.ex_date = "2026-05-11"
    m.amount_per_share = amount
    m.currency = currency
    m.dividend_notified_at = notified_at
    return m


def _asset(symbol="AAPL", name="Apple Inc."):
    m = MagicMock()
    m.symbol = symbol
    m.name = name
    return m


def _holding(quantity=Decimal("50")):
    m = MagicMock()
    m.quantity = quantity
    return m


def _user(has_telegram=True, secondary="THB"):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.currency_secondary = secondary
    if has_telegram:
        m.telegram_bot_token = encrypt("fake_bot_token")
        m.telegram_chat_id = "123456789"
    else:
        m.telegram_bot_token = None
        m.telegram_chat_id = None
    return m


@pytest.mark.asyncio
async def test_notification_sent_for_held_stock():
    event = _event()
    rows = [(event, _asset(), _holding(Decimal("50")), _user())]
    mock_db = AsyncMock()

    with patch("app.services.dividend_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.dividend_alert.send_message", new_callable=AsyncMock) as mock_send:
            with patch("app.services.dividend_alert.get_rate", new_callable=AsyncMock, return_value=Decimal("32.3")):
                count = await check_and_notify(mock_db)

    assert count == 1
    assert event.dividend_notified_at is not None
    mock_send.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_no_notification_when_no_telegram():
    event = _event()
    rows = [(event, _asset(), _holding(Decimal("10")), _user(has_telegram=False))]
    mock_db = AsyncMock()

    with patch("app.services.dividend_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.dividend_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    assert event.dividend_notified_at is None
    mock_send.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_notification_message_contains_symbol_and_total():
    event = _event(amount=Decimal("0.26"), currency="USD")
    rows = [(event, _asset(symbol="AAPL"), _holding(Decimal("50")), _user())]
    mock_db = AsyncMock()
    captured = {}

    async def capture_send(token, chat_id, text):
        captured["text"] = text

    with patch("app.services.dividend_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.dividend_alert.send_message", side_effect=capture_send):
            with patch("app.services.dividend_alert.get_rate", new_callable=AsyncMock, return_value=Decimal("32.3")):
                await check_and_notify(mock_db)

    assert "AAPL" in captured["text"]
    assert "13.00" in captured["text"]   # 50 × 0.26


@pytest.mark.asyncio
async def test_no_rows_returns_zero():
    mock_db = AsyncMock()

    with patch("app.services.dividend_alert._fetch_pending_rows", return_value=[]):
        with patch("app.services.dividend_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    mock_send.assert_not_called()
```

- [ ] **Step 2: Run tests — expect failure (service not yet written)**

```bash
docker compose exec backend pytest tests/services/test_dividend_alert.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `app.services.dividend_alert`

---

### Task 6: Implement `app/services/dividend_alert.py`

**Files:**
- Create: `backend/app/services/dividend_alert.py`

- [ ] **Step 1: Write the service**

```python
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.dividend_event import DividendEvent
from app.models.holding import Holding
from app.models.user import User
from app.services.exchange_rate import get_rate
from app.services.telegram import send_message

logger = get_logger(__name__)


async def _fetch_pending_rows(db: AsyncSession) -> list:
    stmt = (
        select(DividendEvent, Asset, Holding, User)
        .join(Asset, DividendEvent.asset_id == Asset.id)
        .join(Holding, Holding.asset_id == DividendEvent.asset_id)
        .join(User, User.id == Holding.user_id)
        .where(
            DividendEvent.ex_date == date.today(),
            DividendEvent.dividend_notified_at.is_(None),
            Holding.quantity > 0,
        )
    )
    result = await db.execute(stmt)
    return result.all()


def _format_message(
    event: DividendEvent,
    asset: Asset,
    holding: Holding,
    rate: Decimal | None,
    secondary_currency: str,
) -> str:
    total = holding.quantity * event.amount_per_share
    secondary = f"~{total * rate:.2f} {secondary_currency}" if rate else ""
    secondary_part = f" ({secondary})" if secondary else ""
    return (
        f"💰 <b>Dividend Day — {asset.symbol}</b>\n\n"
        f"Ex-dividend date: {event.ex_date}\n"
        f"Amount/share: {float(event.amount_per_share):.4f} {event.currency}\n"
        f"Shares held: {float(holding.quantity):.4f}\n"
        f"Projected income: <b>{float(total):.2f} {event.currency}{secondary_part}</b>"
    )


async def check_and_notify(db: AsyncSession) -> int:
    rows = await _fetch_pending_rows(db)
    count = 0
    for event, asset, holding, user in rows:
        if not user.telegram_bot_token or not user.telegram_chat_id:
            logger.info("No Telegram config for user %s — skipping", user.id)
            continue
        try:
            rate = await get_rate(db, "USD", user.currency_secondary)
            bot_token = decrypt(user.telegram_bot_token)
            text = _format_message(event, asset, holding, rate, user.currency_secondary)
            await send_message(bot_token, user.telegram_chat_id, text)
            event.dividend_notified_at = datetime.now(timezone.utc)
            await db.commit()
            count += 1
            logger.info("Dividend alert sent for %s to user %s", asset.symbol, user.id)
        except Exception:
            logger.exception("Failed to send dividend alert for %s (user %s)", asset.symbol, user.id)
    return count
```

- [ ] **Step 2: Run tests — expect all pass**

```bash
docker compose exec backend pytest tests/services/test_dividend_alert.py -v
```

Expected:
```
PASSED tests/services/test_dividend_alert.py::test_notification_sent_for_held_stock
PASSED tests/services/test_dividend_alert.py::test_no_notification_when_no_telegram
PASSED tests/services/test_dividend_alert.py::test_notification_message_contains_symbol_and_total
PASSED tests/services/test_dividend_alert.py::test_no_rows_returns_zero
4 passed
```

---

### Task 7: Create ARQ worker job

**Files:**
- Create: `backend/worker/jobs/dividend_alert.py`

- [ ] **Step 1: Write the job file**

```python
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.dividend_alert import check_and_notify
from app.services.pipeline import create_log, finish_log

logger = get_logger(__name__)


async def job_dividend_alert(ctx: dict) -> dict:
    """ARQ job: send Telegram alerts for ex-dividend events happening today."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "dividend_alert")
        try:
            count = await check_and_notify(db)
            await finish_log(db, log, success=True)
            logger.info("Dividend alert job done — %d alert(s) sent", count)
            return {"alerts_sent": count}
        except Exception as e:
            logger.exception("job_dividend_alert failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

---

### Task 8: Register job in `worker/main.py`

**Files:**
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Add import**

Add after the `job_fetch_dividends` import line:
```python
from worker.jobs.dividend_alert import job_dividend_alert
```

- [ ] **Step 2: Add to `functions` list**

Add `job_dividend_alert` to the `functions` list:
```python
    functions = [
        job_fetch_prices_us,
        job_fetch_prices_crypto,
        job_fetch_price_gold,
        job_fetch_benchmark_prices,
        job_fetch_prices_th_fund,
        job_fetch_prices_thai_stock,
        job_ingest_document,
        job_run_analysis,
        job_snapshot_net_worth,
        job_fetch_dividends,
        job_fetch_ipos,
        job_dividend_alert,
        job_check_watchlist_alerts,
        job_scan_watchlist_item,
        job_scan_watchlist_batch,
        job_discover_watchlist,
    ]
```

- [ ] **Step 3: Add cron — 06:00 UTC = 13:00 Bangkok**

Add to `cron_jobs` list:
```python
        cron(job_dividend_alert, hour=6, minute=0),
```

- [ ] **Step 4: Verify worker starts without error**

```bash
docker compose restart worker
docker compose logs worker --tail=20
```

Expected: `ARQ worker started — DB pool ready` with no import errors.

---

### Task 9: End-to-end smoke test

- [ ] **Step 1: Manually enqueue the job**

```bash
docker compose exec backend python -c "
import asyncio
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings

async def run():
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await redis.enqueue_job('job_dividend_alert')
    await redis.aclose()
    print('Enqueued')

asyncio.run(run())
"
```

- [ ] **Step 2: Watch worker logs**

```bash
docker compose logs worker -f
```

Expected: `pipeline job started job_type=dividend_alert` → `Dividend alert job done — N alert(s) sent`

- [ ] **Step 3: If you have a dividend event with `ex_date = today` and a holding with `quantity > 0`, a Telegram message should arrive.**

To force-test without waiting for a real ex-date, temporarily insert a test row:
```bash
docker compose exec postgres psql -U postgres -d zentri -c "
UPDATE dividend_events SET ex_date = CURRENT_DATE, dividend_notified_at = NULL
WHERE id = (SELECT id FROM dividend_events ORDER BY created_at DESC LIMIT 1);
"
```

Then enqueue again and check Telegram.

Reset after testing:
```bash
docker compose exec postgres psql -U postgres -d zentri -c "
UPDATE dividend_events SET dividend_notified_at = NULL WHERE ex_date = CURRENT_DATE;
"
```
