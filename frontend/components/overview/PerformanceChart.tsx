"use client";

import { useState } from "react";
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
import { fetchPerformance } from "@/lib/services/overview";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const RANGES = ["1W", "1M", "3M", "1Y"] as const;
type Range = (typeof RANGES)[number];

export function PerformanceChart() {
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
    <div className="flex flex-col gap-2 h-full">
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
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={combined}>
          <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} />
          <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
          <Tooltip formatter={(v) => `${Number(v).toFixed(1)}`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line
            type="monotone"
            dataKey="portfolio"
            stroke="#6366f1"
            dot={false}
            strokeWidth={2}
            name="Portfolio"
          />
          <Line
            type="monotone"
            dataKey="benchmark"
            stroke="#94a3b8"
            dot={false}
            strokeWidth={1.5}
            name="S&P500"
            strokeDasharray="4 2"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
