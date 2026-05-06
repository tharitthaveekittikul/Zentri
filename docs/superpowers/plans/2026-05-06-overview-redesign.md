# Overview Redesign + Dual Currency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the overview dashboard with KPI cards, compact charts, and simultaneous dual-currency display (primary + secondary) sourced from user display settings.

**Architecture:** A new backend exchange rate endpoint wraps the existing `exchange_rate.py` service. A `useDualCurrency` React hook fetches display settings + exchange rate and exposes a `format(value)` function that returns both currency strings. All overview components consume this hook.

**Tech Stack:** Next.js 16 App Router, React Query (`@tanstack/react-query`), Recharts, Tailwind CSS, FastAPI, SQLAlchemy async

---

## File Map

| File | Action |
|------|--------|
| `backend/app/api/settings.py` | Add `GET /settings/exchange-rate` endpoint |
| `frontend/lib/services/settings.ts` | Create — `fetchDisplaySettings`, `fetchExchangeRate` |
| `frontend/hooks/useDualCurrency.ts` | Create — format hook |
| `frontend/components/overview/KpiCards.tsx` | Create — replaces SummaryBar |
| `frontend/components/overview/PerformanceChart.tsx` | Modify — cap height, compact empty state |
| `frontend/components/overview/AllocationDonut.tsx` | Modify — cap height, compact empty state |
| `frontend/components/net-worth-chart.tsx` | Modify — cap height, compact empty state |
| `frontend/components/overview/HoldingsSnapshot.tsx` | Modify — remove NAME col, dual currency VALUE col |
| `frontend/app/(auth)/overview/page.tsx` | Rewrite — new layout using KpiCards |

---

## Task 1: Backend — Exchange Rate Endpoint

**Files:**
- Modify: `backend/app/api/settings.py`

- [ ] **Step 1: Add the endpoint** at the bottom of `backend/app/api/settings.py`, after the existing routes:

```python
from app.services import exchange_rate as exchange_rate_service

@router.get("/exchange-rate")
async def get_exchange_rate(
    from_currency: str,
    to_currency: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rate = await exchange_rate_service.get_rate(db, from_currency, to_currency)
    if rate is None:
        raise HTTPException(status_code=503, detail="Exchange rate unavailable")
    return {"from": from_currency, "to": to_currency, "rate": str(rate)}
```

- [ ] **Step 2: Verify endpoint manually**

With the backend running:
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/settings/exchange-rate?from_currency=THB&to_currency=USD"
```
Expected: `{"from":"THB","to":"USD","rate":"0.028945"}` (approximate)

---

## Task 2: Frontend — Settings Service

**Files:**
- Create: `frontend/lib/services/settings.ts`

- [ ] **Step 1: Create the file**

```typescript
import { api } from "@/lib/api";

export interface DisplaySettings {
  currency_primary: string;
  currency_secondary: string;
}

export interface ExchangeRate {
  from: string;
  to: string;
  rate: string;
}

export async function fetchDisplaySettings(): Promise<DisplaySettings> {
  const res = await api.get("/api/v1/settings/display");
  if (!res.ok) throw new Error("Failed to fetch display settings");
  return res.json();
}

export async function fetchExchangeRate(
  fromCurrency: string,
  toCurrency: string
): Promise<ExchangeRate> {
  const res = await api.get(
    `/api/v1/settings/exchange-rate?from_currency=${fromCurrency}&to_currency=${toCurrency}`
  );
  if (!res.ok) throw new Error("Exchange rate unavailable");
  return res.json();
}
```

- [ ] **Step 2: Verify in browser console**

Open the overview page in browser devtools → Network tab → confirm `GET /api/v1/settings/display` returns `{ currency_primary, currency_secondary }` correctly.

---

## Task 3: Frontend — `useDualCurrency` Hook

**Files:**
- Create: `frontend/hooks/useDualCurrency.ts`

- [ ] **Step 1: Create the hook**

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDisplaySettings, fetchExchangeRate } from "@/lib/services/settings";

export interface DualValue {
  primary: string;
  secondary: string | null;
}

export function useDualCurrency() {
  const { data: display } = useQuery({
    queryKey: ["settings", "display"],
    queryFn: fetchDisplaySettings,
    staleTime: Infinity,
  });

  const primaryCurrency = display?.currency_primary ?? "THB";
  const secondaryCurrency = display?.currency_secondary ?? "USD";

  const { data: rateData } = useQuery({
    queryKey: ["settings", "exchange-rate", primaryCurrency, secondaryCurrency],
    queryFn: () => fetchExchangeRate(primaryCurrency, secondaryCurrency),
    enabled: !!display && primaryCurrency !== secondaryCurrency,
    staleTime: 60 * 60 * 1000,
  });

  function fmt(num: number, decimals = 2): string {
    return num.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  function format(value: string | number): DualValue {
    const num = Number(value);
    const primary = `${fmt(num)} ${primaryCurrency}`;

    let secondary: string | null = null;
    if (rateData) {
      const converted = num * Number(rateData.rate);
      secondary = `≈ ${fmt(converted)} ${secondaryCurrency}`;
    }

    return { primary, secondary };
  }

  function formatPct(value: string | number): string {
    const num = Number(value);
    return `${num >= 0 ? "+" : ""}${fmt(num)}%`;
  }

  return { format, formatPct, primaryCurrency, secondaryCurrency };
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors relating to `useDualCurrency.ts`.

---

## Task 4: Frontend — `KpiCards` Component

**Files:**
- Create: `frontend/components/overview/KpiCards.tsx`

- [ ] **Step 1: Create the component**

```typescript
"use client";

import { cn } from "@/lib/utils";
import { OverviewSummary } from "@/lib/services/overview";
import { useDualCurrency, DualValue } from "@/hooks/useDualCurrency";
import { PrivacyValue } from "@/components/ui/PrivacyValue";

interface CardProps {
  label: string;
  value: DualValue;
  pct?: string;
  direction?: "positive" | "negative" | "neutral";
}

function KpiCard({ label, value, pct, direction = "neutral" }: CardProps) {
  const isPositive = direction === "positive";
  const isNegative = direction === "negative";
  const isColored = isPositive || isNegative;

  return (
    <div
      className={cn(
        "bg-card border border-border rounded-2xl p-5",
        isPositive && "border-l-2 border-l-emerald-500",
        isNegative && "border-l-2 border-l-destructive"
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
        {label}
      </p>
      <p
        className={cn(
          "text-2xl font-semibold font-mono tabular-nums",
          isPositive && "text-emerald-600 dark:text-emerald-400",
          isNegative && "text-destructive"
        )}
      >
        <PrivacyValue value={value.primary} />
        {pct && (
          <span
            className={cn(
              "text-sm font-normal ml-2",
              isColored ? "opacity-80" : "text-muted-foreground"
            )}
          >
            <PrivacyValue value={pct} />
          </span>
        )}
      </p>
      {value.secondary && (
        <p className="text-sm text-muted-foreground font-mono tabular-nums mt-0.5">
          <PrivacyValue value={value.secondary} />
        </p>
      )}
    </div>
  );
}

interface Props {
  summary: OverviewSummary;
}

export function KpiCards({ summary }: Props) {
  const { format, formatPct } = useDualCurrency();

  const pnlPositive = Number(summary.total_pnl) >= 0;
  const dailyPositive = Number(summary.daily_change) >= 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <KpiCard
        label="Portfolio Value"
        value={format(summary.total_value)}
      />
      <KpiCard
        label="Total Cost"
        value={format(summary.total_cost)}
      />
      <KpiCard
        label="Total P&L"
        value={format(summary.total_pnl)}
        pct={formatPct(summary.total_pnl_pct)}
        direction={pnlPositive ? "positive" : "negative"}
      />
      <KpiCard
        label="Today"
        value={format(summary.daily_change)}
        pct={formatPct(summary.daily_change_pct)}
        direction={dailyPositive ? "positive" : "negative"}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no type errors.

---

## Task 5: Frontend — Compact Chart Heights + Empty States

**Files:**
- Modify: `frontend/components/net-worth-chart.tsx`
- Modify: `frontend/components/overview/PerformanceChart.tsx`
- Modify: `frontend/components/overview/AllocationDonut.tsx`

### 5a: Net Worth Chart

- [ ] **Step 1: Cap the `ResponsiveContainer` height and add compact empty state**

In `frontend/components/net-worth-chart.tsx`, find the `ResponsiveContainer` and wrap with a fixed-height container. Also find the empty/loading state and replace with a compact version.

Replace the outer wrapper div containing the chart area with:
```tsx
<div className="h-64 w-full">
  {data.length === 0 ? (
    <div className="h-full flex flex-col items-center justify-center gap-2 text-muted-foreground">
      <TrendingUp className="h-6 w-6 opacity-30" />
      <span className="text-xs">No net worth data yet</span>
    </div>
  ) : (
    <ResponsiveContainer width="100%" height="100%">
      {/* existing chart JSX unchanged */}
    </ResponsiveContainer>
  )}
</div>
```
Add `import { TrendingUp } from "lucide-react"` if not already present.

### 5b: Performance Chart

- [ ] **Step 1: Cap height and add compact empty state**

In `frontend/components/overview/PerformanceChart.tsx`, replace:
```tsx
<ResponsiveContainer width="100%" height={220}>
```
with:
```tsx
<ResponsiveContainer width="100%" height={208}>
```

Replace the current empty rendering (when `combined` is empty) with:
```tsx
{combined.length === 0 ? (
  <div className="h-52 flex flex-col items-center justify-center gap-2 text-muted-foreground">
    <Activity className="h-6 w-6 opacity-30" />
    <span className="text-xs">No performance data yet</span>
  </div>
) : (
  <ResponsiveContainer width="100%" height={208}>
    {/* existing LineChart JSX unchanged */}
  </ResponsiveContainer>
)}
```
Add `import { Activity } from "lucide-react"` if not already present.

### 5c: Allocation Donut

- [ ] **Step 1: Cap height and update existing empty state**

In `frontend/components/overview/AllocationDonut.tsx`, replace:
```tsx
<ResponsiveContainer width="100%" height={180}>
```
with:
```tsx
<ResponsiveContainer width="100%" height={160}>
```

Replace the existing empty state text:
```tsx
<p className="text-sm text-muted-foreground">No holdings with price data yet.</p>
```
with:
```tsx
<div className="h-40 flex flex-col items-center justify-center gap-2 text-muted-foreground">
  <PieChart className="h-6 w-6 opacity-30" />
  <span className="text-xs">No allocation data yet</span>
</div>
```
Add `import { PieChart } from "lucide-react"` — note: rename the recharts import to avoid collision:
```tsx
import { PieChart as RechartsPieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
```
And update the JSX tag from `<PieChart>` to `<RechartsPieChart>`.

- [ ] **Step 2: Verify all three files compile**

```bash
cd frontend && npx tsc --noEmit
```

---

## Task 6: Frontend — Update `HoldingsSnapshot`

**Files:**
- Modify: `frontend/components/overview/HoldingsSnapshot.tsx`

- [ ] **Step 1: Update the interface and table**

Replace the entire file with:

```typescript
"use client";

import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { useDualCurrency } from "@/hooks/useDualCurrency";

export interface SnapshotHolding {
  symbol: string;
  asset_type: string;
  quantity: string;
  current_value: number;
  cost_basis: number;
  pnl_pct: number;
}

interface Props {
  holdings: SnapshotHolding[];
}

export function HoldingsSnapshot({ holdings }: Props) {
  const router = useRouter();
  const { format } = useDualCurrency();

  return (
    <div className="bg-card rounded-2xl border border-border overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted/50">
            <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Symbol</th>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Type</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Quantity</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Value</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Cost Basis</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">P&amp;L%</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const value = format(h.current_value);
            const cost = format(h.cost_basis);
            return (
              <tr
                key={h.symbol}
                className="border-t border-border hover:bg-muted/40 cursor-pointer transition-colors duration-150"
                onClick={() => router.push(`/portfolio/${h.symbol}`)}
              >
                <td className="px-4 py-2.5 font-mono font-semibold">{h.symbol}</td>
                <td className="px-4 py-2.5">
                  <span className="text-xs bg-muted rounded px-1.5 py-0.5 text-muted-foreground">
                    {h.asset_type.replace("_", " ")}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                  <PrivacyValue value={Number(h.quantity).toFixed(4)} />
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                  <div><PrivacyValue value={value.primary} /></div>
                  {value.secondary && (
                    <div className="text-xs text-muted-foreground"><PrivacyValue value={value.secondary} /></div>
                  )}
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                  <div><PrivacyValue value={cost.primary} /></div>
                  {cost.secondary && (
                    <div className="text-xs text-muted-foreground"><PrivacyValue value={cost.secondary} /></div>
                  )}
                </td>
                <td
                  className={cn(
                    "px-4 py-2.5 text-right font-mono tabular-nums",
                    h.pnl_pct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
                  )}
                >
                  <PrivacyValue value={`${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct.toFixed(2)}%`} />
                </td>
              </tr>
            );
          })}
          {holdings.length === 0 && (
            <tr>
              <td colSpan={6} className="py-10">
                <div className="flex flex-col items-center gap-2 text-muted-foreground">
                  <span className="text-xl">📊</span>
                  <span className="text-sm font-medium">No holdings yet</span>
                  <span className="text-xs">Add assets in the Portfolio tab.</span>
                </div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit
```

---

## Task 7: Frontend — Rewrite Overview Page

**Files:**
- Modify: `frontend/app/(auth)/overview/page.tsx`

- [ ] **Step 1: Rewrite the page**

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchOverviewSummary, fetchAllocation } from "@/lib/services/overview";
import { fetchHoldings } from "@/lib/services/portfolio";
import { KpiCards } from "@/components/overview/KpiCards";
import { PerformanceChart } from "@/components/overview/PerformanceChart";
import { AllocationDonut } from "@/components/overview/AllocationDonut";
import { HoldingsSnapshot, SnapshotHolding } from "@/components/overview/HoldingsSnapshot";
import { Skeleton } from "@/components/ui/skeleton";
import { NetWorthChart } from "@/components/net-worth-chart";

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

  const snapshotHoldings: SnapshotHolding[] = holdings
    .map((h) => ({
      symbol: h.symbol,
      asset_type: h.asset_type,
      quantity: h.outstanding_shares,
      current_value: h.holding_value != null ? Number(h.holding_value) : Number(h.total_cost),
      cost_basis: Number(h.total_cost),
      pnl_pct: 0,
    }))
    .sort((a, b) => b.current_value - a.current_value);

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      {summaryLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
      ) : summary ? (
        <KpiCards summary={summary} />
      ) : null}

      <div className="bg-card rounded-2xl border border-border p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-3">
          Net Worth
        </p>
        <NetWorthChart privacyMode={false} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 bg-card rounded-2xl border border-border p-5 overflow-hidden">
          <PerformanceChart />
        </div>
        <div className="lg:col-span-2 bg-card rounded-2xl border border-border p-5 overflow-hidden">
          <AllocationDonut allocation={allocation} />
        </div>
      </div>

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-3">
          Holdings
        </p>
        <HoldingsSnapshot holdings={snapshotHoldings} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify compile + visual check**

```bash
cd frontend && npx tsc --noEmit
```

Open `http://localhost:3000/overview` in the browser and verify:
- 4 KPI cards show with primary + secondary currency values
- Net Worth card has fixed height (no huge blank space)
- Performance and Allocation charts have fixed heights
- Holdings table has no NAME column, shows VALUE with dual currency
- All monetary values show `6,987,432.00 THB` on line 1, `≈ 202,989.37 USD` on line 2

---

## Self-Review Notes

- `SnapshotHolding` interface changed: removed `name`, added `cost_basis`. The page (Task 7) builds `cost_basis: Number(h.total_cost)`. Consistent.
- `KpiCards` consumes `OverviewSummary` directly from `@/lib/services/overview` — same type as current page. No changes needed to that service.
- Exchange rate stale time is 1 hour — appropriate for a display conversion.
- If `fetchExchangeRate` fails (503), `rateData` stays `undefined` and `secondary` is `null` — graceful degradation, only primary value shown.
- `PieChart` lucide import collision in AllocationDonut resolved by aliasing recharts import to `RechartsPieChart`.
