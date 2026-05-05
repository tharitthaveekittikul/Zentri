"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchHoldings,
  deleteHolding,
  fetchSummary,
} from "@/lib/services/portfolio";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { CashAccountsSection } from "@/components/portfolio/CashAccountsSection";
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
import { Info } from "lucide-react";
import { usePrivacyStore } from "@/store/privacy";
import { api } from "@/lib/api";

function InfoTooltip({ content }: { content: React.ReactNode }) {
  return (
    <span className="relative group inline-flex items-center ml-1 align-middle">
      <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
      <span className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-max max-w-56 rounded-md border bg-popover text-popover-foreground text-xs px-2.5 py-1.5 shadow-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
        {content}
      </span>
    </span>
  );
}

export default function PortfolioPage() {
  const qc = useQueryClient();
  const { isPrivate } = usePrivacyStore();
  const [primaryCurrency, setPrimaryCurrency] = useState("THB");
  const [secondaryCurrency, setSecondaryCurrency] = useState("USD");

  useEffect(() => {
    api
      .get("/api/v1/settings/display")
      .then((r) => r.json())
      .then((d: { currency_primary?: string; currency_secondary?: string }) => {
        if (d.currency_primary) setPrimaryCurrency(d.currency_primary);
        if (d.currency_secondary) setSecondaryCurrency(d.currency_secondary);
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
  const displaySecondaryCurrency = summary?.secondary_currency ?? secondaryCurrency;

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
            <CardTitle className="text-sm text-muted-foreground flex items-center">
              Total Cost
              {summary?.exchange_rate && summary.exchange_rate_date && (
                <InfoTooltip
                  content={
                    <>
                      <p>1 {displayCurrency} = {parseFloat(summary.exchange_rate).toFixed(4)} {displaySecondaryCurrency}</p>
                      <p className="text-muted-foreground mt-0.5">Rate date: {summary.exchange_rate_date}</p>
                    </>
                  }
                />
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {isPrivate
                ? "••••"
                : summary
                ? `${parseFloat(summary.total_cost).toLocaleString(undefined, { minimumFractionDigits: 2 })} ${displayCurrency}`
                : "—"}
            </p>
            {!isPrivate && summary?.total_cost_secondary != null && (
              <p className="text-xs text-muted-foreground mt-0.5">
                ≈ {parseFloat(summary.total_cost_secondary).toLocaleString(undefined, { minimumFractionDigits: 2 })} {displaySecondaryCurrency}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <HoldingsTable
          holdings={holdings}
          primaryCurrency={displayCurrency}
          secondaryCurrency={displaySecondaryCurrency}
          primaryToSecondaryRate={
            summary?.total_cost_secondary != null && parseFloat(summary.total_cost) > 0
              ? parseFloat(summary.total_cost_secondary) / parseFloat(summary.total_cost)
              : undefined
          }
          onDelete={(id) => deleteMutation.mutate(id)}
          onUpdated={refresh}
        />
      )}

      <CashAccountsSection />
    </div>
  );
}
