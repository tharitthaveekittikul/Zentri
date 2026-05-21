"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  createChart,
  AreaSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import { TrendingUp } from "lucide-react";
import { fetchNetWorthTimeline, type NetWorthPoint } from "@/lib/services/overview";
import { fetchExchangeRate } from "@/lib/services/settings";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDualCurrency } from "@/hooks/useDualCurrency";

const RANGES = ["1M", "3M", "6M", "1Y", "ALL"] as const;
type Range = (typeof RANGES)[number];

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

export function NetWorthChart({ privacyMode }: { privacyMode: boolean }) {
  const { primaryCurrency } = useDualCurrency();

  const { data: usdToPrimary } = useQuery({
    queryKey: ["exchange-rate", "USD", primaryCurrency],
    queryFn: () => fetchExchangeRate("USD", primaryCurrency),
    enabled: primaryCurrency !== "USD",
    staleTime: 60 * 60 * 1000,
  });

  const conversionRate =
    primaryCurrency === "USD" ? 1 : usdToPrimary ? Number(usdToPrimary.rate) : null;

  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const valueSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const costSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [range, setRange] = useState<Range>("1M");
  const [data, setData] = useState<NetWorthPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 280,
      layout: { background: { color: "transparent" }, textColor: cssVar("--color-muted-foreground") },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { borderColor: "transparent" },
      timeScale: { borderColor: "transparent", timeVisible: false },
    });

    valueSeriesRef.current = chart.addSeries(AreaSeries, {
      lineColor: cssVar("--color-brand-accent"),
      topColor: "rgba(16,185,129,0.20)",
      bottomColor: "rgba(16,185,129,0)",
      lineWidth: 2,
    });
    costSeriesRef.current = chart.addSeries(LineSeries, {
      color: cssVar("--color-brand-sage"),
      lineWidth: 1,
      lineStyle: 1,
    });
    chartRef.current = chart;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize, { passive: true });
    return () => {
      window.removeEventListener("resize", handleResize);
      chartRef.current = null;
      valueSeriesRef.current = null;
      costSeriesRef.current = null;
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (conversionRate === null) return;
    setLoading(true);
    fetchNetWorthTimeline(range)
      .then((points) => {
        setData(points);
        if (!valueSeriesRef.current || !costSeriesRef.current) return;
        const valueData = points.map((p) => ({
          time: p.date,
          value: parseFloat(p.value_usd) * conversionRate,
        }));
        const costData = points.map((p) => ({
          time: p.date,
          value: parseFloat(p.cost_usd) * conversionRate,
        }));
        valueSeriesRef.current.setData(valueData);
        costSeriesRef.current.setData(costData);
        if (containerRef.current) {
          chartRef.current?.applyOptions({ width: containerRef.current.clientWidth });
        }
        chartRef.current?.timeScale().fitContent();
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [range, conversionRate]);

  const latest = data[data.length - 1];
  const rate = conversionRate ?? 1;
  const currentValue = latest ? parseFloat(latest.value_usd) * rate : 0;
  const currentCost = latest ? parseFloat(latest.cost_usd) * rate : 0;
  const pnl = currentValue - currentCost;
  const pnlPct = currentCost > 0 ? (pnl / currentCost) * 100 : 0;

  const fmt = (v: number) =>
    privacyMode
      ? `****** ${primaryCurrency}`
      : `${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${primaryCurrency}`;

  const fmtPnl = () => {
    const sign = pnl >= 0 ? "+" : "";
    const pctStr = `${sign}${pnlPct.toFixed(2)}%`;
    if (privacyMode) return `****** ${primaryCurrency} (${pctStr})`;
    return `${sign}${fmt(pnl)} (${pctStr})`;
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">Net Worth</CardTitle>
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  range === r
                    ? "bg-brand-accent text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-6 mt-2">
          <div>
            <p className="text-xs text-muted-foreground">Current Value</p>
            <p className="text-lg font-semibold tabular-nums">{fmt(currentValue)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Total Cost</p>
            <p className="text-lg font-semibold tabular-nums">{fmt(currentCost)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Unrealized PnL</p>
            <p
              className={`text-lg font-semibold tabular-nums ${
                pnl >= 0 ? "text-brand-mid" : "text-brand-danger"
              }`}
            >
              {fmtPnl()}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="h-64 w-full relative">
          <div ref={containerRef} className="w-full h-full [&_a]:!hidden" />
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
              Loading...
            </div>
          )}
          {!loading && data.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted-foreground">
              <TrendingUp className="h-6 w-6 opacity-30" />
              <span className="text-xs">No net worth data yet</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
