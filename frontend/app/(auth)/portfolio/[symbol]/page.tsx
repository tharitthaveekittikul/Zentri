"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchAssetHistory } from "@/lib/services/overview";
import { fetchAllAssets } from "@/lib/services/assets";
import { PriceChart } from "@/components/portfolio/PriceChart";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { api } from "@/lib/api";
import { VerdictCard } from "@/components/analysis/VerdictCard";

const RANGES = ["1W", "1M", "3M", "1Y"] as const;
type Range = (typeof RANGES)[number];

interface Transaction {
  id: string;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  platform_id: string | null;
}

export default function AssetDetailPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const [range, setRange] = useState<Range>("1M");

  const { data: assets = [] } = useQuery({
    queryKey: ["assets"],
    queryFn: fetchAllAssets,
  });
  const asset = assets.find(
    (a) => a.symbol.toUpperCase() === symbol.toUpperCase(),
  );

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["asset-history", symbol, range],
    queryFn: () => fetchAssetHistory(symbol, range),
    enabled: !!symbol,
  });

  const { data: txData } = useQuery({
    queryKey: ["transactions", asset?.id],
    queryFn: async (): Promise<Transaction[]> => {
      if (!asset) return [];
      const res = await api.get(
        `/api/v1/portfolio/transactions?asset_id=${asset.id}`,
      );
      if (!res.ok) return [];
      return res.json();
    },
    enabled: !!asset,
  });

  const bars = history?.bars ?? [];
  const latestBar = bars[bars.length - 1];
  const prevBar = bars[bars.length - 2];
  const dailyChange =
    latestBar && prevBar
      ? Number(latestBar.close) - Number(prevBar.close)
      : null;
  const dailyChangePct =
    dailyChange != null && prevBar
      ? (dailyChange / Number(prevBar.close)) * 100
      : null;

  return (
    <div className="p-6 flex flex-col gap-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{symbol.toUpperCase()}</h1>
          <p className="text-muted-foreground">{asset?.name ?? "Loading..."}</p>
        </div>
        <div className="text-right">
          {latestBar && (
            <>
              <p className="text-2xl font-semibold">
                <PrivacyValue
                  value={`$${Number(latestBar.close).toLocaleString("en-US", {
                    minimumFractionDigits: 2,
                  })}`}
                />
              </p>
              {dailyChange != null && dailyChangePct != null && (
                <Badge
                  variant={dailyChange >= 0 ? "default" : "destructive"}
                >
                  <PrivacyValue
                    value={`${dailyChange >= 0 ? "+" : ""}${dailyChange.toFixed(2)} (${dailyChangePct.toFixed(2)}%)`}
                  />
                </Badge>
              )}
            </>
          )}
        </div>
      </div>

      <Tabs value={range} onValueChange={(v) => setRange(v as Range)}>
        <TabsList>
          {RANGES.map((r) => (
            <TabsTrigger key={r} value={r}>
              {r}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="bg-card rounded-lg border p-4">
        {historyLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : (
          <PriceChart bars={bars} />
        )}
      </div>

      <VerdictCard symbol={symbol} />

      <div>
        <h2 className="text-sm font-medium text-muted-foreground mb-2">
          Transactions
        </h2>
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3 font-medium text-muted-foreground">
                  Date
                </th>
                <th className="text-left p-3 font-medium text-muted-foreground">
                  Type
                </th>
                <th className="text-right p-3 font-medium text-muted-foreground">
                  Quantity
                </th>
                <th className="text-right p-3 font-medium text-muted-foreground">
                  Price
                </th>
                <th className="text-right p-3 font-medium text-muted-foreground">
                  Fee
                </th>
                <th className="text-left p-3 font-medium text-muted-foreground">
                  Source
                </th>
              </tr>
            </thead>
            <tbody>
              {(txData ?? []).map((tx) => (
                <tr key={tx.id} className="border-t">
                  <td className="p-3 text-muted-foreground">
                    {new Date(tx.executed_at).toLocaleDateString("en-US")}
                  </td>
                  <td className="p-3">
                    <Badge
                      variant={
                        tx.type === "buy"
                          ? "default"
                          : tx.type === "sell"
                            ? "destructive"
                            : "outline"
                      }
                      className="text-xs"
                    >
                      {tx.type}
                    </Badge>
                  </td>
                  <td className="p-3 text-right font-mono">
                    {Number(tx.quantity).toFixed(6)}
                  </td>
                  <td className="p-3 text-right">
                    <PrivacyValue
                      value={`$${Number(tx.price).toLocaleString("en-US", {
                        minimumFractionDigits: 2,
                      })}`}
                    />
                  </td>
                  <td className="p-3 text-right">
                    <PrivacyValue value={`$${Number(tx.fee).toFixed(2)}`} />
                  </td>
                  <td className="p-3 text-muted-foreground capitalize">
                    {tx.source}
                  </td>
                </tr>
              ))}
              {!txData?.length && (
                <tr>
                  <td
                    colSpan={6}
                    className="p-6 text-center text-muted-foreground"
                  >
                    No transactions recorded for this asset.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
