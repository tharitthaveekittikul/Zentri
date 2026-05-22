"use client";

import { memo, useMemo, useState } from "react";
import { PieChart as RechartsPieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { PieChart as PieChartIcon } from "lucide-react";
import { AllocationItem, SectorAllocationItem } from "@/lib/services/overview";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { usePrivacyStore } from "@/store/privacy";

const COLORS = [
  "var(--color-brand-accent)",
  "var(--color-brand-sage)",
  "var(--color-brand-mid)",
  "var(--color-brand-danger)",
  "var(--color-muted-foreground)",
  "var(--color-brand-deep)",
];

function formatCompact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return value.toFixed(0);
}

interface Props {
  allocation: AllocationItem[];
  sectorAllocation: SectorAllocationItem[];
}

export const AllocationDonut = memo(function AllocationDonut({ allocation, sectorAllocation }: Props) {
  const { primaryCurrency } = useDualCurrency();
  const { isPrivate } = usePrivacyStore();
  const [tab, setTab] = useState<"type" | "sector">("type");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const typeData = useMemo(
    () => allocation.map((a) => ({
      name: a.asset_type.replace(/_/g, " ").toUpperCase(),
      value: Number(a.pct),
      rawValue: Number(a.value),
    })),
    [allocation],
  );

  const sectorData = useMemo(
    () => sectorAllocation.map((a) => ({
      name: a.sector,
      value: Number(a.pct),
      rawValue: Number(a.value),
    })),
    [sectorAllocation],
  );

  const data = tab === "type" ? typeData : sectorData;
  const dominant = data.length > 0
    ? data.reduce((max, item) => item.value > max.value ? item : max, data[0])
    : null;

  const isEmpty = data.length === 0;

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Allocation</p>
        <div className="flex rounded-md overflow-hidden border border-border text-xs">
          <button
            className={`px-2 py-0.5 transition-colors ${tab === "type" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
            onClick={() => setTab("type")}
          >
            By Type
          </button>
          <button
            className={`px-2 py-0.5 transition-colors ${tab === "sector" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
            onClick={() => setTab("sector")}
          >
            By Sector
          </button>
        </div>
      </div>

      {isEmpty ? (
        <div className="h-32 flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <PieChartIcon className="h-6 w-6 opacity-30" />
          <span className="text-xs">
            {tab === "sector" ? "Run sector enrichment first" : "No allocation data yet"}
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-4 flex-1">
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
                  isAnimationActive={true}
                  animationBegin={0}
                  animationDuration={800}
                  animationEasing="ease-out"
                >
                  {data.map((_, i) => (
                    <Cell
                      key={i}
                      fill={COLORS[i % COLORS.length]}
                      opacity={hoveredIndex === null || hoveredIndex === i ? 1 : 0.6}
                      onMouseEnter={() => setHoveredIndex(i)}
                      onMouseLeave={() => setHoveredIndex(null)}
                      style={{ transition: 'opacity 150ms ease', cursor: 'pointer' }}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: unknown) => [`${Number(v).toFixed(1)}%`, ""]}
                  contentStyle={{ fontSize: "11px" }}
                />
              </RechartsPieChart>
            </ResponsiveContainer>
            {dominant && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[9px] text-muted-foreground leading-tight text-center px-2 truncate max-w-[80px]">
                  {dominant.name}
                </span>
                <span className="text-sm font-semibold leading-tight">
                  {dominant.value.toFixed(0)}%
                </span>
              </div>
            )}
          </div>

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
                  {isPrivate ? "******" : formatCompact(item.rawValue)} {primaryCurrency}
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
