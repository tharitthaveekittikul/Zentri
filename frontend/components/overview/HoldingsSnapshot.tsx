"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { useDualCurrency } from "@/hooks/useDualCurrency";

export interface SnapshotHolding {
  symbol: string;
  asset_type: string;
  quantity: string;
  current_value: number;
  cost_basis: number;
  pnl_pct: number;
}

interface Props {
  holdings: SnapshotHolding[];
}

export function HoldingsSnapshot({ holdings }: Props) {
  const router = useRouter();
  const { format } = useDualCurrency();
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="bg-card card-surface rounded-2xl border border-border overflow-hidden">
      <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-sm">
        <thead>
          <tr className="bg-muted/50">
            <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Symbol</th>
            <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Type</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Quantity</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Value</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Cost Basis</th>
            <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">P&amp;L%</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h, index) => {
            const value = format(h.current_value);
            const cost = format(h.cost_basis);
            return (
              <tr
                key={h.symbol}
                className="border-t border-border hover:bg-muted/40 cursor-pointer transition-colors duration-150"
                style={{
                  animation: mounted
                    ? `card-in 300ms var(--motion-smooth) ${index * 40}ms both`
                    : undefined,
                  opacity: mounted ? undefined : 0,
                }}
                onClick={() => router.push(`/portfolio/${h.symbol}`)}
              >
                <td className="px-4 py-2.5 font-mono font-semibold">{h.symbol}</td>
                <td className="px-4 py-2.5">
                  <span className="text-xs bg-muted rounded px-1.5 py-0.5 text-muted-foreground">
                    {h.asset_type.replace("_", " ")}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                  {Number(h.quantity).toFixed(4)}
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                  <DualCurrencyAmount value={format(h.current_value)} />
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                  <DualCurrencyAmount value={format(h.cost_basis)} />
                </td>
                <td
                  className={cn(
                    "px-4 py-2.5 text-right font-mono tabular-nums",
                    h.pnl_pct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
                  )}
                >
                  {`${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct.toFixed(2)}%`}
                </td>
              </tr>
            );
          })}
          {holdings.length === 0 && (
            <tr>
              <td colSpan={6} className="py-10">
                <div className="flex flex-col items-center gap-2 text-muted-foreground">
                  <span className="text-xl">📊</span>
                  <span className="text-sm font-medium">No holdings yet</span>
                  <span className="text-xs">Add assets in the Portfolio tab.</span>
                </div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
      </div>
    </div>
  );
}
