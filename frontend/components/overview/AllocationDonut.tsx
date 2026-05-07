"use client";

import { memo, useMemo } from "react";
import { PieChart as RechartsPieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { PieChart as PieChartIcon } from "lucide-react";
import { AllocationItem } from "@/lib/services/overview";
import { useDualCurrency } from "@/hooks/useDualCurrency";

const COLORS = ["#6366f1", "#06b6d4", "#f59e0b", "#10b981", "#f43f5e", "#8b5cf6"];

function formatCompact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return value.toFixed(0);
}

interface Props {
  allocation: AllocationItem[];
}

export const AllocationDonut = memo(function AllocationDonut({ allocation }: Props) {
  const { primaryCurrency } = useDualCurrency();

  const data = useMemo(
    () => allocation.map((a) => ({
      name: a.asset_type.replace("_", " ").toUpperCase(),
      value: Number(a.pct),
      rawValue: Number(a.value),
    })),
    [allocation],
  );

  const dominant = data.reduce((max, item) => item.value > max.value ? item : max, data[0]);

  return (
    <div className="flex flex-col gap-3 h-full">
      <p className="text-sm font-medium">Allocation</p>
      {data.length === 0 ? (
        <div className="h-32 flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <PieChartIcon className="h-6 w-6 opacity-30" />
          <span className="text-xs">No allocation data yet</span>
        </div>
      ) : (
        <div className="flex items-center gap-4 flex-1">
          {/* Donut chart */}
          <div className="relative flex-shrink-0">
            <ResponsiveContainer width={128} height={128}>
              <RechartsPieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={42}
                  outerRadius={60}
                  dataKey="value"
                  paddingAngle={2}
                  startAngle={90}
                  endAngle={-270}
                >
                  {data.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number) => [`${v.toFixed(1)}%`, ""]}
                  contentStyle={{ fontSize: "11px" }}
                />
              </RechartsPieChart>
            </ResponsiveContainer>
            {/* Center label */}
            {dominant && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[10px] text-muted-foreground leading-none">{dominant.name}</span>
                <span className="text-sm font-semibold font-mono tabular-nums leading-tight">
                  {dominant.value.toFixed(0)}%
                </span>
              </div>
            )}
          </div>

          {/* Legend */}
          <div className="flex flex-col gap-1.5 flex-1 min-w-0">
            {data.map((item, i) => (
              <div key={item.name} className="flex items-center gap-1.5">
                <div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: COLORS[i % COLORS.length] }}
                />
                <span className="flex-1 min-w-0 truncate text-xs text-muted-foreground">
                  {item.name}
                </span>
                <span className="text-xs font-mono tabular-nums text-muted-foreground flex-shrink-0">
                  {formatCompact(item.rawValue)} {primaryCurrency}
                </span>
                <span
                  className="text-xs font-mono font-medium tabular-nums flex-shrink-0 w-10 text-right"
                  style={{ color: COLORS[i % COLORS.length] }}
                >
                  {item.value.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});
