# Portfolio: Platform Breakdown Cards + Symbol Links

**Date:** 2026-05-07  
**Status:** Approved

## Summary

Two UI improvements to the Portfolio page:

1. **Platform breakdown cards** — per-platform summary cards showing holding count, current value, and unrealized P/L
2. **Symbol links** — symbol column in HoldingsTable becomes a clickable link to the asset detail page

---

## 1. Platform Breakdown Cards

### Placement
Between the existing summary row (Holdings count / Total Cost cards) and the HoldingsTable in `frontend/app/(auth)/portfolio/page.tsx`.

### Data Source
Computed client-side from the `holdings` array already fetched by the `["holdings"]` query. No new API calls needed.

### Grouping Logic
- Group non-cash holdings by `platform` field
- Holdings with `platform === null` are grouped under "No Platform"
- One card per platform group

### Per-Card Content
| Field | Value |
|---|---|
| Platform name | Group key (or "No Platform") |
| Holdings count | `n holdings` |
| Total value | Sum of `holding_value` per currency group, formatted with `formatNative` |
| Total P/L | Sum of `unrealized_pnl` per currency group, colored green (≥0) / red (<0) |

### Currency Handling
Holdings within a platform may have different currencies (rare but possible). Values are summed per currency, and each currency subtotal is displayed separately using the existing `formatNative` / `DualCurrencyAmount` pattern. Single-currency platforms show one clean line.

### Visual Style
- Matches existing card style (`<Card>` component, same border/radius/padding)
- Horizontal scroll row (`flex overflow-x-auto gap-3`) so it handles many platforms gracefully
- Cards have a minimum width (`min-w-[160px]`) to stay readable on mobile

---

## 2. Symbol Links

### Location
`frontend/components/portfolio/HoldingsTable.tsx` — the `symbol` column cell renderer.

### Target URL
`/portfolio/{symbol}` — the existing `AssetDetailPage` at `frontend/app/(auth)/portfolio/[symbol]/page.tsx`.

### Style
- Wrap cell content in Next.js `<Link>`
- Subtle styling: `hover:underline` only, no color change, to keep the table visually clean
- `prefetch={false}` to avoid prefetching every row on mount

---

## Files to Modify

| File | Change |
|---|---|
| `frontend/app/(auth)/portfolio/page.tsx` | Add platform breakdown cards section |
| `frontend/components/portfolio/HoldingsTable.tsx` | Add `<Link>` to symbol cell |

No new files needed. No backend changes needed.
