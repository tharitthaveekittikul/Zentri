# Allocation Page with Drill-Down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `/allocation` page with a full-page drill-down donut chart and a synced holdings table.

**Architecture:** Single new backend endpoint returns all holdings with symbol/sector/type/value/pct. Frontend groups holdings client-side for the donut, filters for the table based on drill-down state. The existing Overview `AllocationDonut` widget is untouched.

**Tech Stack:** FastAPI + Pydantic (backend), Next.js + React Query + Recharts + Tailwind (frontend)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/schemas/overview.py` | Add `HoldingAllocationItem` schema |
| Modify | `backend/app/services/overview.py` | Add `get_allocation_holdings()` |
| Modify | `backend/app/api/overview.py` | Add `GET /allocation/holdings` route |
| Modify | `backend/tests/test_overview.py` | Tests for the new endpoint |
| Modify | `frontend/lib/services/overview.ts` | Add type + fetch function |
| Create | `frontend/components/allocation/AllocationDrillDonut.tsx` | Drill-down donut component |
| Create | `frontend/components/allocation/AllocationTable.tsx` | Holdings table component |
| Create | `frontend/app/(auth)/allocation/page.tsx` | Allocation page |
| Modify | `frontend/components/layout/Sidebar.tsx` | Add Allocation nav item |

---

## Task 1: Add `HoldingAllocationItem` Pydantic schema

**Files:**
- Modify: `backend/app/schemas/overview.py`

- [ ] **Step 1: Add schema to overview.py**

Open `backend/app/schemas/overview.py` and append after `SectorAllocationItem`:

```python
class HoldingAllocationItem(BaseModel):
    symbol: str
    name: str
    sector: str
    asset_type: str
    value: Decimal
    pct_of_total: Decimal
```

---

## Task 2: Add `get_allocation_holdings()` service function

**Files:**
- Modify: `backend/app/services/overview.py`

- [ ] **Step 1: Add function after `get_sector_allocation`**

In `backend/app/services/overview.py`, add after the `get_sector_allocation` function (after line ~192):

```python
async def get_allocation_holdings(db: AsyncSession, user_id: uuid.UUID, target_currency: str = "USD") -> list[dict]:
    holdings = list((await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )).scalars().all())

    rows = []
    total_value = Decimal("0")

    for h in holdings:
        latest = await _latest_price(db, h.asset_id)
        if not latest:
            continue
        asset = (await db.execute(
            select(Asset).where(Asset.id == h.asset_id)
        )).scalar_one_or_none()
        if not asset:
            continue
        rate = await fx_service.get_rate(db, asset.currency, target_currency)
        value = h.quantity * latest.close * (rate if rate else Decimal("1"))
        sector = asset.sector or asset.asset_type.replace("_", " ").title()
        rows.append({
            "symbol": asset.symbol,
            "name": asset.name or asset.symbol,
            "sector": sector,
            "asset_type": asset.asset_type,
            "value": value,
        })
        total_value += value

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
            value = balance * rate if rate else balance
            rows.append({
                "symbol": ca.symbol,
                "name": ca.name or ca.symbol,
                "sector": "Cash",
                "asset_type": "cash",
                "value": value,
            })
            total_value += value

    if not total_value:
        return []

    rows.sort(key=lambda r: r["value"], reverse=True)
    logger.info("AllocationHoldings: user=%s count=%s", user_id, len(rows))
    return [{**r, "pct_of_total": r["value"] / total_value * 100} for r in rows]
```

---

## Task 3: Add backend route + tests

**Files:**
- Modify: `backend/app/api/overview.py`
- Modify: `backend/tests/test_overview.py`

- [ ] **Step 1: Write failing tests first**

Append to `backend/tests/test_overview.py`:

```python
@pytest.mark.asyncio
async def test_allocation_holdings_empty(auth_client):
    res = await auth_client.get("/api/v1/overview/allocation/holdings")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_allocation_holdings_no_prices(auth_client, asset_with_holding):
    res = await auth_client.get("/api/v1/overview/allocation/holdings")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_allocation_holdings_schema_fields(auth_client, asset_with_holding):
    # With no prices the list is empty — verify the endpoint itself returns valid JSON
    # (full field-shape test requires a price fixture; verify structure here)
    res = await auth_client.get("/api/v1/overview/allocation/holdings")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
```

- [ ] **Step 2: Run tests — expect 404 (route not yet added)**

```bash
cd backend && python -m pytest tests/test_overview.py::test_allocation_holdings_empty -v
```

Expected: FAIL with 404 or import error.

- [ ] **Step 3: Add route to `backend/app/api/overview.py`**

Update the import line at the top to include `HoldingAllocationItem`:

```python
from app.schemas.overview import AllocationItem, HoldingAllocationItem, NetWorthPoint, OverviewSummary, PerformanceResponse, SectorAllocationItem
```

Add the new route **before** the existing `/allocation` route (to avoid prefix conflicts):

```python
@router.get("/allocation/holdings", response_model=list[HoldingAllocationItem])
async def get_allocation_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await overview_service.get_allocation_holdings(db, current_user.id, current_user.currency_primary)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && python -m pytest tests/test_overview.py::test_allocation_holdings_empty tests/test_overview.py::test_allocation_holdings_no_prices tests/test_overview.py::test_allocation_holdings_schema_fields -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd backend && python -m pytest tests/test_overview.py -v
```

Expected: all tests PASS.

---

## Task 4: Add frontend service type and fetch function

**Files:**
- Modify: `frontend/lib/services/overview.ts`

- [ ] **Step 1: Add type and fetch function**

In `frontend/lib/services/overview.ts`, add after the `SectorAllocationItem` interface:

```ts
export interface HoldingAllocationItem {
  symbol: string;
  name: string;
  sector: string;
  asset_type: string;
  value: string;
  pct_of_total: string;
}
```

Add after the `fetchSectorAllocation` function:

```ts
export async function fetchAllocationHoldings(): Promise<HoldingAllocationItem[]> {
  const res = await api.get("/api/v1/overview/allocation/holdings");
  if (!res.ok) throw new Error("Failed to fetch allocation holdings");
  return res.json();
}
```

---

## Task 5: Create `AllocationDrillDonut` component

**Files:**
- Create: `frontend/components/allocation/AllocationDrillDonut.tsx`

- [ ] **Step 1: Create the component**

```tsx
"use client";

import { memo, useMemo } from "react";
import {
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { PieChart as PieChartIcon } from "lucide-react";
import { HoldingAllocationItem } from "@/lib/services/overview";
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
  holdings: HoldingAllocationItem[];
  tab: "type" | "sector";
  onTabChange: (tab: "type" | "sector") => void;
  selectedGroup: string | null;
  onSelectGroup: (group: string) => void;
  onClearGroup: () => void;
}

function groupKey(h: HoldingAllocationItem, tab: "type" | "sector"): string {
  return tab === "type" ? h.asset_type.replace(/_/g, " ").toUpperCase() : h.sector;
}

export const AllocationDrillDonut = memo(function AllocationDrillDonut({
  holdings,
  tab,
  onTabChange,
  selectedGroup,
  onSelectGroup,
  onClearGroup,
}: Props) {
  const { primaryCurrency } = useDualCurrency();
  const { isPrivate } = usePrivacyStore();

  const data = useMemo(() => {
    if (selectedGroup) {
      const group = holdings.filter((h) => groupKey(h, tab) === selectedGroup);
      const groupTotal = group.reduce((s, h) => s + Number(h.value), 0) || 1;
      return group.map((h) => ({
        name: h.symbol,
        value: (Number(h.value) / groupTotal) * 100,
        rawValue: Number(h.value),
      }));
    }
    const grouped: Record<string, { value: number; rawValue: number }> = {};
    for (const h of holdings) {
      const key = groupKey(h, tab);
      if (!grouped[key]) grouped[key] = { value: 0, rawValue: 0 };
      grouped[key].value += Number(h.pct_of_total);
      grouped[key].rawValue += Number(h.value);
    }
    return Object.entries(grouped)
      .map(([name, d]) => ({ name, value: d.value, rawValue: d.rawValue }))
      .sort((a, b) => b.value - a.value);
  }, [holdings, tab, selectedGroup]);

  const dominant = data.length > 0
    ? data.reduce((max, item) => (item.value > max.value ? item : max), data[0])
    : null;

  const isEmpty = data.length === 0;

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Allocation</p>
        {selectedGroup ? (
          <button
            onClick={onClearGroup}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            ← {selectedGroup}
          </button>
        ) : (
          <div className="flex rounded-md overflow-hidden border border-border text-xs">
            <button
              className={`px-2 py-0.5 transition-colors ${tab === "type" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
              onClick={() => onTabChange("type")}
            >
              By Type
            </button>
            <button
              className={`px-2 py-0.5 transition-colors ${tab === "sector" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
              onClick={() => onTabChange("sector")}
            >
              By Sector
            </button>
          </div>
        )}
      </div>

      {isEmpty ? (
        <div className="h-48 flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <PieChartIcon className="h-6 w-6 opacity-30" />
          <span className="text-xs">
            {tab === "sector" && !selectedGroup ? "Run sector enrichment first" : "No data"}
          </span>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="relative mx-auto">
            <ResponsiveContainer width={180} height={180}>
              <RechartsPieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={58}
                  outerRadius={82}
                  dataKey="value"
                  paddingAngle={2}
                  startAngle={90}
                  endAngle={-270}
                  onClick={!selectedGroup ? (entry) => onSelectGroup(entry.name) : undefined}
                >
                  {data.map((_, i) => (
                    <Cell
                      key={i}
                      fill={COLORS[i % COLORS.length]}
                      style={{ cursor: !selectedGroup ? "pointer" : "default" }}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: unknown) => [`${Number(v).toFixed(1)}%`, ""]}
                  contentStyle={{ fontSize: "11px" }}
                />
              </RechartsPieChart>
            </ResponsiveContainer>
            {dominant && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[9px] text-muted-foreground leading-tight text-center px-3 truncate max-w-[100px]">
                  {dominant.name}
                </span>
                <span className="text-base font-semibold leading-tight">
                  {dominant.value.toFixed(0)}%
                </span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            {data.map((item, i) => (
              <div
                key={item.name}
                className={`flex items-center gap-1.5 ${!selectedGroup ? "cursor-pointer hover:opacity-80" : ""}`}
                onClick={!selectedGroup ? () => onSelectGroup(item.name) : undefined}
              >
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

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i "AllocationDrillDonut"
```

Expected: no errors mentioning this file.

---

## Task 6: Create `AllocationTable` component

**Files:**
- Create: `frontend/components/allocation/AllocationTable.tsx`

- [ ] **Step 1: Create the component**

```tsx
"use client";

import { memo, useMemo, useState } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";
import { HoldingAllocationItem } from "@/lib/services/overview";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { usePrivacyStore } from "@/store/privacy";

function formatCompact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return value.toFixed(0);
}

interface Props {
  holdings: HoldingAllocationItem[];
}

export const AllocationTable = memo(function AllocationTable({ holdings }: Props) {
  const { primaryCurrency } = useDualCurrency();
  const { isPrivate } = usePrivacyStore();
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(
    () =>
      [...holdings].sort((a, b) =>
        sortDir === "desc"
          ? Number(b.value) - Number(a.value)
          : Number(a.value) - Number(b.value),
      ),
    [holdings, sortDir],
  );

  if (holdings.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
        No holdings yet
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left py-2 pr-3 font-medium text-muted-foreground">Symbol</th>
            <th className="text-left py-2 pr-3 font-medium text-muted-foreground">Name</th>
            <th className="text-left py-2 pr-3 font-medium text-muted-foreground">Sector</th>
            <th className="text-left py-2 pr-3 font-medium text-muted-foreground">Type</th>
            <th
              className="text-right py-2 pr-3 font-medium text-muted-foreground cursor-pointer select-none hover:text-foreground"
              onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
            >
              <span className="inline-flex items-center gap-0.5">
                Value
                {sortDir === "desc" ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronUp className="h-3 w-3" />
                )}
              </span>
            </th>
            <th className="text-right py-2 font-medium text-muted-foreground">Weight %</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((h) => (
            <tr key={h.symbol} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
              <td className="py-2 pr-3 font-mono font-medium">{h.symbol}</td>
              <td className="py-2 pr-3 text-muted-foreground truncate max-w-[140px]">{h.name}</td>
              <td className="py-2 pr-3 text-muted-foreground">{h.sector}</td>
              <td className="py-2 pr-3 text-muted-foreground">
                {h.asset_type.replace(/_/g, " ").toUpperCase()}
              </td>
              <td className="py-2 pr-3 font-mono tabular-nums text-right">
                {isPrivate ? "******" : formatCompact(Number(h.value))} {primaryCurrency}
              </td>
              <td className="py-2 font-mono tabular-nums text-right text-muted-foreground">
                {Number(h.pct_of_total).toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i "AllocationTable"
```

Expected: no errors.

---

## Task 7: Create the Allocation page

**Files:**
- Create: `frontend/app/(auth)/allocation/page.tsx`

- [ ] **Step 1: Create the page**

```tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAllocationHoldings, HoldingAllocationItem } from "@/lib/services/overview";
import { AllocationDrillDonut } from "@/components/allocation/AllocationDrillDonut";
import { AllocationTable } from "@/components/allocation/AllocationTable";

function groupKey(h: HoldingAllocationItem, tab: "type" | "sector"): string {
  return tab === "type" ? h.asset_type.replace(/_/g, " ").toUpperCase() : h.sector;
}

export default function AllocationPage() {
  const [tab, setTab] = useState<"type" | "sector">("type");
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);

  const { data: holdings = [] } = useQuery({
    queryKey: ["allocation", "holdings"],
    queryFn: fetchAllocationHoldings,
  });

  const tableHoldings = selectedGroup
    ? holdings.filter((h) => groupKey(h, tab) === selectedGroup)
    : holdings;

  function handleTabChange(newTab: "type" | "sector") {
    setTab(newTab);
    setSelectedGroup(null);
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Allocation</h1>
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        <div className="w-full lg:w-[380px] shrink-0 bg-card rounded-2xl p-6 border border-border">
          <AllocationDrillDonut
            holdings={holdings}
            tab={tab}
            onTabChange={handleTabChange}
            selectedGroup={selectedGroup}
            onSelectGroup={setSelectedGroup}
            onClearGroup={() => setSelectedGroup(null)}
          />
        </div>
        <div className="flex-1 min-w-0 bg-card rounded-2xl p-6 border border-border">
          <p className="text-sm font-medium mb-4">
            {selectedGroup ? selectedGroup : "All Holdings"}
          </p>
          <AllocationTable holdings={tableHoldings} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check the full frontend**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

---

## Task 8: Add Allocation to sidebar navigation

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add `PieChart` to lucide-react import**

In `frontend/components/layout/Sidebar.tsx`, update the import block:

```tsx
import {
  LayoutDashboard,
  Briefcase,
  PieChart,
  Star,
  TrendingUp,
  CalendarDays,
  Receipt,
  Activity,
  Bot,
  MessageSquare,
  Settings,
  Upload,
  HardDrive,
  BarChart2,
} from "lucide-react";
```

- [ ] **Step 2: Add Allocation to navItems and update slice**

Replace the `navItems` array and `mainNavItems` line:

```tsx
const navItems = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/allocation", label: "Allocation", icon: PieChart },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/net-worth", label: "Net Worth", icon: TrendingUp },
  { href: "/events", label: "Events", icon: CalendarDays },
  { href: "/transactions", label: "Transactions", icon: Receipt },
  { href: "/pipeline", label: "Pipeline", icon: Activity },
  { href: "/import", label: "Import", icon: Upload },
  { href: "/analysis", label: "Analysis", icon: BarChart2 },
  { href: "/ai-usage", label: "AI Usage", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/settings/backup", label: "Backup", icon: HardDrive },
];

const mainNavItems = navItems.slice(0, 6);
const toolNavItems = navItems.slice(6);
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Start dev server and verify**

```bash
cd frontend && npm run dev
```

Navigate to `http://localhost:3000/allocation`. Verify:
1. "Allocation" appears in the sidebar under Portfolio section
2. The page loads with donut + table side by side
3. Clicking a slice in the donut drills down: donut re-renders with symbols, table filters, breadcrumb pill appears
4. Clicking the breadcrumb pill resets to top-level view
5. Switching tab (By Type ↔ By Sector) resets drill-down
6. Privacy mode masks values in both donut legend and table
