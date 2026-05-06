# Layout Redesign Design Spec

**Date:** 2026-05-06
**Status:** Approved
**References:** `example/design/example-dashboard-1.webp` (Donezo), `example/design/example-web-2.webp` (Crextio)

## Overview

Redesign the app shell — Sidebar, TopNav, and mobile BottomTabBar — to match the visual language of the Donezo dashboard reference. Page titles move out of the header into each page's content area via a new `PageHeader` component.

---

## Section 1 — Sidebar

**File:** `frontend/components/layout/Sidebar.tsx`

### Changes
- **Section labels**: Same text ("Portfolio", "Tools") but styled more prominently — uppercase, tighter letter-spacing, slightly more visible color
- **Active nav item**: Solid filled background using `bg-sidebar-primary` with `text-sidebar-primary-foreground` — no glass/semi-transparency. Full-width rounded pill shape. Strong contrast (like Donezo's solid dark fill)
- **Inactive nav item**: Icon at 60% opacity, muted text, subtle hover fill — unchanged from current
- **Nav item padding**: Slightly taller (increase `py` by 1–2px) for more spacious feel
- **Width**: Stays `w-56`
- **Logo area**: Unchanged

---

## Section 2 — TopNav / Header

**File:** `frontend/components/layout/TopNav.tsx`

### Changes
- **Remove**: Desktop page title span and mobile centered page title span — page title moves into content
- **Add**: Pill-shaped search bar (replaces the icon-only search button)
  - Styled `rounded-full`, muted background (`bg-muted` or similar)
  - Placeholder: `"Search..."`
  - Right side of pill: small keyboard shortcut badge `⌘K`
  - Clicking still opens the command palette (existing `usePaletteStore`)
  - On mobile: pill shrinks (shorter width) but stays visible
- **Keep (right side)**: Privacy toggle, theme toggle, logout — same icon buttons, same order
- **Height**: Stays `h-14`
- **Layout**: `[search pill — grows] [privacy] [theme] [logout]`

---

## Section 3 — Mobile Bottom Tab Bar

**File:** `frontend/components/layout/BottomTabBar.tsx`

### Changes
- **Outer container**: Unchanged — floating `rounded-[26px]` glass card at bottom
- **Active item indicator**: Replace the current square `bg-foreground/[0.09]` box behind the icon with a wider landscape capsule pill — `rounded-full`, `px-4`, `bg-foreground/10` — wider than tall, horizontal pill shape matching Crextio's style
- **Active icon**: Full opacity, `strokeWidth={2.25}` (unchanged)
- **Active label**: Bold, full opacity (unchanged)
- **Inactive items**: Icon + label at 50% opacity, no background (unchanged)
- **Tabs**: 5 tabs unchanged (Overview, Portfolio, Watchlist, Net Worth, Settings)

---

## Section 4 — PageHeader Component + Page Updates

### New Component
**File:** `frontend/components/layout/PageHeader.tsx`

```
Props:
  title: string        — required, large bold page title
  description?: string — optional muted subtitle line
```

- `title`: `text-2xl font-bold tracking-tight`
- `description`: `text-sm text-muted-foreground mt-1` if provided
- Bottom margin: `mb-6` before the page content below

### Pages to Update
All pages under `frontend/app/(auth)/`:
- `/overview/page.tsx` → `<PageHeader title="Overview" />`
- `/portfolio/page.tsx` → `<PageHeader title="Portfolio" />`
- `/watchlist/page.tsx` → `<PageHeader title="Watchlist" />`
- `/net-worth/page.tsx` → `<PageHeader title="Net Worth" />`
- `/events/page.tsx` → `<PageHeader title="Events" />`
- `/transactions/page.tsx` → `<PageHeader title="Transactions" />`
- `/documents/page.tsx` → `<PageHeader title="Documents" />`
- `/pipeline/page.tsx` → `<PageHeader title="Pipeline" />`
- `/import/page.tsx` → `<PageHeader title="Import" />`
- `/ai-usage/page.tsx` → `<PageHeader title="AI Usage" />`
- `/settings/page.tsx` → `<PageHeader title="Settings" />`
- `/settings/backup/page.tsx` → `<PageHeader title="Backup" />`

Remove any existing in-page `<h1>` or title elements that duplicate the PageHeader.

---

## Implementation Order

1. `PageHeader` component
2. `Sidebar` redesign
3. `TopNav` redesign (remove title, add search pill)
4. `BottomTabBar` restyle (active pill indicator)
5. All pages — add `<PageHeader>` and remove duplicate titles
