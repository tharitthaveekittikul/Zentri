"use client";

import { memo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Activity } from "lucide-react";
import { fetchPerformance } from "@/lib/services/overview";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const RANGES = ["1W", "1M", "3M", "1Y"] as const;
type Range = (typeof RANGES)[number];

function CustomTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: string; name: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl px-3 py-2 text-xs"
      style={{
        background: 'var(--glass-bg)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        border: '1px solid var(--glass-border)',
        boxShadow: '0 4px 16px oklch(0 0 0 / 20%)',
      }}
    >
      <p className="font-medium text-foreground mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  );
}

export const PerformanceChart = memo(function PerformanceChart() {
  const [range, setRange] = useState<Range>("1M");

  const { data } = useQuery({
    queryKey: ["overview", "performance", range],
    queryFn: () => fetchPerformance(range),
  });

  const combined = (data?.portfolio ?? []).map((p, i) => ({
    date: p.date,
    portfolio: Number(p.value).toFixed(2),
    benchmark: data?.benchmark[i] ? Number(data.benchmark[i].value).toFixed(2) : null,
  }));

  return (
    <div className="flex flex-col gap-2 min-h-[260px]">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Portfolio vs Benchmark</p>
        <Tabs value={range} onValueChange={(v) => setRange(v as Range)}>
          <TabsList className="h-7">
            {RANGES.map((r) => (
              <TabsTrigger key={r} value={r} className="text-xs px-2 h-6">
                {r}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>
      {combined.length === 0 ? (
        <div className="h-52 flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <Activity className="h-6 w-6 opacity-30" />
          <span className="text-xs">No performance data yet</span>
        </div>
      ) : (
        <div style={{ animation: 'card-in 500ms var(--motion-smooth) 200ms both' }}>
          <ResponsiveContainer width="100%" height={208}>
            <LineChart data={combined}>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} />
              <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line
                type="monotone"
                dataKey="portfolio"
                stroke="var(--color-brand-accent)"
                dot={false}
                strokeWidth={2}
                name="Portfolio"
                isAnimationActive={true}
                animationDuration={1000}
                animationEasing="ease-out"
              />
              <Line
                type="monotone"
                dataKey="benchmark"
                stroke="var(--color-muted-foreground)"
                dot={false}
                strokeWidth={1.5}
                name="S&P500"
                strokeDasharray="4 2"
                isAnimationActive={true}
                animationDuration={1200}
                animationEasing="ease-out"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
});
