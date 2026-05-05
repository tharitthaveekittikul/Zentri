"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchOverviewSummary, fetchAllocation } from "@/lib/services/overview";
import { fetchHoldings } from "@/lib/services/portfolio";
import { SummaryBar } from "@/components/overview/SummaryBar";
import { PerformanceChart } from "@/components/overview/PerformanceChart";
import { AllocationDonut } from "@/components/overview/AllocationDonut";
import { HoldingsSnapshot, SnapshotHolding } from "@/components/overview/HoldingsSnapshot";
import { Skeleton } from "@/components/ui/skeleton";

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

  const snapshotHoldings: SnapshotHolding[] = holdings.map((h) => ({
    symbol: h.symbol,
    name: h.symbol,
    asset_type: h.asset_type,
    quantity: h.outstanding_shares,
    current_value: h.holding_value != null ? Number(h.holding_value) : Number(h.total_cost),
    pnl_pct: 0,
  }));

  const sorted = [...snapshotHoldings].sort((a, b) => b.current_value - a.current_value);

  return (
    <div className="p-6 flex flex-col gap-6 max-w-7xl mx-auto">
      {summaryLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : summary ? (
        <SummaryBar summary={summary} />
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 bg-card rounded-lg border p-4">
          <PerformanceChart />
        </div>
        <div className="lg:col-span-2 bg-card rounded-lg border p-4">
          <AllocationDonut allocation={allocation} />
        </div>
      </div>

      <div>
        <h2 className="text-sm font-medium text-muted-foreground mb-2">Holdings</h2>
        <HoldingsSnapshot holdings={sorted} />
      </div>
    </div>
  );
}
