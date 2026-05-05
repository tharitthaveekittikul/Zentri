"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchHoldings,
  deleteHolding,
  fetchSummary,
} from "@/lib/services/portfolio";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { AddHoldingDialog } from "@/components/portfolio/AddHoldingDialog";
import { AddTransactionDialog } from "@/components/portfolio/AddTransactionDialog";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { usePrivacyStore } from "@/store/privacy";
import { api } from "@/lib/api";

export default function PortfolioPage() {
  const qc = useQueryClient();
  const { isPrivate } = usePrivacyStore();
  const [primaryCurrency, setPrimaryCurrency] = useState("THB");

  useEffect(() => {
    api
      .get("/api/v1/settings/display")
      .then((r) => r.json())
      .then((d: { currency_primary?: string }) => {
        if (d.currency_primary) setPrimaryCurrency(d.currency_primary);
      })
      .catch(() => {});
  }, []);

  const { data: holdings = [], isLoading } = useQuery({
    queryKey: ["holdings"],
    queryFn: fetchHoldings,
  });

  const { data: summary } = useQuery({
    queryKey: ["portfolio-summary"],
    queryFn: fetchSummary,
  });

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
  };

  const displayCurrency = summary?.primary_currency ?? primaryCurrency;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center justify-between flex-1">
          <h1 className="text-2xl font-bold">Portfolio</h1>
          <Link
            href="/import"
            className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium"
          >
            Import
          </Link>
        </div>
        <div className="flex gap-2 ml-4">
          <AddTransactionDialog
            primaryCurrency={displayCurrency}
            onAdded={refresh}
          />
          <AddHoldingDialog
            primaryCurrency={displayCurrency}
            onAdded={refresh}
          />
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
                ? `${displayCurrency} ${parseFloat(summary.total_cost).toLocaleString(undefined, { minimumFractionDigits: 2 })}`
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
          primaryCurrency={displayCurrency}
          onDelete={(id) => deleteMutation.mutate(id)}
        />
      )}
    </div>
  );
}
