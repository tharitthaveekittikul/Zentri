# Phase 4: Price Feeds + Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add background price fetching (US stocks, crypto, gold, benchmarks) via ARQ cron jobs, persist OHLCV data in a TimescaleDB hypertable, track all job executions in pipeline_logs, and expose a live pipeline monitor page with SSE streaming.

**Architecture:** New ARQ worker jobs (`worker/jobs/`) write prices to a `prices` TimescaleDB hypertable and log execution to `pipeline_logs`. A `benchmarks` table seeds S&P500 and SET benchmark data independently of user assets. FastAPI `pipeline` router serves job list, job detail, manual trigger, and an SSE stream endpoint. Frontend pipeline page consumes the SSE stream with a native `EventSource`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, ARQ, yfinance, httpx (CoinGecko), TimescaleDB hypertable, Server-Sent Events (StreamingResponse), Next.js 15 App Router, TanStack Query v5, shadcn/ui Badge/Card/Table

---

## Scope

This plan covers Kanban tasks:

- `feat - ARQ price fetch job for US stocks via yfinance`
- `feat - ARQ price fetch job for crypto via CoinGecko`
- `feat - ARQ price fetch job for gold spot price`
- `feat - pipeline logs table and job tracking`
- `feat - pipeline jobs list and SSE stream endpoints`
- `feat - pipeline monitor page with live SSE feed`
- `feat - benchmark price feed for S&P500 and SET`

Phase 5 (Charts + Asset Detail page) is a separate plan.

---

## File Map

```
backend/
├── app/
│   ├── models/
│   │   ├── __init__.py                   # MODIFY — add Price, PipelineLog, Benchmark imports
│   │   ├── price.py                      # NEW — Price OHLCV model (TimescaleDB hypertable)
│   │   ├── pipeline_log.py               # NEW — PipelineLog model
│   │   └── benchmark.py                  # NEW — Benchmark model (^GSPC, ^SET.BK)
│   ├── schemas/
│   │   ├── price.py                      # NEW — PriceBar, PriceHistoryResponse
│   │   └── pipeline.py                   # NEW — PipelineLogResponse, JobType, JobStatus
│   ├── services/
│   │   ├── pipeline.py                   # NEW — create_log, finish_log, list_logs
│   │   └── price_feed.py                 # NEW — fetch_us_prices, fetch_crypto_prices, fetch_gold_price, fetch_benchmark_prices
│   └── api/
│       ├── __init__.py                   # MODIFY — include pipeline router
│       ├── pipeline.py                   # NEW — list, detail, trigger, SSE stream
│       └── assets.py                     # MODIFY — add GET /assets/{id}/prices endpoint
├── alembic/
│   └── versions/
│       └── 003_price_pipeline_schema.py  # NEW — prices hypertable, pipeline_logs, benchmarks
└── worker/
    ├── main.py                           # MODIFY — startup DB pool, register jobs + cron
    └── jobs/
        ├── __init__.py                   # NEW — empty
        └── price_fetch.py               # NEW — fetch_prices_us, fetch_prices_crypto, fetch_price_gold, fetch_benchmark_prices

frontend/
├── app/(auth)/
│   └── pipeline/
│       └── page.tsx                      # NEW — Pipeline monitor page
├── components/
│   └── pipeline/
│       └── JobsTable.tsx                 # NEW — jobs table with status badges + SSE updates
├── lib/
│   └── services/
│       └── pipeline.ts                   # NEW — fetchJobs, triggerJob API calls
└── components/layout/
    └── Sidebar.tsx                       # MODIFY — add Pipeline nav link
```

---

## Task 1: SQLAlchemy Models — Price, PipelineLog, Benchmark

**Files:**

- Create: `backend/app/models/price.py`
- Create: `backend/app/models/pipeline_log.py`
- Create: `backend/app/models/benchmark.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write `price.py` model**

```python
# backend/app/models/price.py
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Price(Base):
    __tablename__ = "prices"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), primary_key=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    open: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)

    __table_args__ = (
        Index("ix_prices_asset_timestamp", "asset_id", "timestamp"),
    )
```

- [ ] **Step 2: Write `pipeline_log.py` model**

```python
# backend/app/models/pipeline_log.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

JOB_TYPES = ("price_fetch_us", "price_fetch_crypto", "price_fetch_gold", "price_fetch_benchmark")
JOB_STATUSES = ("queued", "running", "done", "failed")


class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(
        Enum(*JOB_TYPES, name="job_type_enum"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(*JOB_STATUSES, name="job_status_enum"), nullable=False, default="queued"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Write `benchmark.py` model**

```python
# backend/app/models/benchmark.py
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class BenchmarkPrice(Base):
    __tablename__ = "benchmark_prices"

    benchmark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benchmarks.id"), primary_key=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    open: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
```

- [ ] **Step 4: Update `models/__init__.py`**

```python
# backend/app/models/__init__.py
from app.models.asset import Asset  # noqa: F401
from app.models.benchmark import Benchmark, BenchmarkPrice  # noqa: F401
from app.models.holding import Holding  # noqa: F401
from app.models.import_profile import ImportProfile  # noqa: F401
from app.models.pipeline_log import PipelineLog  # noqa: F401
from app.models.platform import Platform  # noqa: F401
from app.models.price import Price  # noqa: F401
from app.models.transaction import Transaction  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "User", "Asset", "Platform", "Holding", "Transaction", "ImportProfile",
    "Price", "PipelineLog", "Benchmark", "BenchmarkPrice",
]
```

- [ ] **Step 5: Verify models import without error**

```bash
cd /path/to/zentri/backend
python -c "import app.models; print('OK')"
```

Expected: `OK`

---

## Task 2: Alembic Migration 003 — prices hypertable + pipeline_logs + benchmarks

**Files:**

- Create: `backend/alembic/versions/003_price_pipeline_schema.py`

- [ ] **Step 1: Write the migration**

```python
# backend/alembic/versions/003_price_pipeline_schema.py
"""price feed and pipeline schema

Revision ID: 003
Revises: 002
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enums ---
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_type_enum AS ENUM (
                'price_fetch_us', 'price_fetch_crypto',
                'price_fetch_gold', 'price_fetch_benchmark'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_status_enum AS ENUM ('queued', 'running', 'done', 'failed');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)

    # --- prices table (will become TimescaleDB hypertable) ---
    op.create_table(
        "prices",
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=True),
        sa.Column("high", sa.Numeric(20, 8), nullable=True),
        sa.Column("low", sa.Numeric(20, 8), nullable=True),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(20, 8), nullable=True),
        sa.PrimaryKeyConstraint("asset_id", "timestamp"),
    )
    op.create_index("ix_prices_asset_timestamp", "prices", ["asset_id", "timestamp"])
    # Convert to TimescaleDB hypertable — partitioned by timestamp
    op.execute(
        "SELECT create_hypertable('prices', 'timestamp', if_not_exists => TRUE)"
    )

    # --- pipeline_logs table ---
    op.create_table(
        "pipeline_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "job_type",
            sa.Enum(
                "price_fetch_us", "price_fetch_crypto", "price_fetch_gold", "price_fetch_benchmark",
                name="job_type_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "done", "failed", name="job_status_enum", create_type=False),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_pipeline_logs_started_at", "pipeline_logs", ["started_at"])

    # --- benchmarks table ---
    op.create_table(
        "benchmarks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("symbol", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
    )
    # Seed default benchmarks
    op.execute("""
        INSERT INTO benchmarks (symbol, name) VALUES
            ('^GSPC', 'S&P 500'),
            ('^SET.BK', 'SET Index')
        ON CONFLICT (symbol) DO NOTHING
    """)

    # --- benchmark_prices table (hypertable) ---
    op.create_table(
        "benchmark_prices",
        sa.Column("benchmark_id", UUID(as_uuid=True), sa.ForeignKey("benchmarks.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=True),
        sa.Column("high", sa.Numeric(20, 8), nullable=True),
        sa.Column("low", sa.Numeric(20, 8), nullable=True),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(20, 8), nullable=True),
        sa.PrimaryKeyConstraint("benchmark_id", "timestamp"),
    )
    op.execute(
        "SELECT create_hypertable('benchmark_prices', 'timestamp', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_table("benchmark_prices")
    op.drop_table("benchmarks")
    op.drop_index("ix_pipeline_logs_started_at", table_name="pipeline_logs")
    op.drop_table("pipeline_logs")
    op.drop_index("ix_prices_asset_timestamp", table_name="prices")
    op.drop_table("prices")
    op.execute("DROP TYPE job_status_enum")
    op.execute("DROP TYPE job_type_enum")
```

- [ ] **Step 2: Run migration against the dev DB**

```bash
cd backend
docker compose exec backend alembic upgrade head
```

Expected output ends with: `Running upgrade 002 -> 003, price feed and pipeline schema`

- [ ] **Step 3: Verify hypertables were created**

```bash
docker compose exec postgres psql -U postgres -d zentri -c \
  "SELECT hypertable_name FROM timescaledb_information.hypertables;"
```

Expected: rows for `prices` and `benchmark_prices`

---

## Task 3: PipelineLog Service

**Files:**

- Create: `backend/app/services/pipeline.py`

- [ ] **Step 1: Write the service**

```python
# backend/app/services/pipeline.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.pipeline_log import PipelineLog

logger = get_logger(__name__)


async def create_log(db: AsyncSession, job_type: str) -> PipelineLog:
    log = PipelineLog(
        job_type=job_type,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    logger.info("pipeline job started job_type=%s id=%s", job_type, log.id)
    return log


async def finish_log(
    db: AsyncSession,
    log: PipelineLog,
    *,
    success: bool,
    error_message: str | None = None,
) -> PipelineLog:
    log.status = "done" if success else "failed"
    log.finished_at = datetime.now(timezone.utc)
    log.error_message = error_message
    await db.commit()
    await db.refresh(log)
    logger.info(
        "pipeline job finished job_type=%s status=%s id=%s",
        log.job_type, log.status, log.id,
    )
    return log


async def list_logs(db: AsyncSession, limit: int = 50) -> list[PipelineLog]:
    result = await db.execute(
        select(PipelineLog).order_by(desc(PipelineLog.started_at)).limit(limit)
    )
    return list(result.scalars().all())


async def get_log(db: AsyncSession, log_id: uuid.UUID) -> PipelineLog | None:
    result = await db.execute(
        select(PipelineLog).where(PipelineLog.id == log_id)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 2: Verify import**

```bash
cd backend
python -c "from app.services.pipeline import create_log; print('OK')"
```

Expected: `OK`

---

## Task 4: Price Feed Service

**Files:**

- Create: `backend/app/services/price_feed.py`

Note: `yfinance` and `httpx` must be available. Check `pyproject.toml` first:

```bash
cd backend && grep -E "yfinance|httpx" pyproject.toml
```

If missing, add them:

```bash
uv pip install yfinance httpx
```

And add to `pyproject.toml` dependencies:

```toml
"yfinance>=0.2",
"httpx>=0.27",
```

- [ ] **Step 1: Write the price feed service**

```python
# backend/app/services/price_feed.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import yfinance as yf
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.benchmark import Benchmark, BenchmarkPrice
from app.models.price import Price

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_decimal(val) -> Decimal | None:
    try:
        return Decimal(str(val)) if val is not None and str(val) != "nan" else None
    except Exception:
        return None


async def _upsert_prices(db: AsyncSession, rows: list[dict]) -> int:
    """Bulk upsert into the prices table. Returns count inserted."""
    if not rows:
        return 0
    await db.execute(
        text("""
            INSERT INTO prices (asset_id, timestamp, open, high, low, close, volume)
            VALUES (:asset_id, :timestamp, :open, :high, :low, :close, :volume)
            ON CONFLICT (asset_id, timestamp) DO UPDATE
            SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                close=EXCLUDED.close, volume=EXCLUDED.volume
        """),
        rows,
    )
    await db.commit()
    return len(rows)


async def _upsert_benchmark_prices(db: AsyncSession, rows: list[dict]) -> int:
    """Bulk upsert into benchmark_prices table."""
    if not rows:
        return 0
    await db.execute(
        text("""
            INSERT INTO benchmark_prices (benchmark_id, timestamp, open, high, low, close, volume)
            VALUES (:benchmark_id, :timestamp, :open, :high, :low, :close, :volume)
            ON CONFLICT (benchmark_id, timestamp) DO UPDATE
            SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                close=EXCLUDED.close, volume=EXCLUDED.volume
        """),
        rows,
    )
    await db.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# US Stocks
# ---------------------------------------------------------------------------

async def fetch_us_prices(db: AsyncSession) -> int:
    """Fetch latest daily OHLCV for all us_stock assets via yfinance."""
    result = await db.execute(
        select(Asset).where(Asset.asset_type == "us_stock")
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_us_prices: no us_stock assets found")
        return 0

    symbols = [a.symbol for a in assets]
    asset_map = {a.symbol: a.id for a in assets}

    logger.info("fetch_us_prices: fetching %d symbols", len(symbols))
    # yfinance is sync — run in thread pool
    def _fetch():
        tickers = yf.Tickers(" ".join(symbols))
        rows = []
        for sym, asset_id in asset_map.items():
            try:
                hist = tickers.tickers[sym].history(period="5d", interval="1d")
                for ts, row in hist.iterrows():
                    rows.append({
                        "asset_id": asset_id,
                        "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                        "open": _to_decimal(row.get("Open")),
                        "high": _to_decimal(row.get("High")),
                        "low": _to_decimal(row.get("Low")),
                        "close": _to_decimal(row.get("Close")),
                        "volume": _to_decimal(row.get("Volume")),
                    })
            except Exception as e:
                logger.warning("fetch_us_prices: failed for %s: %s", sym, e)
        return rows

    rows = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    inserted = await _upsert_prices(db, rows)
    logger.info("fetch_us_prices: upserted %d rows", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Crypto (CoinGecko)
# ---------------------------------------------------------------------------

COINGECKO_API = "https://api.coingecko.com/api/v3"


async def fetch_crypto_prices(db: AsyncSession) -> int:
    """Fetch latest prices for all crypto assets via CoinGecko.

    Expects asset.metadata_['coingecko_id'] to be set (e.g. 'bitcoin', 'ethereum').
    Assets without this field are skipped.
    """
    result = await db.execute(
        select(Asset).where(Asset.asset_type == "crypto")
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_crypto_prices: no crypto assets found")
        return 0

    coin_map: dict[str, object] = {}  # coingecko_id -> asset
    for a in assets:
        cg_id = (a.metadata_ or {}).get("coingecko_id")
        if cg_id:
            coin_map[cg_id] = a
        else:
            logger.warning("fetch_crypto_prices: asset %s missing coingecko_id in metadata", a.symbol)

    if not coin_map:
        return 0

    ids_param = ",".join(coin_map.keys())
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{COINGECKO_API}/simple/price",
            params={"ids": ids_param, "vs_currencies": "usd", "include_last_updated_at": "true"},
        )
        resp.raise_for_status()
        data = resp.json()

    now = datetime.now(timezone.utc)
    rows = []
    for cg_id, price_data in data.items():
        asset = coin_map.get(cg_id)
        if not asset:
            continue
        rows.append({
            "asset_id": asset.id,
            "timestamp": now,
            "open": None,
            "high": None,
            "low": None,
            "close": _to_decimal(price_data.get("usd")),
            "volume": None,
        })

    inserted = await _upsert_prices(db, rows)
    logger.info("fetch_crypto_prices: upserted %d rows", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Gold
# ---------------------------------------------------------------------------

async def fetch_gold_price(db: AsyncSession) -> int:
    """Fetch gold spot price via yfinance (GC=F futures as proxy).

    Looks for an asset with symbol='GOLD' and asset_type='gold'.
    Creates the price row even if no holding exists (for display purposes).
    """
    result = await db.execute(
        select(Asset).where(Asset.asset_type == "gold")
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_gold_price: no gold assets found")
        return 0

    def _fetch():
        ticker = yf.Ticker("GC=F")
        hist = ticker.history(period="5d", interval="1d")
        return hist

    hist = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    if hist.empty:
        logger.warning("fetch_gold_price: yfinance returned empty history for GC=F")
        return 0

    rows = []
    for a in assets:
        for ts, row in hist.iterrows():
            rows.append({
                "asset_id": a.id,
                "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                "open": _to_decimal(row.get("Open")),
                "high": _to_decimal(row.get("High")),
                "low": _to_decimal(row.get("Low")),
                "close": _to_decimal(row.get("Close")),
                "volume": _to_decimal(row.get("Volume")),
            })

    inserted = await _upsert_prices(db, rows)
    logger.info("fetch_gold_price: upserted %d rows", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Benchmarks (S&P500 + SET)
# ---------------------------------------------------------------------------

# yfinance symbol for SET index is ^SET.BK
BENCHMARK_YFINANCE_SYMBOLS = {
    "^GSPC": "^GSPC",
    "^SET.BK": "^SET.BK",
}


async def fetch_benchmark_prices(db: AsyncSession) -> int:
    """Fetch benchmark prices (S&P500 and SET) via yfinance."""
    result = await db.execute(select(Benchmark))
    benchmarks = list(result.scalars().all())
    if not benchmarks:
        logger.info("fetch_benchmark_prices: no benchmarks configured")
        return 0

    def _fetch(symbol: str):
        ticker = yf.Ticker(symbol)
        return ticker.history(period="5d", interval="1d")

    rows = []
    for bm in benchmarks:
        yf_sym = BENCHMARK_YFINANCE_SYMBOLS.get(bm.symbol, bm.symbol)
        hist = await asyncio.get_event_loop().run_in_executor(None, _fetch, yf_sym)
        if hist.empty:
            logger.warning("fetch_benchmark_prices: empty history for %s", bm.symbol)
            continue
        for ts, row in hist.iterrows():
            rows.append({
                "benchmark_id": bm.id,
                "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                "open": _to_decimal(row.get("Open")),
                "high": _to_decimal(row.get("High")),
                "low": _to_decimal(row.get("Low")),
                "close": _to_decimal(row.get("Close")),
                "volume": _to_decimal(row.get("Volume")),
            })

    inserted = await _upsert_benchmark_prices(db, rows)
    logger.info("fetch_benchmark_prices: upserted %d rows", inserted)
    return inserted
```

- [ ] **Step 2: Verify import**

```bash
cd backend
python -c "from app.services.price_feed import fetch_us_prices; print('OK')"
```

Expected: `OK`

---

## Task 5: ARQ Worker Jobs + Cron Registration

**Files:**

- Create: `backend/worker/jobs/__init__.py`
- Create: `backend/worker/jobs/price_fetch.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Create `worker/jobs/__init__.py`**

```python
# backend/worker/jobs/__init__.py
```

(empty file)

- [ ] **Step 2: Write `worker/jobs/price_fetch.py`**

```python
# backend/worker/jobs/price_fetch.py
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.services.pipeline import create_log, finish_log
from app.services.price_feed import (
    fetch_benchmark_prices,
    fetch_crypto_prices,
    fetch_gold_price,
    fetch_us_prices,
)

logger = get_logger(__name__)


async def job_fetch_prices_us(ctx: dict) -> dict:
    """ARQ job: fetch US stock prices via yfinance."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "price_fetch_us")
        try:
            count = await fetch_us_prices(db)
            await finish_log(db, log, success=True)
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

- [ ] **Step 3: Update `worker/main.py`** — add DB session factory to ctx, register jobs + cron

```python
# backend/worker/main.py
from arq.connections import RedisSettings
from arq.cron import cron
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from worker.jobs.price_fetch import (
    job_fetch_benchmark_prices,
    job_fetch_price_gold,
    job_fetch_prices_crypto,
    job_fetch_prices_us,
)

setup_logging()
logger = get_logger(__name__)


async def startup(ctx: dict) -> None:
    """Create async DB session factory and attach to worker context."""
    engine = create_async_engine(settings.DATABASE_URL)
    ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    logger.info("ARQ worker started — DB pool ready")


async def shutdown(ctx: dict) -> None:
    logger.info("ARQ worker shutting down")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    functions = [
        job_fetch_prices_us,
        job_fetch_prices_crypto,
        job_fetch_price_gold,
        job_fetch_benchmark_prices,
    ]
    cron_jobs = [
        # Every 15 minutes — matches PRICE_FETCH_INTERVAL env var
        cron(job_fetch_prices_us, minute={0, 15, 30, 45}),
        cron(job_fetch_prices_crypto, minute={0, 15, 30, 45}),
        cron(job_fetch_price_gold, minute={0, 15, 30, 45}),
        # Benchmarks once per hour (less frequent, free API)
        cron(job_fetch_benchmark_prices, minute=0),
    ]
```

- [ ] **Step 4: Verify worker module imports cleanly**

```bash
cd backend
python -c "from worker.main import WorkerSettings; print('functions:', len(WorkerSettings.functions)); print('cron_jobs:', len(WorkerSettings.cron_jobs))"
```

Expected:

```
functions: 4
cron_jobs: 4
```

---

## Task 6: Schemas — Price + Pipeline

**Files:**

- Create: `backend/app/schemas/price.py`
- Create: `backend/app/schemas/pipeline.py`

- [ ] **Step 1: Write `schemas/price.py`**

```python
# backend/app/schemas/price.py
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PriceBar(BaseModel):
    timestamp: datetime
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal
    volume: Decimal | None

    model_config = {"from_attributes": True}


class PriceHistoryResponse(BaseModel):
    asset_id: uuid.UUID
    bars: list[PriceBar]
```

- [ ] **Step 2: Write `schemas/pipeline.py`**

```python
# backend/app/schemas/pipeline.py
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

JobType = Literal[
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark"
]
JobStatus = Literal["queued", "running", "done", "failed"]


class PipelineLogResponse(BaseModel):
    id: uuid.UUID
    job_type: JobType
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}
```

---

## Task 7: Pipeline API Router

**Files:**

- Create: `backend/app/api/pipeline.py`
- Modify: `backend/app/api/__init__.py`

- [ ] **Step 1: Write `api/pipeline.py`** — list, detail, trigger, SSE stream

```python
# backend/app/api/pipeline.py
import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.pipeline import JobType, PipelineLogResponse
from app.services.pipeline import get_log, list_logs

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/jobs", response_model=list[PipelineLogResponse])
async def list_pipeline_jobs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return recent pipeline job logs, newest first."""
    return await list_logs(db, limit=limit)


@router.get("/jobs/{log_id}", response_model=PipelineLogResponse)
async def get_pipeline_job(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    log = await get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Job not found")
    return log


@router.post("/trigger/{job_type}", status_code=202)
async def trigger_job(
    job_type: JobType,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enqueue a job via ARQ for immediate execution."""
    from arq.connections import ArqRedis, create_pool
    from arq.connections import RedisSettings
    from app.core.config import settings

    redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    job_fn_map = {
        "price_fetch_us": "job_fetch_prices_us",
        "price_fetch_crypto": "job_fetch_prices_crypto",
        "price_fetch_gold": "job_fetch_price_gold",
        "price_fetch_benchmark": "job_fetch_benchmark_prices",
    }
    fn_name = job_fn_map[job_type]
    job = await redis.enqueue_job(fn_name)
    await redis.close()
    return {"enqueued": True, "job_id": job.job_id if job else None}


@router.get("/stream")
async def pipeline_stream(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """SSE stream — pushes latest 20 job statuses every 3 seconds."""

    async def event_generator():
        while True:
            logs = await list_logs(db, limit=20)
            data = [
                {
                    "id": str(log.id),
                    "job_type": log.job_type,
                    "status": log.status,
                    "started_at": log.started_at.isoformat(),
                    "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                    "error_message": log.error_message,
                }
                for log in logs
            ]
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 2: Check `app/api/__init__.py` — include pipeline router**

Read `backend/app/api/__init__.py` to see how existing routers are registered, then add:

```python
from app.api.pipeline import router as pipeline_router
# inside the include_router calls:
app.include_router(pipeline_router, prefix="/api/v1")
```

(The exact file to modify is `backend/app/main.py` where routers are mounted — check whether it's in `__init__.py` or `main.py` for your codebase and follow the same pattern.)

- [ ] **Step 3: Verify app starts without error**

```bash
docker compose restart backend
docker compose logs backend --tail 20
```

Expected: no import errors; `Application startup complete.`

- [ ] **Step 4: Smoke test pipeline list endpoint**

```bash
# Get a token first
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}' | jq -r .access_token)

curl -s -H "Authorization: Bearer $TOKEN" http://localhost/api/v1/pipeline/jobs | jq length
```

Expected: `0` (no jobs run yet)

---

## Task 8: Asset Price History Endpoint

**Files:**

- Modify: `backend/app/api/assets.py`

- [ ] **Step 1: Read `backend/app/api/assets.py`** to understand existing structure, then add price history endpoint at the end of the router:

```python
# Add to backend/app/api/assets.py

from sqlalchemy import select, asc
from app.models.price import Price
from app.schemas.price import PriceBar, PriceHistoryResponse


@router.get("/{asset_id}/prices", response_model=PriceHistoryResponse)
async def get_asset_price_history(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return OHLCV price history for an asset."""
    # Verify asset belongs to user
    asset = await asset_service.get_asset(db, asset_id, current_user.id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    result = await db.execute(
        select(Price)
        .where(Price.asset_id == asset_id)
        .order_by(asc(Price.timestamp))
        .limit(500)
    )
    bars = list(result.scalars().all())
    return PriceHistoryResponse(asset_id=asset_id, bars=bars)
```

- [ ] **Step 2: Verify import chain**

```bash
cd backend
python -c "from app.api.assets import router; print('OK')"
```

Expected: `OK`

---

## Task 9: Backend Tests — Pipeline Endpoints + Price Service

**Files:**

- Create: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write `test_pipeline.py`**

```python
# backend/tests/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_list_pipeline_jobs_empty(auth_client):
    response = await auth_client.get("/api/v1/pipeline/jobs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_pipeline_job_not_found(auth_client):
    response = await auth_client.get(
        "/api/v1/pipeline/jobs/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_job_enqueues(auth_client):
    with patch("app.api.pipeline.create_pool") as mock_pool:
        mock_redis = AsyncMock()
        mock_pool.return_value = mock_redis
        mock_job = AsyncMock()
        mock_job.job_id = "test-job-id"
        mock_redis.enqueue_job.return_value = mock_job

        response = await auth_client.post("/api/v1/pipeline/trigger/price_fetch_us")
        assert response.status_code == 202
        data = response.json()
        assert data["enqueued"] is True
        mock_redis.enqueue_job.assert_called_once_with("job_fetch_prices_us")


@pytest.mark.asyncio
async def test_pipeline_log_created_and_finished(auth_client):
    """Integration: create a log then list it."""
    from httpx import AsyncClient
    # Create a log by calling create_log directly via the DB session in auth_client
    # We verify via the list endpoint after inserting through service
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.services.pipeline import create_log, finish_log

    engine = create_async_engine(
        "postgresql+asyncpg://postgres:zentri-password-paotharit@localhost:5432/zentri_test",
        poolclass=NullPool,
    )
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        log = await create_log(db, "price_fetch_us")
        assert log.status == "running"
        finished = await finish_log(db, log, success=True)
        assert finished.status == "done"
        assert finished.finished_at is not None

    response = await auth_client.get("/api/v1/pipeline/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert any(j["job_type"] == "price_fetch_us" for j in jobs)
    await engine.dispose()
```

- [ ] **Step 2: Run the tests**

```bash
cd backend
python -m pytest tests/test_pipeline.py -v
```

Expected: all tests PASS

---

## Task 10: Frontend — Pipeline Service + Monitor Page

**Files:**

- Create: `frontend/lib/services/pipeline.ts`
- Create: `frontend/app/(auth)/pipeline/page.tsx`
- Create: `frontend/components/pipeline/JobsTable.tsx`
- Modify: `frontend/components/layout/Sidebar.tsx`

- [ ] **Step 1: Check `lib/api.ts`** to understand the base fetch client, then write `lib/services/pipeline.ts`

```typescript
// frontend/lib/services/pipeline.ts
import { apiClient } from "@/lib/api";

export type JobType =
  | "price_fetch_us"
  | "price_fetch_crypto"
  | "price_fetch_gold"
  | "price_fetch_benchmark";

export type JobStatus = "queued" | "running" | "done" | "failed";

export interface PipelineJob {
  id: string;
  job_type: JobType;
  status: JobStatus;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}

export async function fetchJobs(limit = 50): Promise<PipelineJob[]> {
  return apiClient(`/pipeline/jobs?limit=${limit}`);
}

export async function triggerJob(
  job_type: JobType,
): Promise<{ enqueued: boolean; job_id: string | null }> {
  return apiClient(`/pipeline/trigger/${job_type}`, { method: "POST" });
}
```

- [ ] **Step 2: Write `components/pipeline/JobsTable.tsx`**

```tsx
// frontend/components/pipeline/JobsTable.tsx
"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type PipelineJob,
  type JobType,
  triggerJob,
} from "@/lib/services/pipeline";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  done: "default",
  running: "secondary",
  queued: "outline",
  failed: "destructive",
};

const JOB_LABELS: Record<JobType, string> = {
  price_fetch_us: "US Stocks",
  price_fetch_crypto: "Crypto",
  price_fetch_gold: "Gold",
  price_fetch_benchmark: "Benchmarks",
};

const ALL_JOB_TYPES: JobType[] = [
  "price_fetch_us",
  "price_fetch_crypto",
  "price_fetch_gold",
  "price_fetch_benchmark",
];

interface JobsTableProps {
  jobs: PipelineJob[];
}

export function JobsTable({ jobs }: JobsTableProps) {
  async function handleTrigger(jobType: JobType) {
    try {
      await triggerJob(jobType);
      toast.success(`${JOB_LABELS[jobType]} job enqueued`);
    } catch {
      toast.error(`Failed to trigger ${JOB_LABELS[jobType]} job`);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Pipeline Jobs</CardTitle>
        <div className="flex gap-2 flex-wrap">
          {ALL_JOB_TYPES.map((jt) => (
            <Button
              key={jt}
              size="sm"
              variant="outline"
              onClick={() => handleTrigger(jt)}
            >
              Run {JOB_LABELS[jt]}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-muted-foreground">
              <th className="text-left py-2 pr-4">Job</th>
              <th className="text-left py-2 pr-4">Status</th>
              <th className="text-left py-2 pr-4">Started</th>
              <th className="text-left py-2">Duration</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  className="py-8 text-center text-muted-foreground"
                >
                  No jobs have run yet. Use the buttons above to trigger a
                  fetch.
                </td>
              </tr>
            )}
            {jobs.map((job) => {
              const duration =
                job.finished_at && job.started_at
                  ? `${((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000).toFixed(1)}s`
                  : job.status === "running"
                    ? "running…"
                    : "—";
              return (
                <tr key={job.id} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-medium">
                    {JOB_LABELS[job.job_type as JobType] ?? job.job_type}
                  </td>
                  <td className="py-2 pr-4">
                    <Badge variant={STATUS_VARIANT[job.status] ?? "outline"}>
                      {job.status}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4 text-muted-foreground">
                    {formatDistanceToNow(new Date(job.started_at), {
                      addSuffix: true,
                    })}
                  </td>
                  <td className="py-2 text-muted-foreground">{duration}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {jobs.some((j) => j.status === "failed") && (
          <div className="mt-4 space-y-2">
            {jobs
              .filter((j) => j.status === "failed" && j.error_message)
              .map((j) => (
                <p
                  key={j.id}
                  className="text-xs text-destructive font-mono bg-destructive/10 p-2 rounded"
                >
                  [{JOB_LABELS[j.job_type as JobType]}] {j.error_message}
                </p>
              ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Write `app/(auth)/pipeline/page.tsx`**

```tsx
// frontend/app/(auth)/pipeline/page.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchJobs, type PipelineJob } from "@/lib/services/pipeline";
import { JobsTable } from "@/components/pipeline/JobsTable";

export default function PipelinePage() {
  const { data: initialJobs = [], isLoading } = useQuery({
    queryKey: ["pipeline-jobs"],
    queryFn: () => fetchJobs(50),
  });

  const [jobs, setJobs] = useState<PipelineJob[]>([]);

  // Seed from initial query
  useEffect(() => {
    if (initialJobs.length > 0) setJobs(initialJobs);
  }, [initialJobs]);

  // SSE live updates
  const sseRef = useRef<EventSource | null>(null);
  useEffect(() => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";
    const token = document.cookie
      .split("; ")
      .find((c) => c.startsWith("access_token="))
      ?.split("=")[1];

    // SSE with auth — use EventSource via URL with token as query param
    // (backend must accept ?token= or use cookies — adjust if needed)
    const url = `${API_BASE}/pipeline/stream`;
    const es = new EventSource(url, { withCredentials: true });
    sseRef.current = es;

    es.onmessage = (e) => {
      try {
        const updated: PipelineJob[] = JSON.parse(e.data);
        setJobs(updated);
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      // EventSource auto-reconnects — no action needed
    };

    return () => {
      es.close();
    };
  }, []);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-bold">Pipeline Monitor</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Pipeline Monitor</h1>
        <p className="text-muted-foreground text-sm">
          Live price fetch job status. Updates every 3 seconds via SSE.
        </p>
      </div>
      <JobsTable jobs={jobs} />
    </div>
  );
}
```

- [ ] **Step 4: Update `Sidebar.tsx`** — read the file first, then add a Pipeline link following the same pattern as existing nav items

Find the existing nav items (Portfolio, Settings) in `frontend/components/layout/Sidebar.tsx` and add:

```tsx
{ href: "/pipeline", label: "Pipeline", icon: <ActivityIcon className="w-4 h-4" /> }
```

Add `import { Activity as ActivityIcon } from "lucide-react"` alongside existing lucide imports.

- [ ] **Step 5: Test the pipeline page loads in the browser**

```bash
cd frontend && npm run dev
```

Navigate to `http://localhost:3000/pipeline` — verify:

- Page loads without errors
- "No jobs have run yet" message shows if DB is empty
- "Run US Stocks" button triggers a job (check network tab for 202 response)

---

## Self-Review

### Spec Coverage

| Kanban Item                                    | Task                                             |
| ---------------------------------------------- | ------------------------------------------------ |
| ARQ price fetch job for US stocks via yfinance | Task 4 + Task 5                                  |
| ARQ price fetch job for crypto via CoinGecko   | Task 4 + Task 5                                  |
| ARQ price fetch job for gold spot price        | Task 4 + Task 5                                  |
| pipeline logs table and job tracking           | Task 1 + Task 2 + Task 3                         |
| pipeline jobs list and SSE stream endpoints    | Task 7                                           |
| pipeline monitor page with live SSE feed       | Task 10                                          |
| benchmark price feed for S&P500 and SET        | Task 4 + Task 2 (migration seeds ^GSPC, ^SET.BK) |

All 7 Kanban items are covered. ✓

### Type Consistency Check

- `PipelineLog.job_type` uses `JOB_TYPES` tuple in model → matches `job_type_enum` in migration → matches `JobType` Literal in schema
- `PipelineLogResponse` uses `JobType` and `JobStatus` Literals — same values as model enums ✓
- `create_log(db, "price_fetch_us")` — string matches `JOB_TYPES` tuple ✓
- `job_fn_map` in trigger endpoint: keys match `JobType` Literal values ✓
- Worker `session_factory` set in `startup()`, read in each job via `ctx["session_factory"]` ✓
- `BenchmarkPrice.benchmark_id` → FK `benchmarks.id` ✓

### No Placeholders Check ✓

All steps contain actual code. No TBDs or "implement later".

---

## SSE Auth Note

The SSE endpoint at `/pipeline/stream` uses `Depends(get_current_user)` which reads the `Authorization` header. Browser `EventSource` does not support custom headers. Two options:

1. **Cookie auth**: If your JWT is stored in an HTTP-only cookie, `withCredentials: true` on `EventSource` will send it automatically. Update `get_current_user` to also accept the cookie.
2. **Token as query param**: Pass `?token=<jwt>` in the EventSource URL and update `get_current_user` to accept `token: str | None = Query(None)`.

The simplest fix for Phase 4: store the JWT in a cookie during login (your login page likely already does this — check `app/login/page.tsx`). If not, the frontend `pipeline/page.tsx` step notes the approach.
