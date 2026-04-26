# Phase 5 — Market Overview & Asset Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the market overview dashboard, asset detail page, PrivacyValue component, and ⌘K command palette so all price/portfolio data collected in Phases 1–4 becomes visible and navigable.

**Architecture:** Feature-by-feature (Option B) — each task ships backend + frontend end-to-end before moving to the next. Backend follows FastAPI router → service → schema pattern. Frontend follows lib/services → Zustand/TanStack Query → page/component pattern.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest-asyncio (backend); Next.js 15 App Router, TanStack Query, Zustand, lightweight-charts, recharts, shadcn/ui (frontend)

---

## File Map

**Create (backend):**

- `backend/app/schemas/overview.py` — Pydantic response schemas for overview endpoints
- `backend/app/services/overview.py` — summary, allocation, performance query logic
- `backend/app/api/overview.py` — FastAPI router for /overview endpoints
- `backend/tests/test_overview.py` — overview endpoint tests

**Modify (backend):**

- `backend/app/api/assets.py` — add `GET /assets/symbol/{symbol}/history?range=` endpoint
- `backend/app/main.py` — register overview router
- `backend/tests/test_assets.py` — add symbol history tests

**Create (frontend):**

- `frontend/lib/services/overview.ts` — fetch functions for overview + asset history
- `frontend/components/ui/PrivacyValue.tsx` — monetary value masking component
- `frontend/components/overview/SummaryBar.tsx` — portfolio total, cost, P&L, daily change
- `frontend/components/overview/PerformanceChart.tsx` — portfolio vs benchmark line chart
- `frontend/components/overview/AllocationDonut.tsx` — asset type donut chart
- `frontend/components/overview/HoldingsSnapshot.tsx` — top holdings table
- `frontend/components/portfolio/PriceChart.tsx` — lightweight-charts candlestick
- `frontend/app/(auth)/portfolio/[symbol]/page.tsx` — asset detail page
- `frontend/store/palette.ts` — Zustand store for command palette state + assets cache
- `frontend/components/layout/CommandPalette.tsx` — ⌘K command palette component

**Modify (frontend):**

- `frontend/app/(auth)/page.tsx` — replace stub with market overview page
- `frontend/components/layout/TopNav.tsx` — add search icon button for palette
- `frontend/app/(auth)/layout.tsx` — mount CommandPalette + ⌘K keydown listener
- `frontend/components/portfolio/HoldingsTable.tsx` — wrap price values in PrivacyValue

---

## Task 1: Overview Backend — Schemas, Service, Router, Tests

**Files:**

- Create: `backend/app/schemas/overview.py`
- Create: `backend/app/services/overview.py`
- Create: `backend/app/api/overview.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_overview.py`

- [ ] **Step 1: Write failing tests for overview endpoints**

```python
# backend/tests/test_overview.py
import pytest


@pytest.fixture
async def asset_with_holding(auth_client):
    asset_res = await auth_client.post("/api/v1/assets", json={
        "symbol": "AAPL", "asset_type": "us_stock", "name": "Apple", "currency": "USD"
    })
    asset_id = asset_res.json()["id"]
    await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD"
    })
    return asset_id


@pytest.mark.asyncio
async def test_summary_empty_portfolio(auth_client):
    res = await auth_client.get("/api/v1/overview/summary")
    assert res.status_code == 200
    data = res.json()
    assert float(data["total_value"]) == 0.0
    assert float(data["total_cost"]) == 0.0
    assert float(data["total_pnl"]) == 0.0


@pytest.mark.asyncio
async def test_summary_with_holding_no_prices(auth_client, asset_with_holding):
    res = await auth_client.get("/api/v1/overview/summary")
    assert res.status_code == 200
    data = res.json()
    # No prices in DB yet → total_value = 0, total_cost = quantity * avg_cost
    assert float(data["total_cost"]) == 1500.0
    assert float(data["total_value"]) == 0.0


@pytest.mark.asyncio
async def test_allocation_empty(auth_client):
    res = await auth_client.get("/api/v1/overview/allocation")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_allocation_with_holding_no_prices(auth_client, asset_with_holding):
    res = await auth_client.get("/api/v1/overview/allocation")
    assert res.status_code == 200
    # No prices → nothing to allocate
    assert res.json() == []


@pytest.mark.asyncio
async def test_performance_returns_structure(auth_client):
    res = await auth_client.get("/api/v1/overview/performance?range=1M")
    assert res.status_code == 200
    data = res.json()
    assert "portfolio" in data
    assert "benchmark" in data
    assert isinstance(data["portfolio"], list)
    assert isinstance(data["benchmark"], list)


@pytest.mark.asyncio
async def test_performance_invalid_range_defaults(auth_client):
    res = await auth_client.get("/api/v1/overview/performance?range=INVALID")
    assert res.status_code == 200
    data = res.json()
    assert "portfolio" in data
```

- [ ] **Step 2: Run tests — verify they fail with 404**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri
docker compose exec backend pytest tests/test_overview.py -v 2>&1 | head -40
```

Expected: FAIL — `404 Not Found` because the router doesn't exist yet.

- [ ] **Step 3: Create overview schemas**

```python
# backend/app/schemas/overview.py
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class OverviewSummary(BaseModel):
    total_value: Decimal
    total_cost: Decimal
    total_pnl: Decimal
    total_pnl_pct: Decimal
    daily_change: Decimal
    daily_change_pct: Decimal


class AllocationItem(BaseModel):
    asset_type: str
    value: Decimal
    pct: Decimal


class PerformancePoint(BaseModel):
    date: date
    value: Decimal


class PerformanceResponse(BaseModel):
    portfolio: list[PerformancePoint]
    benchmark: list[PerformancePoint]
```

- [ ] **Step 4: Create overview service**

```python
# backend/app/services/overview.py
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.price import Price

logger = get_logger(__name__)


def _range_start(range_: str) -> datetime:
    days = {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}
    return datetime.now(timezone.utc) - timedelta(days=days.get(range_, 30))


async def _latest_price(db: AsyncSession, asset_id: uuid.UUID) -> Price | None:
    result = await db.execute(
        select(Price)
        .where(Price.asset_id == asset_id)
        .order_by(Price.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _prev_day_price(db: AsyncSession, asset_id: uuid.UUID) -> Price | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=20)
    result = await db.execute(
        select(Price)
        .where(Price.asset_id == asset_id, Price.timestamp < cutoff)
        .order_by(Price.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    zero = Decimal("0")
    if not holdings:
        return dict(total_value=zero, total_cost=zero, total_pnl=zero,
                    total_pnl_pct=zero, daily_change=zero, daily_change_pct=zero)

    total_cost = sum(h.quantity * h.avg_cost_price for h in holdings)
    total_value = zero
    yesterday_value = zero

    for h in holdings:
        latest = await _latest_price(db, h.asset_id)
        if latest:
            total_value += h.quantity * latest.close
        prev = await _prev_day_price(db, h.asset_id)
        if prev:
            yesterday_value += h.quantity * prev.close

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else zero
    daily_change = total_value - yesterday_value
    daily_change_pct = (daily_change / yesterday_value * 100) if yesterday_value else zero

    logger.info("Summary: user=%s total_value=%s total_cost=%s", user_id, total_value, total_cost)
    return dict(total_value=total_value, total_cost=total_cost, total_pnl=total_pnl,
                total_pnl_pct=total_pnl_pct, daily_change=daily_change, daily_change_pct=daily_change_pct)


async def get_allocation(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    by_type: dict[str, Decimal] = {}
    for h in holdings:
        latest = await _latest_price(db, h.asset_id)
        if not latest:
            continue
        asset = (await db.execute(
            select(Asset).where(Asset.id == h.asset_id)
        )).scalar_one_or_none()
        if not asset:
            continue
        asset_type = asset.asset_type
        by_type[asset_type] = by_type.get(asset_type, Decimal("0")) + h.quantity * latest.close

    total = sum(by_type.values()) or Decimal("1")
    logger.info("Allocation: user=%s types=%s", user_id, list(by_type.keys()))
    return [{"asset_type": k, "value": v, "pct": v / total * 100} for k, v in by_type.items()]


async def get_performance(db: AsyncSession, user_id: uuid.UUID, range_: str) -> dict:
    from datetime import date as date_type
    start = _range_start(range_)
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    date_values: dict[date_type, Decimal] = {}
    for h in holdings:
        prices = list((await db.execute(
            select(Price)
            .where(Price.asset_id == h.asset_id, Price.timestamp >= start)
            .order_by(Price.timestamp.asc())
        )).scalars().all())
        for p in prices:
            d = p.timestamp.date()
            date_values[d] = date_values.get(d, Decimal("0")) + h.quantity * p.close

    portfolio_series = [{"date": d, "value": v} for d, v in sorted(date_values.items())]

    # Benchmark: ^GSPC asset (created by price feed worker, may not have user_id)
    benchmark_asset = (await db.execute(
        select(Asset).where(Asset.symbol == "^GSPC")
    )).scalar_one_or_none()

    benchmark_series: list[dict] = []
    if benchmark_asset:
        b_prices = list((await db.execute(
            select(Price)
            .where(Price.asset_id == benchmark_asset.id, Price.timestamp >= start)
            .order_by(Price.timestamp.asc())
        )).scalars().all())
        benchmark_series = [{"date": p.timestamp.date(), "value": p.close} for p in b_prices]

    def normalize(series: list[dict]) -> list[dict]:
        if not series:
            return []
        base = series[0]["value"]
        if not base:
            return series
        return [{"date": s["date"], "value": s["value"] / base * 100} for s in series]

    logger.info("Performance: user=%s range=%s points=%d", user_id, range_, len(portfolio_series))
    return {"portfolio": normalize(portfolio_series), "benchmark": normalize(benchmark_series)}
```

- [ ] **Step 5: Create overview router**

```python
# backend/app/api/overview.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.overview import AllocationItem, OverviewSummary, PerformanceResponse
from app.services import overview as overview_service

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/summary", response_model=OverviewSummary)
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_summary(db, current_user.id)


@router.get("/allocation", response_model=list[AllocationItem])
async def get_allocation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_allocation(db, current_user.id)


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(
    range: str = "1M",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_performance(db, current_user.id, range)
```

- [ ] **Step 6: Register overview router in main.py**

In `backend/app/main.py`, add after the existing imports and router registrations:

```python
# Add to imports at top:
from app.api import assets, auth, health, overview, pipeline, platforms, portfolio, settings

# Add after the last app.include_router line:
app.include_router(overview.router, prefix="/api/v1")
```

- [ ] **Step 7: Run tests — verify they pass**

```bash
docker compose exec backend pytest tests/test_overview.py -v
```

Expected: All 6 tests PASS.

---

## Task 2: Asset History by Symbol — Backend Endpoint

**Files:**

- Modify: `backend/app/api/assets.py`
- Modify: `backend/tests/test_assets.py`

- [ ] **Step 1: Write failing test for symbol history endpoint**

Add to `backend/tests/test_assets.py`:

```python
@pytest.mark.asyncio
async def test_asset_history_by_symbol(auth_client):
    # Create asset
    await auth_client.post("/api/v1/assets", json={
        "symbol": "AAPL", "asset_type": "us_stock", "name": "Apple", "currency": "USD"
    })
    res = await auth_client.get("/api/v1/assets/symbol/AAPL/history?range=1M")
    assert res.status_code == 200
    data = res.json()
    assert "asset_id" in data
    assert "bars" in data
    assert isinstance(data["bars"], list)


@pytest.mark.asyncio
async def test_asset_history_symbol_not_found(auth_client):
    res = await auth_client.get("/api/v1/assets/symbol/UNKNOWN/history?range=1M")
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
docker compose exec backend pytest tests/test_assets.py::test_asset_history_by_symbol tests/test_assets.py::test_asset_history_symbol_not_found -v
```

Expected: FAIL — 404 or 422 because route doesn't exist.

- [ ] **Step 3: Add symbol history endpoint to assets router**

In `backend/app/api/assets.py`, add this route **before** the `/{asset_id}` routes (order matters in FastAPI to avoid shadowing):

```python
# Add these imports if not present:
from datetime import datetime, timedelta, timezone

from sqlalchemy import asc

# Add this route before the @router.get("/{asset_id}") route:
@router.get("/symbol/{symbol}/history", response_model=PriceHistoryResponse)
async def get_asset_history_by_symbol(
    symbol: str,
    range: str = "1M",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return OHLCV price history for an asset looked up by symbol string."""
    from app.services import asset as asset_svc

    days = {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}
    start = datetime.now(timezone.utc) - timedelta(days=days.get(range, 30))

    assets = await asset_svc.search_assets(db, current_user.id, symbol)
    asset = next((a for a in assets if a.symbol.upper() == symbol.upper()), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    result = await db.execute(
        select(Price)
        .where(Price.asset_id == asset.id, Price.timestamp >= start)
        .order_by(asc(Price.timestamp))
    )
    bars = list(result.scalars().all())
    return PriceHistoryResponse(asset_id=asset.id, bars=bars)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
docker compose exec backend pytest tests/test_assets.py::test_asset_history_by_symbol tests/test_assets.py::test_asset_history_symbol_not_found -v
```

Expected: Both PASS.

---

## Task 3: Market Overview Page — Frontend

**Files:**

- Create: `frontend/lib/services/overview.ts`
- Create: `frontend/components/overview/SummaryBar.tsx`
- Create: `frontend/components/overview/PerformanceChart.tsx`
- Create: `frontend/components/overview/AllocationDonut.tsx`
- Create: `frontend/components/overview/HoldingsSnapshot.tsx`
- Modify: `frontend/app/(auth)/page.tsx`

- [ ] **Step 1: Install recharts (if not already present)**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npm list recharts 2>/dev/null || npm install recharts
```

Expected: recharts listed in node_modules.

- [ ] **Step 2: Create PrivacyValue component first (used in Steps 3–6)**

```tsx
// frontend/components/ui/PrivacyValue.tsx
"use client";

import { usePrivacyStore } from "@/store/privacy";
import { cn } from "@/lib/utils";

interface Props {
  value: string;
  className?: string;
}

export function PrivacyValue({ value, className }: Props) {
  const { isPrivate } = usePrivacyStore();
  return <span className={cn(className)}>{isPrivate ? "••••" : value}</span>;
}
```

- [ ] **Step 3: Create overview service**

```typescript
// frontend/lib/services/overview.ts
import { api } from "@/lib/api";

export interface OverviewSummary {
  total_value: string;
  total_cost: string;
  total_pnl: string;
  total_pnl_pct: string;
  daily_change: string;
  daily_change_pct: string;
}

export interface AllocationItem {
  asset_type: string;
  value: string;
  pct: string;
}

export interface PerformancePoint {
  date: string;
  value: string;
}

export interface PerformanceData {
  portfolio: PerformancePoint[];
  benchmark: PerformancePoint[];
}

export interface PriceBar {
  timestamp: string;
  open: string | null;
  high: string | null;
  low: string | null;
  close: string;
  volume: string | null;
}

export interface AssetHistory {
  asset_id: string;
  bars: PriceBar[];
}

export async function fetchOverviewSummary(): Promise<OverviewSummary> {
  const res = await api.get("/api/v1/overview/summary");
  if (!res.ok) throw new Error("Failed to fetch overview summary");
  return res.json();
}

export async function fetchAllocation(): Promise<AllocationItem[]> {
  const res = await api.get("/api/v1/overview/allocation");
  if (!res.ok) throw new Error("Failed to fetch allocation");
  return res.json();
}

export async function fetchPerformance(
  range: string,
): Promise<PerformanceData> {
  const res = await api.get(`/api/v1/overview/performance?range=${range}`);
  if (!res.ok) throw new Error("Failed to fetch performance");
  return res.json();
}

export async function fetchAssetHistory(
  symbol: string,
  range: string,
): Promise<AssetHistory> {
  const res = await api.get(
    `/api/v1/assets/symbol/${encodeURIComponent(symbol)}/history?range=${range}`,
  );
  if (!res.ok) throw new Error("Failed to fetch asset history");
  return res.json();
}
```

- [ ] **Step 3: Create SummaryBar component**

```tsx
// frontend/components/overview/SummaryBar.tsx
"use client";

import { OverviewSummary } from "@/lib/services/overview";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface Props {
  summary: OverviewSummary;
}

function fmt(val: string, decimals = 2) {
  return Number(val).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function SummaryBar({ summary }: Props) {
  const pnlPositive = Number(summary.total_pnl) >= 0;
  const dailyPositive = Number(summary.daily_change) >= 0;

  return (
    <div className="flex flex-wrap gap-6 items-center p-4 bg-card rounded-lg border">
      <div>
        <p className="text-xs text-muted-foreground">Portfolio Value</p>
        <p className="text-3xl font-bold">
          <PrivacyValue value={`$${fmt(summary.total_value)}`} />
        </p>
      </div>
      <div>
        <p className="text-xs text-muted-foreground">Total Cost</p>
        <p className="text-lg font-medium">
          <PrivacyValue value={`$${fmt(summary.total_cost)}`} />
        </p>
      </div>
      <div>
        <p className="text-xs text-muted-foreground">Total P&L</p>
        <div className="flex items-center gap-1">
          <p
            className={cn(
              "text-lg font-medium",
              pnlPositive ? "text-green-500" : "text-red-500",
            )}
          >
            <PrivacyValue
              value={`${pnlPositive ? "+" : ""}$${fmt(summary.total_pnl)}`}
            />
          </p>
          <Badge
            variant={pnlPositive ? "default" : "destructive"}
            className="text-xs"
          >
            <PrivacyValue
              value={`${pnlPositive ? "+" : ""}${fmt(summary.total_pnl_pct)}%`}
            />
          </Badge>
        </div>
      </div>
      <div>
        <p className="text-xs text-muted-foreground">Today</p>
        <div className="flex items-center gap-1">
          <p
            className={cn(
              "text-lg font-medium",
              dailyPositive ? "text-green-500" : "text-red-500",
            )}
          >
            <PrivacyValue
              value={`${dailyPositive ? "+" : ""}$${fmt(summary.daily_change)}`}
            />
          </p>
          <Badge
            variant={dailyPositive ? "default" : "destructive"}
            className="text-xs"
          >
            <PrivacyValue
              value={`${dailyPositive ? "+" : ""}${fmt(summary.daily_change_pct)}%`}
            />
          </Badge>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create PerformanceChart component**

```tsx
// frontend/components/overview/PerformanceChart.tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { fetchPerformance } from "@/lib/services/overview";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const RANGES = ["1W", "1M", "3M", "1Y"] as const;
type Range = (typeof RANGES)[number];

export function PerformanceChart() {
  const [range, setRange] = useState<Range>("1M");

  const { data } = useQuery({
    queryKey: ["overview", "performance", range],
    queryFn: () => fetchPerformance(range),
  });

  const combined = (data?.portfolio ?? []).map((p, i) => ({
    date: p.date,
    portfolio: Number(p.value).toFixed(2),
    benchmark: data?.benchmark[i]
      ? Number(data.benchmark[i].value).toFixed(2)
      : null,
  }));

  return (
    <div className="flex flex-col gap-2 h-full">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Portfolio vs Benchmark</p>
        <Tabs value={range} onValueChange={(v) => setRange(v as Range)}>
          <TabsList className="h-7">
            {RANGES.map((r) => (
              <TabsTrigger key={r} value={r} className="text-xs px-2 h-6">
                {r}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={combined}>
          <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} />
          <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
          <Tooltip formatter={(v) => `${Number(v).toFixed(1)}`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line
            type="monotone"
            dataKey="portfolio"
            stroke="#6366f1"
            dot={false}
            strokeWidth={2}
            name="Portfolio"
          />
          <Line
            type="monotone"
            dataKey="benchmark"
            stroke="#94a3b8"
            dot={false}
            strokeWidth={1.5}
            name="S&P500"
            strokeDasharray="4 2"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 5: Create AllocationDonut component**

```tsx
// frontend/components/overview/AllocationDonut.tsx
"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { AllocationItem } from "@/lib/services/overview";
import { PrivacyValue } from "@/components/ui/PrivacyValue";

const COLORS = [
  "#6366f1",
  "#06b6d4",
  "#f59e0b",
  "#10b981",
  "#f43f5e",
  "#8b5cf6",
];

interface Props {
  allocation: AllocationItem[];
}

export function AllocationDonut({ allocation }: Props) {
  const data = allocation.map((a) => ({
    name: a.asset_type.replace("_", " ").toUpperCase(),
    value: Number(a.pct),
    rawValue: a.value,
  }));

  return (
    <div className="flex flex-col gap-2 h-full">
      <p className="text-sm font-medium">Allocation</p>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No holdings with price data yet.
        </p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                dataKey="value"
                paddingAngle={2}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-col gap-1">
            {data.map((item, i) => (
              <div
                key={item.name}
                className="flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-1">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ background: COLORS[i % COLORS.length] }}
                  />
                  <span>{item.name}</span>
                </div>
                <span className="text-muted-foreground">
                  <PrivacyValue
                    value={`$${Number(item.rawValue).toLocaleString("en-US", { maximumFractionDigits: 0 })} (${item.value.toFixed(1)}%)`}
                  />
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Create HoldingsSnapshot component**

```tsx
// frontend/components/overview/HoldingsSnapshot.tsx
"use client";

import { useRouter } from "next/navigation";
import { OverviewSummary } from "@/lib/services/overview";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface SnapshotHolding {
  symbol: string;
  name: string;
  asset_type: string;
  quantity: string;
  current_value: number;
  pnl_pct: number;
}

interface Props {
  holdings: SnapshotHolding[];
}

export function HoldingsSnapshot({ holdings }: Props) {
  const router = useRouter();

  return (
    <div className="rounded-lg border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-3 font-medium text-muted-foreground">
              Symbol
            </th>
            <th className="text-left p-3 font-medium text-muted-foreground">
              Name
            </th>
            <th className="text-left p-3 font-medium text-muted-foreground">
              Type
            </th>
            <th className="text-right p-3 font-medium text-muted-foreground">
              Quantity
            </th>
            <th className="text-right p-3 font-medium text-muted-foreground">
              Value
            </th>
            <th className="text-right p-3 font-medium text-muted-foreground">
              P&L%
            </th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr
              key={h.symbol}
              className="border-t hover:bg-muted/30 cursor-pointer transition-colors"
              onClick={() => router.push(`/portfolio/${h.symbol}`)}
            >
              <td className="p-3 font-mono font-medium">{h.symbol}</td>
              <td className="p-3 text-muted-foreground">{h.name}</td>
              <td className="p-3">
                <Badge variant="outline" className="text-xs">
                  {h.asset_type.replace("_", " ")}
                </Badge>
              </td>
              <td className="p-3 text-right">
                {Number(h.quantity).toFixed(4)}
              </td>
              <td className="p-3 text-right">
                <PrivacyValue
                  value={`$${h.current_value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                />
              </td>
              <td
                className={cn(
                  "p-3 text-right font-medium",
                  h.pnl_pct >= 0 ? "text-green-500" : "text-red-500",
                )}
              >
                <PrivacyValue
                  value={`${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct.toFixed(2)}%`}
                />
              </td>
            </tr>
          ))}
          {holdings.length === 0 && (
            <tr>
              <td colSpan={6} className="p-6 text-center text-muted-foreground">
                No holdings yet. Add assets in the Portfolio tab.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 7: Build market overview page**

Note: Before writing this file, read the current `frontend/app/(auth)/page.tsx` to see what's there, then replace its content.

```tsx
// frontend/app/(auth)/page.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchOverviewSummary, fetchAllocation } from "@/lib/services/overview";
import { fetchHoldings } from "@/lib/services/portfolio";
import { fetchAllAssets } from "@/lib/services/assets";
import { SummaryBar } from "@/components/overview/SummaryBar";
import { PerformanceChart } from "@/components/overview/PerformanceChart";
import { AllocationDonut } from "@/components/overview/AllocationDonut";
import {
  HoldingsSnapshot,
  SnapshotHolding,
} from "@/components/overview/HoldingsSnapshot";
import { Skeleton } from "@/components/ui/skeleton";

export default function OverviewPage() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["overview", "summary"],
    queryFn: fetchOverviewSummary,
    refetchInterval: 60_000,
  });

  const { data: allocation = [] } = useQuery({
    queryKey: ["overview", "allocation"],
    queryFn: fetchAllocation,
    refetchInterval: 60_000,
  });

  const { data: holdings = [] } = useQuery({
    queryKey: ["portfolio", "holdings"],
    queryFn: fetchHoldings,
  });

  const { data: assets = [] } = useQuery({
    queryKey: ["assets"],
    queryFn: fetchAllAssets,
  });

  const snapshotHoldings: SnapshotHolding[] = holdings
    .map((h) => {
      const asset = assets.find((a) => a.id === h.asset_id);
      if (!asset) return null;
      const cost = Number(h.avg_cost_price) * Number(h.quantity);
      // current_value without prices → show cost as fallback
      const current_value = cost;
      const pnl_pct = 0;
      return {
        symbol: asset.symbol,
        name: asset.name,
        asset_type: asset.asset_type,
        quantity: h.quantity,
        current_value,
        pnl_pct,
      };
    })
    .filter(Boolean) as SnapshotHolding[];

  const sorted = [...snapshotHoldings].sort(
    (a, b) => b.current_value - a.current_value,
  );

  return (
    <div className="p-6 flex flex-col gap-6 max-w-7xl mx-auto">
      {summaryLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : summary ? (
        <SummaryBar summary={summary} />
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 bg-card rounded-lg border p-4">
          <PerformanceChart />
        </div>
        <div className="lg:col-span-2 bg-card rounded-lg border p-4">
          <AllocationDonut allocation={allocation} />
        </div>
      </div>

      <div>
        <h2 className="text-sm font-medium text-muted-foreground mb-2">
          Holdings
        </h2>
        <HoldingsSnapshot holdings={sorted} />
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Start dev server and verify overview page renders**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri
docker compose up -d
```

Open `http://localhost` in browser. Verify:

- Summary bar shows zeros or real values
- Performance chart renders (may be empty if no price history)
- Allocation donut shows message if no prices
- Holdings table shows holdings or empty state

---

## Task 4: Asset Detail Page — Frontend

**Files:**

- Create: `frontend/components/portfolio/PriceChart.tsx`
- Create: `frontend/app/(auth)/portfolio/[symbol]/page.tsx`

- [ ] **Step 1: Install lightweight-charts (if not already present)**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npm list lightweight-charts 2>/dev/null || npm install lightweight-charts
```

Expected: lightweight-charts listed in node_modules.

- [ ] **Step 2: Create PriceChart component**

```tsx
// frontend/components/portfolio/PriceChart.tsx
"use client";

import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries, ColorType } from "lightweight-charts";
import { PriceBar } from "@/lib/services/overview";

interface Props {
  bars: PriceBar[];
}

export function PriceChart({ bars }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || bars.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      width: containerRef.current.clientWidth,
      height: 300,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#f43f5e",
      borderUpColor: "#10b981",
      borderDownColor: "#f43f5e",
      wickUpColor: "#10b981",
      wickDownColor: "#f43f5e",
    });

    series.setData(
      bars
        .filter((b) => b.open && b.high && b.low)
        .map((b) => ({
          time: b.timestamp.split("T")[0],
          open: Number(b.open),
          high: Number(b.high),
          low: Number(b.low),
          close: Number(b.close),
        })),
    );

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current)
        chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [bars]);

  if (bars.length === 0) {
    return (
      <div className="h-[300px] flex items-center justify-center text-sm text-muted-foreground">
        No price data available yet.
      </div>
    );
  }

  return <div ref={containerRef} className="w-full" />;
}
```

- [ ] **Step 3: Create asset detail page**

```tsx
// frontend/app/(auth)/portfolio/[symbol]/page.tsx
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchAssetHistory } from "@/lib/services/overview";
import { fetchHoldings } from "@/lib/services/portfolio";
import { fetchAllAssets } from "@/lib/services/assets";
import { PriceChart } from "@/components/portfolio/PriceChart";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { api } from "@/lib/api";

const RANGES = ["1W", "1M", "3M", "1Y"] as const;
type Range = (typeof RANGES)[number];

export default function AssetDetailPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const [range, setRange] = useState<Range>("1M");

  const { data: assets = [] } = useQuery({
    queryKey: ["assets"],
    queryFn: fetchAllAssets,
  });
  const asset = assets.find(
    (a) => a.symbol.toUpperCase() === symbol.toUpperCase(),
  );

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["asset-history", symbol, range],
    queryFn: () => fetchAssetHistory(symbol, range),
    enabled: !!symbol,
  });

  const { data: txData } = useQuery({
    queryKey: ["transactions", asset?.id],
    queryFn: async () => {
      if (!asset) return [];
      const res = await api.get(
        `/api/v1/portfolio/transactions?asset_id=${asset.id}`,
      );
      if (!res.ok) return [];
      return res.json() as Promise<
        Array<{
          id: string;
          type: string;
          quantity: string;
          price: string;
          fee: string;
          source: string;
          executed_at: string;
          platform_id: string | null;
        }>
      >;
    },
    enabled: !!asset,
  });

  const bars = history?.bars ?? [];
  const latestBar = bars[bars.length - 1];
  const prevBar = bars[bars.length - 2];
  const dailyChange =
    latestBar && prevBar
      ? Number(latestBar.close) - Number(prevBar.close)
      : null;
  const dailyChangePct =
    dailyChange && prevBar ? (dailyChange / Number(prevBar.close)) * 100 : null;

  return (
    <div className="p-6 flex flex-col gap-6 max-w-5xl mx-auto">
      {/* Chart header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{symbol.toUpperCase()}</h1>
          <p className="text-muted-foreground">{asset?.name ?? "Loading..."}</p>
        </div>
        <div className="text-right">
          {latestBar && (
            <>
              <p className="text-2xl font-semibold">
                <PrivacyValue
                  value={`$${Number(latestBar.close).toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
                />
              </p>
              {dailyChange !== null && dailyChangePct !== null && (
                <Badge variant={dailyChange >= 0 ? "default" : "destructive"}>
                  <PrivacyValue
                    value={`${dailyChange >= 0 ? "+" : ""}${dailyChange.toFixed(2)} (${dailyChangePct.toFixed(2)}%)`}
                  />
                </Badge>
              )}
            </>
          )}
        </div>
      </div>

      {/* Range tabs */}
      <Tabs value={range} onValueChange={(v) => setRange(v as Range)}>
        <TabsList>
          {RANGES.map((r) => (
            <TabsTrigger key={r} value={r}>
              {r}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Price chart */}
      <div className="bg-card rounded-lg border p-4">
        {historyLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : (
          <PriceChart bars={bars} />
        )}
      </div>

      {/* Transactions table */}
      <div>
        <h2 className="text-sm font-medium text-muted-foreground mb-2">
          Transactions
        </h2>
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3 font-medium text-muted-foreground">
                  Date
                </th>
                <th className="text-left p-3 font-medium text-muted-foreground">
                  Type
                </th>
                <th className="text-right p-3 font-medium text-muted-foreground">
                  Quantity
                </th>
                <th className="text-right p-3 font-medium text-muted-foreground">
                  Price
                </th>
                <th className="text-right p-3 font-medium text-muted-foreground">
                  Fee
                </th>
                <th className="text-left p-3 font-medium text-muted-foreground">
                  Source
                </th>
              </tr>
            </thead>
            <tbody>
              {(txData ?? []).map((tx) => (
                <tr key={tx.id} className="border-t">
                  <td className="p-3 text-muted-foreground">
                    {new Date(tx.executed_at).toLocaleDateString("en-US")}
                  </td>
                  <td className="p-3">
                    <Badge
                      variant={
                        tx.type === "buy"
                          ? "default"
                          : tx.type === "sell"
                            ? "destructive"
                            : "outline"
                      }
                      className="text-xs"
                    >
                      {tx.type}
                    </Badge>
                  </td>
                  <td className="p-3 text-right font-mono">
                    {Number(tx.quantity).toFixed(6)}
                  </td>
                  <td className="p-3 text-right">
                    <PrivacyValue
                      value={`$${Number(tx.price).toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
                    />
                  </td>
                  <td className="p-3 text-right">
                    <PrivacyValue value={`$${Number(tx.fee).toFixed(2)}`} />
                  </td>
                  <td className="p-3 text-muted-foreground capitalize">
                    {tx.source}
                  </td>
                </tr>
              ))}
              {!txData?.length && (
                <tr>
                  <td
                    colSpan={6}
                    className="p-6 text-center text-muted-foreground"
                  >
                    No transactions recorded for this asset.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify in browser**

Navigate to `http://localhost/portfolio/AAPL` (or any symbol you have in your portfolio).

Verify:

- Page loads without crash
- Chart renders with candlestick bars if price data exists
- Range tabs change the chart
- Transactions table shows or shows empty state
- Privacy mode toggle masks price values

---

## Task 5: Wire PrivacyValue into Existing Portfolio Components

**Files:**

- Modify: `frontend/components/portfolio/HoldingsTable.tsx`

Note: `PrivacyValue` was created in Task 3 Step 2. The privacy Zustand store and TopNav toggle are already in the codebase. This task wires PrivacyValue into the existing portfolio list page.

- [ ] **Step 1: Read HoldingsTable to find monetary value renders**

Read `frontend/components/portfolio/HoldingsTable.tsx` to identify where `avg_cost_price`, `quantity`, or computed values are rendered as text.

- [ ] **Step 3: Wire PrivacyValue into HoldingsTable**

In `frontend/components/portfolio/HoldingsTable.tsx`, import `PrivacyValue` and wrap any monetary display values:

```tsx
// Add import at top:
import { PrivacyValue } from "@/components/ui/PrivacyValue";

// Wherever avg_cost_price or computed monetary values are shown, replace:
// <span>{value}</span>
// with:
// <PrivacyValue value={value} />
```

The exact lines depend on what's in the file — read it first.

- [ ] **Step 4: Verify privacy mode in browser**

1. Open `http://localhost/portfolio` (holdings list)
2. Click the eye icon in the top nav — all monetary values should change to `••••`
3. Navigate to `/portfolio/AAPL` — prices and fees should also be masked
4. Navigate to `/` (overview) — summary bar, allocation, and holdings snapshot should be masked
5. Click eye icon again — all values should restore
6. Refresh page — privacy state should persist (stored in localStorage via zustand persist)

---

## Task 6: Command Palette — ⌘K Search

**Files:**

- Create: `frontend/store/palette.ts`
- Create: `frontend/components/layout/CommandPalette.tsx`
- Modify: `frontend/app/(auth)/layout.tsx`
- Modify: `frontend/components/layout/TopNav.tsx`

- [ ] **Step 1: Create palette store**

```typescript
// frontend/store/palette.ts
import { create } from "zustand";
import { Asset, fetchAllAssets } from "@/lib/services/assets";

interface PaletteState {
  open: boolean;
  assets: Asset[];
  setOpen: (open: boolean) => void;
  loadAssets: () => Promise<void>;
}

export const usePaletteStore = create<PaletteState>((set) => ({
  open: false,
  assets: [],
  setOpen: (open) => set({ open }),
  loadAssets: async () => {
    try {
      const assets = await fetchAllAssets();
      set({ assets });
    } catch {
      // silently ignore — palette degrades gracefully
    }
  },
}));
```

- [ ] **Step 2: Create CommandPalette component**

```tsx
// frontend/components/layout/CommandPalette.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { usePaletteStore } from "@/store/palette";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function CommandPalette() {
  const { open, setOpen, assets } = usePaletteStore();
  const [query, setQuery] = useState("");
  const router = useRouter();

  const filtered = assets.filter(
    (a) =>
      a.symbol.toLowerCase().includes(query.toLowerCase()) ||
      a.name.toLowerCase().includes(query.toLowerCase()),
  );

  const hasMatches = filtered.length > 0;

  function handleSelect(symbol: string) {
    router.push(`/portfolio/${symbol}`);
    setOpen(false);
    setQuery("");
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Search holdings..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        {hasMatches ? (
          <CommandGroup heading="Holdings">
            {filtered.map((asset) => (
              <CommandItem
                key={asset.id}
                onSelect={() => handleSelect(asset.symbol)}
                className="flex items-center gap-2"
              >
                <span className="font-mono font-medium">{asset.symbol}</span>
                <span className="text-muted-foreground text-sm">
                  {asset.name}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : (
          <CommandEmpty>
            <span>No holdings match &ldquo;{query}&rdquo;</span>
          </CommandEmpty>
        )}

        {/* AI slot — grayed out, available in Phase 6 */}
        {query.length > 0 && (
          <CommandGroup heading="AI">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <CommandItem
                    disabled
                    className="opacity-40 cursor-not-allowed select-none"
                  >
                    <span className="text-muted-foreground">
                      Ask AI: &ldquo;{query}&rdquo;
                    </span>
                  </CommandItem>
                </TooltipTrigger>
                <TooltipContent>
                  AI analysis available once LLM is configured (Phase 6)
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
```

- [ ] **Step 3: Read the auth layout to see its current content**

Read `frontend/app/(auth)/layout.tsx` to understand its current structure before modifying.

- [ ] **Step 4: Update auth layout to mount palette + ⌘K listener**

In `frontend/app/(auth)/layout.tsx`, add the palette mounting. The layout needs to be a client component to use `useEffect`. If it's currently a server component, add `"use client"` at the top.

```tsx
// frontend/app/(auth)/layout.tsx
"use client";

import { useEffect } from "react";
import { usePaletteStore } from "@/store/palette";
import { CommandPalette } from "@/components/layout/CommandPalette";
// Keep all existing imports (Sidebar, TopNav, etc.)

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { setOpen, loadAssets } = usePaletteStore();

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [setOpen]);

  return (
    // Keep the existing JSX structure (Sidebar, TopNav, main content)
    // Just add <CommandPalette /> at the end of the return, before the closing tag
    <>
      {/* existing layout JSX */}
      <CommandPalette />
    </>
  );
}
```

The exact JSX depends on what's in the file — read it first, then insert `<CommandPalette />` and the two `useEffect` hooks.

- [ ] **Step 5: Read TopNav to see its current content**

Read `frontend/components/layout/TopNav.tsx`. The privacy toggle and logout are already there.

- [ ] **Step 6: Add search icon button to TopNav**

In `frontend/components/layout/TopNav.tsx`, add a Search button that opens the palette:

```tsx
// Add to imports:
import { Eye, EyeOff, LogOut, Search } from "lucide-react";
import { usePaletteStore } from "@/store/palette";

// Inside TopNav component, add:
const { setOpen } = usePaletteStore();

// Add this button before the privacy toggle button:
<Button
  variant="ghost"
  size="icon"
  onClick={() => setOpen(true)}
  title="Search (⌘K)"
>
  <Search className="h-4 w-4" />
</Button>;
```

The full updated TopNav should look like:

```tsx
"use client";

import { Eye, EyeOff, LogOut, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePrivacyStore } from "@/store/privacy";
import { usePaletteStore } from "@/store/palette";
import { logout } from "@/lib/auth";
import { useRouter } from "next/navigation";

export function TopNav() {
  const { isPrivate, toggle } = usePrivacyStore();
  const { setOpen } = usePaletteStore();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <header className="h-14 border-b flex items-center justify-end px-4 gap-2 bg-card">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(true)}
        title="Search (⌘K)"
      >
        <Search className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={toggle}
        title="Toggle privacy mode"
      >
        {isPrivate ? (
          <EyeOff className="h-4 w-4" />
        ) : (
          <Eye className="h-4 w-4" />
        )}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={handleLogout}
        title="Log out"
      >
        <LogOut className="h-4 w-4" />
      </Button>
    </header>
  );
}
```

- [ ] **Step 7: Verify command palette in browser**

1. Open `http://localhost`
2. Press `⌘K` (Mac) or `Ctrl+K` (Win/Linux) — palette should open
3. Type a symbol you have in portfolio — matching holdings should appear
4. Click a result — should navigate to `/portfolio/[symbol]`
5. Click the Search icon in TopNav — palette should also open
6. Type something with no match — "Ask AI" item should appear grayed out with tooltip on hover

---

## Phase 5 Complete Verification

After all 6 tasks, do a full smoke test:

- [ ] `http://localhost` — overview page: summary bar, benchmark chart, donut, holdings table
- [ ] Click a holding row → navigates to `/portfolio/[symbol]`
- [ ] Asset detail page: candlestick chart with range tabs, transactions table
- [ ] Eye icon in nav → all monetary values become `••••`, persist on refresh
- [ ] `⌘K` → palette opens, search works, AI slot is grayed out
- [ ] `docker compose exec backend pytest tests/test_overview.py tests/test_assets.py -v` → all green

---

## Kanban Updates

After completing this phase, move the following from "Ready to Dev" → "Done" in the Kanban:

- `[[feat - market overview page]]`
- `[[feat - overview summary allocation and performance endpoints]]`
- `[[feat - asset detail page with lightweight-charts]]`
- `[[feat - privacy mode toggle]]`
- `[[feat - global command palette search]]`
