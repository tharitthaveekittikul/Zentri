# Portfolio Visualizations Design

**Date:** 2026-05-08
**Status:** Approved

## Overview

Add three interactive visualization views to the `/portfolio` page — Grid (treemap), Swarm (beeswarm), and Bubbles (circle pack) — as alternatives to the existing table. Users toggle between views; each holding is sized by market value and colored by P&L.

## Architecture

Port the three pure-JS layout classes from the open-source subgrid project (`/Users/tharitthaveekittikul/Documents/03_Projects/subgrid`) to TypeScript utilities. No new npm dependencies.

**New files:**
```
frontend/
  hooks/
    useResizeObserver.ts — new hook: watches a container ref, returns { width, height }
  lib/visualizations/
    treemap.ts       — squarified treemap layout (Bruls et al. algorithm)
    beeswarm.ts      — beeswarm plot (x-axis by value, y pushed to avoid overlap)
    circlepack.ts    — circle packing (largest first, packed from center)
  components/portfolio/
    PortfolioViewToggle.tsx   — 4-button toggle: Table / Grid / Swarm / Bubbles
    TreemapView.tsx           — Grid visualization
    BeeswarmView.tsx          — Swarm visualization
    CirclepackView.tsx        — Bubbles visualization
```

**Modified files:**
```
app/(auth)/portfolio/page.tsx  — add view state + toggle, conditional rendering
```

## Data Flow

Reuses the existing `allHoldingsPage` query (`page_size: 1000`) — no new API call.

Each holding maps to:
```ts
{ val: market_value, name: symbol, gainLossPct: unrealized_gain_loss_pct }
```

- **Size** → `market_value` (proportional area/radius)
- **Color** → green gradient (`gainLossPct > 0`): `#16a34a`→`#22c55e`; red (`< 0`): `#dc2626`→`#ef4444`; gray (`= 0`): `#4b5563`→`#6b7280`
- **Click** → `router.push(\`/portfolio/${symbol}\`)`
- **Tooltip** → symbol, market value, % of total portfolio, P&L%

Shared color utility:
```ts
getHoldingColor(gainLossPct: number): { bg: string; accent: string }
```

## Components

### PortfolioViewToggle
Row of 4 icon buttons using Lucide icons:
- `List` → Table
- `LayoutGrid` → Grid
- `ScatterChart` → Swarm
- `Circle` → Bubbles

Active view highlighted using existing design system. Rendered between summary cards and content area.

### TreemapView
- `position: relative` container, fills available height
- Absolutely-positioned divs from layout output
- Each cell: ticker symbol (large), market value (small), P&L% badge (top-right)
- Cells too small to label show colored block only

### BeeswarmView
- Dots on horizontal axis (x = market value, sorted left→right)
- Y pushed up/down to avoid overlap
- Ticker label below dot if space allows
- Min/max axis labels at edges

### CirclepackView
- Circles packed from center outward, largest first
- Shows ticker + P&L% inside if circle is large enough
- Tooltip on hover for all sizes

## State & Interactions

**View state** in `portfolio/page.tsx`, persisted to `localStorage`:
```ts
const [view, setView] = useState<'table' | 'grid' | 'swarm' | 'bubbles'>(() =>
  (localStorage.getItem('portfolio-view') as ViewType) ?? 'table'
)
```
Defaults to `'table'` — existing users see no change on first load.

**Resize handling** — `useResizeObserver` hook watches the visualization container. On width/height change, passes new dimensions to the layout class to recompute positions. Handles sidebar collapse, window resize, and mobile orientation change.

**Tooltip** — pure CSS hover using Tailwind `group`/`group-hover` pattern. No JS state needed.

**Loading state** — `Skeleton` block at container height while `allHoldingsPage` is undefined.

**Empty state** — centered muted text: "Add holdings to see visualization."

## Error Handling

- Layout classes receive an empty array → return empty array → view renders empty state
- Holdings with `market_value = 0` are excluded from visualization (zero-area cells)
- `useResizeObserver` guards against zero-dimension containers before running layout

## Testing

- Unit test each layout class: given N items with known values, assert output positions are within container bounds and non-overlapping
- Visual smoke test: load portfolio page, toggle through all four views, click a cell → confirm navigation to `/portfolio/[symbol]`
