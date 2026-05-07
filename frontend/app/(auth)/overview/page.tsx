"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchOverviewSummary, fetchAllocation } from "@/lib/services/overview";
import { KpiCards } from "@/components/overview/KpiCards";
import { PerformanceChart } from "@/components/overview/PerformanceChart";
import { AllocationDonut } from "@/components/overview/AllocationDonut";
import { Skeleton } from "@/components/ui/skeleton";
import { NetWorthChart } from "@/components/net-worth-chart";
import { PageHeader } from "@/components/layout/PageHeader";

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

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      <PageHeader title="Overview" />
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

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <div className="lg:col-span-3 bg-card card-surface rounded-2xl border border-border p-5 overflow-hidden">
          <PerformanceChart />
        </div>
        <div className="lg:col-span-2 bg-card card-surface rounded-2xl border border-border p-5 overflow-hidden">
          <AllocationDonut allocation={allocation} />
        </div>
      </div>
    </div>
  );
}
