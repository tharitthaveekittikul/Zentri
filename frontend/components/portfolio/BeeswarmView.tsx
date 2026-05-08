"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { Beeswarm } from "@/lib/visualizations/beeswarm";
import { getHoldingColor, PortfolioViewItem } from "@/lib/visualizations/types";
import { useResizeObserver } from "@/hooks/useResizeObserver";
import { TickerLogo } from "@/components/ui/TickerLogo";
import { usePrivacyStore } from "@/store/privacy";

interface Props {
  items: PortfolioViewItem[];
}

export function BeeswarmView({ items }: Props) {
  const router = useRouter();
  const { isPrivate } = usePrivacyStore();
  const { ref, width, height } = useResizeObserver<HTMLDivElement>();

  const dots = useMemo(() => {
    if (width === 0 || height === 0 || items.length === 0) return [];
    const isMobile = width < 500;
    return new Beeswarm(width, height, isMobile ? 20 : 40, isMobile).layout(items);
  }, [items, width, height]);

  return (
    <div ref={ref} className="relative w-full" style={{ height: "calc(100svh - 320px)", minHeight: 400 }}>
      {items.length === 0 && (
        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
          Add holdings to see visualization
        </div>
      )}
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
        const showLogo = dot.radius > 18;
        const logoSize = Math.min(Math.floor(dot.radius * 0.9), 28);

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
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20 whitespace-nowrap">
              <div className="bg-popover text-popover-foreground text-xs rounded-lg px-3 py-2 shadow-xl border border-border">
                <div className="font-semibold">{dot.symbol}</div>
                <div className="text-muted-foreground">{isPrivate ? "••••••" : dot.displayValue}</div>
                <div className="text-muted-foreground">
                  {isPrivate ? "••••••" : `${dot.portfolioPct.toFixed(1)}% of portfolio`}
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
              {showLogo && dot.logoUrl ? (
                <TickerLogo symbol={dot.symbol} logoUrl={dot.logoUrl} size={logoSize} />
              ) : showLabel ? (
                <span className="text-white font-bold text-[10px] leading-none text-center px-0.5">
                  {dot.symbol.length > 4 ? dot.symbol.slice(0, 4) : dot.symbol}
                </span>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
