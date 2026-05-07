# Portfolio Platform Breakdown + Symbol Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-platform breakdown cards (count, value, P/L) to the portfolio page, and make symbols in the HoldingsTable link to the existing asset detail page.

**Architecture:** Compute platform groups client-side from the already-fetched `holdings` array using a pure utility function. Render groups as cards in a new `PlatformBreakdownCards` component placed between the summary row and the table. Symbol links use Next.js `<Link>` pointing to the existing `/portfolio/[symbol]` route.

**Tech Stack:** Next.js 14 (App Router), React, TypeScript, TanStack Table, Tailwind CSS, shadcn/ui `<Card>`

---

## File Map

| Action | File | Purpose |
|---|---|---|
| Modify | `frontend/lib/services/portfolio.ts` | Add `PlatformGroup` type and `groupHoldingsByPlatform()` |
| Create | `frontend/components/portfolio/PlatformBreakdownCards.tsx` | New card-row component |
| Modify | `frontend/app/(auth)/portfolio/page.tsx` | Import and render `PlatformBreakdownCards` |
| Modify | `frontend/components/portfolio/HoldingsTable.tsx` | Wrap symbol cell in `<Link>` |

---

### Task 1: Add `PlatformGroup` type and `groupHoldingsByPlatform` to portfolio service

**Files:**
- Modify: `frontend/lib/services/portfolio.ts`

- [ ] **Step 1: Add the type and function**

Open `frontend/lib/services/portfolio.ts` and append after the `HoldingRow` interface (around line 15):

```typescript
export interface PlatformGroup {
  platform: string;
  count: number;
  currencyGroups: {
    currency: string;
    totalValue: number | null;
    totalPnl: number | null;
  }[];
}

export function groupHoldingsByPlatform(holdings: HoldingRow[]): PlatformGroup[] {
  const map = new Map<string, HoldingRow[]>();
  for (const h of holdings) {
    if (h.asset_type === "cash" || Number(h.outstanding_shares) < 1e-6) continue;
    const key = h.platform ?? "No Platform";
    const existing = map.get(key) ?? [];
    existing.push(h);
    map.set(key, existing);
  }

  return Array.from(map.entries()).map(([platform, rows]) => {
    const currencyMap = new Map<string, { value: number | null; pnl: number | null }>();
    for (const row of rows) {
      const curr = row.currency;
      const entry = currencyMap.get(curr) ?? { value: null, pnl: null };
      if (row.holding_value != null) {
        entry.value = (entry.value ?? 0) + Number(row.holding_value);
      }
      if (row.unrealized_pnl != null) {
        entry.pnl = (entry.pnl ?? 0) + Number(row.unrealized_pnl);
      }
      currencyMap.set(curr, entry);
    }
    return {
      platform,
      count: rows.length,
      currencyGroups: Array.from(currencyMap.entries()).map(
        ([currency, { value, pnl }]) => ({
          currency,
          totalValue: value,
          totalPnl: pnl,
        }),
      ),
    };
  });
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors related to `portfolio.ts`.

---

### Task 2: Create `PlatformBreakdownCards` component

**Files:**
- Create: `frontend/components/portfolio/PlatformBreakdownCards.tsx`

- [ ] **Step 1: Create the file**

```tsx
"use client";

import { useMemo } from "react";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { HoldingRow, groupHoldingsByPlatform } from "@/lib/services/portfolio";

interface Props {
  holdings: HoldingRow[];
}

const secondaryCls = "text-xs text-muted-foreground font-mono tabular-nums mt-0.5";

export function PlatformBreakdownCards({ holdings }: Props) {
  const { formatNative } = useDualCurrency();
  const groups = useMemo(() => groupHoldingsByPlatform(holdings), [holdings]);

  if (groups.length === 0) return null;

  return (
    <div className="flex gap-3 overflow-x-auto pb-1">
      {groups.map((group) => (
        <Card key={group.platform} className="min-w-[160px] flex-shrink-0">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide truncate">
              {group.platform}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm text-muted-foreground">
              {group.count} {group.count === 1 ? "holding" : "holdings"}
            </p>
            {group.currencyGroups.map((cg) => {
              const color =
                cg.totalPnl != null && cg.totalPnl >= 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-destructive";
              return (
                <div key={cg.currency} className="space-y-0.5">
                  {cg.totalValue != null && (
                    <DualCurrencyAmount
                      value={formatNative(String(cg.totalValue), cg.currency)}
                      primaryClassName="text-sm font-semibold font-mono tabular-nums"
                      secondaryClassName={secondaryCls}
                    />
                  )}
                  {cg.totalPnl != null && (
                    <div className={`flex items-center gap-0.5 ${color}`}>
                      {cg.totalPnl >= 0 ? (
                        <ArrowUpRight className="h-3 w-3 shrink-0" strokeWidth={2.5} />
                      ) : (
                        <ArrowDownRight className="h-3 w-3 shrink-0" strokeWidth={2.5} />
                      )}
                      <DualCurrencyAmount
                        value={formatNative(String(cg.totalPnl), cg.currency, 2, true)}
                        primaryClassName={`text-xs font-mono tabular-nums ${color}`}
                        secondaryClassName={`${secondaryCls} ${color} opacity-75`}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

---

### Task 3: Add `PlatformBreakdownCards` to the portfolio page

**Files:**
- Modify: `frontend/app/(auth)/portfolio/page.tsx`

- [ ] **Step 1: Add import**

In `frontend/app/(auth)/portfolio/page.tsx`, add this import alongside the other portfolio component imports:

```typescript
import { PlatformBreakdownCards } from "@/components/portfolio/PlatformBreakdownCards";
```

- [ ] **Step 2: Render the cards between summary grid and HoldingsTable**

Find the section after the closing `</div>` of the `grid grid-cols-2 gap-4` div (around line 151) and before the `{isLoading ? ...}` block. Insert:

```tsx
<PlatformBreakdownCards holdings={holdings} />
```

The relevant section should look like:

```tsx
      </div>

      <PlatformBreakdownCards holdings={holdings} />

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
```

- [ ] **Step 3: Verify TypeScript compiles and dev server starts**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Manual verification**

Start the dev server and open the portfolio page. Confirm:
- A row of cards appears between the summary and the table
- Each card shows the correct platform name, holding count, current value, and P/L
- Holdings with no platform appear under "No Platform"
- P/L is green for positive, red for negative
- Row scrolls horizontally if there are many platforms

---

### Task 4: Add symbol link in HoldingsTable

**Files:**
- Modify: `frontend/components/portfolio/HoldingsTable.tsx`

- [ ] **Step 1: Add `Link` import**

In `frontend/components/portfolio/HoldingsTable.tsx`, add at the top:

```typescript
import Link from "next/link";
```

- [ ] **Step 2: Update the symbol column cell renderer**

Find the `symbol` column definition (around line 88–99). Replace its definition with:

```typescript
    {
      accessorKey: "symbol",
      header: ({ column }) => (
        <button
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Symbol <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <Link
          href={`/portfolio/${encodeURIComponent(row.original.symbol)}`}
          className="hover:underline"
          prefetch={false}
        >
          {row.original.symbol}
        </Link>
      ),
    },
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Manual verification**

Open the portfolio page and confirm:
- Symbol cells are clickable
- Clicking navigates to `/portfolio/{SYMBOL}` (the asset detail page with chart, verdict, transactions)
- No underline by default; underline appears on hover
- Sorting still works when clicking the column header button
