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
      layout: { background: { color: "transparent" }, textColor: "#9ca3af" },
      grid: { vertLines: { color: "#1f2937" }, horzLines: { color: "#1f2937" } },
      rightPriceScale: { borderColor: "#374151" },
      timeScale: { borderColor: "#374151", timeVisible: false },
    });

    valueSeriesRef.current = chart.addSeries(AreaSeries, {
      lineColor: "#6366f1",
      topColor: "rgba(99,102,241,0.25)",
      bottomColor: "rgba(99,102,241,0)",
      lineWidth: 2,
    });
    costSeriesRef.current = chart.addSeries(LineSeries, {
      color: "#6b7280",
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
    if (privacyMode) return `****** ${primaryCurrency}`;
    const sign = pnl >= 0 ? "+" : "";
    return `${sign}${fmt(pnl)} (${pnl >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%)`;
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
                    ? "bg-indigo-600 text-white"
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
                pnl >= 0 ? "text-green-500" : "text-red-500"
              }`}
            >
              {fmtPnl()}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="h-64 w-full">
          {loading && (
            <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
              Loading...
            </div>
          )}
          {!loading && data.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-muted-foreground">
              <TrendingUp className="h-6 w-6 opacity-30" />
              <span className="text-xs">No net worth data yet</span>
            </div>
          )}
          <div ref={containerRef} className={loading || data.length === 0 ? "hidden" : "w-full h-full"} />
        </div>
      </CardContent>
    </Card>
  );
}
