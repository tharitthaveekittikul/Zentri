# Theme Toggle Circular Reveal Animation

**Date:** 2026-05-06  
**Status:** Approved  

## Problem

The current theme toggle in `TopNav.tsx` uses a manual overlay `div` with `clip-path: circle()` to simulate a circular reveal. The overlay expands a flat background color — not actual rendered content. The theme (`setTheme`) is called immediately before the animation, so the theme flips instantly and the overlay just paints a flat circle on top. The result looks broken, not like a real reveal.

## Solution

Replace the overlay approach with the native **View Transition API** (`document.startViewTransition`). The browser snapshots the old state as a screenshot, applies the new theme in the callback, then animates between them via CSS `::view-transition` pseudo-elements. The CSS drives a `clip-path: circle()` reveal originating from the toggle button — showing real content (cards, sidebar, charts) rippling in.

## Files Changed

| File | Change |
|------|--------|
| `frontend/components/layout/TopNav.tsx` | Rewrite `toggleTheme()` to use View Transition API |
| `frontend/app/globals.css` | Update `::view-transition` rules to drive circular clip-path |

## Architecture

### `TopNav.tsx` — `toggleTheme()` rewrite

1. Compute button center `(x, y)` from `toggleRef.current.getBoundingClientRect()`
2. Write `--vt-x` and `--vt-y` as CSS custom properties on `document.documentElement`
3. Check `document.startViewTransition` exists:
   - **Not supported**: call `setTheme(newTheme)` directly (instant fallback)
   - **Supported**: call `document.startViewTransition(() => setTheme(newTheme))`
4. Remove all manual overlay `div` creation, animation, and cleanup code

### `globals.css` — `::view-transition` rules

```css
::view-transition-old(root) {
  animation: none;  /* freeze old state */
}

::view-transition-new(root) {
  clip-path: circle(0px at var(--vt-x) var(--vt-y));
  animation: vt-circle-reveal 500ms cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes vt-circle-reveal {
  from { clip-path: circle(0px at var(--vt-x) var(--vt-y)); }
  to   { clip-path: circle(200vmax at var(--vt-x) var(--vt-y)); }
}
```

**Easing:** `cubic-bezier(0.22, 1, 0.36, 1)` (expo-out) — snappy start, smooth deceleration.  
**Duration:** 500ms.

### Icon animation

No change. The existing `icon-spin-in` keyframe (`rotate(-90deg) scale(0.5) → rotate(0) scale(1)`) remains and is independent of the reveal transition.

### Accessibility

`prefers-reduced-motion` already suppresses all animations globally in `globals.css`. No extra handling needed — the View Transition animation is skipped automatically.

## Browser Support

| Browser | Support |
|---------|---------|
| Chrome 111+ | ✅ |
| Edge 111+ | ✅ |
| Firefox 128+ | ✅ |
| Safari 18+ | ✅ |
| Older browsers | Instant theme switch (fallback) |

## Success Criteria

- Clicking the toggle button produces a circle that expands from the button position
- The circle reveals the actual new-theme UI (not a flat color)
- On browsers without View Transition API, the theme still switches correctly (no error)
- `prefers-reduced-motion` users get an instant switch
- No layout shift, no flash of unstyled content
