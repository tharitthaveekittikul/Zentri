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
    <div className="flex flex-wrap gap-6 items-center p-4 bg-card rounded-lg border">
      <div>
        <p className="text-xs text-muted-foreground">Portfolio Value</p>
        <p className="text-3xl font-bold">
          <PrivacyValue value={`$${fmt(summary.total_value)}`} />
        </p>
      </div>
      <div>
        <p className="text-xs text-muted-foreground">Total Cost</p>
        <p className="text-lg font-medium">
          <PrivacyValue value={`$${fmt(summary.total_cost)}`} />
        </p>
      </div>
      <div>
        <p className="text-xs text-muted-foreground">Total P&amp;L</p>
        <div className="flex items-center gap-1">
          <p className={cn("text-lg font-medium", pnlPositive ? "text-green-500" : "text-red-500")}>
            <PrivacyValue value={`${pnlPositive ? "+" : ""}$${fmt(summary.total_pnl)}`} />
          </p>
          <Badge variant={pnlPositive ? "default" : "destructive"} className="text-xs">
            <PrivacyValue value={`${pnlPositive ? "+" : ""}${fmt(summary.total_pnl_pct)}%`} />
          </Badge>
        </div>
      </div>
      <div>
        <p className="text-xs text-muted-foreground">Today</p>
        <div className="flex items-center gap-1">
          <p className={cn("text-lg font-medium", dailyPositive ? "text-green-500" : "text-red-500")}>
            <PrivacyValue value={`${dailyPositive ? "+" : ""}$${fmt(summary.daily_change)}`} />
          </p>
          <Badge variant={dailyPositive ? "default" : "destructive"} className="text-xs">
            <PrivacyValue value={`${dailyPositive ? "+" : ""}${fmt(summary.daily_change_pct)}%`} />
          </Badge>
        </div>
      </div>
    </div>
  );
}
