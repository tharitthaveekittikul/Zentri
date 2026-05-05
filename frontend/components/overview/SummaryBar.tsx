"use client";

import { OverviewSummary } from "@/lib/services/overview";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface Props {
  summary: OverviewSummary;
}

function fmt(val: string, decimals = 2) {
  return Number(val).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function SummaryBar({ summary }: Props) {
  const pnlPositive = Number(summary.total_pnl) >= 0;
  const dailyPositive = Number(summary.daily_change) >= 0;

  return (
    <div className="flex flex-wrap gap-8 items-center px-6 py-5 bg-card rounded-2xl border border-border">
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Portfolio Value</p>
        <p className="text-3xl font-semibold tabular-nums tracking-tight font-mono">
          <PrivacyValue value={`$${fmt(summary.total_value)}`} />
        </p>
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Total Cost</p>
        <p className="text-base font-semibold tabular-nums font-mono">
          <PrivacyValue value={`$${fmt(summary.total_cost)}`} />
        </p>
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Total P&amp;L</p>
        <div className="flex items-center gap-2">
          <p className={cn("text-base font-semibold tabular-nums font-mono", pnlPositive ? "text-emerald-600 dark:text-emerald-400" : "text-destructive")}>
            <PrivacyValue value={`${pnlPositive ? "+" : ""}$${fmt(summary.total_pnl)}`} />
          </p>
          <Badge variant={pnlPositive ? "default" : "destructive"} className="text-xs font-mono tabular-nums">
            <PrivacyValue value={`${pnlPositive ? "+" : ""}${fmt(summary.total_pnl_pct)}%`} />
          </Badge>
        </div>
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Today</p>
        <div className="flex items-center gap-2">
          <p className={cn("text-base font-semibold tabular-nums font-mono", dailyPositive ? "text-emerald-600 dark:text-emerald-400" : "text-destructive")}>
            <PrivacyValue value={`${dailyPositive ? "+" : ""}$${fmt(summary.daily_change)}`} />
          </p>
          <Badge variant={dailyPositive ? "default" : "destructive"} className="text-xs font-mono tabular-nums">
            <PrivacyValue value={`${dailyPositive ? "+" : ""}${fmt(summary.daily_change_pct)}%`} />
          </Badge>
        </div>
      </div>
    </div>
  );
}
