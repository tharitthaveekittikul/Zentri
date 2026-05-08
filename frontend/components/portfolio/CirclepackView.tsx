"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { CirclePack } from "@/lib/visualizations/circlepack";
import { getHoldingColor, PortfolioViewItem } from "@/lib/visualizations/types";
import { useResizeObserver } from "@/hooks/useResizeObserver";
import { TickerLogo } from "@/components/ui/TickerLogo";
import { usePrivacyStore } from "@/store/privacy";

interface Props {
  items: PortfolioViewItem[];
}

export function CirclepackView({ items }: Props) {
  const router = useRouter();
  const { isPrivate } = usePrivacyStore();
  const { ref, width, height } = useResizeObserver<HTMLDivElement>();

  const circles = useMemo(() => {
    if (width === 0 || height === 0 || items.length === 0) return [];
    return new CirclePack(width, height, 30).layout(items);
  }, [items, width, height]);

  return (
    <div ref={ref} className="relative w-full" style={{ height: "calc(100svh - 320px)", minHeight: 400 }}>
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
        const showLogo = circle.radius > 32;
        const logoSize = Math.min(Math.floor(circle.radius * 0.5), 36);
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
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20 whitespace-nowrap">
              <div className="bg-popover text-popover-foreground text-xs rounded-lg px-3 py-2 shadow-xl border border-border">
                <div className="font-semibold">{circle.symbol}</div>
                <div className="text-muted-foreground">{isPrivate ? "••••••" : circle.displayValue}</div>
                <div className="text-muted-foreground">
                  {isPrivate ? "••••••" : `${circle.portfolioPct.toFixed(1)}% of portfolio`}
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
              {showLogo && (
                <TickerLogo symbol={circle.symbol} logoUrl={circle.logoUrl} size={logoSize} />
              )}
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
