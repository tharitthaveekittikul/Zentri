# Mobile Responsive Layout — Design Spec
**Date:** 2026-05-22  
**Scope:** Adapted layout — column hiding + overflow fixes  
**Breakpoint:** `md` (768px) — Tailwind default

---

## Context

The navigation shell is already mobile-ready: the Sidebar is `hidden md:flex` and the BottomTabBar is `md:hidden`. The auth layout applies `pb-safe-tab` for bottom bar clearance and `p-6 md:p-8` content padding.

The remaining mobile problems are: wide data tables with too many columns, a calendar that squashes cells below a usable size, and a few missing `overflow-x-auto` wrappers.

---

## Approach

Pure Tailwind CSS — `hidden md:table-cell` on secondary table columns, `overflow-x-auto` wrappers where missing. No JavaScript, no `useMediaQuery`, no hydration concerns.

---

## Pages Already Responsive (No Changes)

- `/overview` — KpiCards `grid-cols-2 md:grid-cols-4`, charts `lg:grid-cols-5`
- `/chat` — `max-w-3xl mx-auto`, `grid-cols-1 sm:grid-cols-2` suggestion chips
- `/settings`, `/settings/ai`, `/settings/backup` — single-column `max-w-2xl`
- `/import` — centered flex column
- `/research` — `max-w-4xl mx-auto`
- `/documents` — already has `overflow-x-auto` and `flex-wrap`
- `/net-worth` — chart-only, `ResponsiveContainer` handles width

---

## Changes Required

### 1. HoldingsTable (`frontend/components/portfolio/HoldingsTable.tsx`)

**Table already has `overflow-x-auto`.** Add `hidden md:table-cell` to secondary columns.

| Column | Mobile | Desktop |
|---|---|---|
| Symbol | visible | visible |
| Current Value | visible | visible |
| P&L | visible | visible |
| P&L % | visible | visible |
| Shares | **hidden** | visible |
| Cost/Share | **hidden** | visible |
| Total Cost | **hidden** | visible |
| Actions | visible | visible |

Apply `hidden md:table-cell` to both the `<TableHead>` and each corresponding `<TableCell>` for hidden columns.

### 2. Watchlist Page (`frontend/app/(auth)/watchlist/page.tsx`)

**Table already has `overflow-x-auto`.** Hide secondary columns on mobile.

| Column | Mobile | Desktop |
|---|---|---|
| Ticker | visible | visible |
| Price | visible | visible |
| AI Verdict | visible | visible |
| Actions | visible | visible |
| Target | **hidden** | visible |
| % to Target | **hidden** | visible |
| AI Price | **hidden** | visible |
| Last Scanned | **hidden** | visible |

The filter toolbar already uses `flex-wrap` ✅. The action button group (Scan All / Discover / Add) uses `flex flex-wrap gap-2 shrink-0` — change `shrink-0` to allow it to go full-width on small screens: `flex flex-wrap gap-2 w-full sm:w-auto`.

### 3. Transactions Page (`frontend/app/(auth)/transactions/page.tsx`)

The table wrapper needs `overflow-x-auto` added. Hide secondary columns on mobile.

| Column | Mobile | Desktop |
|---|---|---|
| Date | visible | visible |
| Asset | visible | visible |
| Type | visible | visible |
| Price | visible | visible |
| Actions | visible | visible |
| Quantity | **hidden** | visible |
| Fee | **hidden** | visible |
| Platform | **hidden** | visible |

The summary stats area uses `grid grid-cols-2 gap-3` which is fine on mobile ✅.

### 4. Events Calendar (`frontend/app/(auth)/events/page.tsx`)

The `grid-cols-7` calendar is semantically correct (7 days per week) but cells become unusably small (~51px) at 360px viewport width. Wrap the calendar grid section in:

```
overflow-x-auto
```

with an inner container of `min-w-[560px]`. The calendar header nav row and the events list table below it are already fine.

### 5. Allocation Page (`frontend/app/(auth)/allocation/page.tsx`)

`flex flex-col gap-6` — chart-only page. Verify that all chart/card children are 100% width and have no fixed pixel widths that would overflow. If any fixed widths exist, replace with `w-full` or `max-w-full`.

### 6. Portfolio Detail Page (`frontend/app/(auth)/portfolio/[symbol]/page.tsx`)

`max-w-5xl mx-auto flex flex-col gap-6` — Verify any sub-component tables or stat grids are responsive. Apply `overflow-x-auto` to any table wrappers found.

### 7. Dividends Page (`frontend/app/(auth)/dividends/page.tsx`)

Audit for overflow and grid issues. Apply `overflow-x-auto` wrapper if a table is present.

---

## Non-Goals

- No card-mode rows (table rows become stacked cards) — out of scope
- No swipe gestures or native-app interactions
- No changes to the BottomTabBar tabs (already covers the 5 primary navigation destinations)
- No changes to the TopNav

---

## Quality Checks

After implementation:
1. Test each changed page at 375px (iPhone SE) and 768px (tablet breakpoint)
2. Verify no horizontal page-level overflow (body/html should not scroll horizontally)
3. Verify bottom tab bar clears the last row of content on all pages (`pb-safe-tab`)
4. Confirm tables still sort correctly after column changes
