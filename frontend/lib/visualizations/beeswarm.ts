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

    const sorted = [...items].sort((a, b) => a.val - b.val);
    const vals = sorted.map((d) => d.val);
    const minVal = Math.min(...vals);
    const maxVal = Math.max(...vals);

    const minRadius = this.isMobile ? 10 : 14;
    const maxRadius = this.isMobile ? 25 : 35;
    const minDistance = 4;

    const withRadius = sorted.map((item) => {
      const ratio = maxVal === minVal ? 0.5 : (item.val - minVal) / (maxVal - minVal);
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

      let attempt = 0;
      while (this._hasOverlap(x, y, item.radius, placed, minDistance)) {
        attempt++;
        const sign = attempt % 2 === 1 ? 1 : -1;
        const mag = Math.ceil(attempt / 2) * (item.radius + minDistance);
        y = this.centerY + sign * mag;
        if (Math.abs(y - this.centerY) > this.height / 2) break;
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
