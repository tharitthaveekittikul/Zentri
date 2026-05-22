"use client";

import { memo, useMemo } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";
import { HoldingAllocationItem } from "@/lib/services/overview";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { usePrivacyStore } from "@/store/privacy";
import { formatCompact } from "@/lib/formatCompact";

interface Props {
  holdings: HoldingAllocationItem[];
  sortDir: "asc" | "desc";
  onSortDirChange: (dir: "asc" | "desc") => void;
}

export const AllocationTable = memo(function AllocationTable({ holdings, sortDir, onSortDirChange }: Props) {
  const { primaryCurrency } = useDualCurrency();
  const { isPrivate } = usePrivacyStore();

  const sorted = useMemo(
    () =>
      [...holdings].sort((a, b) =>
        sortDir === "desc"
          ? Number(b.value) - Number(a.value)
          : Number(a.value) - Number(b.value),
      ),
    [holdings, sortDir],
  );

  if (holdings.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
        No holdings yet
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left py-2 pr-3 font-medium text-muted-foreground">Symbol</th>
            <th className="text-left py-2 pr-3 font-medium text-muted-foreground">Name</th>
            <th className="text-left py-2 pr-3 font-medium text-muted-foreground">Sector</th>
            <th className="text-left py-2 pr-3 font-medium text-muted-foreground">Type</th>
            <th
              className="text-right py-2 pr-3 font-medium text-muted-foreground cursor-pointer select-none hover:text-foreground"
              onClick={() => onSortDirChange(sortDir === "desc" ? "asc" : "desc")}
            >
              <span className="inline-flex items-center gap-0.5">
                Value
                {sortDir === "desc" ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronUp className="h-3 w-3" />
                )}
              </span>
            </th>
            <th className="text-right py-2 font-medium text-muted-foreground">Weight %</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((h) => (
            <tr key={h.symbol} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
              <td className="py-2 pr-3 font-mono font-medium">{h.symbol}</td>
              <td className="py-2 pr-3 text-muted-foreground truncate max-w-[140px]">{h.name}</td>
              <td className="py-2 pr-3 text-muted-foreground">{h.sector}</td>
              <td className="py-2 pr-3 text-muted-foreground">
                {h.asset_type.replace(/_/g, " ").toUpperCase()}
              </td>
              <td className="py-2 pr-3 font-mono tabular-nums text-right">
                {isPrivate ? "******" : formatCompact(Number(h.value))} {primaryCurrency}
              </td>
              <td className="py-2 font-mono tabular-nums text-right text-muted-foreground">
                {isPrivate ? "***%" : `${Number(h.pct_of_total).toFixed(1)}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});
