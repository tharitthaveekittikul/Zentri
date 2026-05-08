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
      this._squarify(remaining, [], bounds.nx, bounds.ny, bounds.nw, bounds.nh, output);
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
      const ratio = Math.max(rowThickness / itemLength, itemLength / rowThickness);
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
        output.push({ ...item, x: x + gap / 2, y: y + offset + gap / 2, w: thickness - gap, h: length - gap });
      } else {
        output.push({ ...item, x: x + offset + gap / 2, y: y + gap / 2, w: length - gap, h: thickness - gap });
      }
      offset += length;
    }

    return horizontal
      ? { nx: x + thickness, ny: y, nw: w - thickness, nh: h }
      : { nx: x, ny: y + thickness, nw: w, nh: h - thickness };
  }
}
