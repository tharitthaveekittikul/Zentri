# UI Revamp: Borderless Cards & Premium Minimal Design

**Date:** 2026-05-08  
**Scope:** Frontend content area only (sidebar and topnav unchanged)  
**Goal:** Remove all card borders, give every component its own white background, achieve a premium minimal look with white tiles on gray canvas. Mobile responsive throughout.

---

## Problem

In light mode, `--card: var(--page-bg)` makes cards the same color as the shell background (`#F8FAFC`). Cards are only visually defined by a faint 8%-opacity border. Without that border, components vanish into the background. The fix is to give cards a white background so the existing shadow system can do its job.

---

## Design

### 1. Token Changes (`frontend/app/globals.css`)

**Change `--card` in `:root` (light mode only):**
```css
--card: oklch(1 0 0);   /* was: var(--page-bg) */
```

This makes every `<Card>`, `bg-card`, and `.card-surface` element pure white, creating contrast against the gray shell (`oklch(0.984 0.003 264)` / `#F8FAFC`).

**Add border-removal rule in `@layer base`:**
```css
[data-slot="card"],
.card-surface {
  border-width: 0;
}
```

Overrides shadcn's `* { @apply border-border }` default. Shadow carries all depth.

**Shadow:** No change. `--card-shadow: 0 1px 4px oklch(0 0 0 / 5%), 0 6px 20px oklch(0 0 0 / 5%)` already applies automatically — it just becomes visible now that there's color contrast.

**Dark mode:** No token change needed (dark cards `oklch(0.13 0 0)` already contrast with black background). The border-removal rule applies to both modes for consistency.

---

### 2. Table Wrapper Pattern

Pages with naked tables/content need a white card wrapper added. Pattern:

```tsx
<div className="bg-card card-surface rounded-2xl overflow-hidden">
  {/* existing content */}
</div>
```

**Pages requiring wrappers:**

| Page | File | What gets wrapped |
|------|------|-------------------|
| Portfolio | `app/(auth)/portfolio/page.tsx` | Holdings table area (search bar + table) |
| Transactions | `app/(auth)/transactions/page.tsx` | Full table |
| Watchlist | `app/(auth)/watchlist/page.tsx` | Main table + AI Suggestions (separate cards) |
| Pipeline | `app/(auth)/pipeline/page.tsx` | Pipeline Jobs table |
| AI Usage | `app/(auth)/ai-usage/page.tsx` | Tabs + table |
| Documents | `app/(auth)/documents/page.tsx` | Filter bar + table |
| Events | `app/(auth)/events/page.tsx` | Calendar grid + Upcoming Events table (separate cards) |

**Already fixed by token change (no wrapper needed):**
- Overview: inline `bg-card card-surface` divs already present
- Net Worth: chart card uses `bg-card card-surface`
- Settings: uses `<Card>` components throughout
- Backup: uses `<Card>` components throughout
- Import: dropzone uses `<Card>` (dashed border on dropzone zone is intentional — keep)

---

### 3. Mobile Responsive Fixes

Applied during the same pass as table wrappers:

- **Horizontal scroll:** Add `overflow-x-auto` on all table wrapper divs so tables scroll on small screens instead of breaking layout
- **Text truncation:** Add `truncate` + `max-w-0` (or explicit max-width) on ticker/symbol/name columns that overflow on mobile
- **Stat card grids:** Ensure all multi-column stat card grids use responsive breakpoints: `grid-cols-1 sm:grid-cols-2 md:grid-cols-N`
- **Min-width columns:** Currency/numeric columns get `min-w-[80px]` or similar to prevent collapse
- **Net Worth chart:** Ensure chart container has `min-h-0` to prevent mobile overflow
- **Import page:** Center the upload area properly on mobile with responsive padding

---

### 4. Per-Page Notes

**Overview:** `PerformanceChart` and `AllocationDonut` are already wrapped in `bg-card card-surface rounded-2xl` inline divs — auto-fixed by token change.

**Net Worth:** Chart card auto-fixed. Add `min-h-0` to chart container for mobile.

**Import:** Dropzone dashed border is intentional visual element — do not remove it. The outer page card (if wrapping) uses `card-surface`.

**Events:** Two separate card sections — calendar grid and upcoming events list.

**Settings:** All sections already `<Card>` — auto-fixed. No manual work.

---

## Files to Change

| File | Change Type |
|------|-------------|
| `frontend/app/globals.css` | Token + CSS rule |
| `frontend/app/(auth)/portfolio/page.tsx` | Card wrapper + mobile |
| `frontend/app/(auth)/transactions/page.tsx` | Card wrapper + mobile |
| `frontend/app/(auth)/watchlist/page.tsx` | Card wrappers + mobile |
| `frontend/app/(auth)/pipeline/page.tsx` | Card wrapper + mobile |
| `frontend/app/(auth)/ai-usage/page.tsx` | Card wrapper + mobile |
| `frontend/app/(auth)/documents/page.tsx` | Card wrapper + mobile |
| `frontend/app/(auth)/events/page.tsx` | Card wrappers + mobile |
| `frontend/app/(auth)/net-worth/page.tsx` | Mobile min-h fix |
| `frontend/app/(auth)/import/page.tsx` | Mobile responsive padding |

---

## Out of Scope

- Sidebar, TopNav, BottomTabBar
- All component logic, data fetching, API calls
- Color palette, typography, brand tokens
- Dark mode token values
- Any new features
