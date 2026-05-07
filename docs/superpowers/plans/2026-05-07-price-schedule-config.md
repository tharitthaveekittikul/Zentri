# Price Schedule Config + Pipeline Triggers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-job price fetch schedule (enable/disable, time, days) stored in DB, a worker guard that skips jobs outside their schedule, manual trigger buttons on the Pipeline page, a Schedule tab in Settings, and schedule backup/restore.

**Architecture:** Option A — job-level guard. Crons run at conservative intervals; each job reads its schedule config from DB (primary user's row) and skips if conditions don't match. Manual triggers bypass the guard. Settings stored in `price_schedule_config` table, included in backup as v2.

**Tech Stack:** Python/FastAPI/SQLAlchemy (asyncpg), ARQ workers, zoneinfo (Asia/Bangkok), Next.js 14/React, TanStack Query, shadcn/ui, pytest-asyncio.

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/app/models/price_schedule_config.py` |
| Create | `backend/alembic/versions/024_add_price_schedule_config.py` |
| Modify | `backend/app/models/__init__.py` |
| Create | `backend/app/schemas/price_schedule_config.py` |
| Create | `backend/app/services/price_schedule_config.py` |
| Modify | `backend/app/api/settings.py` |
| Modify | `backend/app/schemas/pipeline.py` |
| Modify | `backend/app/api/pipeline.py` |
| Modify | `backend/worker/jobs/price_fetch.py` |
| Modify | `backend/worker/main.py` |
| Modify | `backend/app/schemas/system_backup.py` |
| Modify | `backend/app/services/system_backup.py` |
| Create | `backend/tests/test_schedule_api.py` |
| Create | `frontend/lib/services/schedule.ts` |
| Modify | `frontend/lib/services/pipeline.ts` |
| Create | `frontend/components/pipeline/TriggerButtons.tsx` |
| Modify | `frontend/app/(auth)/pipeline/page.tsx` |
| Create | `frontend/components/settings/ScheduleTab.tsx` |
| Modify | `frontend/app/(auth)/settings/page.tsx` |

---

## Task 1: DB Model

**Files:**
- Create: `backend/app/models/price_schedule_config.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create the SQLAlchemy model**

`backend/app/models/price_schedule_config.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PriceScheduleConfig(Base):
    __tablename__ = "price_schedule_config"
    __table_args__ = (UniqueConstraint("user_id", "job_key", name="uq_user_job_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    job_key: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    days: Mapped[list] = mapped_column(JSONB(), nullable=False, default=list)
    run_at_hour: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    run_at_minute: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Register in `__init__.py`**

Add to `backend/app/models/__init__.py`:
```python
from app.models.price_schedule_config import PriceScheduleConfig  # noqa: F401
```

Add `"PriceScheduleConfig"` to the `__all__` list.

---

## Task 2: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/024_add_price_schedule_config.py`

- [ ] **Step 1: Create migration file**

`backend/alembic/versions/024_add_price_schedule_config.py`:
```python
"""add price_schedule_config table

Revision ID: 024
Revises: 023
Create Date: 2026-05-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_schedule_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("job_key", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("days", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("run_at_hour", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_at_minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "job_key", name="uq_user_job_key"),
    )


def downgrade() -> None:
    op.drop_table("price_schedule_config")
```

- [ ] **Step 2: Apply migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected output ends with: `Running upgrade 023 -> 024, add price_schedule_config table`

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/price_schedule_config.py`

- [ ] **Step 1: Create schema file**

`backend/app/schemas/price_schedule_config.py`:
```python
from pydantic import BaseModel, Field


class ScheduleConfigOut(BaseModel):
    job_key: str
    enabled: bool
    days: list[int]
    run_at_hour: int
    run_at_minute: int

    model_config = {"from_attributes": True}


class ScheduleConfigIn(BaseModel):
    job_key: str
    enabled: bool
    days: list[int] = Field(..., description="Weekday ints: 0=Mon … 6=Sun")
    run_at_hour: int = Field(..., ge=0, le=23)
    run_at_minute: int = Field(..., ge=0, le=59)
```

---

## Task 4: Service Layer

**Files:**
- Create: `backend/app/services/price_schedule_config.py`

- [ ] **Step 1: Create service file**

`backend/app/services/price_schedule_config.py`:
```python
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.price_schedule_config import PriceScheduleConfig
from app.models.user import User
from app.schemas.price_schedule_config import ScheduleConfigIn

logger = get_logger(__name__)

VALID_JOB_KEYS = frozenset(
    {"us_stock", "thai_stock", "thai_fund", "crypto", "gold", "benchmark"}
)

DEFAULT_CONFIGS: dict[str, dict] = {
    "us_stock":   {"enabled": True, "days": [0, 1, 2, 3, 4], "run_at_hour": 19, "run_at_minute": 0},
    "thai_stock": {"enabled": True, "days": [0, 1, 2, 3, 4], "run_at_hour": 13, "run_at_minute": 0},
    "thai_fund":  {"enabled": True, "days": [0, 1, 2, 3, 4], "run_at_hour": 13, "run_at_minute": 0},
    "crypto":     {"enabled": True, "days": list(range(7)), "run_at_hour": 0, "run_at_minute": 0},
    "gold":       {"enabled": True, "days": list(range(7)), "run_at_hour": 0, "run_at_minute": 0},
    "benchmark":  {"enabled": True, "days": list(range(7)), "run_at_hour": 0, "run_at_minute": 0},
}


async def get_all_configs(
    db: AsyncSession, user_id: uuid.UUID
) -> list[PriceScheduleConfig]:
    """Return all 6 schedule configs for user, seeding defaults for any missing rows."""
    result = await db.execute(
        select(PriceScheduleConfig).where(PriceScheduleConfig.user_id == user_id)
    )
    existing = {c.job_key: c for c in result.scalars().all()}

    configs: list[PriceScheduleConfig] = []
    for job_key, defaults in DEFAULT_CONFIGS.items():
        if job_key not in existing:
            config = PriceScheduleConfig(user_id=user_id, job_key=job_key, **defaults)
            db.add(config)
            configs.append(config)
        else:
            configs.append(existing[job_key])
    await db.flush()
    return configs


async def upsert_configs(
    db: AsyncSession, user_id: uuid.UUID, updates: list[ScheduleConfigIn]
) -> list[PriceScheduleConfig]:
    """Bulk upsert schedule configs. Ignores unknown job_keys."""
    result = await db.execute(
        select(PriceScheduleConfig).where(PriceScheduleConfig.user_id == user_id)
    )
    existing = {c.job_key: c for c in result.scalars().all()}

    configs: list[PriceScheduleConfig] = []
    now = datetime.now(timezone.utc)
    for item in updates:
        if item.job_key not in VALID_JOB_KEYS:
            continue
        if item.job_key in existing:
            config = existing[item.job_key]
            config.enabled = item.enabled
            config.days = item.days
            config.run_at_hour = item.run_at_hour
            config.run_at_minute = item.run_at_minute
            config.updated_at = now
        else:
            config = PriceScheduleConfig(
                user_id=user_id,
                job_key=item.job_key,
                enabled=item.enabled,
                days=item.days,
                run_at_hour=item.run_at_hour,
                run_at_minute=item.run_at_minute,
            )
            db.add(config)
        configs.append(config)
    await db.flush()
    return configs


async def should_run_job(db: AsyncSession, job_key: str, pattern: str) -> bool:
    """Check if job should run based on primary user's schedule config.

    pattern: "once_daily" → run only when hour == run_at_hour
             "interval"   → run when hour >= run_at_hour
    """
    result = await db.execute(select(User).order_by(User.created_at).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        return True

    configs = await get_all_configs(db, user.id)
    await db.commit()
    config = next((c for c in configs if c.job_key == job_key), None)
    if not config:
        return True

    if not config.enabled:
        logger.debug("job %s skipped: disabled", job_key)
        return False

    now_bkk = datetime.now(ZoneInfo("Asia/Bangkok"))
    if now_bkk.weekday() not in config.days:
        logger.debug("job %s skipped: weekday %d not in %s", job_key, now_bkk.weekday(), config.days)
        return False

    if pattern == "once_daily":
        return now_bkk.hour == config.run_at_hour
    if pattern == "interval":
        return now_bkk.hour >= config.run_at_hour
    return True
```

---

## Task 5: Settings API Endpoints

**Files:**
- Modify: `backend/app/api/settings.py`

- [ ] **Step 1: Add imports to settings.py**

At the top of `backend/app/api/settings.py`, add:
```python
from app.schemas.price_schedule_config import ScheduleConfigIn, ScheduleConfigOut
from app.services import price_schedule_config as schedule_service
```

- [ ] **Step 2: Add GET and PUT /schedule endpoints**

Append to `backend/app/api/settings.py` (before the end of file):
```python
@router.get("/schedule", response_model=list[ScheduleConfigOut])
async def get_schedule(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    configs = await schedule_service.get_all_configs(db, current_user.id)
    await db.commit()
    return configs


@router.put("/schedule", response_model=list[ScheduleConfigOut])
async def update_schedule(
    updates: list[ScheduleConfigIn],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    configs = await schedule_service.upsert_configs(db, current_user.id, updates)
    await db.commit()
    return configs
```

- [ ] **Step 3: Write tests**

Create `backend/tests/test_schedule_api.py`:
```python
import pytest


@pytest.mark.asyncio
async def test_get_schedule_returns_6_defaults(auth_client):
    res = await auth_client.get("/api/v1/settings/schedule")
    assert res.status_code == 200
    configs = res.json()
    assert len(configs) == 6
    keys = {c["job_key"] for c in configs}
    assert keys == {"us_stock", "thai_stock", "thai_fund", "crypto", "gold", "benchmark"}


@pytest.mark.asyncio
async def test_get_schedule_us_stock_defaults(auth_client):
    res = await auth_client.get("/api/v1/settings/schedule")
    configs = {c["job_key"]: c for c in res.json()}
    us = configs["us_stock"]
    assert us["enabled"] is True
    assert us["days"] == [0, 1, 2, 3, 4]
    assert us["run_at_hour"] == 19
    assert us["run_at_minute"] == 0


@pytest.mark.asyncio
async def test_get_schedule_idempotent(auth_client):
    """Calling GET twice does not duplicate rows."""
    await auth_client.get("/api/v1/settings/schedule")
    res = await auth_client.get("/api/v1/settings/schedule")
    assert len(res.json()) == 6


@pytest.mark.asyncio
async def test_put_schedule_updates_config(auth_client):
    get_res = await auth_client.get("/api/v1/settings/schedule")
    configs = get_res.json()
    # Change thai_stock to disabled, hour 10
    for c in configs:
        if c["job_key"] == "thai_stock":
            c["enabled"] = False
            c["run_at_hour"] = 10

    put_res = await auth_client.put("/api/v1/settings/schedule", json=configs)
    assert put_res.status_code == 200

    verify = await auth_client.get("/api/v1/settings/schedule")
    updated = {c["job_key"]: c for c in verify.json()}
    assert updated["thai_stock"]["enabled"] is False
    assert updated["thai_stock"]["run_at_hour"] == 10


@pytest.mark.asyncio
async def test_put_schedule_rejects_invalid_hour(auth_client):
    get_res = await auth_client.get("/api/v1/settings/schedule")
    configs = get_res.json()
    configs[0]["run_at_hour"] = 25  # invalid
    res = await auth_client.put("/api/v1/settings/schedule", json=configs)
    assert res.status_code == 422
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec backend pytest tests/test_schedule_api.py -v
```

Expected: 5 passed.

---

## Task 6: Pipeline Schema + API (add thai_stock, thai_fund triggers)

**Files:**
- Modify: `backend/app/schemas/pipeline.py`
- Modify: `backend/app/api/pipeline.py`

- [ ] **Step 1: Add new job types to schema**

In `backend/app/schemas/pipeline.py`, update `JobType`:
```python
JobType = Literal[
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "price_fetch_thai_stock", "price_fetch_th_fund",
    "snapshot_net_worth",
    "watchlist_discovery", "watchlist_scan",
    "run_analysis", "ingest_document",
]
```

- [ ] **Step 2: Add new entries to job_fn_map in pipeline API**

In `backend/app/api/pipeline.py`, inside `trigger_job`, update `job_fn_map`:
```python
job_fn_map = {
    "price_fetch_us": "job_fetch_prices_us",
    "price_fetch_crypto": "job_fetch_prices_crypto",
    "price_fetch_gold": "job_fetch_price_gold",
    "price_fetch_benchmark": "job_fetch_benchmark_prices",
    "price_fetch_thai_stock": "job_fetch_prices_thai_stock",
    "price_fetch_th_fund": "job_fetch_prices_th_fund",
    "snapshot_net_worth": "job_snapshot_net_worth",
}
```

- [ ] **Step 3: Write test**

`JobType` is a `Literal` — FastAPI returns 422 for unknown values, so the new types are validated at schema level. Test the boundary:

Add to `backend/tests/test_schedule_api.py`:
```python
@pytest.mark.asyncio
async def test_trigger_invalid_job_returns_422(auth_client):
    """Unknown job type is rejected by FastAPI schema validation."""
    res = await auth_client.post("/api/v1/pipeline/trigger/not_a_real_job")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_trigger_thai_stock_job_type_accepted_by_schema(auth_client):
    """price_fetch_thai_stock passes schema validation (may fail at Redis step in CI, that's OK)."""
    res = await auth_client.post("/api/v1/pipeline/trigger/price_fetch_thai_stock")
    # 202 if Redis available, 500 if not — either way, NOT 422
    assert res.status_code != 422


@pytest.mark.asyncio
async def test_trigger_th_fund_job_type_accepted_by_schema(auth_client):
    res = await auth_client.post("/api/v1/pipeline/trigger/price_fetch_th_fund")
    assert res.status_code != 422
```

- [ ] **Step 4: Run tests**

```bash
docker compose exec backend pytest tests/test_schedule_api.py::test_trigger_invalid_job_returns_422 -v
```

Expected: 1 passed.

---

## Task 7: Worker Guard + Cron Update

**Files:**
- Modify: `backend/worker/jobs/price_fetch.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Add guard import to price_fetch.py**

At the top of `backend/worker/jobs/price_fetch.py`, add:
```python
from app.services.price_schedule_config import should_run_job
```

- [ ] **Step 2: Add guard to `job_fetch_prices_us`**

Replace the function body:
```python
async def job_fetch_prices_us(ctx: dict) -> dict:
    """ARQ job: fetch US stock prices via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not await should_run_job(db, "us_stock", "interval"):
            logger.info("job_fetch_prices_us skipped by schedule")
            return {"skipped": True}
        log = await create_log(db, "price_fetch_us")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_us_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_prices_us failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 3: Add guard to `job_fetch_prices_crypto`**

```python
async def job_fetch_prices_crypto(ctx: dict) -> dict:
    """ARQ job: fetch crypto prices via CoinGecko."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not await should_run_job(db, "crypto", "interval"):
            logger.info("job_fetch_prices_crypto skipped by schedule")
            return {"skipped": True}
        log = await create_log(db, "price_fetch_crypto")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_crypto_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_prices_crypto failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 4: Add guard to `job_fetch_price_gold`**

```python
async def job_fetch_price_gold(ctx: dict) -> dict:
    """ARQ job: fetch gold spot price."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not await should_run_job(db, "gold", "interval"):
            logger.info("job_fetch_price_gold skipped by schedule")
            return {"skipped": True}
        log = await create_log(db, "price_fetch_gold")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_gold_price(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_price_gold failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 5: Add guard to `job_fetch_prices_thai_stock`**

```python
async def job_fetch_prices_thai_stock(ctx: dict) -> dict:
    """ARQ job: fetch Thai stock and Thai DR prices via yfinance (.BK suffix)."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not await should_run_job(db, "thai_stock", "once_daily"):
            logger.info("job_fetch_prices_thai_stock skipped by schedule")
            return {"skipped": True}
        log = await create_log(db, "price_fetch_thai_stock")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_thai_stock_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_prices_thai_stock failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 6: Add guard to `job_fetch_prices_th_fund`**

```python
async def job_fetch_prices_th_fund(ctx: dict) -> dict:
    """ARQ job: fetch Thai mutual fund NAV via SEC Thailand API v2."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not await should_run_job(db, "thai_fund", "once_daily"):
            logger.info("job_fetch_prices_th_fund skipped by schedule")
            return {"skipped": True}
        log = await create_log(db, "price_fetch_th_fund")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_th_fund_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            await ctx["redis"].enqueue_job("job_check_watchlist_alerts", _job_id="watchlist_alert_check")
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_prices_th_fund failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 7: Add guard to `job_fetch_benchmark_prices`**

```python
async def job_fetch_benchmark_prices(ctx: dict) -> dict:
    """ARQ job: fetch S&P500 and SET benchmark prices."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        if not await should_run_job(db, "benchmark", "once_daily"):
            logger.info("job_fetch_benchmark_prices skipped by schedule")
            return {"skipped": True}
        log = await create_log(db, "price_fetch_benchmark")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_benchmark_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            return {"inserted": result["inserted"]}
        except Exception as e:
            logger.exception("job_fetch_benchmark_prices failed: %s", e)
            await finish_step(db, step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 8: Update cron schedule in `worker/main.py`**

Change `cron_jobs` in `WorkerSettings` — once-daily jobs switch to `minute=0` (every hour; guard picks right hour). US/Crypto/Gold/Benchmark weekday is now controlled by the DB guard, so cron day constraints are removed:

```python
cron_jobs = [
    cron(job_fetch_prices_us, minute={0, 15, 30, 45}),
    cron(job_fetch_prices_crypto, minute={0, 15, 30, 45}),
    cron(job_fetch_price_gold, minute={0, 15, 30, 45}),
    cron(job_fetch_benchmark_prices, minute=0),         # every hour; guard checks hour==0 Bangkok
    cron(job_fetch_prices_thai_stock, minute=0),        # every hour; guard checks hour==13 Bangkok
    cron(job_fetch_prices_th_fund, minute=0),           # every hour; guard checks hour==13 Bangkok
    cron(job_snapshot_net_worth, hour=1, minute=0),
    cron(job_fetch_dividends, weekday=0, hour=2, minute=0),
]
```

---

## Task 8: Backup Update

**Files:**
- Modify: `backend/app/schemas/system_backup.py`
- Modify: `backend/app/services/system_backup.py`

- [ ] **Step 1: Add BackupScheduleConfig and update BackupSettings**

In `backend/app/schemas/system_backup.py`, add before `BackupSettings`:
```python
class BackupScheduleConfig(BaseModel):
    job_key: str
    enabled: bool
    days: list[int]
    run_at_hour: int
    run_at_minute: int
```

Update `BackupSettings` to add the new field:
```python
class BackupSettings(BaseModel):
    currency_primary: str
    currency_secondary: str
    birth_date: Optional[date] = None
    plan_to_age: Optional[int] = None
    privacy_mode: bool = False
    telegram_chat_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    sec_api_key: Optional[str] = None
    schedule_configs: list[BackupScheduleConfig] = []
```

Update `SystemBackup.version` default to `"2"`:
```python
class SystemBackup(BaseModel):
    model_config = {"from_attributes": True}

    version: str = "2"
    ...
```

- [ ] **Step 2: Update export_backup to include schedule configs**

In `backend/app/services/system_backup.py`:

Add import at top:
```python
from app.services import price_schedule_config as schedule_service
from app.schemas.system_backup import BackupScheduleConfig
```

Inside `export_backup`, before the `return SystemBackup(...)` call, add:
```python
    raw_schedules = await schedule_service.get_all_configs(db, user.id)
    await db.commit()
    schedule_configs = [
        BackupScheduleConfig(
            job_key=c.job_key,
            enabled=c.enabled,
            days=c.days,
            run_at_hour=c.run_at_hour,
            run_at_minute=c.run_at_minute,
        )
        for c in raw_schedules
    ]
```

Then in the existing `BackupSettings(...)` constructor call (already present in `export_backup`), add `schedule_configs=schedule_configs` as the last keyword argument. Do NOT rewrite the whole constructor — just append the one argument.

- [ ] **Step 3: Update import_backup to restore schedule configs**

In `backend/app/services/system_backup.py`, update `SUPPORTED_VERSIONS`:
```python
SUPPORTED_VERSIONS = {"1", "2"}
```

Inside `import_backup`, after restoring settings, add:
```python
    if backup.settings.schedule_configs:
        from app.schemas.price_schedule_config import ScheduleConfigIn
        updates = [
            ScheduleConfigIn(
                job_key=s.job_key,
                enabled=s.enabled,
                days=s.days,
                run_at_hour=s.run_at_hour,
                run_at_minute=s.run_at_minute,
            )
            for s in backup.settings.schedule_configs
        ]
        await schedule_service.upsert_configs(db, user.id, updates)
        logger.info("Restored %d schedule configs", len(updates))
```

- [ ] **Step 4: Write test**

Add to `backend/tests/test_schedule_api.py`:
```python
@pytest.mark.asyncio
async def test_export_includes_schedule_configs(auth_client):
    # Seed defaults first
    await auth_client.get("/api/v1/settings/schedule")

    res = await auth_client.get("/api/v1/system/export")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == "2"
    assert "schedule_configs" in data["settings"]
    assert len(data["settings"]["schedule_configs"]) == 6


@pytest.mark.asyncio
async def test_import_v1_backup_does_not_fail(auth_client):
    """v1 backup without schedule_configs imports successfully."""
    import json, io
    backup_v1 = {
        "version": "1",
        "exported_at": "2026-01-01T00:00:00Z",
        "settings": {
            "currency_primary": "THB",
            "currency_secondary": "USD",
        },
        "portfolio": {"holdings": [], "transactions": []},
    }
    file_content = json.dumps(backup_v1).encode()
    res = await auth_client.post(
        "/api/v1/system/import",
        files={"file": ("backup.json", io.BytesIO(file_content), "application/json")},
    )
    assert res.status_code == 200
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec backend pytest tests/test_schedule_api.py -v
```

Expected: all tests pass.

---

## Task 9: Frontend Schedule Service + Pipeline Types

**Files:**
- Create: `frontend/lib/services/schedule.ts`
- Modify: `frontend/lib/services/pipeline.ts`

- [ ] **Step 1: Create schedule service**

`frontend/lib/services/schedule.ts`:
```typescript
import { api } from "@/lib/api";

export interface ScheduleConfig {
  job_key: string;
  enabled: boolean;
  days: number[];       // 0=Mon … 6=Sun
  run_at_hour: number;
  run_at_minute: number;
}

export async function fetchScheduleConfigs(): Promise<ScheduleConfig[]> {
  const res = await api.get("/api/v1/settings/schedule");
  if (!res.ok) throw new Error("Failed to fetch schedule configs");
  return res.json();
}

export async function saveScheduleConfigs(
  configs: ScheduleConfig[]
): Promise<ScheduleConfig[]> {
  const res = await api.put("/api/v1/settings/schedule", configs);
  if (!res.ok) throw new Error("Failed to save schedule configs");
  return res.json();
}
```

- [ ] **Step 2: Add new job types to pipeline service**

In `frontend/lib/services/pipeline.ts`, update `JobType`:
```typescript
export type JobType =
  | "price_fetch_us"
  | "price_fetch_crypto"
  | "price_fetch_gold"
  | "price_fetch_benchmark"
  | "price_fetch_thai_stock"
  | "price_fetch_th_fund"
  | "watchlist_discovery"
  | "watchlist_scan"
  | "run_analysis"
  | "ingest_document";
```

---

## Task 10: Frontend TriggerButtons Component + Pipeline Page

**Files:**
- Create: `frontend/components/pipeline/TriggerButtons.tsx`
- Modify: `frontend/app/(auth)/pipeline/page.tsx`

- [ ] **Step 1: Create TriggerButtons component**

`frontend/components/pipeline/TriggerButtons.tsx`:
```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { triggerJob, type JobType } from "@/lib/services/pipeline";
import { toast } from "sonner";

const JOBS: { key: JobType; label: string }[] = [
  { key: "price_fetch_us", label: "US Stock" },
  { key: "price_fetch_crypto", label: "Crypto" },
  { key: "price_fetch_gold", label: "Gold" },
  { key: "price_fetch_thai_stock", label: "Thai Stock/DR" },
  { key: "price_fetch_th_fund", label: "Thai Fund" },
  { key: "price_fetch_benchmark", label: "Benchmark" },
];

export function TriggerButtons() {
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  async function handleTrigger(key: JobType, label: string) {
    setLoading((prev) => ({ ...prev, [key]: true }));
    try {
      await triggerJob(key);
      toast.success(`${label} job enqueued`);
    } catch {
      toast.error(`Failed to trigger ${label}`);
    } finally {
      setLoading((prev) => ({ ...prev, [key]: false }));
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {JOBS.map(({ key, label }) => (
        <Button
          key={key}
          variant="outline"
          size="sm"
          disabled={!!loading[key]}
          onClick={() => handleTrigger(key, label)}
        >
          {loading[key] ? "Running…" : `▶ ${label}`}
        </Button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Add TriggerButtons to pipeline page**

In `frontend/app/(auth)/pipeline/page.tsx`, add import:
```tsx
import { TriggerButtons } from "@/components/pipeline/TriggerButtons";
```

In the return JSX, add `<TriggerButtons />` between the description paragraph and `<JobsTable>`:
```tsx
return (
  <div className="space-y-4">
    <PageHeader title="Pipeline" />
    <p className="text-muted-foreground text-sm">
      Live price fetch job status. Updates every 3 seconds via SSE.
    </p>
    <TriggerButtons />
    <JobsTable jobs={jobs} />
  </div>
);
```

---

## Task 11: Frontend ScheduleTab Component + Settings Page

**Files:**
- Create: `frontend/components/settings/ScheduleTab.tsx`
- Modify: `frontend/app/(auth)/settings/page.tsx`

- [ ] **Step 1: Create ScheduleTab component**

`frontend/components/settings/ScheduleTab.tsx`:
```tsx
"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchScheduleConfigs,
  saveScheduleConfigs,
  type ScheduleConfig,
} from "@/lib/services/schedule";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

const JOB_LABELS: Record<string, string> = {
  us_stock: "US Stock",
  thai_stock: "Thai Stock / DR",
  thai_fund: "Thai Fund",
  crypto: "Crypto",
  gold: "Gold",
  benchmark: "Benchmark",
};

const JOB_ORDER = ["us_stock", "thai_stock", "thai_fund", "crypto", "gold", "benchmark"];
const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function ScheduleTab() {
  const queryClient = useQueryClient();

  const { data: serverConfigs, isLoading } = useQuery({
    queryKey: ["schedule-configs"],
    queryFn: fetchScheduleConfigs,
  });

  const [configs, setConfigs] = useState<ScheduleConfig[]>([]);

  useEffect(() => {
    if (serverConfigs) setConfigs(serverConfigs);
  }, [serverConfigs]);

  const { mutate: save, isPending } = useMutation({
    mutationFn: saveScheduleConfigs,
    onSuccess: (data) => {
      setConfigs(data);
      queryClient.invalidateQueries({ queryKey: ["schedule-configs"] });
      toast.success("Schedule saved");
    },
    onError: () => toast.error("Failed to save schedule"),
  });

  function updateConfig(jobKey: string, patch: Partial<ScheduleConfig>) {
    setConfigs((prev) =>
      prev.map((c) => (c.job_key === jobKey ? { ...c, ...patch } : c))
    );
  }

  function toggleDay(jobKey: string, day: number, checked: boolean) {
    setConfigs((prev) =>
      prev.map((c) => {
        if (c.job_key !== jobKey) return c;
        const days = checked
          ? [...c.days, day].sort((a, b) => a - b)
          : c.days.filter((d) => d !== day);
        return { ...c, days };
      })
    );
  }

  if (isLoading) {
    return <p className="text-muted-foreground text-sm">Loading schedule…</p>;
  }

  const ordered = JOB_ORDER.map((key) =>
    configs.find((c) => c.job_key === key)
  ).filter(Boolean) as ScheduleConfig[];

  return (
    <div className="space-y-4">
      {ordered.map((config) => (
        <div
          key={config.job_key}
          className="border rounded-lg p-4 space-y-3"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium">
              {JOB_LABELS[config.job_key] ?? config.job_key}
            </span>
            <Switch
              checked={config.enabled}
              onCheckedChange={(v) =>
                updateConfig(config.job_key, { enabled: v })
              }
            />
          </div>

          <div className="flex items-center gap-3">
            <Label className="text-sm text-muted-foreground w-28 shrink-0">
              Time (Bangkok)
            </Label>
            <Select
              value={String(config.run_at_hour)}
              onValueChange={(v) =>
                updateConfig(config.job_key, { run_at_hour: Number(v) })
              }
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 24 }, (_, i) => (
                  <SelectItem key={i} value={String(i)}>
                    {String(i).padStart(2, "0")}:00
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-muted-foreground text-sm">:</span>
            <Select
              value={String(config.run_at_minute)}
              onValueChange={(v) =>
                updateConfig(config.job_key, { run_at_minute: Number(v) })
              }
            >
              <SelectTrigger className="w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[0, 15, 30, 45].map((m) => (
                  <SelectItem key={m} value={String(m)}>
                    :{String(m).padStart(2, "0")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-3">
            <Label className="text-sm text-muted-foreground w-28 shrink-0">
              Days
            </Label>
            <div className="flex gap-4">
              {DAY_LABELS.map((day, i) => (
                <label
                  key={day}
                  className="flex flex-col items-center gap-1 cursor-pointer"
                >
                  <Checkbox
                    checked={config.days.includes(i)}
                    onCheckedChange={(v) =>
                      toggleDay(config.job_key, i, !!v)
                    }
                  />
                  <span className="text-xs text-muted-foreground">{day}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      ))}

      <Button onClick={() => save(configs)} disabled={isPending}>
        {isPending ? "Saving…" : "Save Schedule"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Add Schedule tab to settings page**

In `frontend/app/(auth)/settings/page.tsx`:

Add import at the top:
```tsx
import { ScheduleTab } from "@/components/settings/ScheduleTab";
```

Add a 5th tab trigger inside `<TabsList>` (after Notifications):
```tsx
<TabsTrigger value="schedule">Schedule</TabsTrigger>
```

Add the tab content after the Notifications `</TabsContent>`:
```tsx
<TabsContent value="schedule" className="space-y-6 mt-4">
  <ScheduleTab />
</TabsContent>
```

- [ ] **Step 3: Verify in browser**

Start dev server if not running:
```bash
docker compose up frontend
```

1. Open `/settings` → confirm **Schedule** tab appears as the 5th tab.
2. Confirm 6 job cards render with correct defaults (US Stock: Mon–Fri, 19:00; Thai Stock: Mon–Fri, 13:00).
3. Toggle a job off → click Save → refresh page → confirm toggle stays off.
4. Open `/pipeline` → confirm 6 trigger buttons appear above the jobs table.
5. Click **▶ Thai Stock/DR** → confirm toast "Thai Stock/DR job enqueued" appears.
