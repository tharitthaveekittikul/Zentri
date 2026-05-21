"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  type Time,
} from "lightweight-charts";
import { PriceBar } from "@/lib/services/overview";

interface Props {
  bars: PriceBar[];
}

function cssVar(name: string): string {
  const dark = document.documentElement.classList.contains("dark");
  const map: Record<string, string> = {
    "--color-brand-accent":     "#10b981",
    "--color-brand-danger":     "#f43f5e",
    "--color-brand-sage":       "#5fbd92",
    "--color-brand-mid":        "#227d53",
    "--color-muted-foreground": dark ? "#919191" : "#707070",
  };
  return map[name] ?? "#94a3b8";
}

export function PriceChart({ bars }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || bars.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: cssVar("--color-muted-foreground"),
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      width: containerRef.current.clientWidth,
      height: 300,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: cssVar("--color-brand-accent"),
      downColor: cssVar("--color-brand-danger"),
      borderUpColor: cssVar("--color-brand-accent"),
      borderDownColor: cssVar("--color-brand-danger"),
      wickUpColor: cssVar("--color-brand-accent"),
      wickDownColor: cssVar("--color-brand-danger"),
    });

    series.setData(
      bars
        .filter((b) => b.open && b.high && b.low)
        .map((b) => ({
          time: b.timestamp.split("T")[0] as Time,
          open: Number(b.open),
          high: Number(b.high),
          low: Number(b.low),
          close: Number(b.close),
        })),
    );

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current)
        chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [bars]);

  if (bars.length === 0) {
    return (
      <div className="h-[300px] flex items-center justify-center text-sm text-muted-foreground">
        No price data available yet.
      </div>
    );
  }

  return <div ref={containerRef} className="w-full [&_a]:!hidden" />;
}
