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
    <div className="rounded-lg border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-3 font-medium text-muted-foreground">Symbol</th>
            <th className="text-left p-3 font-medium text-muted-foreground">Name</th>
            <th className="text-left p-3 font-medium text-muted-foreground">Type</th>
            <th className="text-right p-3 font-medium text-muted-foreground">Quantity</th>
            <th className="text-right p-3 font-medium text-muted-foreground">Cost Basis</th>
            <th className="text-right p-3 font-medium text-muted-foreground">P&amp;L%</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr
              key={h.symbol}
              className="border-t hover:bg-muted/30 cursor-pointer transition-colors"
              onClick={() => router.push(`/portfolio/${h.symbol}`)}
            >
              <td className="p-3 font-mono font-medium">{h.symbol}</td>
              <td className="p-3 text-muted-foreground">{h.name}</td>
              <td className="p-3">
                <Badge variant="outline" className="text-xs">
                  {h.asset_type.replace("_", " ")}
                </Badge>
              </td>
              <td className="p-3 text-right">{Number(h.quantity).toFixed(4)}</td>
              <td className="p-3 text-right">
                <PrivacyValue
                  value={`$${h.current_value.toLocaleString("en-US", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}`}
                />
              </td>
              <td
                className={cn(
                  "p-3 text-right font-medium",
                  h.pnl_pct >= 0 ? "text-green-500" : "text-red-500"
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
              <td colSpan={6} className="p-6 text-center text-muted-foreground">
                No holdings yet. Add assets in the Portfolio tab.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
