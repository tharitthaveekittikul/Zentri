# Responsive Mobile Layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Zentri page usable on mobile (375px+) by hiding secondary table columns and fixing overflow issues — no JS, pure Tailwind CSS.

**Architecture:** The navigation shell is already mobile-ready (Sidebar hides at `md`, BottomTabBar shows). The remaining work is: (1) add `hidden md:table-cell` to secondary columns in wide tables, (2) wrap a calendar grid in `overflow-x-auto`, (3) fix a button group that doesn't wrap. All changes are pure Tailwind class additions.

**Tech Stack:** Next.js, Tailwind CSS, tanstack/react-table (HoldingsTable only), shadcn/ui Table components

---

## File Map

| File | Change |
|---|---|
| `frontend/components/portfolio/HoldingsTable.tsx` | Add `meta.className` to 4 column defs; read meta in `<TableHead>` and `<TableCell>` render loops |
| `frontend/app/(auth)/watchlist/page.tsx` | Add `hidden md:table-cell` to 4 `<TableHead>` + 4 `<TableCell>` per row; fix action button group |
| `frontend/app/(auth)/transactions/page.tsx` | Add `hidden md:table-cell` to 3 `<TableHead>` + 3 `<TableCell>` per row |
| `frontend/app/(auth)/events/page.tsx` | Wrap CalendarGrid inner div in `overflow-x-auto` + `min-w-[480px]` |

---

## Task 1: HoldingsTable — hide secondary columns on mobile

**Files:**
- Modify: `frontend/components/portfolio/HoldingsTable.tsx`

### Background

HoldingsTable uses tanstack/react-table. All headers render via `flexRender(h.column.columnDef.header, h.getContext())` inside a generic `<TableHead>` loop, and all cells via `flexRender(cell.column.columnDef.cell, cell.getContext())` inside a generic `<TableCell>` loop. You cannot add classes to individual `<TableHead>`/`<TableCell>` elements directly — they're all rendered in the same loop.

The pattern: add `meta: { className: "hidden md:table-cell" }` to column defs, then read it in the render loops.

### Columns to hide on mobile

| Column | accessorKey / id | Action |
|---|---|---|
| Symbol | `symbol` | keep |
| Shares | `outstanding_shares` | **hide** |
| Cost/Share | `cost_per_share` | **hide** |
| Total Cost | `total_cost` | **hide** |
| Price | `current_price` | keep |
| 1D Change | `price_1d_change` | **hide** |
| Value | `holding_value` | keep |
| P/L | `unrealized_pnl` | keep |
| Actions | `actions` | keep |

- [ ] **Step 1: Add meta.className to the 4 columns to hide**

In `HoldingsTable.tsx`, add `meta: { className: "hidden md:table-cell" }` to the `outstanding_shares`, `cost_per_share`, `total_cost`, and `price_1d_change` column definitions.

Find the `outstanding_shares` column def (line ~211) and add the meta field:

```tsx
{
  accessorKey: "outstanding_shares",
  sortingFn: "alphanumeric",
  meta: { className: "hidden md:table-cell" },
  header: ({ column }) => ( ... ),
  cell: ({ row }) => ( ... ),
},
```

Do the same for `cost_per_share` (line ~229), `total_cost` (line ~254), and `price_1d_change` (line ~301).

- [ ] **Step 2: Read meta.className in the TableHead render loop**

Find the `<TableHead>` render loop (around line 536):

```tsx
{hg.headers.map((h) => (
  <TableHead key={h.id}>
    {flexRender(h.column.columnDef.header, h.getContext())}
  </TableHead>
))}
```

Replace it with:

```tsx
{hg.headers.map((h) => (
  <TableHead
    key={h.id}
    className={(h.column.columnDef.meta as { className?: string } | undefined)?.className}
  >
    {flexRender(h.column.columnDef.header, h.getContext())}
  </TableHead>
))}
```

- [ ] **Step 3: Read meta.className in the TableCell render loop**

Find the `<TableCell>` render loop (around line 551):

```tsx
{row.getVisibleCells().map((cell) => (
  <TableCell key={cell.id}>
    {flexRender(
      cell.column.columnDef.cell,
      cell.getContext(),
    )}
  </TableCell>
))}
```

Replace it with:

```tsx
{row.getVisibleCells().map((cell) => (
  <TableCell
    key={cell.id}
    className={(cell.column.columnDef.meta as { className?: string } | undefined)?.className}
  >
    {flexRender(
      cell.column.columnDef.cell,
      cell.getContext(),
    )}
  </TableCell>
))}
```

- [ ] **Step 4: Verify**

Run the TypeScript compiler to check no type errors:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors related to `meta`.

Open `/portfolio` in a browser. At 375px width: table should show 5 columns (Symbol, Price, Value, P/L, Actions). At 768px+: all 9 columns visible.

---

## Task 2: Watchlist — hide secondary columns + fix action button group

**Files:**
- Modify: `frontend/app/(auth)/watchlist/page.tsx`

### Columns to hide on mobile

| Column | Action |
|---|---|
| Ticker | keep |
| Price | keep |
| Target | **hide** |
| % to Target | **hide** |
| AI Verdict | keep |
| AI Price | **hide** |
| Last Scanned | **hide** |
| Actions | keep |

### Part A — TableHead elements

- [ ] **Step 1: Add hidden md:table-cell to 4 TableHead elements**

Find the `<TableRow>` inside `<TableHeader>` (around line 612). The current static headers are:

```tsx
<TableRow>
  <TableHead>Ticker</TableHead>
  <TableHead className="text-right">Price</TableHead>
  <TableHead className="text-right">Target</TableHead>
  <TableHead className="text-right">% to Target</TableHead>
  <TableHead>AI Verdict</TableHead>
  <TableHead className="text-right">AI Price</TableHead>
  <TableHead>Last Scanned</TableHead>
  <TableHead className="text-right">Actions</TableHead>
</TableRow>
```

Replace with:

```tsx
<TableRow>
  <TableHead>Ticker</TableHead>
  <TableHead className="text-right">Price</TableHead>
  <TableHead className="hidden md:table-cell text-right">Target</TableHead>
  <TableHead className="hidden md:table-cell text-right">% to Target</TableHead>
  <TableHead>AI Verdict</TableHead>
  <TableHead className="hidden md:table-cell text-right">AI Price</TableHead>
  <TableHead className="hidden md:table-cell">Last Scanned</TableHead>
  <TableHead className="text-right">Actions</TableHead>
</TableRow>
```

### Part B — WatchlistRow TableCell elements

- [ ] **Step 2: Add hidden md:table-cell to 4 TableCell elements in WatchlistRow**

Find `WatchlistRow` (around line 193). The `<TableCell>` elements for Target, % to Target, AI Price, and Last Scanned need `hidden md:table-cell`.

Target cell (the one rendering `item.target_price`):
```tsx
<TableCell className="hidden md:table-cell text-right">
  {item.target_price
    ? <DualCurrencyAmount
        value={formatNative(item.target_price, item.currency)}
      />
    : "—"}
</TableCell>
```

% to Target cell (the one rendering `item.pct_from_target`):
```tsx
<TableCell className="hidden md:table-cell text-right">
  {item.pct_from_target !== null ? (
    <span
      className={
        item.pct_from_target <= 0
          ? "text-green-600"
          : "text-muted-foreground"
      }
    >
      {item.pct_from_target > 0 ? "+" : ""}
      {item.pct_from_target.toFixed(1)}%
    </span>
  ) : (
    "—"
  )}
</TableCell>
```

AI Price cell (the one rendering `item.ai_suggested_price`):
```tsx
<TableCell className="hidden md:table-cell text-right">
  {item.ai_suggested_price
    ? <DualCurrencyAmount
        value={formatNative(item.ai_suggested_price, item.currency ?? "USD")}
      />
    : "—"}
</TableCell>
```

Last Scanned cell (the one rendering `item.last_scanned_at`):
```tsx
<TableCell className="hidden md:table-cell text-xs text-muted-foreground">
  {item.last_scanned_at
    ? new Date(item.last_scanned_at).toLocaleDateString("en-GB")
    : "Never"}
</TableCell>
```

### Part C — Action button group wrapping

- [ ] **Step 3: Fix action button group to wrap on mobile**

Find the action button group div (around line 551):

```tsx
<div className="flex flex-wrap gap-2 shrink-0">
```

Change `shrink-0` to allow the group to go full-width on small screens by removing `shrink-0`:

```tsx
<div className="flex flex-wrap gap-2">
```

- [ ] **Step 4: Verify**

Open `/watchlist` at 375px. Table should show 4 columns (Ticker, Price, AI Verdict, Actions). At 768px+: all 8 columns visible. Action buttons (Scan All / Discover / Add) should wrap to second line on narrow screens.

---

## Task 3: Transactions — hide secondary columns on mobile

**Files:**
- Modify: `frontend/app/(auth)/transactions/page.tsx`

### Columns to hide on mobile

| Column | Action |
|---|---|
| Date | keep |
| Asset | keep |
| Type | keep |
| Quantity | **hide** |
| Price | keep |
| Fee | **hide** |
| Platform | **hide** |
| Actions | keep |

Note: The table wrapper already has `overflow-x-auto` (line 256) ✅. The `colSpan={8}` on the empty-state cell will need to become `colSpan={5}` to match the visible column count on mobile — but since `colSpan` doesn't interact with CSS `hidden`, the empty-state row will still span all columns correctly. No change needed there.

- [ ] **Step 1: Add hidden md:table-cell to 3 TableHead elements**

Find the `<TableRow>` inside `<TableHeader>` (around line 268):

```tsx
<TableRow>
  <TableHead>Date</TableHead>
  <TableHead>Asset</TableHead>
  <TableHead>Type</TableHead>
  <TableHead className="text-right">Quantity</TableHead>
  <TableHead className="text-right">Price</TableHead>
  <TableHead className="text-right">Fee</TableHead>
  <TableHead>Platform</TableHead>
  <TableHead className="text-right">Actions</TableHead>
</TableRow>
```

Replace with:

```tsx
<TableRow>
  <TableHead>Date</TableHead>
  <TableHead>Asset</TableHead>
  <TableHead>Type</TableHead>
  <TableHead className="hidden md:table-cell text-right">Quantity</TableHead>
  <TableHead className="text-right">Price</TableHead>
  <TableHead className="hidden md:table-cell text-right">Fee</TableHead>
  <TableHead className="hidden md:table-cell">Platform</TableHead>
  <TableHead className="text-right">Actions</TableHead>
</TableRow>
```

- [ ] **Step 2: Add hidden md:table-cell to 3 TableCell elements per row**

Find the `data.items.map((tx) => ...)` row rendering (around line 290). Apply `hidden md:table-cell` to the Quantity, Fee, and Platform cells:

Quantity cell:
```tsx
<TableCell className="hidden md:table-cell text-right">
  {parseFloat(tx.quantity).toLocaleString()}
</TableCell>
```

Fee cell:
```tsx
<TableCell className="hidden md:table-cell text-right">
  <DualCurrencyAmount
    value={formatNative(tx.fee, tx.currency ?? "USD")}
  />
</TableCell>
```

Platform cell:
```tsx
<TableCell className="hidden md:table-cell text-muted-foreground text-sm">
  {tx.platform ?? "—"}
</TableCell>
```

- [ ] **Step 3: Verify**

Open `/transactions` at 375px. Table should show 5 columns (Date, Asset, Type, Price, Actions). At 768px+: all 8 columns visible.

---

## Task 4: Events — wrap calendar in overflow-x-auto

**Files:**
- Modify: `frontend/app/(auth)/events/page.tsx`

The `CalendarGrid` component renders three sibling `grid-cols-7` divs (day-of-week header, day cells). At 375px these cells are ~47px wide — too small to read event chips. The fix: wrap the calendar section in `overflow-x-auto` so users can scroll it, with a minimum width that keeps cells legible (68px × 7 = 476px).

- [ ] **Step 1: Wrap the CalendarGrid return in overflow-x-auto**

Find the `return (` inside `CalendarGrid` (the function at the top of the file). The current return is:

```tsx
return (
  <div className="overflow-hidden">
    <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
      ...nav buttons...
    </div>
    <div className="grid grid-cols-7 text-xs text-center text-muted-foreground border-b">
      ...day names...
    </div>
    <div className="grid grid-cols-7">
      ...day cells...
    </div>
  </div>
);
```

Replace the outer `<div className="overflow-hidden">` with `overflow-x-auto`, and add a `min-w-[476px]` inner wrapper around the three grid divs:

```tsx
return (
  <div className="overflow-x-auto">
    <div className="min-w-[476px]">
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
        ...nav buttons...
      </div>
      <div className="grid grid-cols-7 text-xs text-center text-muted-foreground border-b">
        ...day names...
      </div>
      <div className="grid grid-cols-7">
        ...day cells...
      </div>
    </div>
  </div>
);
```

- [ ] **Step 2: Verify**

Open `/events` at 375px. The calendar should scroll horizontally rather than crushing cells. Day cells should be at least 68px wide. The nav header (month/year + arrows) and filter buttons above the calendar remain full-width.

---

## Task 5: Final TypeScript check

- [ ] **Step 1: Run tsc across the frontend**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors. If errors appear in edited files, fix them before declaring done.

- [ ] **Step 2: Cross-check all changed pages at 375px**

Open each page below in browser devtools at 375px (iPhone SE) and confirm no horizontal body scroll:

- `/portfolio` — 5 columns visible
- `/watchlist` — 4 columns visible, action buttons wrap
- `/transactions` — 5 columns visible
- `/events` — calendar scrolls, does not crush

At 768px: all columns reappear on each page.
