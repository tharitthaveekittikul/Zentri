"use client";

import { cn } from "@/lib/utils";
import { OverviewSummary } from "@/lib/services/overview";
import { useDualCurrency, DualValue } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";

interface CardProps {
  label: string;
  value: DualValue;
  pct?: string;
  direction?: "positive" | "negative" | "neutral";
}

function KpiCard({ label, value, pct, direction = "neutral" }: CardProps) {
  const isPositive = direction === "positive";
  const isNegative = direction === "negative";
  const isColored = isPositive || isNegative;

  return (
    <div
      className={cn("card-surface border border-border rounded-2xl p-5")}
      style={{
        backgroundColor: isPositive
          ? "var(--signal-gain-bg)"
          : isNegative
            ? "var(--signal-loss-bg)"
            : "var(--card)",
      }}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
        {label}
      </p>
      <DualCurrencyAmount
        value={value}
        primaryClassName={cn(
          "text-2xl font-semibold font-mono tabular-nums",
          isPositive && "text-[var(--signal-gain-text)]",
          isNegative && "text-destructive"
        )}
      />
      {pct && (
        <p
          className={cn(
            "text-sm font-mono tabular-nums mt-1",
            isColored ? "opacity-80" : "text-muted-foreground"
          )}
          style={{
            color: isPositive
              ? "var(--signal-gain-text)"
              : isNegative
                ? "var(--destructive)"
                : undefined,
          }}
        >
          {pct}
        </p>
      )}
    </div>
  );
}

interface Props {
  summary: OverviewSummary;
}

export function KpiCards({ summary }: Props) {
  const { format, formatPct } = useDualCurrency();

  const pnlPositive = Number(summary.total_pnl) >= 0;
  const dailyPositive = Number(summary.daily_change) >= 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <KpiCard
        label="Portfolio Value"
        value={format(summary.total_value)}
      />
      <KpiCard
        label="Total Cost"
        value={format(summary.total_cost)}
      />
      <KpiCard
        label="Total P&L"
        value={format(summary.total_pnl)}
        pct={formatPct(summary.total_pnl_pct)}
        direction={pnlPositive ? "positive" : "negative"}
      />
      <KpiCard
        label="Today"
        value={format(summary.daily_change)}
        pct={formatPct(summary.daily_change_pct)}
        direction={dailyPositive ? "positive" : "negative"}
      />
    </div>
  );
}
