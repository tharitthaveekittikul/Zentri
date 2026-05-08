"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { Treemap } from "@/lib/visualizations/treemap";
import { getHoldingColor, PortfolioViewItem } from "@/lib/visualizations/types";
import { useResizeObserver } from "@/hooks/useResizeObserver";
import { TickerLogo } from "@/components/ui/TickerLogo";
import { usePrivacyStore } from "@/store/privacy";

interface Props {
  items: PortfolioViewItem[];
}

export function TreemapView({ items }: Props) {
  const router = useRouter();
  const { isPrivate } = usePrivacyStore();
  const { ref, width, height } = useResizeObserver<HTMLDivElement>();

  const cells = useMemo(() => {
    if (width === 0 || height === 0 || items.length === 0) return [];
    return new Treemap(width, height).layout(items);
  }, [items, width, height]);

  return (
    <div ref={ref} className="relative w-full" style={{ height: "calc(100svh - 320px)", minHeight: 400 }}>
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
        const showLogo = minDim > 48;
        const logoSize = Math.min(Math.floor(minDim * 0.28), 32);
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
            <div className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-colors rounded-lg" />

            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20 whitespace-nowrap">
              <div className="bg-popover text-popover-foreground text-xs rounded-lg px-3 py-2 shadow-xl border border-border">
                <div className="font-semibold">{cell.symbol}</div>
                <div className="text-muted-foreground">{isPrivate ? "••••••" : cell.displayValue}</div>
                <div className="text-muted-foreground">
                  {isPrivate ? "••••••" : `${cell.portfolioPct.toFixed(1)}% of portfolio`}
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
                {showLogo && (
                  <TickerLogo symbol={cell.symbol} logoUrl={cell.logoUrl} size={logoSize} />
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
                    {isPrivate ? "••••••" : cell.displayValue}
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
