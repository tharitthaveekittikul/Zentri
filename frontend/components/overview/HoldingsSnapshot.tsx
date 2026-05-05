"use client";

import { useRouter } from "next/navigation";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface SnapshotHolding {
  symbol: string;
  name: string;
  asset_type: string;
  quantity: string;
  current_value: number;
  pnl_pct: number;
}

interface Props {
  holdings: SnapshotHolding[];
}

export function HoldingsSnapshot({ holdings }: Props) {
  const router = useRouter();

  return (
    <div className="bg-card rounded-2xl border border-border overflow-hidden px-5 pt-5 pb-5">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">Symbol</th>
            <th className="text-left p-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">Name</th>
            <th className="text-left p-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">Type</th>
            <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">Quantity</th>
            <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">Cost Basis</th>
            <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">P&amp;L%</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr
              key={h.symbol}
              className="border-t hover:bg-muted/40 cursor-pointer transition-colors duration-150"
              onClick={() => router.push(`/portfolio/${h.symbol}`)}
            >
              <td className="p-3 font-mono font-semibold tabular-nums">{h.symbol}</td>
              <td className="p-3 text-muted-foreground">{h.name}</td>
              <td className="p-3">
                <Badge variant="outline" className="text-xs">
                  {h.asset_type.replace("_", " ")}
                </Badge>
              </td>
              <td className="p-3 text-right font-mono tabular-nums">{Number(h.quantity).toFixed(4)}</td>
              <td className="p-3 text-right font-mono tabular-nums">
                <PrivacyValue
                  value={`$${h.current_value.toLocaleString("en-US", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}`}
                />
              </td>
              <td
                className={cn(
                  "p-3 text-right font-mono tabular-nums font-medium",
                  h.pnl_pct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
                )}
              >
                <PrivacyValue
                  value={`${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct.toFixed(2)}%`}
                />
              </td>
            </tr>
          ))}
          {holdings.length === 0 && (
            <tr>
              <td colSpan={6} className="py-12">
                <div className="flex flex-col items-center gap-2 text-muted-foreground">
                  <span className="text-2xl">📊</span>
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
