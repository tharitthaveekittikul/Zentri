# Overview Page Redesign + Dual Currency Display

**Date:** 2026-05-06  
**Status:** Approved  
**Scope:** `frontend/app/(auth)/overview/page.tsx` and related overview components

---

## Goal

Replace the current flat overview layout with a premium, clean, minimal dashboard (Option A: Stat Cards + Compact Charts). Add simultaneous dual-currency display using `currency_primary` and `currency_secondary` from user settings.

---

## Currency Display Rules

- Fetch user currency settings from `GET /api/v1/settings` — fields `currency_primary` and `currency_secondary`
- All monetary values show **two lines**:
  - Line 1 (primary): `6,987,432.00 THB` — large, full weight
  - Line 2 (secondary): `≈ 202,989.37 USD` — small, muted (`text-muted-foreground`)
- Currency code appears **after** the number as a suffix
- Currency code is rendered in a lighter font weight so it doesn't compete with the number
- The `≈` symbol prefixes the secondary line to signal it is a converted approximation
- No currency symbols (`$`, `฿`) used anywhere — ISO codes only
- Currency codes (THB, USD) are dynamic from settings, not hardcoded

---

## Section 1: KPI Cards (replaces SummaryBar)

**Layout:** `grid grid-cols-2 md:grid-cols-4 gap-4`

**Four cards:** Portfolio Value | Total Cost | Total P&L | Today's Change

**Each card structure:**
```
bg-card border border-border rounded-2xl p-5
├── Label: text-xs uppercase tracking-wide font-medium text-muted-foreground
├── Primary value: text-2xl font-semibold font-mono tabular-nums
│   └── "6,987,432.00 THB" (currency code in text-sm font-normal text-muted-foreground)
└── Secondary value: text-sm text-muted-foreground font-mono
    └── "≈ 202,989.37 USD"
```

**P&L and Today cards:** Add a `border-l-2` left accent — `border-emerald-500` if positive, `border-destructive` if negative. The primary value text also takes the color (emerald/destructive). Percentage shown inline after the value: `+6.12%` in a lighter weight, same color.

**No badge component** — percentage is plain inline text.

---

## Section 2: Net Worth Chart

- Full width, fixed height `h-64` (no more unbounded empty canvas)
- Empty state: compact centered message — small chart icon + "No net worth data yet" — instead of a large blank card
- Section label above: `text-xs uppercase tracking-wide text-muted-foreground mb-3`

---

## Section 3: Performance + Allocation Charts

- Keep 3/5 + 2/5 grid split (`lg:grid-cols-5`)
- Performance chart: cap height at `h-52`
- Allocation donut: cap height at `h-52`
- Both get compact empty states (single line message, no large blank area)

---

## Section 4: Holdings Table

**Columns:** SYMBOL | TYPE | QUANTITY | VALUE | COST BASIS | P&L%

- Remove NAME column (currently identical to SYMBOL)
- VALUE column: shows `6,987,432.00 THB` on line 1, `≈ 202,989.37 USD` on line 2 (smaller, muted)
- COST BASIS: same dual-line format
- P&L%: colored text only (emerald/destructive), no badge, right-aligned
- Row padding: `py-2.5 px-3` (tighter than current `p-3`)
- Row hover: `hover:bg-muted/40`

---

## Data Requirements

### Currency settings
- Source: `GET /api/v1/settings` — fields `currency_primary`, `currency_secondary`
- Fetch once on page load, cache in React Query with key `["settings", "currency"]`

### Overview summary conversion
- The backend `exchange_rate_cache` and `exchange_rate.py` service already support conversion
- Check if `GET /api/v1/overview/summary` already returns both currency values or needs a `?currency=` param
- If not, the frontend computes secondary value client-side using an exchange rate endpoint: `GET /api/v1/settings/exchange-rate?from=THB&to=USD` (verify this exists or use the nearest equivalent)
- If no exchange rate API is exposed, secondary currency display is best-effort and may show "—" when rate unavailable

### Holdings
- Holdings already have `primary_currency` and `secondary_currency` in the schema — use those directly

---

## Visual System

| Token | Value |
|-------|-------|
| Card background | `bg-card` |
| Card border | `border border-border rounded-2xl` |
| Card padding | `p-5` |
| Section gap | `gap-4` or `gap-6` |
| Number font | `font-mono tabular-nums` |
| Label style | `text-xs uppercase tracking-wide font-medium text-muted-foreground` |
| Positive color | `text-emerald-600 dark:text-emerald-400` |
| Negative color | `text-destructive` |
| Secondary value | `text-sm text-muted-foreground font-mono` |

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `frontend/app/(auth)/overview/page.tsx` | Rewrite layout |
| `frontend/components/overview/SummaryBar.tsx` | Replace with `KpiCards.tsx` |
| `frontend/components/overview/KpiCards.tsx` | Create new component |
| `frontend/components/overview/HoldingsSnapshot.tsx` | Update columns + dual currency |
| `frontend/components/overview/AllocationDonut.tsx` | Add compact empty state |
| `frontend/components/overview/PerformanceChart.tsx` | Fix height, compact empty state |
| `frontend/components/net-worth-chart.tsx` | Fix height, compact empty state |
| `frontend/lib/services/settings.ts` | Add `fetchCurrencySettings()` if not present |

---

## Out of Scope

- Changing the backend overview summary API (frontend adapts to what exists)
- Redesigning other pages (portfolio, transactions, etc.)
- Dark/light mode toggle (existing system handles this)
