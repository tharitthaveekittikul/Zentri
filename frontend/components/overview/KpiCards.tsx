"use client";

import { cn } from "@/lib/utils";
import { OverviewSummary } from "@/lib/services/overview";
import { useDualCurrency, DualValue } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import { ReactNode, useState, useEffect } from "react";

interface CardProps {
  label: string;
  value: DualValue;
  pct?: ReactNode;
  direction?: "positive" | "negative" | "neutral";
  index?: number;
  mounted?: boolean;
}

function KpiCard({ label, value, pct, direction = "neutral", index = 0, mounted = false }: CardProps) {
  const isPositive = direction === "positive";
  const isNegative = direction === "negative";
  const isColored = isPositive || isNegative;

  return (
    <div
      className={cn("card-surface rounded-2xl p-5 group")}
      style={{
        backgroundColor: isPositive
          ? "var(--signal-gain-bg)"
          : isNegative
            ? "var(--signal-loss-bg)"
            : "var(--card)",
        animation: mounted
          ? `card-in 400ms var(--motion-smooth) ${index * 60}ms both`
          : undefined,
        opacity: mounted ? undefined : 0,
      }}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2 transition-colors duration-150 group-hover:text-foreground">
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
  const { format, formatPnl, formatPct } = useDualCurrency();

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

  const pnlPositive = Number(summary.total_pnl) >= 0;
  const dailyPositive = Number(summary.daily_change) >= 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <KpiCard
        label="Portfolio Value"
        value={format(summary.total_value)}
        index={0}
        mounted={mounted}
      />
      <KpiCard
        label="Total Cost"
        value={format(summary.total_cost)}
        index={1}
        mounted={mounted}
      />
      <KpiCard
        label="Total P&L"
        value={formatPnl(summary.total_pnl)}
        pct={<span className="inline-flex items-center gap-0.5">{pnlPositive ? <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={2.5} /> : <ArrowDownRight className="h-3.5 w-3.5" strokeWidth={2.5} />}{formatPct(summary.total_pnl_pct)}</span>}
        direction={pnlPositive ? "positive" : "negative"}
        index={2}
        mounted={mounted}
      />
      <KpiCard
        label="Today"
        value={formatPnl(summary.daily_change)}
        pct={<span className="inline-flex items-center gap-0.5">{dailyPositive ? <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={2.5} /> : <ArrowDownRight className="h-3.5 w-3.5" strokeWidth={2.5} />}{formatPct(summary.daily_change_pct)}</span>}
        direction={dailyPositive ? "positive" : "negative"}
        index={3}
        mounted={mounted}
      />
    </div>
  );
}
