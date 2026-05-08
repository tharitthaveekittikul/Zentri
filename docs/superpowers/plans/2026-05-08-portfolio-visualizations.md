# Portfolio Visualizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Grid (treemap), Swarm (beeswarm), and Bubbles (circle pack) visualization views to the `/portfolio` page as toggleable alternatives to the existing holdings table.

**Architecture:** Port three pure-JS layout classes from the local subgrid project (`/Users/tharitthaveekittikul/Documents/03_Projects/subgrid/js/`) to TypeScript utilities. Each layout class takes an array of `PortfolioViewItem` and returns pixel-positioned output. React view components render the output as absolutely-positioned divs, sized/colored by market value and P&L.

**Tech Stack:** Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, Lucide React, `@tanstack/react-query` (existing). No new npm dependencies.

---

## File Map

| Action | File                                                    | Responsibility                                    |
| ------ | ------------------------------------------------------- | ------------------------------------------------- |
| Create | `frontend/lib/visualizations/types.ts`                  | Shared types, color utility, holdings transformer |
| Create | `frontend/hooks/useResizeObserver.ts`                   | Watch container size for layout recompute         |
| Create | `frontend/lib/visualizations/treemap.ts`                | Squarified treemap layout class                   |
| Create | `frontend/lib/visualizations/beeswarm.ts`               | Beeswarm dot layout class                         |
| Create | `frontend/lib/visualizations/circlepack.ts`             | Circle packing layout class                       |
| Create | `frontend/components/portfolio/PortfolioViewToggle.tsx` | 4-button view toggle                              |
| Create | `frontend/components/portfolio/TreemapView.tsx`         | Grid view renderer                                |
| Create | `frontend/components/portfolio/BeeswarmView.tsx`        | Swarm view renderer                               |
| Create | `frontend/components/portfolio/CirclepackView.tsx`      | Bubbles view renderer                             |
| Modify | `frontend/app/(auth)/portfolio/page.tsx`                | Add view state, toggle, and conditional rendering |

---

### Task 1: Shared types, color utility, and holdings transformer

**Files:**

- Create: `frontend/lib/visualizations/types.ts`

- [ ] **Step 1: Create the file**

```typescript
// frontend/lib/visualizations/types.ts

export type ViewMode = "table" | "grid" | "swarm" | "bubbles";

export interface PortfolioViewItem {
  symbol: string;
  val: number; // market value (holding_value as number)
  pnlPct: number; // (unrealized_pnl / total_cost) * 100
  portfolioPct: number; // (val / sum of all vals) * 100
  displayValue: string; // formatted e.g. "1,234.56"
}

export interface TreemapCell extends PortfolioViewItem {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface VisDot extends PortfolioViewItem {
  x: number;
  y: number;
  radius: number;
}

export function getHoldingColor(pnlPct: number): {
  bg: string;
  accent: string;
} {
  if (pnlPct > 0) return { bg: "#16a34a", accent: "#22c55e" };
  if (pnlPct < 0) return { bg: "#dc2626", accent: "#ef4444" };
  return { bg: "#4b5563", accent: "#6b7280" };
}

export function holdingsToViewItems(
  holdings: Array<{
    symbol: string;
    asset_type: string;
    holding_value: string | null;
    unrealized_pnl: string | null;
    total_cost: string;
  }>,
): PortfolioViewItem[] {
  const items = holdings
    .filter(
      (h) =>
        h.asset_type !== "cash" &&
        h.holding_value != null &&
        Number(h.holding_value) > 0,
    )
    .map((h) => ({
      symbol: h.symbol,
      val: Number(h.holding_value),
      pnlPct:
        Number(h.total_cost) > 0
          ? (Number(h.unrealized_pnl ?? 0) / Number(h.total_cost)) * 100
          : 0,
      displayValue: Number(h.holding_value).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
    }));

  const total = items.reduce((sum, i) => sum + i.val, 0);
  return items.map((i) => ({
    ...i,
    portfolioPct: total > 0 ? (i.val / total) * 100 : 0,
  }));
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors for the new file (other pre-existing errors are acceptable).

---

### Task 2: useResizeObserver hook

**Files:**

- Create: `frontend/hooks/useResizeObserver.ts`

- [ ] **Step 1: Create the hook**

```typescript
// frontend/hooks/useResizeObserver.ts
import { useEffect, useRef, useState } from "react";

export function useResizeObserver<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const update = (w: number, h: number) => {
      if (w > 0 && h > 0) setSize({ width: w, height: h });
    };

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) update(entry.contentRect.width, entry.contentRect.height);
    });

    observer.observe(el);
    const rect = el.getBoundingClientRect();
    update(rect.width, rect.height);

    return () => observer.disconnect();
  }, []);

  return { ref, width: size.width, height: size.height };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors for the new file.

---

### Task 3: Treemap layout class

**Files:**

- Create: `frontend/lib/visualizations/treemap.ts`
- Reference: `/Users/tharitthaveekittikul/Documents/03_Projects/subgrid/js/treemap.js`

- [ ] **Step 1: Create the TypeScript port**

```typescript
// frontend/lib/visualizations/treemap.ts
import { PortfolioViewItem, TreemapCell } from "./types";

interface WorkItem extends PortfolioViewItem {
  area: number;
}

interface Bounds {
  nx: number;
  ny: number;
  nw: number;
  nh: number;
}

export class Treemap {
  private cellGap = 4;

  constructor(
    private width: number,
    private height: number,
  ) {}

  layout(items: PortfolioViewItem[]): TreemapCell[] {
    if (items.length === 0) return [];

    const total = items.reduce((s, i) => s + i.val, 0);
    if (total === 0) return [];

    const totalArea = this.width * this.height;
    const normalized: WorkItem[] = items.map((item) => ({
      ...item,
      area: (item.val / total) * totalArea,
    }));

    const rectangles: TreemapCell[] = [];
    this._squarify(normalized, [], 0, 0, this.width, this.height, rectangles);
    return rectangles;
  }

  private _squarify(
    remaining: WorkItem[],
    currentRow: WorkItem[],
    x: number,
    y: number,
    w: number,
    h: number,
    output: TreemapCell[],
  ): void {
    if (remaining.length === 0) {
      this._layoutRow(currentRow, x, y, w, h, output);
      return;
    }

    const next = remaining[0];
    const withNext = currentRow.concat([next]);

    if (
      currentRow.length === 0 ||
      this._worstRatio(currentRow, w, h) >= this._worstRatio(withNext, w, h)
    ) {
      this._squarify(remaining.slice(1), withNext, x, y, w, h, output);
    } else {
      const bounds = this._layoutRow(currentRow, x, y, w, h, output);
      this._squarify(
        remaining,
        [],
        bounds.nx,
        bounds.ny,
        bounds.nw,
        bounds.nh,
        output,
      );
    }
  }

  private _worstRatio(row: WorkItem[], w: number, h: number): number {
    if (row.length === 0) return Infinity;

    const areaSum = row.reduce((s, i) => s + i.area, 0);
    const shortSide = Math.min(w, h);
    if (shortSide === 0) return Infinity;

    const rowThickness = areaSum / shortSide;
    if (rowThickness === 0) return Infinity;

    let worstRatio = 0;
    for (const item of row) {
      const itemLength = item.area / rowThickness;
      if (itemLength === 0) continue;
      const ratio = Math.max(
        rowThickness / itemLength,
        itemLength / rowThickness,
      );
      if (ratio > worstRatio) worstRatio = ratio;
    }
    return worstRatio;
  }

  private _layoutRow(
    row: WorkItem[],
    x: number,
    y: number,
    w: number,
    h: number,
    output: TreemapCell[],
  ): Bounds {
    if (row.length === 0) return { nx: x, ny: y, nw: w, nh: h };

    const areaSum = row.reduce((s, i) => s + i.area, 0);
    const horizontal = w >= h;
    const shortSide = horizontal ? h : w;
    const thickness = areaSum / shortSide;
    const gap = this.cellGap;

    let offset = 0;
    for (const item of row) {
      const length = item.area / thickness;
      if (horizontal) {
        output.push({
          ...item,
          x: x + gap / 2,
          y: y + offset + gap / 2,
          w: thickness - gap,
          h: length - gap,
        });
      } else {
        output.push({
          ...item,
          x: x + offset + gap / 2,
          y: y + gap / 2,
          w: length - gap,
          h: thickness - gap,
        });
      }
      offset += length;
    }

    return horizontal
      ? { nx: x + thickness, ny: y, nw: w - thickness, nh: h }
      : { nx: x, ny: y + thickness, nw: w, nh: h - thickness };
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors for the new file.

---

### Task 4: Beeswarm layout class

**Files:**

- Create: `frontend/lib/visualizations/beeswarm.ts`
- Reference: `/Users/tharitthaveekittikul/Documents/03_Projects/subgrid/js/beeswarm.js`

- [ ] **Step 1: Create the TypeScript port**

```typescript
// frontend/lib/visualizations/beeswarm.ts
import { PortfolioViewItem, VisDot } from "./types";

export class Beeswarm {
  private centerY: number;

  constructor(
    private width: number,
    private height: number,
    private padding = 20,
    private isMobile = false,
  ) {
    this.centerY = height / 2;
  }

  layout(items: PortfolioViewItem[]): VisDot[] {
    if (!items.length) return [];

    // cheap items first for balanced distribution when pushing y
    const sorted = [...items].sort((a, b) => a.val - b.val);
    const vals = sorted.map((d) => d.val);
    const minVal = Math.min(...vals);
    const maxVal = Math.max(...vals);

    const minRadius = this.isMobile ? 10 : 14;
    const maxRadius = this.isMobile ? 25 : 35;
    const minDistance = 4;

    const withRadius = sorted.map((item) => {
      const ratio =
        maxVal === minVal ? 0.5 : (item.val - minVal) / (maxVal - minVal);
      const radius = minRadius + Math.sqrt(ratio) * (maxRadius - minRadius);
      return { ...item, radius };
    });

    const xScale = (val: number): number => {
      if (maxVal === minVal) return this.width / 2;
      return (
        this.padding +
        ((val - minVal) / (maxVal - minVal)) * (this.width - 2 * this.padding)
      );
    };

    const placed: VisDot[] = [];

    for (const item of withRadius) {
      const x = xScale(item.val);
      let y = this.centerY;
      let direction = 1;
      let step = item.radius + minDistance;

      while (this._hasOverlap(x, y, item.radius, placed, minDistance)) {
        y = this.centerY + direction * step;
        direction =
          direction > 0
            ? -(step + item.radius + minDistance) / step
            : (step + item.radius + minDistance) / step;
        step += item.radius * 0.5;
        if (step > this.height) break;
      }

      placed.push({ ...item, x, y });
    }

    return this._normalizeY(placed);
  }

  private _hasOverlap(
    x: number,
    y: number,
    radius: number,
    placed: VisDot[],
    minDistance: number,
  ): boolean {
    for (const item of placed) {
      const dx = x - item.x;
      const dy = y - item.y;
      if (Math.sqrt(dx * dx + dy * dy) < radius + item.radius + minDistance) {
        return true;
      }
    }
    return false;
  }

  private _normalizeY(items: VisDot[]): VisDot[] {
    if (!items.length) return items;
    const ys = items.map((d) => d.y);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const rangeY = maxY - minY;
    const availableHeight = this.height - this.padding * 2;
    const scale = rangeY > 0 ? Math.min(1, availableHeight / rangeY) : 1;
    const centerCurrent = (minY + maxY) / 2;
    return items.map((item) => ({
      ...item,
      y: this.centerY + (item.y - centerCurrent) * scale,
    }));
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors for the new file.

---

### Task 5: CirclePack layout class

**Files:**

- Create: `frontend/lib/visualizations/circlepack.ts`
- Reference: `/Users/tharitthaveekittikul/Documents/03_Projects/subgrid/js/circlepack.js`

- [ ] **Step 1: Create the TypeScript port**

```typescript
// frontend/lib/visualizations/circlepack.ts
import { PortfolioViewItem, VisDot } from "./types";

interface PlacedCircle extends VisDot {
  radius: number;
}

export class CirclePack {
  private centerX: number;
  private centerY: number;

  constructor(
    private width: number,
    private height: number,
    private padding = 20,
  ) {
    this.centerX = width / 2;
    this.centerY = height / 2;
  }

  layout(items: PortfolioViewItem[]): VisDot[] {
    if (!items.length) return [];

    const sorted = [...items].sort((a, b) => b.val - a.val);
    const vals = sorted.map((d) => d.val);
    const minVal = Math.min(...vals);
    const maxVal = Math.max(...vals);

    const availableArea = Math.min(this.width, this.height) * 0.45;
    const minRadius = 20;
    const maxRadius = Math.min(80, availableArea * 0.4);

    const withRadius = sorted.map((item) => {
      const ratio =
        maxVal === minVal ? 0.5 : (item.val - minVal) / (maxVal - minVal);
      const radius = minRadius + Math.sqrt(ratio) * (maxRadius - minRadius);
      return { ...item, radius };
    });

    return this._packCircles(withRadius);
  }

  private _packCircles(circles: PlacedCircle[]): VisDot[] {
    if (circles.length === 0) return [];
    if (circles.length === 1) {
      return [{ ...circles[0], x: this.centerX, y: this.centerY }];
    }

    const placed: PlacedCircle[] = [];

    placed.push({ ...circles[0], x: this.centerX, y: this.centerY });
    placed.push({
      ...circles[1],
      x: this.centerX + circles[0].radius + circles[1].radius + 4,
      y: this.centerY,
    });

    for (let i = 2; i < circles.length; i++) {
      const circle = circles[i];
      const pos = this._findBestPosition(circle.radius, placed);
      placed.push({ ...circle, x: pos.x, y: pos.y });
    }

    return this._centerPack(placed);
  }

  private _findBestPosition(
    radius: number,
    placed: PlacedCircle[],
  ): { x: number; y: number } {
    let bestPos: { x: number; y: number } | null = null;
    let bestDist = Infinity;

    for (let i = 0; i < placed.length; i++) {
      for (let j = i + 1; j < placed.length; j++) {
        const positions = this._tangentPositions(placed[i], placed[j], radius);
        for (const pos of positions) {
          if (!this._hasCollision(pos.x, pos.y, radius, placed)) {
            const dist = Math.sqrt(
              Math.pow(pos.x - this.centerX, 2) +
                Math.pow(pos.y - this.centerY, 2),
            );
            if (dist < bestDist) {
              bestDist = dist;
              bestPos = pos;
            }
          }
        }
      }
    }

    if (!bestPos) {
      const angles = [
        0,
        Math.PI / 4,
        Math.PI / 2,
        (3 * Math.PI) / 4,
        Math.PI,
        (5 * Math.PI) / 4,
        (3 * Math.PI) / 2,
        (7 * Math.PI) / 4,
      ];
      for (const p of placed) {
        for (const angle of angles) {
          const dist = p.radius + radius + 4;
          const x = p.x + Math.cos(angle) * dist;
          const y = p.y + Math.sin(angle) * dist;
          if (!this._hasCollision(x, y, radius, placed)) {
            const d = Math.sqrt(
              Math.pow(x - this.centerX, 2) + Math.pow(y - this.centerY, 2),
            );
            if (d < bestDist) {
              bestDist = d;
              bestPos = { x, y };
            }
          }
        }
      }
    }

    return bestPos ?? { x: this.centerX, y: this.centerY };
  }

  private _tangentPositions(
    c1: PlacedCircle,
    c2: PlacedCircle,
    r: number,
  ): { x: number; y: number }[] {
    const d = Math.sqrt(Math.pow(c2.x - c1.x, 2) + Math.pow(c2.y - c1.y, 2));
    if (d === 0) return [];

    const a =
      (Math.pow(c1.radius + r, 2) - Math.pow(c2.radius + r, 2) + d * d) /
      (2 * d);
    const h2 = Math.pow(c1.radius + r, 2) - a * a;
    if (h2 < 0) return [];

    const h = Math.sqrt(h2);
    const px = c1.x + (a * (c2.x - c1.x)) / d;
    const py = c1.y + (a * (c2.y - c1.y)) / d;
    const dx = (h * (c2.y - c1.y)) / d;
    const dy = (h * (c2.x - c1.x)) / d;

    return [
      { x: px + dx, y: py - dy },
      { x: px - dx, y: py + dy },
    ];
  }

  private _hasCollision(
    x: number,
    y: number,
    radius: number,
    placed: PlacedCircle[],
  ): boolean {
    const gap = 4;
    for (const p of placed) {
      const dist = Math.sqrt(Math.pow(x - p.x, 2) + Math.pow(y - p.y, 2));
      if (dist < radius + p.radius + gap) return true;
    }
    return false;
  }

  private _centerPack(circles: PlacedCircle[]): VisDot[] {
    if (!circles.length) return [];

    let minX = Infinity,
      maxX = -Infinity;
    let minY = Infinity,
      maxY = -Infinity;

    for (const c of circles) {
      minX = Math.min(minX, c.x - c.radius);
      maxX = Math.max(maxX, c.x + c.radius);
      minY = Math.min(minY, c.y - c.radius);
      maxY = Math.max(maxY, c.y + c.radius);
    }

    const packWidth = maxX - minX;
    const packHeight = maxY - minY;
    const packCenterX = (minX + maxX) / 2;
    const packCenterY = (minY + maxY) / 2;

    const scaleX = (this.width - this.padding * 2) / packWidth;
    const scaleY = (this.height - this.padding * 2) / packHeight;
    const scale = Math.min(1, scaleX, scaleY);

    return circles.map((c) => ({
      ...c,
      x: this.centerX + (c.x - packCenterX) * scale,
      y: this.centerY + (c.y - packCenterY) * scale,
      radius: c.radius * scale,
    }));
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors for the new file.

---

### Task 6: PortfolioViewToggle component

**Files:**

- Create: `frontend/components/portfolio/PortfolioViewToggle.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/portfolio/PortfolioViewToggle.tsx
"use client";

import { LayoutGrid, List, ScatterChart, Circle } from "lucide-react";
import { ViewMode } from "@/lib/visualizations/types";

interface Props {
  view: ViewMode;
  onChange: (view: ViewMode) => void;
}

const VIEWS: { mode: ViewMode; icon: React.ReactNode; label: string }[] = [
  { mode: "table", icon: <List className="h-4 w-4" />, label: "Table" },
  { mode: "grid", icon: <LayoutGrid className="h-4 w-4" />, label: "Grid" },
  { mode: "swarm", icon: <ScatterChart className="h-4 w-4" />, label: "Swarm" },
  { mode: "bubbles", icon: <Circle className="h-4 w-4" />, label: "Bubbles" },
];

export function PortfolioViewToggle({ view, onChange }: Props) {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/40 p-1">
      {VIEWS.map(({ mode, icon, label }) => (
        <button
          key={mode}
          onClick={() => onChange(mode)}
          title={label}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            view === mode
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {icon}
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors for the new file.

---

### Task 7: TreemapView component

**Files:**

- Create: `frontend/components/portfolio/TreemapView.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/portfolio/TreemapView.tsx
"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { Treemap } from "@/lib/visualizations/treemap";
import { getHoldingColor, PortfolioViewItem } from "@/lib/visualizations/types";
import { useResizeObserver } from "@/hooks/useResizeObserver";

interface Props {
  items: PortfolioViewItem[];
}

export function TreemapView({ items }: Props) {
  const router = useRouter();
  const { ref, width, height } = useResizeObserver<HTMLDivElement>();

  const cells = useMemo(() => {
    if (width === 0 || height === 0 || items.length === 0) return [];
    return new Treemap(width, height).layout(items);
  }, [items, width, height]);

  return (
    <div ref={ref} className="relative w-full h-[520px]">
      {items.length === 0 && (
        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
          Add holdings to see visualization
        </div>
      )}
      {cells.map((cell) => {
        const color = getHoldingColor(cell.pnlPct);
        const minDim = Math.min(cell.w, cell.h);
        const showSymbol = minDim > 28;
        const showValue = minDim > 52;
        const showBadge = minDim > 44;
        const fontSize = Math.max(10, Math.min(minDim * 0.18, 16));
        const valueSize = Math.max(9, Math.min(minDim * 0.13, 12));

        return (
          <div
            key={cell.symbol}
            onClick={() => router.push(`/portfolio/${cell.symbol}`)}
            className="absolute cursor-pointer group overflow-hidden rounded-lg"
            style={{
              left: cell.x,
              top: cell.y,
              width: cell.w,
              height: cell.h,
              background: `linear-gradient(135deg, ${color.bg} 0%, ${color.accent} 100%)`,
            }}
          >
            {/* Hover overlay */}
            <div className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-colors rounded-lg" />

            {/* Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20 whitespace-nowrap">
              <div className="bg-popover text-popover-foreground text-xs rounded-lg px-3 py-2 shadow-xl border border-border">
                <div className="font-semibold">{cell.symbol}</div>
                <div className="text-muted-foreground">{cell.displayValue}</div>
                <div className="text-muted-foreground">
                  {cell.portfolioPct.toFixed(1)}% of portfolio
                </div>
                <div style={{ color: color.accent }}>
                  {cell.pnlPct >= 0 ? "+" : ""}
                  {cell.pnlPct.toFixed(2)}%
                </div>
              </div>
            </div>

            {showSymbol && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5 p-1 text-center">
                {showBadge && (
                  <span className="absolute top-1.5 right-1.5 text-[9px] font-bold bg-black/20 px-1.5 py-0.5 rounded-full text-white">
                    {cell.pnlPct >= 0 ? "+" : ""}
                    {cell.pnlPct.toFixed(1)}%
                  </span>
                )}
                <span
                  className="font-bold text-white leading-none"
                  style={{ fontSize }}
                >
                  {cell.symbol}
                </span>
                {showValue && (
                  <span
                    className="text-white/80 font-medium"
                    style={{ fontSize: valueSize }}
                  >
                    {cell.displayValue}
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors for the new file.

---

### Task 8: BeeswarmView component

**Files:**

- Create: `frontend/components/portfolio/BeeswarmView.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/portfolio/BeeswarmView.tsx
"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { Beeswarm } from "@/lib/visualizations/beeswarm";
import { getHoldingColor, PortfolioViewItem } from "@/lib/visualizations/types";
import { useResizeObserver } from "@/hooks/useResizeObserver";

interface Props {
  items: PortfolioViewItem[];
}

export function BeeswarmView({ items }: Props) {
  const router = useRouter();
  const { ref, width, height } = useResizeObserver<HTMLDivElement>();

  const dots = useMemo(() => {
    if (width === 0 || height === 0 || items.length === 0) return [];
    const isMobile = width < 500;
    return new Beeswarm(width, height, isMobile ? 20 : 40, isMobile).layout(
      items,
    );
  }, [items, width, height]);

  return (
    <div ref={ref} className="relative w-full h-[520px]">
      {items.length === 0 && (
        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
          Add holdings to see visualization
        </div>
      )}
      {/* Center axis line */}
      {dots.length > 0 && (
        <div
          className="absolute left-0 right-0 border-t border-border/40"
          style={{ top: height / 2 }}
        />
      )}
      {dots.map((dot) => {
        const color = getHoldingColor(dot.pnlPct);
        const size = dot.radius * 2;
        const showLabel = dot.radius > 18;

        return (
          <div
            key={dot.symbol}
            onClick={() => router.push(`/portfolio/${dot.symbol}`)}
            className="absolute cursor-pointer group"
            style={{
              left: dot.x,
              top: dot.y,
              width: size,
              height: size,
              transform: "translate(-50%, -50%)",
            }}
          >
            {/* Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20 whitespace-nowrap">
              <div className="bg-popover text-popover-foreground text-xs rounded-lg px-3 py-2 shadow-xl border border-border">
                <div className="font-semibold">{dot.symbol}</div>
                <div className="text-muted-foreground">{dot.displayValue}</div>
                <div className="text-muted-foreground">
                  {dot.portfolioPct.toFixed(1)}% of portfolio
                </div>
                <div style={{ color: color.accent }}>
                  {dot.pnlPct >= 0 ? "+" : ""}
                  {dot.pnlPct.toFixed(2)}%
                </div>
              </div>
              <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-popover" />
            </div>

            <div
              className="w-full h-full rounded-full shadow-md transition-transform group-hover:scale-110 flex items-center justify-center"
              style={{
                background: `linear-gradient(135deg, ${color.bg} 0%, ${color.accent} 100%)`,
              }}
            >
              {showLabel && (
                <span className="text-white font-bold text-[10px] leading-none text-center px-0.5">
                  {dot.symbol.length > 4 ? dot.symbol.slice(0, 4) : dot.symbol}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors for the new file.

---

### Task 9: CirclepackView component

**Files:**

- Create: `frontend/components/portfolio/CirclepackView.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/portfolio/CirclepackView.tsx
"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { CirclePack } from "@/lib/visualizations/circlepack";
import { getHoldingColor, PortfolioViewItem } from "@/lib/visualizations/types";
import { useResizeObserver } from "@/hooks/useResizeObserver";

interface Props {
  items: PortfolioViewItem[];
}

export function CirclepackView({ items }: Props) {
  const router = useRouter();
  const { ref, width, height } = useResizeObserver<HTMLDivElement>();

  const circles = useMemo(() => {
    if (width === 0 || height === 0 || items.length === 0) return [];
    return new CirclePack(width, height, 30).layout(items);
  }, [items, width, height]);

  return (
    <div ref={ref} className="relative w-full h-[520px]">
      {items.length === 0 && (
        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
          Add holdings to see visualization
        </div>
      )}
      {circles.map((circle) => {
        const color = getHoldingColor(circle.pnlPct);
        const size = circle.radius * 2;
        const showName = circle.radius > 28;
        const showPnl = circle.radius > 38;
        const fontSize = Math.max(8, Math.min(circle.radius * 0.22, 14));
        const pnlSize = Math.max(8, Math.min(circle.radius * 0.18, 11));

        return (
          <div
            key={circle.symbol}
            onClick={() => router.push(`/portfolio/${circle.symbol}`)}
            className="absolute cursor-pointer group transition-transform duration-200 hover:scale-105"
            style={{
              left: circle.x,
              top: circle.y,
              width: size,
              height: size,
              transform: "translate(-50%, -50%)",
            }}
          >
            {/* Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20 whitespace-nowrap">
              <div className="bg-popover text-popover-foreground text-xs rounded-lg px-3 py-2 shadow-xl border border-border">
                <div className="font-semibold">{circle.symbol}</div>
                <div className="text-muted-foreground">
                  {circle.displayValue}
                </div>
                <div className="text-muted-foreground">
                  {circle.portfolioPct.toFixed(1)}% of portfolio
                </div>
                <div style={{ color: color.accent }}>
                  {circle.pnlPct >= 0 ? "+" : ""}
                  {circle.pnlPct.toFixed(2)}%
                </div>
              </div>
              <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-popover" />
            </div>

            <div
              className="w-full h-full rounded-full shadow-lg flex flex-col items-center justify-center overflow-hidden transition-shadow hover:shadow-xl"
              style={{
                background: `linear-gradient(135deg, ${color.bg} 0%, ${color.accent} 100%)`,
                border: `2px solid ${color.accent}`,
              }}
            >
              {showName && (
                <span
                  className="font-bold text-white leading-none text-center px-1"
                  style={{ fontSize }}
                >
                  {circle.symbol}
                </span>
              )}
              {showPnl && (
                <span
                  className="text-white/80 font-medium leading-none mt-0.5"
                  style={{ fontSize: pnlSize }}
                >
                  {circle.pnlPct >= 0 ? "+" : ""}
                  {circle.pnlPct.toFixed(1)}%
                </span>
              )}
              {!showName && (
                <span
                  className="font-bold text-white/90"
                  style={{ fontSize: Math.max(8, circle.radius * 0.3) }}
                >
                  {circle.symbol.charAt(0)}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors for the new file.

---

### Task 10: Wire up portfolio page

**Files:**

- Modify: `frontend/app/(auth)/portfolio/page.tsx`

The existing page already has `allHoldingsPage` fetched with `page_size: 1000`. We add view state and render the toggle + correct view below the filter bar, replacing the `{holdingsPage ? <HoldingsTable ...> : <Skeleton>}` block conditionally.

- [ ] **Step 1: Add imports at the top of `portfolio/page.tsx`**

Add after the existing imports:

```tsx
import { useCallback } from "react";
import { PortfolioViewToggle } from "@/components/portfolio/PortfolioViewToggle";
import { TreemapView } from "@/components/portfolio/TreemapView";
import { BeeswarmView } from "@/components/portfolio/BeeswarmView";
import { CirclepackView } from "@/components/portfolio/CirclepackView";
import { holdingsToViewItems, type ViewMode } from "@/lib/visualizations/types";
```

- [ ] **Step 2: Add view state inside the component, after the existing `useState` calls**

```tsx
const [portfolioView, setPortfolioView] = useState<ViewMode>(() => {
  if (typeof window !== "undefined") {
    return (localStorage.getItem("portfolio-view") as ViewMode) ?? "table";
  }
  return "table";
});

const handleViewChange = useCallback((v: ViewMode) => {
  setPortfolioView(v);
  localStorage.setItem("portfolio-view", v);
}, []);
```

- [ ] **Step 3: Add the toggle and computed items in the JSX**

Find the existing `<div className="flex items-center gap-2 flex-wrap">` action bar and add the toggle after it:

```tsx
<PortfolioViewToggle view={portfolioView} onChange={handleViewChange} />
```

Then find the block:

```tsx
{holdingsPage ? (
  <HoldingsTable ... />
) : (
  <Skeleton className="h-64 w-full" />
)}
```

Replace it with:

```tsx
{
  portfolioView === "table" ? (
    holdingsPage ? (
      <HoldingsTable
        data={holdingsPage}
        params={{
          search: tableParams.search ?? "",
          platform: tableParams.platform ?? "",
          asset_type: tableParams.asset_type ?? "",
          page: tableParams.page ?? 1,
          page_size: tableParams.page_size ?? 25,
        }}
        onParamChange={setParam}
        onDelete={(id) => deleteMutation.mutate(id)}
        onUpdated={refresh}
        isFetching={holdingsFetching}
        platformColors={platformColors}
      />
    ) : (
      <Skeleton className="h-64 w-full" />
    )
  ) : allHoldingsPage ? (
    (() => {
      const vizItems = holdingsToViewItems(allHoldingsPage.items);
      if (portfolioView === "grid") return <TreemapView items={vizItems} />;
      if (portfolioView === "swarm") return <BeeswarmView items={vizItems} />;
      return <CirclepackView items={vizItems} />;
    })()
  ) : (
    <Skeleton className="h-[520px] w-full" />
  );
}
```

> **Note:** Check the exact props passed to `<HoldingsTable>` in the existing file — copy them verbatim. The snippet above shows the shape but the actual prop names may differ slightly.

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors beyond any pre-existing ones.

- [ ] **Step 5: Start dev server and verify all four views work**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri
docker compose up -d
```

Then open `http://localhost:3000/portfolio` and:

1. Confirm Table view (default) shows the existing holdings table unchanged
2. Click Grid → treemap cells appear, sized by holding value, green/red/gray
3. Click Swarm → dots appear on horizontal axis
4. Click Bubbles → packed circles appear
5. Click any cell/dot/bubble → navigates to `/portfolio/[symbol]`
6. Hover over any element → tooltip shows symbol, value, %, P&L
7. Refresh page → previously selected view is restored from localStorage
