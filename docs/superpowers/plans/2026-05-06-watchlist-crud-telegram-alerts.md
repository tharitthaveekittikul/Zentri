# Watchlist CRUD + Telegram Price Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add watchlist CRUD endpoints, Telegram alert config in settings, and an ARQ job that fires a Telegram message once when a watched asset's price reaches the user's target.

**Architecture:** WatchlistItem model + two Alembic migrations → Pydantic schemas → telegram service → alert service (tested in isolation) → API routers → ARQ job wired into the price fetch pipeline via `_job_id`-deduplicated enqueue.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, ARQ, httpx (async Telegram calls), AES-256 via `app.core.encryption` (existing)

---

## File Map

| Action | Path |
|---|---|
| Create | `backend/app/models/watchlist_item.py` |
| Modify | `backend/app/models/user.py` |
| Create | `backend/alembic/versions/014_watchlist.py` |
| Create | `backend/alembic/versions/015_telegram_config.py` |
| Create | `backend/app/schemas/watchlist.py` |
| Create | `backend/app/services/telegram.py` |
| Create | `backend/app/services/watchlist_alert.py` |
| Create | `backend/app/api/watchlist.py` |
| Modify | `backend/app/api/settings.py` |
| Modify | `backend/app/main.py` |
| Create | `backend/worker/jobs/watchlist_alert.py` |
| Modify | `backend/worker/main.py` |
| Modify | `backend/worker/jobs/price_fetch.py` |
| Create | `backend/tests/services/test_watchlist_alert.py` |

---

### Task 1: WatchlistItem SQLAlchemy Model

**Files:**
- Create: `backend/app/models/watchlist_item.py`

- [ ] **Step 1: Create the model file**

```python
# backend/app/models/watchlist_item.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, Text
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    alert_enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Verify import works**

```bash
cd backend && python -c "from app.models.watchlist_item import WatchlistItem; print('ok')"
```

Expected: `ok`

---

### Task 2: Add Telegram Columns to User Model

**Files:**
- Modify: `backend/app/models/user.py`

- [ ] **Step 1: Add telegram columns to User**

Add `Text` to the sqlalchemy import line and append two columns to the `User` class:

```python
# Add Text to the existing import:
from sqlalchemy import Date, DateTime, Integer, String, Text

# Add these two columns to the User class body:
    telegram_bot_token: Mapped[str | None] = mapped_column(Text(), nullable=True, default=None)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
```

- [ ] **Step 2: Verify import works**

```bash
cd backend && python -c "from app.models.user import User; print(User.telegram_bot_token)"
```

Expected: prints the column descriptor (no error)

---

### Task 3: Alembic Migrations

**Files:**
- Create: `backend/alembic/versions/014_watchlist.py`
- Create: `backend/alembic/versions/015_telegram_config.py`

- [ ] **Step 1: Find current alembic head revision**

```bash
cd backend && python -m alembic heads
```

Note the revision ID printed (e.g. `013` or a hash). Use it as `down_revision` in 014.

- [ ] **Step 2: Create migration 014 — watchlist_items table**

```python
# backend/alembic/versions/014_watchlist.py
"""add watchlist_items table

Revision ID: 014
Revises: 013
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "014"
down_revision = "013"  # Replace with actual head from Step 1
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id"),
            nullable=False,
        ),
        sa.Column("target_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("alert_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_user_id", table_name="watchlist_items")
    op.drop_table("watchlist_items")
```

- [ ] **Step 3: Create migration 015 — telegram columns on users**

```python
# backend/alembic/versions/015_telegram_config.py
"""add telegram config to users

Revision ID: 015
Revises: 014
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_bot_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "telegram_chat_id")
    op.drop_column("users", "telegram_bot_token")
```

- [ ] **Step 4: Run migrations**

```bash
cd backend && python -m alembic upgrade head
```

Expected: two new revision lines applied, no errors.

---

### Task 4: Watchlist Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/watchlist.py`

- [ ] **Step 1: Create schemas file**

```python
# backend/app/schemas/watchlist.py
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AssetSummary(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    currency: str
    model_config = ConfigDict(from_attributes=True)


class WatchlistItemCreate(BaseModel):
    asset_id: uuid.UUID
    target_price: Decimal | None = None
    currency: str = "USD"
    notes: str | None = None


class WatchlistItemUpdate(BaseModel):
    target_price: Decimal | None = None
    notes: str | None = None
    alert_enabled: bool | None = None


class WatchlistItemOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    target_price: Decimal | None
    currency: str
    notes: str | None
    alert_enabled: bool
    alerted_at: datetime | None
    created_at: datetime
    asset: AssetSummary
    current_price: Decimal | None
    pct_from_target: float | None
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from app.schemas.watchlist import WatchlistItemOut; print('ok')"
```

Expected: `ok`

---

### Task 5: Telegram Service

**Files:**
- Create: `backend/app/services/telegram.py`

- [ ] **Step 1: Check httpx is available**

```bash
cd backend && python -c "import httpx; print(httpx.__version__)"
```

If missing, install: `uv pip install httpx`

- [ ] **Step 2: Create telegram service**

```python
# backend/app/services/telegram.py
import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_message(bot_token: str, chat_id: str, text: str) -> None:
    """Send a Telegram message. Raises RuntimeError on API failure."""
    url = _TELEGRAM_API.format(token=bot_token)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
    if not resp.is_success:
        raise RuntimeError(f"Telegram API {resp.status_code}: {resp.text[:200]}")
    logger.info("Telegram message sent to chat %s", chat_id)
```

- [ ] **Step 3: Verify import**

```bash
cd backend && python -c "from app.services.telegram import send_message; print('ok')"
```

Expected: `ok`

---

### Task 6: Watchlist Alert Service

**Files:**
- Create: `backend/app/services/watchlist_alert.py`

- [ ] **Step 1: Create alert service**

```python
# backend/app/services/watchlist_alert.py
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.price import Price
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.services.telegram import send_message

logger = get_logger(__name__)


async def _fetch_pending_rows(db: AsyncSession) -> list:
    """Return rows (WatchlistItem, Asset, Price, User) ready for alert check."""
    latest_ts = (
        select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
        .group_by(Price.asset_id)
        .subquery("latest_ts")
    )
    stmt = (
        select(WatchlistItem, Asset, Price, User)
        .join(Asset, WatchlistItem.asset_id == Asset.id)
        .join(User, WatchlistItem.user_id == User.id)
        .outerjoin(latest_ts, WatchlistItem.asset_id == latest_ts.c.asset_id)
        .outerjoin(
            Price,
            and_(
                Price.asset_id == WatchlistItem.asset_id,
                Price.timestamp == latest_ts.c.max_ts,
            ),
        )
        .where(
            WatchlistItem.alert_enabled.is_(True),
            WatchlistItem.alerted_at.is_(None),
            WatchlistItem.target_price.isnot(None),
        )
    )
    result = await db.execute(stmt)
    return result.all()


def _format_alert_message(item: WatchlistItem, asset: Asset, price: Price) -> str:
    direction = "at" if price.close == item.target_price else "below"
    return (
        f"🎯 <b>Price Alert — {asset.symbol}</b>\n"
        f"{asset.name}\n\n"
        f"Current price: <b>{price.close:.4f} {asset.currency}</b>\n"
        f"Your target: {item.target_price:.4f} {item.currency}\n\n"
        f"Price is now {direction} your target! Open Zentri to review."
    )


async def check_and_notify(db: AsyncSession) -> int:
    """Check pending watchlist alerts and send Telegram messages. Returns alert count."""
    rows = await _fetch_pending_rows(db)
    count = 0
    for item, asset, price, user in rows:
        if price is None:
            continue
        if price.close > item.target_price:
            continue
        if not user.telegram_bot_token or not user.telegram_chat_id:
            logger.info("No Telegram config for user %s — skipping alert", user.id)
            continue
        try:
            bot_token = decrypt(user.telegram_bot_token)
            text = _format_alert_message(item, asset, price)
            await send_message(bot_token, user.telegram_chat_id, text)
            item.alerted_at = datetime.now(timezone.utc)
            count += 1
            logger.info("Alert sent for %s (item %s)", asset.symbol, item.id)
        except Exception:
            logger.exception("Failed to send alert for item %s (asset %s)", item.id, asset.symbol)
    await db.commit()
    return count
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from app.services.watchlist_alert import check_and_notify; print('ok')"
```

Expected: `ok`

---

### Task 7: Tests for Watchlist Alert Service

**Files:**
- Create: `backend/tests/services/test_watchlist_alert.py`

- [ ] **Step 1: Write the tests**

```python
# backend/tests/services/test_watchlist_alert.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.encryption import encrypt
from app.services.watchlist_alert import check_and_notify


def _item(target_price=Decimal("100"), alerted_at=None, alert_enabled=True):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.target_price = target_price
    m.alerted_at = alerted_at
    m.alert_enabled = alert_enabled
    return m


def _asset(symbol="AAPL", name="Apple Inc.", currency="USD"):
    m = MagicMock()
    m.symbol = symbol
    m.name = name
    m.currency = currency
    return m


def _price(close=Decimal("99")):
    m = MagicMock()
    m.close = close
    return m


def _user(has_telegram=True):
    m = MagicMock()
    if has_telegram:
        m.telegram_bot_token = encrypt("fake_token_abc")
        m.telegram_chat_id = "987654321"
    else:
        m.telegram_bot_token = None
        m.telegram_chat_id = None
    return m


@pytest.mark.asyncio
async def test_alert_sent_when_price_hits_target():
    item = _item(target_price=Decimal("100"))
    rows = [(item, _asset(), _price(close=Decimal("99")), _user())]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 1
    assert item.alerted_at is not None
    mock_send.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_no_alert_when_price_above_target():
    item = _item(target_price=Decimal("100"))
    rows = [(item, _asset(), _price(close=Decimal("110")), _user())]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    assert item.alerted_at is None
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_no_alert_when_no_telegram_config():
    item = _item(target_price=Decimal("100"))
    rows = [(item, _asset(), _price(close=Decimal("95")), _user(has_telegram=False))]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_no_alert_when_price_is_none():
    item = _item(target_price=Decimal("100"))
    rows = [(item, _asset(), None, _user())]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_continues_after_send_failure():
    item1 = _item(target_price=Decimal("100"))
    item2 = _item(target_price=Decimal("50"))
    rows = [
        (item1, _asset("AAPL"), _price(Decimal("90")), _user()),
        (item2, _asset("BTC"), _price(Decimal("45")), _user()),
    ]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch(
            "app.services.watchlist_alert.send_message",
            new_callable=AsyncMock,
            side_effect=[RuntimeError("network error"), None],
        ):
            count = await check_and_notify(mock_db)

    assert count == 1
    assert item1.alerted_at is None
    assert item2.alerted_at is not None
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && python -m pytest tests/services/test_watchlist_alert.py -v
```

Expected: 5 passed

---

### Task 8: Watchlist API Router

**Files:**
- Create: `backend/app/api/watchlist.py`

- [ ] **Step 1: Create the router**

```python
# backend/app/api/watchlist.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.price import Price
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.schemas.watchlist import (
    AssetSummary,
    WatchlistItemCreate,
    WatchlistItemOut,
    WatchlistItemUpdate,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
logger = get_logger(__name__)


async def _get_owned_item(db: AsyncSession, item_id: uuid.UUID, user_id: uuid.UUID) -> WatchlistItem:
    result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.id == item_id,
            WatchlistItem.user_id == user_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item


async def _item_to_out(db: AsyncSession, item: WatchlistItem) -> WatchlistItemOut:
    asset = (await db.execute(select(Asset).where(Asset.id == item.asset_id))).scalar_one()
    price_row = (
        await db.execute(
            select(Price)
            .where(Price.asset_id == item.asset_id)
            .order_by(Price.timestamp.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    current_price = price_row.close if price_row else None
    pct = None
    if current_price is not None and item.target_price:
        pct = float((current_price - item.target_price) / item.target_price * 100)
    return WatchlistItemOut(
        id=item.id,
        asset_id=item.asset_id,
        target_price=item.target_price,
        currency=item.currency,
        notes=item.notes,
        alert_enabled=item.alert_enabled,
        alerted_at=item.alerted_at,
        created_at=item.created_at,
        asset=AssetSummary(id=asset.id, symbol=asset.symbol, name=asset.name, currency=asset.currency),
        current_price=current_price,
        pct_from_target=pct,
    )


@router.get("", response_model=list[WatchlistItemOut])
async def list_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    latest_ts = (
        select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
        .group_by(Price.asset_id)
        .subquery("latest_ts")
    )
    stmt = (
        select(WatchlistItem, Asset, Price)
        .join(Asset, WatchlistItem.asset_id == Asset.id)
        .outerjoin(latest_ts, WatchlistItem.asset_id == latest_ts.c.asset_id)
        .outerjoin(
            Price,
            and_(
                Price.asset_id == WatchlistItem.asset_id,
                Price.timestamp == latest_ts.c.max_ts,
            ),
        )
        .where(WatchlistItem.user_id == current_user.id)
        .order_by(WatchlistItem.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    out = []
    for item, asset, price in rows:
        current_price = price.close if price else None
        pct = None
        if current_price is not None and item.target_price:
            pct = float((current_price - item.target_price) / item.target_price * 100)
        out.append(
            WatchlistItemOut(
                id=item.id,
                asset_id=item.asset_id,
                target_price=item.target_price,
                currency=item.currency,
                notes=item.notes,
                alert_enabled=item.alert_enabled,
                alerted_at=item.alerted_at,
                created_at=item.created_at,
                asset=AssetSummary(id=asset.id, symbol=asset.symbol, name=asset.name, currency=asset.currency),
                current_price=current_price,
                pct_from_target=pct,
            )
        )
    return out


@router.post("", response_model=WatchlistItemOut, status_code=201)
async def add_to_watchlist(
    body: WatchlistItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == current_user.id,
                WatchlistItem.asset_id == body.asset_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Asset already in watchlist")

    asset = (await db.execute(select(Asset).where(Asset.id == body.asset_id))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    item = WatchlistItem(
        user_id=current_user.id,
        asset_id=body.asset_id,
        target_price=body.target_price,
        currency=body.currency or asset.currency,
        notes=body.notes,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    logger.info("Watchlist item added: %s for user %s", asset.symbol, current_user.id)
    return await _item_to_out(db, item)


@router.patch("/{item_id}", response_model=WatchlistItemOut)
async def update_watchlist_item(
    item_id: uuid.UUID,
    body: WatchlistItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(db, item_id, current_user.id)
    if "target_price" in body.model_fields_set:
        item.target_price = body.target_price
    if "notes" in body.model_fields_set:
        item.notes = body.notes
    if "alert_enabled" in body.model_fields_set:
        item.alert_enabled = body.alert_enabled
    await db.commit()
    await db.refresh(item)
    return await _item_to_out(db, item)


@router.delete("/{item_id}", status_code=204)
async def delete_watchlist_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(db, item_id, current_user.id)
    await db.delete(item)
    await db.commit()


@router.post("/{item_id}/rearm", response_model=WatchlistItemOut)
async def rearm_watchlist_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await _get_owned_item(db, item_id, current_user.id)
    item.alerted_at = None
    await db.commit()
    await db.refresh(item)
    return await _item_to_out(db, item)
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from app.api.watchlist import router; print('ok')"
```

Expected: `ok`

---

### Task 9: Telegram Settings Endpoints

**Files:**
- Modify: `backend/app/api/settings.py`

- [ ] **Step 1: Add Telegram import and schemas at the top of settings.py**

Add after the existing imports:

```python
from app.services.telegram import send_message as _send_telegram
```

- [ ] **Step 2: Add Telegram schemas and endpoints at the bottom of settings.py**

Append to the end of `backend/app/api/settings.py`:

```python
class TelegramConfigIn(BaseModel):
    bot_token: str
    chat_id: str


class TelegramConfigOut(BaseModel):
    chat_id: str | None
    has_token: bool


@router.get("/telegram", response_model=TelegramConfigOut)
async def get_telegram_config(
    current_user: User = Depends(get_current_user),
):
    return TelegramConfigOut(
        chat_id=current_user.telegram_chat_id,
        has_token=bool(current_user.telegram_bot_token),
    )


@router.put("/telegram", response_model=TelegramConfigOut)
async def save_telegram_config(
    body: TelegramConfigIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.telegram_bot_token = encrypt(body.bot_token)
    current_user.telegram_chat_id = body.chat_id
    await db.commit()
    return TelegramConfigOut(chat_id=body.chat_id, has_token=True)


@router.post("/telegram/test")
async def test_telegram(
    current_user: User = Depends(get_current_user),
):
    if not current_user.telegram_bot_token or not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured — save bot_token and chat_id first")
    try:
        bot_token = decrypt(current_user.telegram_bot_token)
        await _send_telegram(
            bot_token,
            current_user.telegram_chat_id,
            "✅ <b>Zentri</b> — Test message received! Price alerts are configured correctly.",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"ok": True}
```

- [ ] **Step 3: Verify import**

```bash
cd backend && python -c "from app.api.settings import router; print('ok')"
```

Expected: `ok`

---

### Task 10: Register Watchlist Router in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add watchlist to the import line**

Change:
```python
from app.api import (
    analysis, assets, auth, cash_balance, dividends, documents,
    feature_llm_config, health, import_pipeline, llm_usage,
    overview, pipeline, portfolio, provider_config, settings,
)
```

To:
```python
from app.api import (
    analysis, assets, auth, cash_balance, dividends, documents,
    feature_llm_config, health, import_pipeline, llm_usage,
    overview, pipeline, portfolio, provider_config, settings, watchlist,
)
```

- [ ] **Step 2: Register the router**

After the last `app.include_router` line, add:

```python
app.include_router(watchlist.router, prefix="/api/v1")
```

- [ ] **Step 3: Verify the app starts**

```bash
cd backend && python -c "from app.main import app; print('ok')"
```

Expected: `ok`

---

### Task 11: ARQ Watchlist Alert Job + Worker Registration

**Files:**
- Create: `backend/worker/jobs/watchlist_alert.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Create the ARQ job**

```python
# backend/worker/jobs/watchlist_alert.py
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.pipeline import create_log, finish_log
from app.services.watchlist_alert import check_and_notify

logger = get_logger(__name__)


async def job_check_watchlist_alerts(ctx: dict) -> dict:
    """ARQ job: check watchlist target prices and send Telegram alerts."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "watchlist_alert")
        try:
            count = await check_and_notify(db)
            await finish_log(db, log, success=True)
            logger.info("Watchlist alert job done — %d alert(s) sent", count)
            return {"alerts_sent": count}
        except Exception as e:
            logger.exception("job_check_watchlist_alerts failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 2: Register in worker/main.py**

Add import after the existing job imports:

```python
from worker.jobs.watchlist_alert import job_check_watchlist_alerts
```

Add to `WorkerSettings.functions` list:

```python
        job_check_watchlist_alerts,
```

- [ ] **Step 3: Verify worker imports**

```bash
cd backend && python -c "from worker.main import WorkerSettings; print('ok')"
```

Expected: `ok`

---

### Task 12: Enqueue Alert Job from Price Fetch Jobs

**Files:**
- Modify: `backend/worker/jobs/price_fetch.py`

- [ ] **Step 1: Enqueue alert job after each price fetch**

In `price_fetch.py`, modify `job_fetch_prices_us`, `job_fetch_prices_crypto`, and `job_fetch_price_gold` to enqueue the alert job after a successful fetch. Use `_job_id="watchlist_alert_check"` so ARQ deduplicates concurrent enqueues.

Replace the three job functions with:

```python
async def job_fetch_prices_us(ctx: dict) -> dict:
    """ARQ job: fetch US stock prices via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_us")
        try:
            count = await fetch_us_prices(db)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_prices_us failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_prices_crypto(ctx: dict) -> dict:
    """ARQ job: fetch crypto prices via CoinGecko."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_crypto")
        try:
            count = await fetch_crypto_prices(db)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_prices_crypto failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_price_gold(ctx: dict) -> dict:
    """ARQ job: fetch gold spot price."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_gold")
        try:
            count = await fetch_gold_price(db)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_price_gold failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise


async def job_fetch_benchmark_prices(ctx: dict) -> dict:
    """ARQ job: fetch S&P500 and SET benchmark prices."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_benchmark")
        try:
            count = await fetch_benchmark_prices(db)
            await finish_log(db, log, success=True)
            return {"inserted": count}
        except Exception as e:
            logger.exception("job_fetch_benchmark_prices failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

Note: `job_fetch_benchmark_prices` does NOT enqueue the alert job — benchmark prices are index prices, not individual asset prices users would watch.

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from worker.jobs.price_fetch import job_fetch_prices_us; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Run all tests to confirm nothing broken**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all existing tests pass + 5 new watchlist_alert tests pass
