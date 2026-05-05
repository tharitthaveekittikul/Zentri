# Net Worth Daily Snapshot Worker + Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize daily net worth snapshots into a `net_worth_snapshots` table and display them as an absolute USD timeline chart on the overview page.

**Architecture:** An ARQ cron job runs daily at 01:00 UTC, computing each user's total investment value in USD from current holdings × historical prices, writing one row per `(user_id, date)`. On first run it backfills from the earliest available price. A new `GET /overview/net-worth` endpoint queries this table. A `NetWorthChart` component is inserted above the allocation section on the overview page.

**Tech Stack:** Python 3.13, SQLAlchemy async, FastAPI, ARQ + Redis, Alembic, Next.js 15, React, lightweight-charts

---

## File Map

| Action | File |
|---|---|
| CREATE | `backend/app/models/net_worth_snapshot.py` |
| MODIFY | `backend/app/models/__init__.py` |
| CREATE | `backend/alembic/versions/010_net_worth_snapshot.py` |
| CREATE | `backend/app/services/net_worth_snapshot.py` |
| CREATE | `backend/tests/test_net_worth_snapshot.py` |
| CREATE | `backend/worker/jobs/net_worth_snapshot.py` |
| MODIFY | `backend/worker/main.py` |
| MODIFY | `backend/app/schemas/overview.py` |
| MODIFY | `backend/app/services/overview.py` |
| MODIFY | `backend/app/api/overview.py` |
| MODIFY | `frontend/lib/services/overview.ts` |
| CREATE | `frontend/components/net-worth-chart.tsx` |
| MODIFY | `frontend/app/(auth)/page.tsx` |

---

## Task 1: DB Model + Migration

**Files:**
- Create: `backend/app/models/net_worth_snapshot.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/010_net_worth_snapshot.py`

- [ ] **Step 1: Create the SQLAlchemy model**

Create `backend/app/models/net_worth_snapshot.py`:

```python
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NetWorthSnapshot(Base):
    __tablename__ = "net_worth_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "snapshot_date", name="uq_net_worth_snapshots_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    total_cost_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Register the model in `__init__.py`**

In `backend/app/models/__init__.py`, add one import line and one entry to `__all__`:

```python
from app.models.net_worth_snapshot import NetWorthSnapshot  # noqa: F401
```

And add `"NetWorthSnapshot"` to the `__all__` list.

- [ ] **Step 3: Create the Alembic migration**

Create `backend/alembic/versions/010_net_worth_snapshot.py`:

```python
"""add net worth snapshots table

Revision ID: 010
Revises: 009
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "net_worth_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_value_usd", sa.Numeric(20, 8), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(20, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_net_worth_snapshots_user_date", "net_worth_snapshots", ["user_id", "snapshot_date"])
    op.create_unique_constraint("uq_net_worth_snapshots_user_date", "net_worth_snapshots", ["user_id", "snapshot_date"])


def downgrade() -> None:
    op.drop_constraint("uq_net_worth_snapshots_user_date", "net_worth_snapshots", type_="unique")
    op.drop_index("ix_net_worth_snapshots_user_date", "net_worth_snapshots")
    op.drop_table("net_worth_snapshots")
```

- [ ] **Step 4: Run the migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected output ends with: `Running upgrade 009 -> 010, add net worth snapshots table`

---

## Task 2: Snapshot Service (TDD)

**Files:**
- Create: `backend/tests/test_net_worth_snapshot.py`
- Create: `backend/app/services/net_worth_snapshot.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_net_worth_snapshot.py`:

```python
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from app.services.net_worth_snapshot import compute_snapshot


def _holding(asset_id_hex: str, quantity: str, avg_cost: str):
    h = MagicMock()
    h.asset_id = uuid.UUID(asset_id_hex)
    h.quantity = Decimal(quantity)
    h.avg_cost_price = Decimal(avg_cost)
    return h


AID1 = "aaaaaaaa-0000-0000-0000-000000000001"
AID2 = "aaaaaaaa-0000-0000-0000-000000000002"


def test_compute_snapshot_sums_value_and_cost():
    holdings = [_holding(AID1, "10", "100"), _holding(AID2, "2", "50")]
    price_map = {uuid.UUID(AID1): Decimal("120"), uuid.UUID(AID2): Decimal("60")}
    result = compute_snapshot(holdings, price_map)
    assert result["total_value_usd"] == Decimal("1320")  # 10*120 + 2*60
    assert result["total_cost_usd"] == Decimal("1100")   # 10*100 + 2*50


def test_compute_snapshot_skips_holdings_without_price():
    holdings = [_holding(AID1, "10", "100"), _holding(AID2, "2", "50")]
    price_map = {uuid.UUID(AID1): Decimal("120")}  # AID2 has no price
    result = compute_snapshot(holdings, price_map)
    assert result["total_value_usd"] == Decimal("1200")
    assert result["total_cost_usd"] == Decimal("1000")


def test_compute_snapshot_returns_none_when_no_prices():
    holdings = [_holding(AID1, "10", "100")]
    result = compute_snapshot(holdings, {})
    assert result is None


def test_compute_snapshot_returns_none_for_empty_holdings():
    result = compute_snapshot([], {})
    assert result is None
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
docker compose exec backend python -m pytest tests/test_net_worth_snapshot.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `compute_snapshot` does not exist yet.

- [ ] **Step 3: Implement the service**

Create `backend/app/services/net_worth_snapshot.py`:

```python
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.holding import Holding
from app.models.net_worth_snapshot import NetWorthSnapshot
from app.models.price import Price

logger = get_logger(__name__)


def compute_snapshot(
    holdings: list, price_map: dict[uuid.UUID, Decimal]
) -> dict | None:
    total_value = Decimal("0")
    total_cost = Decimal("0")
    any_priced = False

    for h in holdings:
        price = price_map.get(h.asset_id)
        if price is None:
            continue
        total_value += h.quantity * price
        total_cost += h.quantity * h.avg_cost_price
        any_priced = True

    if not any_priced:
        return None
    return {"total_value_usd": total_value, "total_cost_usd": total_cost}


async def _get_price_on_date(
    db: AsyncSession, asset_id: uuid.UUID, target_date: date
) -> Decimal | None:
    cutoff = datetime(
        target_date.year, target_date.month, target_date.day,
        23, 59, 59, tzinfo=timezone.utc
    )
    result = await db.execute(
        select(Price.close)
        .where(Price.asset_id == asset_id, Price.timestamp <= cutoff)
        .order_by(Price.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def take_snapshot(
    db: AsyncSession, user_id: uuid.UUID, snapshot_date: date
) -> NetWorthSnapshot | None:
    holdings = list(
        (await db.execute(select(Holding).where(Holding.user_id == user_id))).scalars().all()
    )
    if not holdings:
        return None

    price_map: dict[uuid.UUID, Decimal] = {}
    for h in holdings:
        price = await _get_price_on_date(db, h.asset_id, snapshot_date)
        if price is not None:
            price_map[h.asset_id] = price

    computed = compute_snapshot(holdings, price_map)
    if computed is None:
        logger.info("snapshot skipped user=%s date=%s (no prices)", user_id, snapshot_date)
        return None

    snapshot = NetWorthSnapshot(
        user_id=user_id,
        snapshot_date=snapshot_date,
        total_value_usd=computed["total_value_usd"],
        total_cost_usd=computed["total_cost_usd"],
    )
    db.add(snapshot)
    try:
        await db.commit()
        await db.refresh(snapshot)
        logger.info("snapshot saved user=%s date=%s value=%s", user_id, snapshot_date, computed["total_value_usd"])
        return snapshot
    except IntegrityError:
        await db.rollback()
        logger.debug("snapshot already exists user=%s date=%s (skipped)", user_id, snapshot_date)
        return None


async def backfill_snapshots(db: AsyncSession, user_id: uuid.UUID) -> int:
    earliest_result = await db.execute(
        select(func.min(Price.timestamp))
        .join(Holding, Price.asset_id == Holding.asset_id)
        .where(Holding.user_id == user_id)
    )
    earliest_ts = earliest_result.scalar_one_or_none()
    if earliest_ts is None:
        return 0

    earliest_date = earliest_ts.date()
    yesterday = date.today() - timedelta(days=1)

    existing_result = await db.execute(
        select(NetWorthSnapshot.snapshot_date).where(NetWorthSnapshot.user_id == user_id)
    )
    existing_dates = {row[0] for row in existing_result.all()}

    count = 0
    current = earliest_date
    while current <= yesterday:
        if current not in existing_dates:
            snap = await take_snapshot(db, user_id, current)
            if snap is not None:
                count += 1
        current += timedelta(days=1)

    logger.info("backfill complete user=%s snapshots=%d", user_id, count)
    return count
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
docker compose exec backend python -m pytest tests/test_net_worth_snapshot.py -v
```

Expected:
```
PASSED tests/test_net_worth_snapshot.py::test_compute_snapshot_sums_value_and_cost
PASSED tests/test_net_worth_snapshot.py::test_compute_snapshot_skips_holdings_without_price
PASSED tests/test_net_worth_snapshot.py::test_compute_snapshot_returns_none_when_no_prices
PASSED tests/test_net_worth_snapshot.py::test_compute_snapshot_returns_none_for_empty_holdings
4 passed
```

---

## Task 3: Worker Job + Registration

**Files:**
- Create: `backend/worker/jobs/net_worth_snapshot.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Create the worker job**

Create `backend/worker/jobs/net_worth_snapshot.py`:

```python
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.net_worth_snapshot import NetWorthSnapshot
from app.models.user import User
from app.services.net_worth_snapshot import backfill_snapshots, take_snapshot
from app.services.pipeline import create_log, finish_log

logger = get_logger(__name__)


async def job_snapshot_net_worth(ctx: dict) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "snapshot_net_worth")
        try:
            users = list((await db.execute(select(User))).scalars().all())
            total_written = 0

            for user in users:
                has_any = (await db.execute(
                    select(NetWorthSnapshot).where(NetWorthSnapshot.user_id == user.id).limit(1)
                )).scalar_one_or_none()

                if has_any is None:
                    written = await backfill_snapshots(db, user.id)
                    total_written += written
                else:
                    yesterday = date.today() - timedelta(days=1)
                    snap = await take_snapshot(db, user.id, yesterday)
                    if snap is not None:
                        total_written += 1

            await finish_log(db, log, success=True)
            logger.info("snapshot_net_worth done users=%d snapshots_written=%d", len(users), total_written)
            return {"users": len(users), "snapshots_written": total_written}
        except Exception as e:
            logger.exception("job_snapshot_net_worth failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 2: Register in `worker/main.py`**

Add the import at the top of `backend/worker/main.py` alongside the other job imports:

```python
from worker.jobs.net_worth_snapshot import job_snapshot_net_worth
```

Add `job_snapshot_net_worth` to `functions`:

```python
functions = [
    job_fetch_prices_us,
    job_fetch_prices_crypto,
    job_fetch_price_gold,
    job_fetch_benchmark_prices,
    job_ingest_document,
    job_run_analysis,
    job_snapshot_net_worth,  # add this
]
```

Add to `cron_jobs`:

```python
cron_jobs = [
    cron(job_fetch_prices_us, minute={0, 15, 30, 45}),
    cron(job_fetch_prices_crypto, minute={0, 15, 30, 45}),
    cron(job_fetch_price_gold, minute={0, 15, 30, 45}),
    cron(job_fetch_benchmark_prices, minute=0),
    cron(job_snapshot_net_worth, hour=1, minute=0),  # add this — daily at 01:00 UTC
]
```

- [ ] **Step 3: Verify worker starts without errors**

```bash
docker compose restart worker
docker compose logs worker --tail=20
```

Expected: `ARQ worker started — DB pool ready` with no import errors.

---

## Task 4: API Schema + Endpoint

**Files:**
- Modify: `backend/app/schemas/overview.py`
- Modify: `backend/app/services/overview.py`
- Modify: `backend/app/api/overview.py`

- [ ] **Step 1: Add `NetWorthPoint` schema**

In `backend/app/schemas/overview.py`, append:

```python
class NetWorthPoint(BaseModel):
    date: date
    value_usd: Decimal
    cost_usd: Decimal
```

- [ ] **Step 2: Add `get_net_worth_timeline` to the overview service**

In `backend/app/services/overview.py`, add these imports at the top if not already present:

```python
from datetime import timedelta
from app.models.net_worth_snapshot import NetWorthSnapshot
```

Then append this function at the bottom of the file:

```python
def _net_worth_range_start(range_: str) -> "date | None":
    from datetime import date as date_type
    today = date_type.today()
    ranges = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}
    days = ranges.get(range_)
    if days is None:
        return None
    return today - timedelta(days=days)


async def get_net_worth_timeline(
    db: AsyncSession, user_id: uuid.UUID, range_: str
) -> list[dict]:
    stmt = select(NetWorthSnapshot).where(NetWorthSnapshot.user_id == user_id)
    start = _net_worth_range_start(range_)
    if start is not None:
        stmt = stmt.where(NetWorthSnapshot.snapshot_date >= start)
    stmt = stmt.order_by(NetWorthSnapshot.snapshot_date.asc())

    rows = list((await db.execute(stmt)).scalars().all())
    logger.info("net_worth_timeline user=%s range=%s points=%d", user_id, range_, len(rows))
    return [
        {"date": r.snapshot_date, "value_usd": r.total_value_usd, "cost_usd": r.total_cost_usd}
        for r in rows
    ]
```

- [ ] **Step 3: Add the endpoint**

In `backend/app/api/overview.py`, add `NetWorthPoint` to the schema import:

```python
from app.schemas.overview import AllocationItem, NetWorthPoint, OverviewSummary, PerformanceResponse
```

Then append the endpoint to the router:

```python
@router.get("/net-worth", response_model=list[NetWorthPoint])
async def get_net_worth_timeline(
    range: str = "1M",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_net_worth_timeline(db, current_user.id, range)
```

- [ ] **Step 4: Verify endpoint responds**

```bash
docker compose restart backend
```

Then hit the endpoint (replace TOKEN with a real access token from your browser's localStorage):

```bash
curl -s -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/v1/overview/net-worth?range=1M" | head -c 200
```

Expected: `[]` (empty, since no snapshots yet) or a JSON array of points. No 500 error.

---

## Task 5: Trigger a Manual Backfill (Smoke Test)

Before building the frontend, verify the worker job actually produces data.

- [ ] **Step 1: Trigger the job manually via ARQ**

```bash
docker compose exec worker python -c "
import asyncio
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings

async def run():
    pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await pool.enqueue_job('job_snapshot_net_worth')
    print('Job enqueued')

asyncio.run(run())
"
```

- [ ] **Step 2: Watch worker logs**

```bash
docker compose logs worker -f --tail=30
```

Expected log lines:
```
pipeline job started job_type=snapshot_net_worth
backfill complete user=<uuid> snapshots=<N>
snapshot_net_worth done users=1 snapshots_written=<N>
pipeline job finished job_type=snapshot_net_worth status=done
```

- [ ] **Step 3: Verify data in DB**

```bash
docker compose exec db psql -U zentri -d zentri -c \
  "SELECT snapshot_date, total_value_usd, total_cost_usd FROM net_worth_snapshots ORDER BY snapshot_date DESC LIMIT 5;"
```

Expected: rows with dates and non-zero USD values.

- [ ] **Step 4: Re-test the API endpoint**

```bash
curl -s -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/v1/overview/net-worth?range=ALL" | python3 -m json.tool | head -30
```

Expected: array of `{"date": "...", "value_usd": "...", "cost_usd": "..."}` objects.

---

## Task 6: Frontend Service Function

**Files:**
- Modify: `frontend/lib/services/overview.ts`

- [ ] **Step 1: Add the type and fetch function**

In `frontend/lib/services/overview.ts`, append:

```typescript
export interface NetWorthPoint {
  date: string;
  value_usd: string;
  cost_usd: string;
}

export async function fetchNetWorthTimeline(range: string): Promise<NetWorthPoint[]> {
  const res = await api.get(`/api/v1/overview/net-worth?range=${range}`);
  if (!res.ok) throw new Error("Failed to fetch net worth timeline");
  return res.json();
}
```

---

## Task 7: NetWorthChart Component

**Files:**
- Create: `frontend/components/net-worth-chart.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/components/net-worth-chart.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { fetchNetWorthTimeline, type NetWorthPoint } from "@/lib/services/overview";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const RANGES = ["1M", "3M", "6M", "1Y", "ALL"] as const;
type Range = (typeof RANGES)[number];

export function NetWorthChart({ privacyMode }: { privacyMode: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const valueSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const costSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [range, setRange] = useState<Range>("1M");
  const [data, setData] = useState<NetWorthPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 280,
      layout: { background: { color: "transparent" }, textColor: "#9ca3af" },
      grid: { vertLines: { color: "#1f2937" }, horzLines: { color: "#1f2937" } },
      rightPriceScale: { borderColor: "#374151" },
      timeScale: { borderColor: "#374151", timeVisible: false },
    });

    valueSeriesRef.current = chart.addAreaSeries({
      lineColor: "#6366f1",
      topColor: "rgba(99,102,241,0.25)",
      bottomColor: "rgba(99,102,241,0)",
      lineWidth: 2,
    });
    costSeriesRef.current = chart.addLineSeries({
      color: "#6b7280",
      lineWidth: 1,
      lineStyle: 1,
    });
    chartRef.current = chart;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchNetWorthTimeline(range)
      .then((points) => {
        setData(points);
        if (!valueSeriesRef.current || !costSeriesRef.current) return;
        const valueData = points.map((p) => ({
          time: p.date as UTCTimestamp,
          value: parseFloat(p.value_usd),
        }));
        const costData = points.map((p) => ({
          time: p.date as UTCTimestamp,
          value: parseFloat(p.cost_usd),
        }));
        valueSeriesRef.current.setData(valueData);
        costSeriesRef.current.setData(costData);
        chartRef.current?.timeScale().fitContent();
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [range]);

  const latest = data[data.length - 1];
  const currentValue = latest ? parseFloat(latest.value_usd) : 0;
  const currentCost = latest ? parseFloat(latest.cost_usd) : 0;
  const pnl = currentValue - currentCost;
  const pnlPct = currentCost > 0 ? (pnl / currentCost) * 100 : 0;

  const fmt = (v: number) =>
    privacyMode
      ? "***"
      : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const fmtPnl = () => {
    if (privacyMode) return "***";
    const sign = pnl >= 0 ? "+" : "";
    return `${sign}${fmt(pnl)} (${pnl >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%)`;
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">Net Worth</CardTitle>
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  range === r
                    ? "bg-indigo-600 text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-6 mt-2">
          <div>
            <p className="text-xs text-muted-foreground">Current Value</p>
            <p className="text-lg font-semibold tabular-nums">{fmt(currentValue)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Total Cost</p>
            <p className="text-lg font-semibold tabular-nums">{fmt(currentCost)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Unrealized PnL</p>
            <p
              className={`text-lg font-semibold tabular-nums ${
                pnl >= 0 ? "text-green-500" : "text-red-500"
              }`}
            >
              {fmtPnl()}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {loading && (
          <div className="h-[280px] flex items-center justify-center text-muted-foreground text-sm">
            Loading...
          </div>
        )}
        <div ref={containerRef} className={loading ? "hidden" : "w-full"} />
      </CardContent>
    </Card>
  );
}
```

---

## Task 8: Wire into Overview Page

**Files:**
- Modify: `frontend/app/(auth)/page.tsx`

- [ ] **Step 1: Read the current page**

Read `frontend/app/(auth)/page.tsx` to find the exact location of the summary cards and allocation section before making edits.

- [ ] **Step 2: Add the import**

At the top of `frontend/app/(auth)/page.tsx`, add:

```tsx
import { NetWorthChart } from "@/components/net-worth-chart";
```

- [ ] **Step 3: Insert the component**

Find the JSX section where summary cards end and the allocation section begins. Insert `<NetWorthChart>` between them:

```tsx
{/* existing summary cards section */}
<NetWorthChart privacyMode={privacyMode} />
{/* existing allocation section */}
```

Note: `privacyMode` is the existing boolean state already managed by the page. If the prop name differs in the file, match it to whatever the page uses.

- [ ] **Step 4: Verify the page loads**

Open the browser at `http://localhost:3000`. The overview page should show:
- Summary cards (unchanged)
- **Net Worth chart with range selector** (new)
- Allocation pie (unchanged)
- Performance chart (unchanged)

Verify:
- Range buttons switch data correctly
- Privacy mode toggle masks values with `***`
- Chart renders without console errors
- Empty state (Loading...) shows briefly then resolves

---

## Self-Review Checklist

- [x] **Spec coverage:** Model ✓ Migration ✓ Service (`take_snapshot`, `backfill_snapshots`, `compute_snapshot`) ✓ Worker job ✓ Registration ✓ Schema ✓ Endpoint ✓ Frontend service ✓ Component ✓ Page integration ✓
- [x] **Placeholders:** None — every step has complete code
- [x] **Type consistency:** `NetWorthSnapshot` used consistently; `NetWorthPoint` in schema matches frontend `NetWorthPoint` interface; `total_value_usd`/`total_cost_usd` in model maps to `value_usd`/`cost_usd` in API response (aliased in the service return dict)
- [x] **Migration chain:** 010 revises 009 ✓
- [x] **Import chain:** model registered in `__init__.py` ✓; worker job imported in `main.py` ✓; schema imported in API ✓
