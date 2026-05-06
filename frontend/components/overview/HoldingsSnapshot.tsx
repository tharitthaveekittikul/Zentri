"use client";

import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
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

  return (
    <div className="bg-card card-surface rounded-2xl border border-border overflow-hidden">
      <table className="w-full text-sm">
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
          {holdings.map((h) => {
            const value = format(h.current_value);
            const cost = format(h.cost_basis);
            return (
              <tr
                key={h.symbol}
                className="border-t border-border hover:bg-muted/40 cursor-pointer transition-colors duration-150"
                onClick={() => router.push(`/portfolio/${h.symbol}`)}
              >
                <td className="px-4 py-2.5 font-mono font-semibold">{h.symbol}</td>
                <td className="px-4 py-2.5">
                  <span className="text-xs bg-muted rounded px-1.5 py-0.5 text-muted-foreground">
                    {h.asset_type.replace("_", " ")}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                  <PrivacyValue value={Number(h.quantity).toFixed(4)} />
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                  <div><PrivacyValue value={value.primary} /></div>
                  {value.secondary && (
                    <div className="text-xs text-muted-foreground"><PrivacyValue value={value.secondary} /></div>
                  )}
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">
                  <div><PrivacyValue value={cost.primary} /></div>
                  {cost.secondary && (
                    <div className="text-xs text-muted-foreground"><PrivacyValue value={cost.secondary} /></div>
                  )}
                </td>
                <td
                  className={cn(
                    "px-4 py-2.5 text-right font-mono tabular-nums",
                    h.pnl_pct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
                  )}
                >
                  <PrivacyValue value={`${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct.toFixed(2)}%`} />
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
  );
}
