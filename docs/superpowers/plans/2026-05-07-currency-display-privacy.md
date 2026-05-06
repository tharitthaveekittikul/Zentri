# Currency Display & Privacy Masking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all hardcoded `$` currency displays with a consistent dual-currency system that respects user settings, and redesign privacy mode to show `****** {CURRENCY}` instead of hiding the entire string.

**Architecture:** Add `formatNative()` + currency label fields to `useDualCurrency`, create a new `DualCurrencyAmount` shared component that owns both stacked rendering and privacy masking, then fix each broken page/component to use it.

**Tech Stack:** Next.js (App Router), React, TypeScript, TanStack Query (`useQuery`), Zustand (`usePrivacyStore`), Tailwind CSS

---

## File Map

| Action | File |
|--------|------|
| Modify | `frontend/hooks/useDualCurrency.ts` |
| Create | `frontend/components/ui/DualCurrencyAmount.tsx` |
| Modify | `frontend/components/ui/PrivacyValue.tsx` |
| Modify | `frontend/components/overview/KpiCards.tsx` |
| Modify | `frontend/components/overview/HoldingsSnapshot.tsx` |
| Modify | `frontend/components/overview/AllocationDonut.tsx` |
| Modify | `frontend/components/portfolio/HoldingsTable.tsx` |
| Modify | `frontend/components/overview/SummaryBar.tsx` |
| Modify | `frontend/components/net-worth-chart.tsx` |
| Modify | `frontend/components/portfolio/CashAccountsSection.tsx` |
| Modify | `frontend/app/(auth)/portfolio/[symbol]/page.tsx` |
| Modify | `frontend/app/(auth)/watchlist/page.tsx` |
| Modify | `frontend/app/(auth)/events/page.tsx` |
| Modify | `frontend/app/(auth)/transactions/page.tsx` |

---

## Task 1: Extend `useDualCurrency` — add `formatNative` and currency labels to `DualValue`

**Files:**
- Modify: `frontend/hooks/useDualCurrency.ts`

- [ ] **Step 1: Replace the full file content**

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDisplaySettings, fetchExchangeRate } from "@/lib/services/settings";

export interface DualValue {
  primary: string;
  secondary: string | null;
  primaryCurrency: string;
  secondaryCurrency: string;
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

  // Use when the value is already in primaryCurrency.
  function format(value: string | number): DualValue {
    const num = Number(value);
    const primary = `${fmt(num)} ${primaryCurrency}`;

    let secondary: string | null = null;
    if (rateData) {
      const converted = num * Number(rateData.rate);
      secondary = `≈ ${fmt(converted)} ${secondaryCurrency}`;
    }

    return { primary, secondary, primaryCurrency, secondaryCurrency };
  }

  // Use when the value is in a native asset currency that may differ from primaryCurrency.
  // Converts to primary (and secondary) if the native currency matches one of the two.
  // Falls back to native currency label when no conversion is possible.
  function formatNative(value: string | number, nativeCurrency: string): DualValue {
    const num = Number(value);
    const native = nativeCurrency.toUpperCase();
    const primary = primaryCurrency.toUpperCase();
    const secondary = secondaryCurrency.toUpperCase();
    const rate = rateData ? Number(rateData.rate) : null;

    if (native === primary) {
      return format(value);
    }

    if (native === secondary && rate !== null && rate > 0) {
      const primaryVal = num / rate;
      return {
        primary: `${fmt(primaryVal)} ${primaryCurrency}`,
        secondary: `≈ ${fmt(num)} ${secondaryCurrency}`,
        primaryCurrency,
        secondaryCurrency,
      };
    }

    // Unknown currency pair — show native only.
    return {
      primary: `${fmt(num)} ${nativeCurrency}`,
      secondary: null,
      primaryCurrency: nativeCurrency,
      secondaryCurrency,
    };
  }

  function formatPct(value: string | number): string {
    const num = Number(value);
    return `${num >= 0 ? "+" : ""}${fmt(num)}%`;
  }

  return { format, formatNative, formatPct, primaryCurrency, secondaryCurrency };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors (or only pre-existing errors unrelated to this file).

---

## Task 2: Create `DualCurrencyAmount` component

**Files:**
- Create: `frontend/components/ui/DualCurrencyAmount.tsx`

- [ ] **Step 1: Create the file**

```typescript
"use client";

import { cn } from "@/lib/utils";
import { usePrivacyStore } from "@/store/privacy";
import { DualValue } from "@/hooks/useDualCurrency";

interface Props {
  value: DualValue;
  primaryClassName?: string;
  // inline=true: "1,234.56 THB (≈ 45.67 USD)" on one line — for table cells
  // inline=false (default): primary on top, secondary muted below — for cards/KPIs
  inline?: boolean;
}

export function DualCurrencyAmount({
  value,
  primaryClassName,
  inline = false,
}: Props) {
  const { isPrivate } = usePrivacyStore();

  const primaryDisplay = isPrivate
    ? `****** ${value.primaryCurrency}`
    : value.primary;

  const secondaryDisplay =
    value.secondary === null
      ? null
      : isPrivate
        ? `≈ ****** ${value.secondaryCurrency}`
        : value.secondary;

  if (inline) {
    return (
      <span className={cn("font-mono tabular-nums", primaryClassName)}>
        {primaryDisplay}
        {secondaryDisplay && (
          <span className="text-muted-foreground ml-1 text-xs">
            ({secondaryDisplay})
          </span>
        )}
      </span>
    );
  }

  return (
    <div>
      <span className={cn("font-mono tabular-nums", primaryClassName)}>
        {primaryDisplay}
      </span>
      {secondaryDisplay && (
        <p className="text-sm text-muted-foreground font-mono tabular-nums mt-0.5">
          {secondaryDisplay}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors from `DualCurrencyAmount.tsx`.

---

## Task 3: Migrate `KpiCards` to `DualCurrencyAmount`

**Files:**
- Modify: `frontend/components/overview/KpiCards.tsx`

`KpiCards` currently wraps `value.primary` and `value.secondary` in separate `PrivacyValue` spans. After Task 3's `PrivacyValue` change to `******`, the currency label would be hidden. Replace with `DualCurrencyAmount` which handles privacy correctly.

- [ ] **Step 1: Replace the full file content**

```typescript
"use client";

import { cn } from "@/lib/utils";
import { OverviewSummary } from "@/lib/services/overview";
import { useDualCurrency, DualValue } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";

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
        "card-surface border border-border rounded-2xl p-4 flex flex-col gap-1"
      )}
    >
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </p>
      <DualCurrencyAmount
        value={value}
        primaryClassName={cn(
          "text-xl font-semibold tracking-tight",
          isColored && (isPositive ? "" : ""),
        )}
      />
      {pct && (
        <p
          className={cn(
            "text-sm font-mono tabular-nums",
            isColored ? "opacity-80" : "text-muted-foreground",
          )}
          style={{
            color: isPositive
              ? "var(--signal-gain-text)"
              : isNegative
                ? "var(--destructive)"
                : undefined,
          }}
        >
          {pct}
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

Note: The `primaryClassName` color for P&L is controlled by `direction` — match the original's color logic by reading the current `KpiCards.tsx` and preserving the `style` prop or `cn` class for the primary value. The template above passes `direction` to the card but does not yet apply color to `DualCurrencyAmount.primaryClassName`. Open the current file and check lines 36–43 for the original color logic, then apply via `primaryClassName` as needed.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

---

## Task 4: Migrate `HoldingsSnapshot` to `DualCurrencyAmount`

**Files:**
- Modify: `frontend/components/overview/HoldingsSnapshot.tsx`

`HoldingsSnapshot` uses `format()` and renders `value.primary` / `value.secondary` manually with `PrivacyValue`. Replace with `DualCurrencyAmount`.

- [ ] **Step 1: Replace imports in `HoldingsSnapshot.tsx`**

Find:
```typescript
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { useDualCurrency } from "@/hooks/useDualCurrency";
```

Replace with:
```typescript
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
```

- [ ] **Step 2: Replace monetary table cells**

In the `holdings.map()` loop, find the cells that render `value.primary`/`value.secondary` (current value and cost basis). Replace each with `DualCurrencyAmount`:

```typescript
// Current value cell — replace PrivacyValue wrapping of value.primary/secondary with:
<td className="px-4 py-3 text-right font-mono tabular-nums text-sm">
  <DualCurrencyAmount value={format(h.current_value)} />
</td>

// Cost basis cell:
<td className="px-4 py-3 text-right font-mono tabular-nums text-sm">
  <DualCurrencyAmount value={format(h.cost_basis)} />
</td>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

---

## Task 5: Migrate `AllocationDonut` to `DualCurrencyAmount`

**Files:**
- Modify: `frontend/components/overview/AllocationDonut.tsx`

`AllocationDonut` uses `format(item.rawValue).primary` inside a `PrivacyValue`. Replace with `DualCurrencyAmount inline`.

- [ ] **Step 1: Replace imports**

Find:
```typescript
import { PrivacyValue } from "@/components/ui/PrivacyValue";
```

Replace with:
```typescript
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
```

- [ ] **Step 2: Replace the `PrivacyValue` wrapping `format(...).primary`**

Find:
```typescript
<PrivacyValue value={`${format(item.rawValue).primary} (${item.value.toFixed(1)}%)`} />
```

Replace with:
```typescript
<span>
  <DualCurrencyAmount value={format(item.rawValue)} inline />
  <span className="text-muted-foreground ml-1">({item.value.toFixed(1)}%)</span>
</span>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

---

## Task 6: Update `PrivacyValue` mask character (do this AFTER Tasks 3–5)

**Files:**
- Modify: `frontend/components/ui/PrivacyValue.tsx`

- [ ] **Step 1: Change `••••` to `******`**

Current line 14:
```typescript
return <span className={cn(className)}>{isPrivate ? "••••" : value}</span>;
```

Replace with:
```typescript
return <span className={cn(className)}>{isPrivate ? "******" : value}</span>;
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

---

## Task 7: Update `MoneyCell` privacy masking in `HoldingsTable`

**Files:**
- Modify: `frontend/components/portfolio/HoldingsTable.tsx` (lines 101–143)

- [ ] **Step 1: Add `usePrivacyStore` import**

Find the existing import block at the top of the file (around line 1–35). Add this import after the existing imports:

```typescript
import { usePrivacyStore } from "@/store/privacy";
```

- [ ] **Step 2: Replace the `MoneyCell` function body (lines 101–143)**

Replace the entire `MoneyCell` function with:

```typescript
  function MoneyCell({
    val,
    nativeCurrency,
  }: {
    val: string | null | undefined;
    nativeCurrency: string;
  }) {
    const { isPrivate } = usePrivacyStore();
    if (val == null) return <span>—</span>;
    const num = Number(val);
    const native = nativeCurrency.toUpperCase();
    const primary = primaryCurrency.toUpperCase();
    const secondary = secondaryCurrency?.toUpperCase();

    let primaryVal: number = num;
    let secondaryVal: number | null = null;

    if (native === primary) {
      primaryVal = num;
      if (primaryToSecondaryRate != null && secondaryCurrency) {
        secondaryVal = num * primaryToSecondaryRate;
      }
    } else if (
      native === secondary &&
      primaryToSecondaryRate != null &&
      primaryToSecondaryRate > 0
    ) {
      primaryVal = num / primaryToSecondaryRate;
      secondaryVal = num;
    } else {
      if (isPrivate) return <span>****** {nativeCurrency}</span>;
      return <span>{fmt(num, nativeCurrency)}</span>;
    }

    if (isPrivate) {
      return (
        <span>
          ****** {primaryCurrency}
          {secondaryCurrency && (
            <span className="block text-xs text-muted-foreground">
              ≈ ****** {secondaryCurrency}
            </span>
          )}
        </span>
      );
    }

    return (
      <span>
        {fmt(primaryVal, primaryCurrency)}
        {secondaryCurrency && secondaryVal != null && (
          <span className="block text-xs text-muted-foreground">
            ≈ {fmt(secondaryVal, secondaryCurrency)}
          </span>
        )}
      </span>
    );
  }
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

---

## Task 8: Fix `SummaryBar` — remove hardcoded `$`

**Files:**
- Modify: `frontend/components/overview/SummaryBar.tsx`

- [ ] **Step 1: Replace the full file content**

```typescript
"use client";

import { OverviewSummary } from "@/lib/services/overview";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";

interface Props {
  summary: OverviewSummary;
}

export function SummaryBar({ summary }: Props) {
  const { format, formatPct } = useDualCurrency();
  const pnlPositive = Number(summary.total_pnl) >= 0;
  const dailyPositive = Number(summary.daily_change) >= 0;

  return (
    <div className="flex flex-wrap gap-8 items-start px-6 py-5 bg-card card-surface rounded-2xl border border-border">
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Portfolio Value</p>
        <DualCurrencyAmount
          value={format(summary.total_value)}
          primaryClassName="text-3xl font-semibold tracking-tight"
        />
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Total Cost</p>
        <DualCurrencyAmount
          value={format(summary.total_cost)}
          primaryClassName="text-base font-semibold"
        />
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Total P&amp;L</p>
        <div className="flex items-center gap-2">
          <DualCurrencyAmount
            value={format(summary.total_pnl)}
            primaryClassName={cn(
              "text-base font-semibold",
              pnlPositive ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
            )}
          />
          <Badge variant={pnlPositive ? "default" : "destructive"} className="text-xs font-mono tabular-nums self-start mt-0.5">
            {formatPct(summary.total_pnl_pct)}
          </Badge>
        </div>
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Today</p>
        <div className="flex items-center gap-2">
          <DualCurrencyAmount
            value={format(summary.daily_change)}
            primaryClassName={cn(
              "text-base font-semibold",
              dailyPositive ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
            )}
          />
          <Badge variant={dailyPositive ? "default" : "destructive"} className="text-xs font-mono tabular-nums self-start mt-0.5">
            {formatPct(summary.daily_change_pct)}
          </Badge>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

---

## Task 9: Fix `net-worth-chart` — convert `value_usd`/`cost_usd` to primary currency

**Files:**
- Modify: `frontend/components/net-worth-chart.tsx`

The chart currently plots raw USD values (`value_usd`, `cost_usd`) but labels with `primaryCurrency`. The fix fetches the USD→primary exchange rate and multiplies chart data before plotting.

- [ ] **Step 1: Add `useQuery` and `fetchExchangeRate` imports**

At the top of the file, the current imports are:
```typescript
import { useEffect, useRef, useState } from "react";
// ...
import { useDualCurrency } from "@/hooks/useDualCurrency";
```

Add `useQuery` to the React imports and add `fetchExchangeRate`:
```typescript
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
// ...
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { fetchExchangeRate } from "@/lib/services/settings";
```

- [ ] **Step 2: Add exchange rate query and `conversionRate` variable**

After the existing `const { primaryCurrency } = useDualCurrency();` line, add:

```typescript
const { data: usdToPrimary } = useQuery({
  queryKey: ["exchange-rate", "USD", primaryCurrency],
  queryFn: () => fetchExchangeRate("USD", primaryCurrency),
  enabled: primaryCurrency !== "USD",
  staleTime: 60 * 60 * 1000,
});

const conversionRate =
  primaryCurrency === "USD" ? 1 : usdToPrimary ? Number(usdToPrimary.rate) : null;
```

- [ ] **Step 3: Update the `useEffect` to use `conversionRate`**

Find the existing `useEffect` that calls `fetchNetWorthTimeline`. Replace it with:

```typescript
useEffect(() => {
  if (conversionRate === null) return;
  setLoading(true);
  fetchNetWorthTimeline(range)
    .then((points) => {
      setData(points);
      if (!valueSeriesRef.current || !costSeriesRef.current) return;
      const valueData = points.map((p) => ({
        time: p.date,
        value: parseFloat(p.value_usd) * conversionRate,
      }));
      const costData = points.map((p) => ({
        time: p.date,
        value: parseFloat(p.cost_usd) * conversionRate,
      }));
      valueSeriesRef.current.setData(valueData);
      costSeriesRef.current.setData(costData);
      chartRef.current?.timeScale().fitContent();
    })
    .catch(console.error)
    .finally(() => setLoading(false));
}, [range, conversionRate]);
```

- [ ] **Step 4: Update the display value calculations**

Find these two lines:
```typescript
const currentValue = latest ? parseFloat(latest.value_usd) : 0;
const currentCost = latest ? parseFloat(latest.cost_usd) : 0;
```

Replace with:
```typescript
const rate = conversionRate ?? 1;
const currentValue = latest ? parseFloat(latest.value_usd) * rate : 0;
const currentCost = latest ? parseFloat(latest.cost_usd) * rate : 0;
```

- [ ] **Step 5: Update the `fmt` function to respect privacy correctly**

Find:
```typescript
const fmt = (v: number) =>
  privacyMode
    ? "***"
    : `${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${primaryCurrency}`;
```

Replace with:
```typescript
const fmt = (v: number) =>
  privacyMode
    ? `****** ${primaryCurrency}`
    : `${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${primaryCurrency}`;
```

- [ ] **Step 6: Update `fmtPnl` privacy string**

Find:
```typescript
const fmtPnl = () => {
  if (privacyMode) return "***";
```

Replace with:
```typescript
const fmtPnl = () => {
  if (privacyMode) return `****** ${primaryCurrency}`;
```

- [ ] **Step 7: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

---

## Task 10: Fix `CashAccountsSection` — add dual-currency display for balances

**Files:**
- Modify: `frontend/components/portfolio/CashAccountsSection.tsx`

- [ ] **Step 1: Add imports**

In the existing import block at the top of the file, add:
```typescript
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
```

Remove the existing `PrivacyValue` import since it will no longer be used for the balance display:
```typescript
// Remove this line:
import { PrivacyValue } from "@/components/ui/PrivacyValue";
```

- [ ] **Step 2: Call `useDualCurrency` inside the component**

At the top of the `CashAccountsSection` function body (after the `useState` declarations), add:

```typescript
const { formatNative } = useDualCurrency();
```

- [ ] **Step 3: Replace the balance display block**

Find this block (around lines 159–168):
```typescript
<div className="text-2xl font-semibold font-mono tabular-nums tracking-tight">
  <PrivacyValue
    value={
      latest
        ? `${Number(latest.balance).toLocaleString(undefined, {
            minimumFractionDigits: 2,
          })} ${asset.currency}`
        : "—"
    }
  />
</div>
```

Replace with:
```typescript
<div className="text-2xl font-semibold tracking-tight">
  {latest ? (
    <DualCurrencyAmount
      value={formatNative(latest.balance, asset.currency)}
      primaryClassName="text-2xl font-semibold"
    />
  ) : (
    <span className="font-mono tabular-nums">—</span>
  )}
</div>
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

---

## Task 11: Fix `portfolio/[symbol]/page.tsx` — remove hardcoded `$`

**Files:**
- Modify: `frontend/app/(auth)/portfolio/[symbol]/page.tsx`

The page shows `$${latestBar.close}` for the asset price, `$${tx.price}` and `$${tx.fee}` in the transactions table. The asset has a `currency` field.

- [ ] **Step 1: Add `useDualCurrency` import**

At the top of the file, the existing imports include `PrivacyValue`. Add after the existing imports:
```typescript
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
```

- [ ] **Step 2: Call `useDualCurrency` in the component body**

After the existing `useQuery` calls, add:
```typescript
const { formatNative } = useDualCurrency();
const assetCurrency = asset?.currency ?? "USD";
```

- [ ] **Step 3: Replace the `latestBar.close` price display**

Find:
```typescript
value={`$${Number(latestBar.close).toLocaleString("en-US", {
```

The full block looks like:
```typescript
<PrivacyValue
  value={`$${Number(latestBar.close).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`}
/>
```

Replace with:
```typescript
<DualCurrencyAmount
  value={formatNative(latestBar.close, assetCurrency)}
  inline
/>
```

- [ ] **Step 4: Replace `tx.price` display in the transactions table**

Find:
```typescript
<PrivacyValue
  value={`$${Number(tx.price).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`}
/>
```

Replace with:
```typescript
<DualCurrencyAmount
  value={formatNative(tx.price, assetCurrency)}
  inline
/>
```

- [ ] **Step 5: Replace `tx.fee` display**

Find:
```typescript
<PrivacyValue value={`$${Number(tx.fee).toFixed(2)}`} />
```

Replace with:
```typescript
<DualCurrencyAmount
  value={formatNative(tx.fee, assetCurrency)}
  inline
/>
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -30
```

---

## Task 12: Fix `watchlist/page.tsx` — remove hardcoded `$` on prices

**Files:**
- Modify: `frontend/app/(auth)/watchlist/page.tsx`

- [ ] **Step 1: Add imports**

Add to the import block at the top:
```typescript
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
```

- [ ] **Step 2: Call `useDualCurrency` in the main watchlist component**

Find the main component that renders the table (the function that uses `items.map(...)`). Add near the top of that function body:
```typescript
const { formatNative } = useDualCurrency();
```

- [ ] **Step 3: Replace `current_price` display**

Find:
```typescript
{item.current_price
  ? `$${parseFloat(item.current_price).toFixed(2)}`
  : "—"}
```

Replace with:
```typescript
{item.current_price
  ? <DualCurrencyAmount
      value={formatNative(item.current_price, item.asset.currency ?? item.currency ?? "USD")}
      inline
    />
  : "—"}
```

Note: check whether the field is `item.asset.currency` or `item.currency` by inspecting the `WatchlistItem` type from `@/lib/services/watchlist`. Use whichever is present.

- [ ] **Step 4: Replace `target_price` display**

Find:
```typescript
{item.target_price
  ? `$${parseFloat(item.target_price).toFixed(2)}`
  : "—"}
```

Replace with:
```typescript
{item.target_price
  ? <DualCurrencyAmount
      value={formatNative(item.target_price, item.asset.currency ?? item.currency ?? "USD")}
      inline
    />
  : "—"}
```

- [ ] **Step 5: Verify TypeScript compiles and correct the currency field if needed**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -40
```

If TypeScript reports that `item.asset.currency` doesn't exist but `item.currency` does (or vice versa), update the field access in steps 3 and 4 accordingly.

---

## Task 13: Fix `events/page.tsx` — remove hardcoded `$` on dividend amounts

**Files:**
- Modify: `frontend/app/(auth)/events/page.tsx`

- [ ] **Step 1: Add imports**

Add to the import block:
```typescript
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
```

- [ ] **Step 2: Call `useDualCurrency` in the component that renders the events table**

Find the component/function that renders the events table rows. Add:
```typescript
const { formatNative } = useDualCurrency();
```

- [ ] **Step 3: Replace the dividend amount cell in the table**

Find:
```typescript
ev.event_type === "dividend"
  ? `$${parseFloat((ev as DividendCalendarEvent).amount_per_share).toFixed(4)}/sh`
  : (ev as IpoCalendarEvent).price_low
  ? `$${(ev as IpoCalendarEvent).price_low}–$${(ev as IpoCalendarEvent).price_high}`
  : "N/A"
```

Replace with:
```typescript
ev.event_type === "dividend" ? (
  <span>
    <DualCurrencyAmount
      value={formatNative(
        (ev as DividendCalendarEvent).amount_per_share,
        (ev as DividendCalendarEvent).currency
      )}
      inline
    />
    <span className="text-muted-foreground">/sh</span>
  </span>
) : (ev as IpoCalendarEvent).price_low ? (
  `${(ev as IpoCalendarEvent).price_low}–${(ev as IpoCalendarEvent).price_high} ${(ev as IpoCalendarEvent).currency ?? "USD"}`
) : (
  "N/A"
)
```

- [ ] **Step 4: Replace the dividend dialog "Amount per share" line**

Find:
```typescript
{selectedDividend ? parseFloat(selectedDividend.amount_per_share).toFixed(4) : "—"} {selectedDividend?.currency}
```

Replace with:
```typescript
{selectedDividend ? (
  <DualCurrencyAmount
    value={formatNative(selectedDividend.amount_per_share, selectedDividend.currency)}
    inline
  />
) : "—"}
```

- [ ] **Step 5: Replace the dividend dialog "Total income" line**

Find:
```typescript
<span>${(parseFloat(confirmQty) * parseFloat(selectedDividend.amount_per_share)).toFixed(2)} {selectedDividend.currency}</span>
```

Replace with:
```typescript
<DualCurrencyAmount
  value={formatNative(
    parseFloat(confirmQty) * parseFloat(selectedDividend.amount_per_share),
    selectedDividend.currency
  )}
  inline
/>
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -40
```

---

## Task 14: Fix `transactions/page.tsx` — add currency labels to price and fee

**Files:**
- Modify: `frontend/app/(auth)/transactions/page.tsx`

The `TransactionRow` type does not include a `currency` field. The backend `/api/v1/portfolio/transactions` endpoint almost certainly returns `currency` since it is stored per-transaction. We add it as optional so the app degrades gracefully if absent.

- [ ] **Step 1: Add `currency` to `TransactionRow` type**

Find:
```typescript
type TransactionRow = {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  platform: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  created_at: string;
};
```

Replace with:
```typescript
type TransactionRow = {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  currency?: string;
  platform: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  created_at: string;
};
```

- [ ] **Step 2: Add imports**

Add to the import block:
```typescript
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
```

- [ ] **Step 3: Call `useDualCurrency` in the component**

Inside `TransactionsPage`, after the `useState` declarations, add:
```typescript
const { formatNative } = useDualCurrency();
```

- [ ] **Step 4: Replace the price table cell**

Find the `<TableCell>` that renders `tx.price` (around line 172):
```typescript
{parseFloat(tx.price).toFixed(2)}
```

Replace with:
```typescript
<DualCurrencyAmount
  value={formatNative(tx.price, tx.currency ?? "USD")}
  inline
/>
```

- [ ] **Step 5: Replace the fee table cell**

Find the `<TableCell>` that renders `tx.fee` (around line 175):
```typescript
{parseFloat(tx.fee).toFixed(2)}
```

Replace with:
```typescript
<DualCurrencyAmount
  value={formatNative(tx.fee, tx.currency ?? "USD")}
  inline
/>
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit 2>&1 | head -40
```

---

## Task 15: Final build verification

- [ ] **Step 1: Run full Next.js build**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npm run build 2>&1 | tail -30
```

Expected output ends with:
```
✓ Compiled successfully
Route (app) ...
```

If there are TypeScript or compilation errors, fix them before proceeding.

- [ ] **Step 2: Visual checklist — start dev server and verify each location**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npm run dev
```

Open the app and verify:

| Page/Component | Check |
|---|---|
| Overview (SummaryBar) | Shows `1,234.56 THB` not `$1,234.56` |
| Overview (SummaryBar) | Privacy ON: shows `****** THB`, percentage badge unchanged |
| Overview (KpiCards) | Secondary currency shown below primary (already worked, still works) |
| Net Worth chart | Y-axis and tooltip values match primary currency symbol |
| Portfolio page | HoldingsTable cells show `****** THB / ≈ ****** USD` in privacy mode |
| Portfolio > [symbol] | Price, fee use primary currency, no hardcoded `$` |
| Cash accounts | Balance shows dual currency; privacy ON shows `****** THB` |
| Watchlist | Current price, target price show currency label, no `$` |
| Events | Dividend amount shows currency label, no `$` |
| Transactions | Price and fee columns show currency label |
| Settings toggle | Toggling privacy ON/OFF updates all pages instantly |

---

## Acceptance Criteria Cross-Check

- [ ] No `$` hardcoded anywhere except `settings/ai/page.tsx` (AI billing — intentionally USD)
- [ ] Every monetary value shows both primary and secondary currency
- [ ] Privacy ON: amounts show `****** {CURRENCY}`, percentages and exchange rates unchanged
- [ ] `DualCurrencyAmount` is the only component constructing monetary display strings
- [ ] `net-worth-chart` y-axis and tooltip values match user's primary currency
- [ ] `CashAccountsSection` balance shows with secondary currency conversion
- [ ] `transactions/page.tsx` price and fee columns have currency labels
