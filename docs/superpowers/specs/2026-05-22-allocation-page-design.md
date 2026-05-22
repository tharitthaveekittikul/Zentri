# Allocation Page with Drill-Down

**Date:** 2026-05-22
**Status:** Approved

## Summary

Add a dedicated `/allocation` page with a full-page donut chart and synced holdings table. Clicking a sector or asset-type slice drills down in-place to show per-symbol breakdown. The existing Overview widget is unchanged.

## Architecture & Data Flow

**New backend endpoint:**
- Service: `get_allocation_holdings(db, user_id, target_currency)` in `backend/app/services/overview.py`
  - Iterates holdings, fetches latest price + exchange rate
  - Returns `[{symbol, name, sector, asset_type, value, pct_of_total}]` sorted by value desc
  - Falls back to `asset_type` label when `sector` is missing (same as current logic)
- Route: `GET /api/overview/allocation/holdings` in `backend/app/api/overview.py`

**Frontend data flow:**
- Page `app/(auth)/allocation/page.tsx` fetches the single holdings endpoint via React Query (`queryKey: ["allocation", "holdings"]`)
- Client computes donut groups from holdings data (group by `asset_type` or `sector`)
- `selectedGroup: string | null` state lives in the page, passed to both donut and table
- When `selectedGroup` is set: donut shows symbols within that group; table filters to those rows

**Navigation:**
- Add "Allocation" link to the sidebar nav alongside Overview, Portfolio, etc.

## Components

### `AllocationDrillDonut` — new component

File: `frontend/components/allocation/AllocationDrillDonut.tsx`

- Props: `holdings`, `tab`, `selectedGroup`, `onSelectGroup`, `onClearGroup`
- Internally computes `typeData` and `sectorData` from `holdings`
- **Top-level view** (selectedGroup = null): renders groups, slices are clickable → calls `onSelectGroup`
- **Drill-down view** (selectedGroup set): filters holdings to that group, renders one slice per symbol, display-only
- Breadcrumb pill `← {selectedGroup}` replaces tab switcher when drilled in; clicking calls `onClearGroup`

### `AllocationDonut` — unchanged

The existing `frontend/components/overview/AllocationDonut.tsx` is not modified. The Overview page continues using it with the old `allocation` + `sectorAllocation` props and existing API calls.

### `AllocationTable` — new

File: `frontend/components/allocation/AllocationTable.tsx`

- Props: `holdings: HoldingAllocationItem[]`
- Columns: Symbol, Name, Sector, Type, Value, Weight %
- Value column: respects `primaryCurrency` + privacy mask
- Default sort: Value desc
- Sortable columns

### Page layout

File: `app/(auth)/allocation/page.tsx`

- Desktop: two-column — donut ~40% left, table ~60% right
- Mobile: single column stack (donut above table)

## API Contract

```ts
// GET /api/overview/allocation/holdings
HoldingAllocationItem {
  symbol: string
  name: string
  sector: string         // falls back to asset_type label if no sector
  asset_type: string
  value: number          // in target currency
  pct_of_total: number   // 0–100
}
```

## Edge Cases

- **No holdings**: Donut shows existing empty state; table shows "No holdings yet"
- **Single holding in a group**: Drill-down shows one 100% slice — valid, no special handling needed
- **Missing sector**: Falls back to `asset_type.replace("_", " ").title()` — no missing slices
- **Overview page**: Unchanged — still uses old `get_allocation` + `get_sector_allocation` endpoints via its own queries

## Out of Scope

- Historical allocation over time
- Further drill-down beyond symbol level
- Editing or rebalancing from this page
