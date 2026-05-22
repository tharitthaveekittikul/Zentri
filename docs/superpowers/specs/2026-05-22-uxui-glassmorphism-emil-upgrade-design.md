# Zentri UI/UX Upgrade — Glassmorphism + Emil Polish

**Date**: 2026-05-22
**Skills applied**: `design-taste-frontend` (glassmorphism elevated + premium minimal hybrid) + `emil-design-eng` (expressive spring motion)
**Scope**: Global chrome → Overview screen → Portfolio + tables (phased)

---

## Design Direction

**Chrome surfaces**: Glassmorphism elevated — backdrop-filter blur, specular borders, layered depth using existing `--glass-*` tokens.

**Data surfaces**: Premium minimal — no glass on tables/charts, ruthless clarity for financial numbers.

**Motion**: Expressive (Emil full toolkit) — spring physics on interactive chrome, staggered entrances on data, zero animation on the raw numbers themselves (instant = trustworthy).

---

## New Global Tokens (globals.css)

Three additions to the existing token system:

```css
--motion-spring: cubic-bezier(0.34, 1.56, 0.64, 1);  /* spring overshoot for interactive elements */
--motion-smooth: cubic-bezier(0.16, 1, 0.3, 1);       /* smooth entrance/exit */
--elevation-hover: 0 8px 32px oklch(0 0 0 / 30%), 0 2px 8px oklch(0 0 0 / 20%);
```

New utility class:

```css
.table-row-spring {
  /* hover + left-accent treatment shared across all tables */
  transition: background 120ms var(--motion-spring);
  position: relative;
}
.table-row-spring::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 2px;
  background: var(--brand-sage);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 120ms var(--motion-spring);
}
.table-row-spring:hover::before {
  transform: scaleX(1);
}
.table-row-spring:hover {
  background: var(--muted);
}
```

---

## Phase 1 — Global Chrome

### Sidebar (`frontend/components/layout/Sidebar.tsx`)

**Glass surface**
- Replace `bg-shell dark:bg-shell` with `backdrop-filter: blur(20px)` + `background: var(--glass-bg)`
- Add `border-right: 1px solid var(--glass-border)` for edge definition
- Add a specular top highlight: `box-shadow: inset 0 1px 0 var(--glass-specular)`

**Active nav item — spring pill**
- Add a `motion.div` (or CSS-only approach with `transition`) that slides behind the active item
- The 3px gradient indicator: animate `scaleY(0)→scaleY(1)` with `transform-origin: center` on route change, 200ms `--motion-spring`
- Icon on hover: `scale(1)→scale(1.08)`, 120ms `--motion-spring`
- Nav item: `transition: color 150ms ease, background 150ms ease`

**Section labels**
- `text-[9px]` → `text-[10px]`
- Opacity: `text-slate-400/70` → `text-slate-400/80`

**Logo area**
- Add a 24×24px brand mark to the left of "Zentri" text: a styled `div` with `background: var(--gradient-brand); border-radius: 6px; width: 24px; height: 24px; flex-shrink: 0` — no new SVG asset needed
- Gives the header row visual anchor weight

### card-surface (globals.css)

```css
.card-surface {
  transition: transform 200ms var(--motion-spring), box-shadow 200ms var(--motion-spring), border-color 200ms ease;
  border-top: 1px solid oklch(1 0 0 / 12%);  /* specular catch light */
}
.card-surface:hover {
  transform: translateY(-2px);
  box-shadow: var(--elevation-hover);
  border-color: oklch(1 0 0 / 18%);
}
.card-surface:focus-visible {
  outline: 2px solid var(--brand-sage);
  outline-offset: 2px;
}
```

### PageHeader (`frontend/components/layout/PageHeader.tsx`)

- Add scroll detection: when `scrollY > 8`, apply `backdrop-filter: blur(16px)` + `border-bottom: 1px solid var(--glass-border)`
- Transition: `opacity 0→1` over 150ms `ease`, `backdrop-filter` animates natively
- Implementation: `useEffect` + `window.addEventListener('scroll', ...)` or `IntersectionObserver` on a sentinel div

---

## Phase 2 — Overview Screen

### KPI Cards (`frontend/components/overview/KpiCards.tsx`)

**Staggered entrance**
- Each card: `translateY(12px)→0` + `opacity 0→1`
- Delays: `[0, 60, 120, 180]ms`
- Duration: 400ms `--motion-smooth`
- Trigger: on component mount (wrap in `useState(mounted)` + `useEffect`)

**Number counter**
- On mount (and on data refresh), numeric values animate from 0 to final value
- Duration: 800ms `easeOutExpo`
- Implementation: custom `useCountUp(value, duration)` hook — create at `frontend/hooks/useCountUp.ts`, shared across KpiCards and HoldingsSnapshot
- Only applies to the numeric portion — currency symbols and signs appear immediately

**Hover**
- Inherits global card-surface hover lift
- Label: `text-muted-foreground` → `text-foreground` opacity transition on hover (150ms ease)

**P&L card glow pulse (gain/loss cards only)**
```css
@keyframes pnl-pulse {
  0%, 100% { box-shadow: 0 0 0 1px var(--signal-gain-bg); }
  50%       { box-shadow: 0 0 0 4px transparent; }
}
.kpi-card--gain { animation: pnl-pulse 2s ease-in-out infinite; }
```
Loss variant uses `--signal-loss-bg`. Subtle — barely perceptible, signals data is live.

### PerformanceChart (`frontend/components/overview/PerformanceChart.tsx`)

**Draw-on-load**
- SVG line: animate `stroke-dashoffset` from full path length → 0 over 1000ms `easeOutCubic`
- Area fill: `opacity 0→1` starting 200ms after line completes (100ms duration)

**Crosshair on hover**
- Vertical hairline: `scaleY(0)→scaleY(1)` spring from top, 150ms `--motion-spring`
- Tooltip: glass surface (`background: var(--glass-bg)`, `border: 1px solid var(--glass-border)`, `backdrop-filter: blur(8px)`)
- Tooltip entrance: `translateY(4px)→0` + `opacity 0→1`, 120ms `--motion-smooth`

### AllocationDonut (`frontend/components/overview/AllocationDonut.tsx`)

**Arc entrance**
- Each segment draws in sequentially, 80ms stagger, `--motion-spring`
- Implementation: SVG `stroke-dashoffset` per segment

**Segment hover**
- Hovered segment: scale out 4px radially (SVG `transform` on the path)
- Sibling segments: `opacity 1→0.6`, 150ms ease
- Legend item highlight syncs with segment hover

### HoldingsSnapshot (`frontend/components/overview/HoldingsSnapshot.tsx`)

**Row entrance**
- `translateX(-8px)→0` + `opacity 0→1`
- Stagger: 40ms per row
- Duration: 300ms `--motion-smooth`

**Value column**
- Refresh counter animation (same `useCountUp` hook as KPI cards)

---

## Phase 3 — Portfolio + Tables

### Portfolio Table (`frontend/app/(auth)/portfolio/page.tsx` + components)

**Row hover**
- Apply `.table-row-spring` utility class to all `TableRow` elements
- Left-edge brand-sage accent animates `scaleX(0)→scaleX(1)` on hover

**Sticky glass header**
- `TableHeader`: `position: sticky; top: 0; z-index: 10`
- `backdrop-filter: blur(16px); background: var(--glass-bg)`
- `border-bottom: 1px solid var(--glass-border)`

**Sort indicator**
- Sort arrow: `rotate(0)→rotate(180deg)` on direction toggle, 150ms `--motion-spring`
- Sorted column header: `opacity 0.7→1` (brightens vs. unsorted)

**P&L cells on hover**
- Gain/loss cells get `signal-gain-bg` / `signal-loss-bg` pill background on hover only
- `border-radius: 4px; padding: 2px 6px; transition: background 120ms ease`
- Default: no background — keeps table clean

**Row entrance**
- `translateY(6px)→0` + opacity, 25ms stagger (fast — many rows)
- Duration: 250ms `--motion-smooth`

### Watchlist Table

**Price change badge pulse**
- When price updates via polling: `scale(1)→scale(1.15)→scale(1)`, single spring, 300ms
- Signals freshness without distraction
- Implementation: track `prevPrice` in ref, trigger animation when value changes

### Transactions Table

- Same `.table-row-spring` row hover + sticky glass header
- Amount column: debit/credit uses signal colors at **70% opacity by default** (not hover-only) — transactions are always directional

---

## Implementation Order

```
Phase 1
  1. globals.css — add motion tokens + .table-row-spring
  2. Sidebar — glass surface + spring active item + logo mark
  3. card-surface — hover lift + specular border
  4. PageHeader — scroll-triggered glass

Phase 2
  5. useCountUp hook (shared utility)
  6. KpiCards — stagger entrance + counter + glow pulse
  7. PerformanceChart — draw-on-load + glass tooltip
  8. AllocationDonut — arc entrance + hover dim
  9. HoldingsSnapshot — row entrance + counter

Phase 3
  10. table-row-spring applied to Portfolio, Watchlist, Transactions
  11. Sticky glass TableHeader (shared pattern)
  12. Sort indicator animation
  13. Portfolio P&L cell hover pill
  14. Watchlist price badge pulse
```

---

## Constraints

- All colors MUST use CSS variables from `globals.css` — no hardcoded hex
- No animation on raw financial numbers mid-session (only on mount/refresh) — users must be able to read live prices
- Dark mode: test both modes for every change — glass tokens have separate light/dark values
- TypeScript: no type errors (`tsc --noEmit` runs automatically on save)
- Do NOT use `framer-motion` unless already installed — prefer CSS transitions + `useEffect` for spring animations to keep bundle size controlled
