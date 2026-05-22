# Zentri UI/UX Upgrade — Glassmorphism + Emil Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevate Zentri's UI across all pages using glassmorphism for chrome surfaces and Emil Kowalski-style expressive spring animations for interactive elements.

**Architecture:** Three phased layers — Phase 1 upgrades global tokens + shared layout chrome (every page improves immediately), Phase 2 upgrades the Overview screen, Phase 3 upgrades Portfolio and table views. All animation uses pure CSS transitions + React `useEffect` — no Framer Motion required.

**Tech Stack:** Next.js (app router), React, Tailwind CSS v4, shadcn/ui, Recharts, CSS custom properties (oklch color space)

**Spec:** `docs/superpowers/specs/2026-05-22-uxui-glassmorphism-emil-upgrade-design.md`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `frontend/app/globals.css` | Modify | Add motion tokens, elevation-hover, table-row-spring, card-surface hover lift |
| `frontend/components/layout/Sidebar.tsx` | Modify | Glass surface, spring active nav, logo mark |
| `frontend/components/layout/PageHeader.tsx` | Modify | Scroll-triggered sticky glass header |
| `frontend/hooks/useCountUp.ts` | Create | Animated number counter hook |
| `frontend/components/overview/KpiCards.tsx` | Modify | Staggered entrance, counter, glow pulse |
| `frontend/components/overview/PerformanceChart.tsx` | Modify | Recharts animation + glass tooltip |
| `frontend/components/overview/AllocationDonut.tsx` | Modify | Arc entrance animation + segment hover |
| `frontend/components/overview/HoldingsSnapshot.tsx` | Modify | Row stagger entrance |
| `frontend/app/(auth)/portfolio/page.tsx` | Modify | table-row-spring, sticky glass header, sort animation |
| `frontend/app/(auth)/watchlist/page.tsx` | Modify | Price badge pulse on update |
| `frontend/app/(auth)/transactions/page.tsx` | Modify | Signal colors at default opacity, sticky glass header |

---

## Phase 1 — Global Chrome

---

### Task 1: Add motion tokens and elevation-hover to globals.css

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Add motion tokens after the `@theme inline` block**

In `frontend/app/globals.css`, find the `@theme inline {` block (around line 3). Add these three tokens inside it, after the last existing `--color-*` entry:

```css
  --motion-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --motion-smooth: cubic-bezier(0.16, 1, 0.3, 1);
  --elevation-hover: 0 8px 32px oklch(0 0 0 / 30%), 0 2px 8px oklch(0 0 0 / 20%);
```

- [ ] **Step 2: Add card-in keyframe animation**

At the bottom of `globals.css`, before the final closing brace or after the last `@keyframes` block, add:

```css
@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pnl-pulse-gain {
  0%, 100% { box-shadow: 0 0 0 1px var(--signal-gain-bg), var(--card-shadow); }
  50%       { box-shadow: 0 0 0 4px transparent, var(--card-shadow); }
}

@keyframes pnl-pulse-loss {
  0%, 100% { box-shadow: 0 0 0 1px var(--signal-loss-bg), var(--card-shadow); }
  50%       { box-shadow: 0 0 0 4px transparent, var(--card-shadow); }
}
```

- [ ] **Step 3: Verify globals.css parses without errors**

Run:
```bash
cd /path/to/project/frontend && npx tsc --noEmit
```
Expected: no errors related to CSS (TypeScript won't catch CSS errors, but the dev server will). If you have the dev server running, check the terminal for CSS parse errors.

---

### Task 2: Add .table-row-spring utility and card-surface hover lift to globals.css

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Add transform to the existing card-surface transition**

Find the existing block (around lines 254–264):
```css
body,
.glass-chrome,
[data-slot="card"],
.card-surface {
  transition:
    background-color 250ms cubic-bezier(0.16, 1, 0.3, 1),
    border-color 200ms cubic-bezier(0.16, 1, 0.3, 1),
    color 200ms cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 250ms cubic-bezier(0.16, 1, 0.3, 1);
}
```

Replace with:
```css
body,
.glass-chrome,
[data-slot="card"],
.card-surface {
  transition:
    background-color 250ms cubic-bezier(0.16, 1, 0.3, 1),
    border-color 200ms cubic-bezier(0.16, 1, 0.3, 1),
    color 200ms cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 250ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 200ms var(--motion-spring);
}
```

- [ ] **Step 2: Add card-surface hover lift and specular border**

After the block you just edited, add:

```css
  .card-surface:hover {
    transform: translateY(-2px);
    box-shadow: var(--elevation-hover);
  }

  [data-slot="card"]:hover {
    transform: translateY(-2px);
    box-shadow: var(--elevation-hover);
  }
```

Also add a specular top border to card-surface. Find where `.card-surface` is first defined (around line 238) and add a `border-top`:

```css
  [data-slot="card"],
  .card-surface {
    box-shadow: var(--card-shadow);
    border-top: 1px solid oklch(1 0 0 / 12%);
  }
```

- [ ] **Step 3: Add .table-row-spring utility class**

Add this block to `globals.css` (outside `@layer`, at the root level, after the existing keyframes):

```css
.table-row-spring {
  position: relative;
  transition: background 120ms var(--motion-spring);
}

.table-row-spring::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
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

- [ ] **Step 4: Check dark mode card border**

The specular border `oklch(1 0 0 / 12%)` is a white border — correct for dark mode, but may be too visible in light mode. The existing `.dark .card-surface { border-width: 1px; }` already handles this. Wrap the border-top in the dark rule instead:

Find `.dark [data-slot="card"], .dark .card-surface { border-width: 1px; }` and add `border-top` to the light mode explicitly:

```css
  /* Specular catch-light — subtle in light, more visible in dark */
  [data-slot="card"],
  .card-surface {
    border-top: 1px solid oklch(1 0 0 / 8%);
  }
  .dark [data-slot="card"],
  .dark .card-surface {
    border-top: 1px solid oklch(1 0 0 / 14%);
  }
```

---

### Task 3: Upgrade Sidebar — glass surface + logo mark

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`

- [ ] **Step 1: Replace the sidebar inner container background**

In `Sidebar.tsx`, find:
```tsx
<div className="flex-1 bg-shell dark:bg-shell rounded-[24px] flex flex-col overflow-hidden">
```

Replace with:
```tsx
<div className="flex-1 rounded-[24px] flex flex-col overflow-hidden"
  style={{
    background: 'var(--glass-bg)',
    backdropFilter: `blur(var(--glass-blur)) saturate(var(--glass-saturate))`,
    WebkitBackdropFilter: `blur(var(--glass-blur)) saturate(var(--glass-saturate))`,
    boxShadow: 'inset 0 1px 0 var(--glass-specular)',
    border: '1px solid var(--glass-border)',
  }}
>
```

- [ ] **Step 2: Add logo mark to the logo area**

Find:
```tsx
<div className="flex items-center gap-4 px-5 h-20 shrink-0">
  <span className="text-base font-semibold tracking-[0.06em] uppercase text-brand-deep dark:text-brand-sage leading-none">
    Zentri
  </span>
</div>
```

Replace with:
```tsx
<div className="flex items-center gap-3 px-5 h-20 shrink-0">
  <div
    className="shrink-0 rounded-[6px]"
    style={{
      width: 24,
      height: 24,
      background: 'var(--gradient-brand)',
    }}
  />
  <span className="text-base font-semibold tracking-[0.06em] uppercase text-brand-deep dark:text-brand-sage leading-none">
    Zentri
  </span>
</div>
```

- [ ] **Step 3: Verify sidebar renders correctly in both light and dark mode**

Start the dev server (`npm run dev` in `frontend/`) and navigate to any page. Toggle dark mode. Sidebar should show glass blur effect with the gradient square mark. No layout breakage.

---

### Task 4: Upgrade Sidebar — spring active nav item

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add icon hover scale to NavItem**

Find the `NavItem` function in `Sidebar.tsx`. Find the `<Link>` inside it:
```tsx
<Link
  href={href}
  className={cn(
    "mx-3 flex items-center gap-3 px-3 py-2.5 rounded-full text-[15px] tracking-wide transition-colors duration-150",
    isActive
      ? "bg-brand-accent/10 dark:bg-brand-accent/15 text-brand-deep dark:text-brand-sage font-semibold"
      : "text-ink-muted/60 dark:text-ink-muted/60 font-normal hover:text-ink dark:hover:text-ink",
  )}
>
  <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.2} />
  {label}
</Link>
```

Replace with:
```tsx
<Link
  href={href}
  className={cn(
    "mx-3 flex items-center gap-3 px-3 py-2.5 rounded-full text-[15px] tracking-wide group",
    "transition-colors duration-150",
    isActive
      ? "bg-brand-accent/10 dark:bg-brand-accent/15 text-brand-deep dark:text-brand-sage font-semibold"
      : "text-ink-muted/60 dark:text-ink-muted/60 font-normal hover:text-ink dark:hover:text-ink",
  )}
  style={{ transition: 'color 150ms ease, background-color 150ms ease' }}
>
  <Icon
    className="h-[18px] w-[18px] shrink-0"
    strokeWidth={1.2}
    style={{
      transition: 'transform 120ms var(--motion-spring)',
    }}
    onMouseEnter={(e) => { (e.currentTarget as SVGElement).style.transform = 'scale(1.08)'; }}
    onMouseLeave={(e) => { (e.currentTarget as SVGElement).style.transform = 'scale(1)'; }}
  />
  {label}
</Link>
```

- [ ] **Step 2: Animate the 3px active indicator**

Find the active indicator `<span>`:
```tsx
<span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-full" style={{ background: 'var(--gradient-brand)' }} />
```

Replace with:
```tsx
<span
  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-full"
  style={{
    background: 'var(--gradient-brand)',
    transform: `translateY(-50%) scaleY(${isActive ? 1 : 0})`,
    transformOrigin: 'center',
    transition: 'transform 200ms var(--motion-spring)',
  }}
/>
```

- [ ] **Step 3: Update section label sizing**

Find the two section label `<p>` elements (for "Portfolio" and "Tools"):
```tsx
<p className="px-5 mb-2 text-[10px] font-semibold tracking-[0.12em] uppercase text-slate-400/70 dark:text-slate-500">
```

Change `text-slate-400/70` to `text-slate-400/80` and `dark:text-slate-500` to `dark:text-slate-400` in both.

- [ ] **Step 4: Verify nav animations**

In the dev server, click between nav items. The brand gradient indicator should spring-animate in (scale from center). Icon should scale 1.08 on hover. No flickering.

---

### Task 5: Upgrade PageHeader — scroll-triggered sticky glass

**Files:**
- Modify: `frontend/components/layout/PageHeader.tsx`

- [ ] **Step 1: Convert to client component with scroll detection**

Replace the entire contents of `frontend/components/layout/PageHeader.tsx` with:

```tsx
"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
}

export function PageHeader({ title, description }: PageHeaderProps) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className={cn(
        "sticky top-0 z-20 mb-6 px-1 py-4 -mx-1",
        "transition-all duration-150 ease-out"
      )}
      style={scrolled ? {
        backdropFilter: `blur(16px) saturate(160%)`,
        WebkitBackdropFilter: `blur(16px) saturate(160%)`,
        background: 'var(--glass-bg)',
        borderBottom: '1px solid var(--glass-border)',
      } : {}}
    >
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      {description && (
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify sticky header**

In the dev server, open a page with enough content to scroll (Portfolio or Transactions). Scroll down — the PageHeader should gain a glass blur and bottom border. Scroll back up — it returns to transparent. No layout jump.

---

## Phase 2 — Overview Screen

---

### Task 6: Create useCountUp hook

**Files:**
- Create: `frontend/hooks/useCountUp.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/hooks/useCountUp.ts`:

```ts
import { useEffect, useRef, useState } from "react";

function easeOutExpo(t: number): number {
  return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

export function useCountUp(target: number, duration = 800): number {
  const [value, setValue] = useState(0);
  const startRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    startRef.current = null;

    const animate = (timestamp: number) => {
      if (startRef.current === null) startRef.current = timestamp;
      const elapsed = timestamp - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      setValue(target * easeOutExpo(progress));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setValue(target);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration]);

  return value;
}
```

- [ ] **Step 2: Verify TypeScript**

Run:
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors in `hooks/useCountUp.ts`.

---

### Task 7: Upgrade KpiCards — stagger entrance + counter + glow pulse

**Files:**
- Modify: `frontend/components/overview/KpiCards.tsx`

- [ ] **Step 1: Add mounted state for stagger entrance**

In `KpiCards.tsx`, the outer `KpiCards` function needs a `mounted` state. Add at the top of the `KpiCards` function body:

```tsx
const [mounted, setMounted] = useState(false);
useEffect(() => {
  const t = setTimeout(() => setMounted(true), 50);
  return () => clearTimeout(t);
}, []);
```

Add `useState, useEffect` to the React import if not already present.

- [ ] **Step 2: Pass index and mounted to KpiCard**

Update the `KpiCards` return to pass `index` and `mounted` to each card:

```tsx
return (
  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
    <KpiCard
      label="Portfolio Value"
      value={format(summary.total_value)}
      index={0}
      mounted={mounted}
    />
    <KpiCard
      label="Total Cost"
      value={format(summary.total_cost)}
      index={1}
      mounted={mounted}
    />
    <KpiCard
      label="Total P&L"
      value={formatPnl(summary.total_pnl)}
      pct={<span className="inline-flex items-center gap-1">
        {pnlPositive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
        {formatPct(summary.total_pnl_pct)}
      </span>}
      direction={pnlPositive ? "positive" : "negative"}
      index={2}
      mounted={mounted}
    />
    <KpiCard
      label="Daily Change"
      value={formatPnl(summary.daily_change)}
      pct={<span className="inline-flex items-center gap-1">
        {dailyPositive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
        {formatPct(summary.daily_change_pct)}
      </span>}
      direction={dailyPositive ? "positive" : "negative"}
      index={3}
      mounted={mounted}
    />
  </div>
);
```

- [ ] **Step 3: Update KpiCard interface and apply entrance animation**

Update the `CardProps` interface:
```tsx
interface CardProps {
  label: string;
  value: DualValue;
  pct?: ReactNode;
  direction?: "positive" | "negative" | "neutral";
  index?: number;
  mounted?: boolean;
}
```

Update the `KpiCard` function signature:
```tsx
function KpiCard({ label, value, pct, direction = "neutral", index = 0, mounted = false }: CardProps) {
```

Update the card's outer `div` to apply entrance animation:
```tsx
<div
  className={cn("card-surface rounded-2xl p-5")}
  style={{
    backgroundColor: isPositive
      ? "var(--signal-gain-bg)"
      : isNegative
        ? "var(--signal-loss-bg)"
        : "var(--card)",
    animation: mounted
      ? `card-in 400ms var(--motion-smooth) ${index * 60}ms both`
      : undefined,
    opacity: mounted ? undefined : 0,
    ...(isColored ? {
      animation: mounted
        ? `card-in 400ms var(--motion-smooth) ${index * 60}ms both, ${
            isPositive ? 'pnl-pulse-gain' : 'pnl-pulse-loss'
          } 2s ease-in-out ${400 + index * 60}ms infinite`
        : undefined,
    } : {}),
  }}
>
```

- [ ] **Step 4: Add label hover brightening**

Add a `group` class to the card div and update the label `<p>`:
```tsx
<div className={cn("card-surface rounded-2xl p-5 group")} ...>
  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2 transition-colors duration-150 group-hover:text-foreground">
    {label}
  </p>
```

- [ ] **Step 5: Verify KpiCards**

Open the Overview page in the dev server. Hard-refresh (`Cmd+Shift+R`). Cards should stagger-animate in from below. P&L cards should have a subtle pulsing glow ring. Hover a card — label text brightens.

---

### Task 8: Upgrade PerformanceChart — Recharts animation + glass tooltip

**Files:**
- Modify: `frontend/components/overview/PerformanceChart.tsx`

- [ ] **Step 1: Enable explicit Recharts line animation**

In `PerformanceChart.tsx`, find the `<Line>` components and add explicit animation props:

```tsx
<Line
  type="monotone"
  dataKey="portfolio"
  stroke="var(--brand-accent)"
  strokeWidth={2}
  dot={false}
  isAnimationActive={true}
  animationDuration={1000}
  animationEasing="ease-out"
/>
<Line
  type="monotone"
  dataKey="benchmark"
  stroke="var(--brand-sage)"
  strokeWidth={1.5}
  dot={false}
  strokeDasharray="4 2"
  isAnimationActive={true}
  animationDuration={1200}
  animationEasing="ease-out"
/>
```

- [ ] **Step 2: Create a custom glass tooltip**

Add a `CustomTooltip` component above the `PerformanceChart` function:

```tsx
function CustomTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: string; name: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl px-3 py-2 text-xs"
      style={{
        background: 'var(--glass-bg)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        border: '1px solid var(--glass-border)',
        boxShadow: '0 4px 16px oklch(0 0 0 / 20%)',
      }}
    >
      <p className="font-medium text-foreground mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Replace the Tooltip usage**

Find `<Tooltip formatter={(v) => `${Number(v).toFixed(1)}`} />` and replace with:

```tsx
<Tooltip content={<CustomTooltip />} />
```

- [ ] **Step 4: Add chart container entrance animation**

Wrap the `<ResponsiveContainer>` in a div with entrance animation:

```tsx
<div
  style={{
    animation: 'card-in 500ms var(--motion-smooth) 200ms both',
  }}
>
  <ResponsiveContainer width="100%" height={208}>
    {/* ... existing LineChart ... */}
  </ResponsiveContainer>
</div>
```

- [ ] **Step 5: Verify chart**

Open Overview. The chart line should draw in (Recharts default animation). Hover the chart — a glass tooltip appears. No TypeScript errors.

---

### Task 9: Upgrade AllocationDonut — arc entrance + segment hover

**Files:**
- Modify: `frontend/components/overview/AllocationDonut.tsx`

- [ ] **Step 1: Read the current AllocationDonut**

Read `frontend/components/overview/AllocationDonut.tsx` to understand the current Recharts component structure before editing.

- [ ] **Step 2: Enable Recharts arc animation**

In the `<Pie>` component, add animation props:

```tsx
<Pie
  data={data}
  cx="50%"
  cy="50%"
  innerRadius={60}
  outerRadius={90}
  paddingAngle={2}
  dataKey="value"
  isAnimationActive={true}
  animationBegin={0}
  animationDuration={800}
  animationEasing="ease-out"
>
```

- [ ] **Step 3: Add segment hover dim effect**

Add a `hoveredIndex` state to the component:

```tsx
const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
```

Add `onMouseEnter` / `onMouseLeave` to each `<Cell>`:

```tsx
{data.map((entry, index) => (
  <Cell
    key={`cell-${index}`}
    fill={entry.color ?? COLORS[index % COLORS.length]}
    opacity={hoveredIndex === null || hoveredIndex === index ? 1 : 0.6}
    onMouseEnter={() => setHoveredIndex(index)}
    onMouseLeave={() => setHoveredIndex(null)}
    style={{ transition: 'opacity 150ms ease', cursor: 'pointer' }}
  />
))}
```

- [ ] **Step 4: Verify donut**

Open Overview. The donut arcs should animate in on load. Hover a segment — siblings dim to 60% opacity. No errors.

---

### Task 10: Upgrade HoldingsSnapshot — row stagger entrance

**Files:**
- Modify: `frontend/components/overview/HoldingsSnapshot.tsx`

- [ ] **Step 1: Read the current HoldingsSnapshot**

Read `frontend/components/overview/HoldingsSnapshot.tsx` to understand the row rendering structure.

- [ ] **Step 2: Add mounted state**

Add at the top of the component function:

```tsx
const [mounted, setMounted] = useState(false);
useEffect(() => {
  const t = setTimeout(() => setMounted(true), 50);
  return () => clearTimeout(t);
}, []);
```

- [ ] **Step 3: Apply row entrance animation**

Find the map over holdings rows. For each row element, add:

```tsx
style={{
  animation: mounted
    ? `card-in 300ms var(--motion-smooth) ${index * 40}ms both`
    : undefined,
  opacity: mounted ? undefined : 0,
}}
```

Where `index` is the map index.

- [ ] **Step 4: Wire useCountUp to numeric value cells (if applicable)**

After reading the file in Step 1, if HoldingsSnapshot renders raw numeric values (not via `DualCurrencyAmount`), wrap them with the hook:

```tsx
import { useCountUp } from "@/hooks/useCountUp";

// Inside the row component (extract to sub-component if needed):
const animatedValue = useCountUp(numericValue, 800);
// Then display: {formatCurrency(animatedValue)}
```

If rows use `DualCurrencyAmount` (which takes a `DualValue` object, not a raw number), skip this step — the entrance animation from Step 3 is sufficient.

- [ ] **Step 5: Verify**

Open Overview. Holdings rows should stagger-animate in from the left with a slight fade. No TypeScript errors.

---

## Phase 3 — Portfolio + Tables

---

### Task 11: Portfolio table — row hover, sticky header, sort animation

**Files:**
- Modify: `frontend/app/(auth)/portfolio/page.tsx`

- [ ] **Step 1: Read the portfolio page**

Read `frontend/app/(auth)/portfolio/page.tsx` to understand the Table structure and sort implementation.

- [ ] **Step 2: Apply .table-row-spring to portfolio rows**

Find the `<TableRow>` elements in the portfolio table. Add the utility class:

```tsx
<TableRow
  key={holding.id}
  className="table-row-spring"
>
```

- [ ] **Step 3: Add sticky glass header to portfolio table**

Find the `<TableHeader>` element. Apply:

```tsx
<TableHeader
  className="sticky top-0 z-10"
  style={{
    backdropFilter: 'blur(16px) saturate(160%)',
    WebkitBackdropFilter: 'blur(16px) saturate(160%)',
    background: 'var(--glass-bg)',
    borderBottom: '1px solid var(--glass-border)',
  }}
>
```

- [ ] **Step 4: Add sort indicator animation**

Find the sort column header buttons/icons. If the sort icon is rendered as a React element, wrap it in a `<span>` with a rotation style:

```tsx
<span
  style={{
    display: 'inline-block',
    transition: 'transform 150ms var(--motion-spring)',
    transform: sortDirection === 'desc' ? 'rotate(180deg)' : 'rotate(0deg)',
  }}
>
  {sortIcon}
</span>
```

If the column header is a button, also add opacity brightening on the sorted column header:

```tsx
className={cn(
  "transition-opacity duration-150",
  isSorted ? "opacity-100" : "opacity-70"
)}
```

- [ ] **Step 5: Add row entrance animation to portfolio**

Add `mounted` state to the portfolio page (same pattern as Task 7/10). Apply stagger to rows:

```tsx
<TableRow
  key={holding.id}
  className="table-row-spring"
  style={{
    animation: mounted
      ? `card-in 250ms var(--motion-smooth) ${Math.min(index * 25, 500)}ms both`
      : undefined,
    opacity: mounted ? undefined : 0,
  }}
>
```

Cap the max delay at 500ms (`Math.min(index * 25, 500)`) so the last rows of a long list don't wait forever.

- [ ] **Step 6: Verify portfolio table**

Open Portfolio. Table rows should animate in quickly. Hover a row — left brand-sage accent slides in. Table header sticks to the top with glass blur. Sort a column — arrow rotates with spring.

---

### Task 12: Watchlist — price badge pulse on update

**Files:**
- Modify: `frontend/app/(auth)/watchlist/page.tsx`

- [ ] **Step 1: Read the watchlist page**

Read `frontend/app/(auth)/watchlist/page.tsx` to understand the price display and polling setup.

- [ ] **Step 2: Apply .table-row-spring to watchlist rows**

Same as Task 11 Step 2 — add `className="table-row-spring"` to `<TableRow>` elements.

- [ ] **Step 3: Add sticky glass header**

Same as Task 11 Step 3 — apply to `<TableHeader>`.

- [ ] **Step 4: Add price badge pulse on change**

Find the price/change badge component in the watchlist row. Add a `useRef` to track the previous price and trigger animation:

```tsx
const prevPriceRef = useRef(item.current_price);
const [pulsing, setPulsing] = useState(false);

useEffect(() => {
  if (prevPriceRef.current !== item.current_price) {
    prevPriceRef.current = item.current_price;
    setPulsing(true);
    const t = setTimeout(() => setPulsing(false), 400);
    return () => clearTimeout(t);
  }
}, [item.current_price]);
```

Apply to the price element:

```tsx
<span
  style={{
    display: 'inline-block',
    transition: 'transform 300ms var(--motion-spring)',
    transform: pulsing ? 'scale(1.15)' : 'scale(1)',
  }}
>
  {formatPrice(item.current_price)}
</span>
```

If the price display is not in a per-row component, extract the row into a small `WatchlistRow` component so `useRef`/`useEffect` can be scoped per row.

- [ ] **Step 5: Verify watchlist**

Open Watchlist. Rows should animate in, have hover accent. If price polling is active (check the backend is running), the price badge should pulse scale when a value changes.

---

### Task 13: Transactions table — signal colors + sticky header

**Files:**
- Modify: `frontend/app/(auth)/transactions/page.tsx`

- [ ] **Step 1: Read the transactions page**

Read `frontend/app/(auth)/transactions/page.tsx` to understand the amount display and table structure.

- [ ] **Step 2: Apply .table-row-spring and sticky header**

Same as Task 11 Steps 2–3.

- [ ] **Step 3: Apply default signal colors to amount column**

Find the amount/value cell in the transactions table. Apply signal colors at 70% opacity **by default** (not hover-only — transactions are always directional):

```tsx
<TableCell>
  <span
    className="font-mono tabular-nums text-sm"
    style={{
      color: isDebit
        ? 'oklch(from var(--destructive) l c h / 0.7)'
        : 'oklch(from var(--brand-sage) l c h / 0.7)',
    }}
  >
    {isDebit ? '-' : '+'}{formatAmount(tx.amount)}
  </span>
</TableCell>
```

If `oklch(from ...)` relative color syntax isn't supported in the target browser, use:

```tsx
style={{
  color: isDebit ? 'var(--brand-danger)' : 'var(--brand-sage)',
  opacity: 0.7,
}}
```

- [ ] **Step 4: Add row entrance animation**

Same `mounted` + stagger pattern (25ms per row, max 500ms cap).

- [ ] **Step 5: Verify transactions**

Open Transactions page. Debit amounts show in muted danger color, credits in muted brand-sage. Rows animate in. Sticky glass header on scroll.

---

## Self-Review Checklist

After all tasks are complete:

- [ ] Run `cd frontend && npx tsc --noEmit` — zero errors
- [ ] Open Overview in light mode: KPI card stagger, chart draw, donut arc, holdings rows all animate on hard refresh
- [ ] Open Overview in dark mode: same — verify glass tokens render correctly
- [ ] Open Portfolio: sticky glass header, row hover accent, sort arrow rotation
- [ ] Open Watchlist: row hover accent, sticky header
- [ ] Open Transactions: signal colors visible, sticky header
- [ ] Open any page with PageHeader and scroll — header gains glass on scroll
- [ ] Sidebar: brand mark visible, nav indicator spring-animates on route change
- [ ] Check `prefers-reduced-motion` — all animations should be disabled (already handled by the existing `@media (prefers-reduced-motion: reduce)` block in globals.css)
