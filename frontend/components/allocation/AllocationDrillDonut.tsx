"use client";

import { memo, useMemo } from "react";
import {
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { PieChart as PieChartIcon } from "lucide-react";
import { HoldingAllocationItem } from "@/lib/services/overview";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { usePrivacyStore } from "@/store/privacy";
import { formatCompact } from "@/lib/formatCompact";

const COLORS = [
  "var(--color-brand-accent)",
  "var(--color-brand-sage)",
  "var(--color-brand-mid)",
  "var(--color-brand-danger)",
  "var(--color-muted-foreground)",
  "var(--color-brand-deep)",
];

interface Props {
  holdings: HoldingAllocationItem[];
  tab: "type" | "sector";
  onTabChange: (tab: "type" | "sector") => void;
  selectedGroup: string | null;
  onSelectGroup: (group: string) => void;
  onClearGroup: () => void;
}

function groupKey(h: HoldingAllocationItem, tab: "type" | "sector"): string {
  return tab === "type" ? h.asset_type.replace(/_/g, " ").toUpperCase() : h.sector;
}

export const AllocationDrillDonut = memo(function AllocationDrillDonut({
  holdings,
  tab,
  onTabChange,
  selectedGroup,
  onSelectGroup,
  onClearGroup,
}: Props) {
  const { primaryCurrency } = useDualCurrency();
  const { isPrivate } = usePrivacyStore();

  const data = useMemo(() => {
    if (selectedGroup) {
      const group = holdings.filter((h) => groupKey(h, tab) === selectedGroup);
      const groupTotal = group.reduce((s, h) => s + Number(h.value), 0) || 1;
      return group.map((h) => ({
        name: h.symbol,
        value: (Number(h.value) / groupTotal) * 100,
        rawValue: Number(h.value),
      }));
    }
    const grouped: Record<string, { value: number; rawValue: number }> = {};
    for (const h of holdings) {
      const key = groupKey(h, tab);
      if (!grouped[key]) grouped[key] = { value: 0, rawValue: 0 };
      grouped[key].value += Number(h.pct_of_total);
      grouped[key].rawValue += Number(h.value);
    }
    return Object.entries(grouped)
      .map(([name, d]) => ({ name, value: d.value, rawValue: d.rawValue }))
      .sort((a, b) => b.value - a.value);
  }, [holdings, tab, selectedGroup]);

  const dominant = data.length > 0
    ? data.reduce((max, item) => (item.value > max.value ? item : max), data[0])
    : null;

  const isEmpty = data.length === 0;

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Allocation</p>
        {selectedGroup ? (
          <button
            onClick={onClearGroup}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            ← {selectedGroup}
          </button>
        ) : (
          <div className="flex rounded-md overflow-hidden border border-border text-xs">
            <button
              className={`px-2 py-0.5 transition-colors ${tab === "type" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
              onClick={() => onTabChange("type")}
            >
              By Type
            </button>
            <button
              className={`px-2 py-0.5 transition-colors ${tab === "sector" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
              onClick={() => onTabChange("sector")}
            >
              By Sector
            </button>
          </div>
        )}
      </div>

      {isEmpty ? (
        <div className="h-48 flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <PieChartIcon className="h-6 w-6 opacity-30" />
          <span className="text-xs">
            {tab === "sector" && !selectedGroup ? "Run sector enrichment first" : "No data"}
          </span>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="relative mx-auto">
            <ResponsiveContainer width={180} height={180}>
              <RechartsPieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={58}
                  outerRadius={82}
                  dataKey="value"
                  paddingAngle={2}
                  startAngle={90}
                  endAngle={-270}
                  onClick={!selectedGroup ? (entry) => entry.name && onSelectGroup(entry.name) : undefined}
                >
                  {data.map((_, i) => (
                    <Cell
                      key={i}
                      fill={COLORS[i % COLORS.length]}
                      style={{ cursor: !selectedGroup ? "pointer" : "default" }}
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
                <span className="text-[9px] text-muted-foreground leading-tight text-center px-3 truncate max-w-[100px]">
                  {dominant.name}
                </span>
                <span className="text-base font-semibold leading-tight">
                  {dominant.value.toFixed(0)}%
                </span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            {data.map((item, i) => (
              <div
                key={item.name}
                className={`flex items-center gap-1.5 ${!selectedGroup ? "cursor-pointer hover:opacity-80" : ""}`}
                onClick={!selectedGroup ? () => onSelectGroup(item.name) : undefined}
              >
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
