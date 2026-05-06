"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchOverviewSummary, fetchAllocation } from "@/lib/services/overview";
import { fetchHoldings } from "@/lib/services/portfolio";
import { KpiCards } from "@/components/overview/KpiCards";
import { PerformanceChart } from "@/components/overview/PerformanceChart";
import { AllocationDonut } from "@/components/overview/AllocationDonut";
import { HoldingsSnapshot, SnapshotHolding } from "@/components/overview/HoldingsSnapshot";
import { Skeleton } from "@/components/ui/skeleton";
import { NetWorthChart } from "@/components/net-worth-chart";

export default function OverviewPage() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["overview", "summary"],
    queryFn: fetchOverviewSummary,
    refetchInterval: 60_000,
  });

  const { data: allocation = [] } = useQuery({
    queryKey: ["overview", "allocation"],
    queryFn: fetchAllocation,
    refetchInterval: 60_000,
  });

  const { data: holdings = [] } = useQuery({
    queryKey: ["portfolio", "holdings"],
    queryFn: fetchHoldings,
  });

  const snapshotHoldings: SnapshotHolding[] = holdings
    .map((h) => ({
      symbol: h.symbol,
      asset_type: h.asset_type,
      quantity: h.outstanding_shares,
      current_value: h.holding_value != null ? Number(h.holding_value) : Number(h.total_cost),
      cost_basis: Number(h.total_cost),
      pnl_pct: h.holding_value != null && Number(h.total_cost) > 0
        ? ((Number(h.holding_value) - Number(h.total_cost)) / Number(h.total_cost)) * 100
        : 0,
    }))
    .sort((a, b) => b.current_value - a.current_value);

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      {summaryLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
      ) : summary ? (
        <KpiCards summary={summary} />
      ) : null}

      <NetWorthChart privacyMode={false} />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 bg-card rounded-2xl border border-border p-5 overflow-hidden">
          <PerformanceChart />
        </div>
        <div className="lg:col-span-2 bg-card rounded-2xl border border-border p-5 overflow-hidden">
          <AllocationDonut allocation={allocation} />
        </div>
      </div>

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-3">
          Holdings
        </p>
        <HoldingsSnapshot holdings={snapshotHoldings} />
      </div>
    </div>
  );
}
