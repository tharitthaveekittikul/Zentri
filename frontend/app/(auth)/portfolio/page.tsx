"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchHoldings,
  deleteHolding,
  fetchSummary,
} from "@/lib/services/portfolio";
import { fetchAllAssets } from "@/lib/services/assets";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { AddHoldingDialog } from "@/components/portfolio/AddHoldingDialog";
import { ImportDrawer } from "@/components/portfolio/ImportDrawer";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { usePrivacyStore } from "@/store/privacy";

export default function PortfolioPage() {
  const qc = useQueryClient();
  const { isPrivate } = usePrivacyStore();

  const { data: holdings = [], isLoading } = useQuery({
    queryKey: ["holdings"],
    queryFn: fetchHoldings,
  });

  const { data: summary } = useQuery({
    queryKey: ["portfolio-summary"],
    queryFn: fetchSummary,
  });

  const { data: assets = [] } = useQuery({
    queryKey: ["assets"],
    queryFn: fetchAllAssets,
  });

  const assetMap = Object.fromEntries(
    assets.map((a) => [a.id, a.symbol])
  );

  const deleteMutation = useMutation({
    mutationFn: deleteHolding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holdings"] });
      qc.invalidateQueries({ queryKey: ["portfolio-summary"] });
      toast.success("Holding removed");
    },
    onError: () => toast.error("Failed to remove holding"),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["holdings"] });
    qc.invalidateQueries({ queryKey: ["portfolio-summary"] });
    qc.invalidateQueries({ queryKey: ["assets"] });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Portfolio</h1>
        <div className="flex gap-2">
          <ImportDrawer onImported={refresh} />
          <AddHoldingDialog onAdded={refresh} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">
              Holdings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {summary?.holdings_count ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">
              Total Cost
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {isPrivate
                ? "••••"
                : summary
                ? `$${parseFloat(summary.total_cost_usd).toLocaleString()}`
                : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <HoldingsTable
          holdings={holdings}
          assetMap={assetMap}
          onDelete={(id) => deleteMutation.mutate(id)}
        />
      )}
    </div>
  );
}
