# Sector & Industry Allocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `sector` and `industry` columns to assets, enrich them via yfinance, expose a `/overview/allocation/sector` endpoint, and add a tab toggle on the AllocationDonut card.

**Architecture:** Store `sector`, `industry`, `market_cap_category` as nullable columns on the `assets` table. A new `POST /assets/enrich-metadata` endpoint calls yfinance `.info` for stocks/ETFs (same pattern as `refresh_asset_names`) and hard-codes categories for crypto/gold/cash/th_fund. The overview service gains a `get_sector_allocation` function that groups holding values by `sector`. The frontend AllocationDonut card gets a "By Type" / "By Sector" tab toggle.

**Tech Stack:** Python/SQLAlchemy/Alembic (backend), yfinance (data source), FastAPI (API), Next.js/React Query/Recharts (frontend)

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/alembic/versions/044_add_sector_to_assets.py` |
| Modify | `backend/app/models/asset.py` |
| Create | `backend/app/services/asset_enrichment.py` |
| Modify | `backend/app/api/assets.py` |
| Modify | `backend/app/schemas/overview.py` |
| Modify | `backend/app/services/overview.py` |
| Modify | `backend/app/api/overview.py` |
| Modify | `frontend/lib/services/overview.ts` |
| Modify | `frontend/components/overview/AllocationDonut.tsx` |
| Modify | `frontend/app/(auth)/overview/page.tsx` |

---

## Task 1: DB Migration — add sector/industry/market_cap_category to assets

**Files:**
- Create: `backend/alembic/versions/044_add_sector_to_assets.py`

- [ ] **Step 1: Create migration file**

```python
"""add sector industry market_cap_category to assets

Revision ID: 044
Revises: 043
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("sector", sa.String(100), nullable=True))
    op.add_column("assets", sa.Column("industry", sa.String(100), nullable=True))
    op.add_column("assets", sa.Column("market_cap_category", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "market_cap_category")
    op.drop_column("assets", "industry")
    op.drop_column("assets", "sector")
```

- [ ] **Step 2: Run migration**

```bash
cd backend
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 043 -> 044`

---

## Task 2: Add fields to Asset model

**Files:**
- Modify: `backend/app/models/asset.py`

- [ ] **Step 1: Add three nullable columns after `metadata_`**

In `backend/app/models/asset.py`, add after `metadata_: Mapped[dict] = ...`:

```python
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_cap_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

Full updated model:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ASSET_TYPES = ("us_stock", "thai_stock", "thai_dr", "th_fund", "etf", "crypto", "gold", "cash")


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
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_cap_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

---

## Task 3: Asset enrichment service

**Files:**
- Create: `backend/app/services/asset_enrichment.py`

This service is the core of the feature. It follows the same pattern as `refresh_asset_names` in `assets_api.py`.

**market_cap_category rules (USD):** Large > $10B, Mid $2B–$10B, Small < $2B.  
**Hard-coded sectors:** crypto → "Crypto", gold → "Commodities", cash → "Cash", th_fund → "Mutual Fund".  
**yfinance coverage:** us_stock, etf, thai_stock (.BK suffix), thai_dr (.BK suffix).

- [ ] **Step 1: Create the service file**

```python
from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset

logger = get_logger(__name__)

_STATIC_SECTOR: dict[str, str] = {
    "crypto": "Crypto",
    "gold": "Commodities",
    "cash": "Cash",
    "th_fund": "Mutual Fund",
}

_MC_THRESHOLDS = [
    (10_000_000_000, "Large Cap"),
    (2_000_000_000, "Mid Cap"),
]


def _categorize_market_cap(market_cap: int | None) -> str | None:
    if not market_cap:
        return None
    for threshold, label in _MC_THRESHOLDS:
        if market_cap >= threshold:
            return label
    return "Small Cap"


async def enrich_assets(db: AsyncSession, user_id: uuid.UUID) -> dict:
    result = await db.execute(select(Asset).where(Asset.user_id == user_id))
    assets = list(result.scalars().all())

    # Hard-code static sectors
    for asset in assets:
        static = _STATIC_SECTOR.get(asset.asset_type)
        if static:
            asset.sector = static
            asset.industry = static

    # Build yfinance symbol map for types that have real sector data
    yf_map: dict[str, uuid.UUID] = {}
    for asset in assets:
        if asset.asset_type in ("us_stock", "etf"):
            yf_map[asset.symbol] = asset.id
        elif asset.asset_type in ("thai_stock", "thai_dr"):
            yf_map[f"{asset.symbol}.BK"] = asset.id

    enriched = 0
    if yf_map:
        def _fetch() -> dict[uuid.UUID, dict]:
            out: dict[uuid.UUID, dict] = {}
            tickers = yf.Tickers(" ".join(yf_map.keys()))
            for yf_sym, asset_id in yf_map.items():
                try:
                    info = tickers.tickers[yf_sym].info
                    out[asset_id] = {
                        "sector": info.get("sector") or info.get("category"),
                        "industry": info.get("industry") or info.get("fundFamily"),
                        "market_cap": info.get("marketCap"),
                    }
                except Exception as e:
                    logger.warning("enrich_assets: yfinance failed for %s: %s", yf_sym, e)
            return out

        info_map = await asyncio.get_event_loop().run_in_executor(None, _fetch)

        asset_by_id = {a.id: a for a in assets}
        for asset_id, info in info_map.items():
            asset = asset_by_id.get(asset_id)
            if not asset:
                continue
            if info.get("sector"):
                asset.sector = info["sector"]
            if info.get("industry"):
                asset.industry = info["industry"]
            asset.market_cap_category = _categorize_market_cap(info.get("market_cap"))
            enriched += 1

    await db.commit()
    logger.info("enrich_assets: enriched %d/%d assets for user=%s", enriched, len(assets), user_id)
    return {"enriched": enriched, "total": len(assets)}
```

---

## Task 4: Enrich-metadata API endpoint

**Files:**
- Modify: `backend/app/api/assets.py`

- [ ] **Step 1: Add import for enrichment service at top of `assets.py`**

Add alongside existing service imports:
```python
from app.services.asset_enrichment import enrich_assets
```

- [ ] **Step 2: Add endpoint after `backfill-logos` route (before `/{asset_id}` routes)**

```python
@router.post("/enrich-metadata")
async def enrich_asset_metadata(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await enrich_assets(db, current_user.id)
```

- [ ] **Step 3: Verify route ordering — `/enrich-metadata` must appear before `/{asset_id}` routes**

Run: `grep -n 'router\.' backend/app/api/assets.py | grep -E 'enrich|asset_id'`  
Expected: `enrich-metadata` line number is lower than `/{asset_id}` lines.

---

## Task 5: Sector allocation — backend schema + service + endpoint

**Files:**
- Modify: `backend/app/schemas/overview.py`
- Modify: `backend/app/services/overview.py`
- Modify: `backend/app/api/overview.py`

### 5a — Schema

- [ ] **Step 1: Add `SectorAllocationItem` to `backend/app/schemas/overview.py`**

Add after `AllocationItem`:
```python
class SectorAllocationItem(BaseModel):
    sector: str
    value: Decimal
    pct: Decimal
```

### 5b — Service

- [ ] **Step 2: Add `get_sector_allocation` to `backend/app/services/overview.py`**

Add after the `get_allocation` function:

```python
async def get_sector_allocation(db: AsyncSession, user_id: uuid.UUID, target_currency: str = "USD") -> list[dict]:
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    by_sector: dict[str, Decimal] = {}

    for h in holdings:
        latest = await _latest_price(db, h.asset_id)
        if not latest:
            continue
        asset = (await db.execute(
            select(Asset).where(Asset.id == h.asset_id)
        )).scalar_one_or_none()
        if not asset:
            continue
        sector = asset.sector or asset.asset_type.replace("_", " ").title()
        value_native = h.quantity * latest.close
        rate = await fx_service.get_rate(db, asset.currency, target_currency)
        value_converted = value_native * rate if rate else value_native
        by_sector[sector] = by_sector.get(sector, Decimal("0")) + value_converted

    # Add cash balances under "Cash" sector
    cash_assets = list((await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.asset_type == "cash")
    )).scalars().all())

    for ca in cash_assets:
        snap_result = await db.execute(
            select(CashBalance)
            .where(CashBalance.asset_id == ca.id, CashBalance.user_id == user_id)
            .order_by(CashBalance.snapshot_date.desc())
            .limit(1)
        )
        snap = snap_result.scalar_one_or_none()
        if snap:
            balance = Decimal(str(snap.balance))
            rate = await fx_service.get_rate(db, ca.currency, target_currency)
            balance_converted = balance * rate if rate else balance
            by_sector["Cash"] = by_sector.get("Cash", Decimal("0")) + balance_converted

    total = sum(by_sector.values()) or Decimal("1")
    logger.info("SectorAllocation: user=%s sectors=%s", user_id, list(by_sector.keys()))
    return [{"sector": k, "value": v, "pct": v / total * 100} for k, v in by_sector.items()]
```

### 5c — API endpoint

- [ ] **Step 3: Update imports in `backend/app/api/overview.py`**

Change:
```python
from app.schemas.overview import AllocationItem, NetWorthPoint, OverviewSummary, PerformanceResponse
```
To:
```python
from app.schemas.overview import AllocationItem, NetWorthPoint, OverviewSummary, PerformanceResponse, SectorAllocationItem
```

- [ ] **Step 4: Add sector allocation endpoint after the existing `/allocation` route**

```python
@router.get("/allocation/sector", response_model=list[SectorAllocationItem])
async def get_sector_allocation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_sector_allocation(db, current_user.id, current_user.currency_primary)
```

---

## Task 6: Frontend — types + service functions

**Files:**
- Modify: `frontend/lib/services/overview.ts`

- [ ] **Step 1: Add `SectorAllocationItem` interface and two new fetch functions**

Add after the `AllocationItem` interface:
```typescript
export interface SectorAllocationItem {
  sector: string;
  value: string;
  pct: string;
}
```

Add after `fetchAllocation`:
```typescript
export async function fetchSectorAllocation(): Promise<SectorAllocationItem[]> {
  const res = await api.get("/api/v1/overview/allocation/sector");
  if (!res.ok) throw new Error("Failed to fetch sector allocation");
  return res.json();
}

export async function triggerEnrichMetadata(): Promise<{ enriched: number; total: number }> {
  const res = await api.post("/api/v1/assets/enrich-metadata");
  if (!res.ok) throw new Error("Failed to enrich metadata");
  return res.json();
}
```

---

## Task 7: Frontend — AllocationDonut tab toggle

**Files:**
- Modify: `frontend/components/overview/AllocationDonut.tsx`

The component currently receives `allocation: AllocationItem[]` and displays a single donut. We add a second `sectorAllocation: SectorAllocationItem[]` prop and a two-tab toggle ("By Type" / "By Sector").

- [ ] **Step 1: Rewrite `AllocationDonut.tsx`**

```tsx
"use client";

import { memo, useMemo, useState } from "react";
import { PieChart as RechartsPieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { PieChart as PieChartIcon } from "lucide-react";
import { AllocationItem, SectorAllocationItem } from "@/lib/services/overview";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { usePrivacyStore } from "@/store/privacy";

const COLORS = [
  "var(--color-brand-accent)",
  "var(--color-brand-sage)",
  "var(--color-brand-mid)",
  "var(--color-brand-danger)",
  "var(--color-muted-foreground)",
  "var(--color-brand-deep)",
];

function formatCompact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return value.toFixed(0);
}

interface Props {
  allocation: AllocationItem[];
  sectorAllocation: SectorAllocationItem[];
}

export const AllocationDonut = memo(function AllocationDonut({ allocation, sectorAllocation }: Props) {
  const { primaryCurrency } = useDualCurrency();
  const { isPrivate } = usePrivacyStore();
  const [tab, setTab] = useState<"type" | "sector">("type");

  const typeData = useMemo(
    () => allocation.map((a) => ({
      name: a.asset_type.replace(/_/g, " ").toUpperCase(),
      value: Number(a.pct),
      rawValue: Number(a.value),
    })),
    [allocation],
  );

  const sectorData = useMemo(
    () => sectorAllocation.map((a) => ({
      name: a.sector,
      value: Number(a.pct),
      rawValue: Number(a.value),
    })),
    [sectorAllocation],
  );

  const data = tab === "type" ? typeData : sectorData;
  const dominant = data.length > 0
    ? data.reduce((max, item) => item.value > max.value ? item : max, data[0])
    : null;

  const isEmpty = data.length === 0;

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Allocation</p>
        <div className="flex rounded-md overflow-hidden border border-border text-xs">
          <button
            className={`px-2 py-0.5 transition-colors ${tab === "type" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
            onClick={() => setTab("type")}
          >
            By Type
          </button>
          <button
            className={`px-2 py-0.5 transition-colors ${tab === "sector" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
            onClick={() => setTab("sector")}
          >
            By Sector
          </button>
        </div>
      </div>

      {isEmpty ? (
        <div className="h-32 flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <PieChartIcon className="h-6 w-6 opacity-30" />
          <span className="text-xs">
            {tab === "sector" ? "Run sector enrichment first" : "No allocation data yet"}
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-4 flex-1">
          <div className="relative flex-shrink-0">
            <ResponsiveContainer width={128} height={128}>
              <RechartsPieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={42}
                  outerRadius={60}
                  dataKey="value"
                  paddingAngle={2}
                  startAngle={90}
                  endAngle={-270}
                >
                  {data.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number) => [`${v.toFixed(1)}%`, ""]}
                  contentStyle={{ fontSize: "11px" }}
                />
              </RechartsPieChart>
            </ResponsiveContainer>
            {dominant && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[9px] text-muted-foreground leading-tight text-center px-2 truncate max-w-[80px]">
                  {dominant.name}
                </span>
                <span className="text-sm font-semibold leading-tight">
                  {dominant.value.toFixed(0)}%
                </span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1.5 flex-1 min-w-0">
            {data.map((item, i) => (
              <div key={item.name} className="flex items-center gap-1.5">
                <div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: COLORS[i % COLORS.length] }}
                />
                <span className="flex-1 min-w-0 truncate text-xs text-muted-foreground">
                  {item.name}
                </span>
                <span className="text-xs font-mono tabular-nums text-muted-foreground flex-shrink-0">
                  {isPrivate ? "******" : formatCompact(item.rawValue)} {primaryCurrency}
                </span>
                <span
                  className="text-xs font-mono font-medium tabular-nums flex-shrink-0 w-10 text-right"
                  style={{ color: COLORS[i % COLORS.length] }}
                >
                  {item.value.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});
```

---

## Task 8: Frontend — overview page wiring

**Files:**
- Modify: `frontend/app/(auth)/overview/page.tsx`

Read the current page first: it imports `AllocationDonut` and has a `useQuery` for allocation. We need to:
1. Add a second `useQuery` for sector allocation
2. Add a `useMutation` for the enrich button
3. Pass `sectorAllocation` to `AllocationDonut`
4. Add the "Update Sector Data" button on the AllocationDonut card

- [ ] **Step 1: Add imports at the top of overview page**

Add to existing imports from `@/lib/services/overview`:
```typescript
import { fetchSectorAllocation, triggerEnrichMetadata } from "@/lib/services/overview";
```

Add React Query `useMutation`:
```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
```

- [ ] **Step 2: Add queries inside the page component**

After the existing `const { data: allocation = [] } = useQuery(...)`, add:

```typescript
const queryClient = useQueryClient();

const { data: sectorAllocation = [] } = useQuery({
  queryKey: ["overview", "allocation", "sector"],
  queryFn: fetchSectorAllocation,
});

const enrichMutation = useMutation({
  mutationFn: triggerEnrichMetadata,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["overview", "allocation", "sector"] });
  },
});
```

- [ ] **Step 3: Update the `AllocationDonut` usage to pass both props**

Change:
```tsx
<AllocationDonut allocation={allocation} />
```
To:
```tsx
<AllocationDonut allocation={allocation} sectorAllocation={sectorAllocation} />
```

- [ ] **Step 4: Add "Update Sector Data" button in the AllocationDonut card**

Wrap the `AllocationDonut` in a card that has the button. Find the card/div wrapping `<AllocationDonut .../>` and add the button below it:

```tsx
<button
  onClick={() => enrichMutation.mutate()}
  disabled={enrichMutation.isPending}
  className="text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 mt-1 self-end"
>
  {enrichMutation.isPending ? "Updating..." : "Update Sector Data"}
</button>
```

---

## Task 9: Verify end-to-end

- [ ] **Step 1: Restart backend and confirm migration applied**

```bash
docker compose logs backend | grep "044"
```
Expected: `Running upgrade 043 -> 044`

- [ ] **Step 2: Hit enrich endpoint manually**

```bash
curl -X POST http://localhost:8000/api/v1/assets/enrich-metadata \
  -H "Authorization: Bearer <your_token>"
```
Expected: `{"enriched": N, "total": N}`

- [ ] **Step 3: Hit sector allocation endpoint**

```bash
curl http://localhost:8000/api/v1/overview/allocation/sector \
  -H "Authorization: Bearer <your_token>"
```
Expected: JSON array with `sector`, `value`, `pct` fields. Sectors like "Technology", "Energy", "Financials", "Mutual Fund", "Crypto", "Cash".

- [ ] **Step 4: Verify frontend tab toggle**

Open the app → Overview page → click "By Sector" tab → confirm donut shows sector breakdown.

- [ ] **Step 5: Verify "Update Sector Data" button**

Click the button → loading state appears → on success, "By Sector" tab refreshes.

---

## Self-Review

### Spec coverage
- ✅ `sector`/`industry` DB columns on assets — Task 1 & 2
- ✅ Enrich via yfinance for US/Thai stocks — Task 3
- ✅ Hard-coded sectors for crypto/gold/cash/th_fund — Task 3
- ✅ `POST /assets/enrich-metadata` endpoint — Task 4
- ✅ `GET /overview/allocation/sector` endpoint — Task 5
- ✅ AllocationDonut tab toggle "By Type" / "By Sector" — Task 7
- ✅ "Update Sector Data" button — Task 8
- ✅ `market_cap_category` stored per asset (Large/Mid/Small Cap) — Task 3

### Type consistency
- `SectorAllocationItem` defined in schema (Task 5a), imported in API (Task 5c), frontend interface (Task 6), component props (Task 7) — consistent
- `get_sector_allocation` returns `list[dict]` with keys `sector`, `value`, `pct` — matches `SectorAllocationItem` schema
- `AllocationDonut` `Props` adds `sectorAllocation: SectorAllocationItem[]` — matches what overview page passes in Task 8

### Edge cases
- Assets with no sector data fall back to `asset_type.replace("_", " ").title()` — covered in service
- Empty `sectorAllocation` array shows a hint "Run sector enrichment first" — covered in component
- `market_cap_category` is informational only in this plan (stored but not displayed) — YAGNI, can add later
