"use client";

import { OverviewSummary } from "@/lib/services/overview";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";

interface Props {
  summary: OverviewSummary;
}

export function SummaryBar({ summary }: Props) {
  const { format, formatPct } = useDualCurrency();
  const pnlPositive = Number(summary.total_pnl) >= 0;
  const dailyPositive = Number(summary.daily_change) >= 0;

  return (
    <div className="flex flex-wrap gap-8 items-center px-6 py-5 bg-card card-surface rounded-2xl border border-border">
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Portfolio Value</p>
        <DualCurrencyAmount
          value={format(summary.total_value)}
          primaryClassName="text-3xl font-semibold tracking-tight"
        />
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Total Cost</p>
        <DualCurrencyAmount
          value={format(summary.total_cost)}
          primaryClassName="text-base font-semibold"
        />
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Total P&amp;L</p>
        <div className="flex items-center gap-2">
          <DualCurrencyAmount
            value={format(summary.total_pnl)}
            primaryClassName={cn(
              "text-base font-semibold",
              pnlPositive ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
            )}
          />
          <Badge variant={pnlPositive ? "default" : "destructive"} className="text-xs font-mono tabular-nums self-start mt-0.5">
            {formatPct(summary.total_pnl_pct)}
          </Badge>
        </div>
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Today</p>
        <div className="flex items-center gap-2">
          <DualCurrencyAmount
            value={format(summary.daily_change)}
            primaryClassName={cn(
              "text-base font-semibold",
              dailyPositive ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
            )}
          />
          <Badge variant={dailyPositive ? "default" : "destructive"} className="text-xs font-mono tabular-nums self-start mt-0.5">
            {formatPct(summary.daily_change_pct)}
          </Badge>
        </div>
      </div>
    </div>
  );
}
