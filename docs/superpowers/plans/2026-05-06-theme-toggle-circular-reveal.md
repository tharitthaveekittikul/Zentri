# Theme Toggle Circular Reveal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken flat-color overlay approach with the native View Transition API so the theme toggle produces a real circular reveal of actual UI content from the button position.

**Architecture:** Set CSS custom properties `--vt-x`/`--vt-y` on `<html>` before calling `document.startViewTransition(() => setTheme(newTheme))`. CSS drives `::view-transition-new(root)` with a `clip-path: circle()` keyframe animation originating from those coordinates. Browsers without View Transition API fall back to an instant theme switch.

**Tech Stack:** Next.js (App Router), next-themes, Web Animations API / View Transition API, CSS custom properties, Tailwind CSS + globals.css

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/app/globals.css` | Modify lines 200–205 | Split `::view-transition-old/new` rules; add `vt-circle-reveal` keyframe |
| `frontend/components/layout/TopNav.tsx` | Modify `toggleTheme()` | Replace overlay div logic with View Transition API call |

---

### Task 1: Update `::view-transition` CSS rules in `globals.css`

**Files:**
- Modify: `frontend/app/globals.css` (lines 200–205 — the existing `::view-transition-old(root), ::view-transition-new(root)` block)

> This is a pure CSS change — no tests. Verify visually in Task 3.

- [ ] **Step 1: Replace the existing view-transition block**

Find this block in `globals.css` (around line 200):

```css
/* View Transition — circular whoosh reveal from theme toggle */
::view-transition-old(root),
::view-transition-new(root) {
  animation: none;
  mix-blend-mode: normal;
}
```

Replace it with:

```css
/* View Transition — circular whoosh reveal from theme toggle */
::view-transition-old(root) {
  animation: none;
  mix-blend-mode: normal;
}

::view-transition-new(root) {
  mix-blend-mode: normal;
  clip-path: circle(0px at var(--vt-x, 50%) var(--vt-y, 50%));
  animation: vt-circle-reveal 500ms cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes vt-circle-reveal {
  from { clip-path: circle(0px at var(--vt-x, 50%) var(--vt-y, 50%)); }
  to   { clip-path: circle(200vmax at var(--vt-x, 50%) var(--vt-y, 50%)); }
}
```

> `200vmax` guarantees the circle always covers the full viewport regardless of aspect ratio. Defaults `50%` are fallbacks in case JS hasn't run yet.

- [ ] **Step 2: Verify CSS parses without error**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors (CSS syntax errors surface in Next.js build, not tsc, but this confirms the TS side is clean going into Task 2).

---

### Task 2: Rewrite `toggleTheme()` in `TopNav.tsx`

**Files:**
- Modify: `frontend/components/layout/TopNav.tsx` (lines 24–70 — the `toggleTheme` function)

> This is a browser animation feature. No unit test can capture the visual effect — verification is manual (Task 3).

- [ ] **Step 1: Replace the `toggleTheme` function body**

Find the full `toggleTheme` function in `TopNav.tsx` (lines 24–70):

```typescript
function toggleTheme() {
  const newTheme = resolvedTheme === "dark" ? "light" : "dark";
  const btn = toggleRef.current;

  const rect = btn?.getBoundingClientRect();
  const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
  const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;
  const endRadius = Math.hypot(
    Math.max(x, window.innerWidth - x),
    Math.max(y, window.innerHeight - y)
  );

  // Incoming theme background color
  const incomingBg =
    newTheme === "dark" ? "oklch(0.145 0.004 255)" : "oklch(0.95 0 0)";

  const overlay = document.createElement("div");
  overlay.style.cssText = `
    position: fixed;
    inset: 0;
    z-index: 99999;
    background: ${incomingBg};
    clip-path: circle(0px at ${x}px ${y}px);
    pointer-events: none;
    will-change: clip-path;
  `;
  document.body.appendChild(overlay);

  // Apply theme immediately so it renders under the overlay
  setTheme(newTheme);

  overlay
    .animate(
      [
        { clipPath: `circle(0px at ${x}px ${y}px)` },
        { clipPath: `circle(${endRadius}px at ${x}px ${y}px)` },
      ],
      {
        duration: 600,
        easing: "cubic-bezier(0.4, 0, 0.2, 1)",
        fill: "forwards",
      }
    )
    .addEventListener("finish", () => {
      requestAnimationFrame(() => overlay.remove());
    });
}
```

Replace with:

```typescript
function toggleTheme() {
  const newTheme = resolvedTheme === "dark" ? "light" : "dark";
  const btn = toggleRef.current;
  const rect = btn?.getBoundingClientRect();
  const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
  const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;

  document.documentElement.style.setProperty("--vt-x", `${x}px`);
  document.documentElement.style.setProperty("--vt-y", `${y}px`);

  if (!("startViewTransition" in document)) {
    setTheme(newTheme);
    return;
  }

  (document as Document & { startViewTransition: (cb: () => void) => void })
    .startViewTransition(() => setTheme(newTheme));
}
```

- [ ] **Step 2: Confirm TypeScript compiles cleanly**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: 0 errors. If TypeScript reports `startViewTransition` not found despite the `in` guard, the cast handles it — but confirm no errors.

---

### Task 3: Manual visual verification

- [ ] **Step 1: Start the dev server**

```bash
cd frontend && npm run dev
```

Navigate to `http://localhost:3000` and log in.

- [ ] **Step 2: Verify circular reveal — dark → light**

Click the Sun/Moon button in the top-right nav.  
Expected:
- A circle expands from the button position outward
- Inside the circle: the actual new-theme UI (cards, sidebar, correct colors) — not a flat color
- The old theme is frozen outside the circle until covered
- Total duration ≈ 500ms, decelerating smoothly (expo-out)

- [ ] **Step 3: Verify circular reveal — light → dark**

Click again.  
Expected: same circular reveal, same origin point, correct dark theme content visible through the expanding circle.

- [ ] **Step 4: Verify icon animation still works**

Confirm the Sun/Moon icon still spins in on each toggle (`icon-spin-in` keyframe). It should be unaffected.

- [ ] **Step 5: Verify reduced-motion fallback**

In Chrome DevTools → Rendering → Emulate CSS media feature → `prefers-reduced-motion: reduce`.  
Click the toggle.  
Expected: theme switches instantly with no animation.

- [ ] **Step 6: Verify fallback for unsupported browsers (optional)**

In DevTools console:
```javascript
delete document.startViewTransition;
```
Then click toggle.  
Expected: theme switches instantly, no error in console.
