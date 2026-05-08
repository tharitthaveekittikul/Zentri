import { PortfolioViewItem, VisDot } from "./types";

type WithRadius = PortfolioViewItem & { radius: number };

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
      const ratio = maxVal === minVal ? 0.5 : (item.val - minVal) / (maxVal - minVal);
      const radius = minRadius + Math.sqrt(ratio) * (maxRadius - minRadius);
      return { ...item, radius };
    });

    return this._packCircles(withRadius);
  }

  private _packCircles(circles: WithRadius[]): VisDot[] {
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

    if (!bestPos) {
      const rightmost = Math.max(...placed.map((p) => p.x + p.radius));
      bestPos = { x: rightmost + radius + 4, y: this.centerY };
    }
    return bestPos;
  }

  private _tangentPositions(
    c1: PlacedCircle,
    c2: PlacedCircle,
    r: number,
  ): { x: number; y: number }[] {
    const d = Math.sqrt(
      Math.pow(c2.x - c1.x, 2) + Math.pow(c2.y - c1.y, 2),
    );
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
