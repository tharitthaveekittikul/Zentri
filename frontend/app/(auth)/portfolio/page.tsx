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
import { PlatformBreakdownCards } from "@/components/portfolio/PlatformBreakdownCards";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { Info } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { DualValue } from "@/hooks/useDualCurrency";

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
      <PageHeader title="Portfolio" />
      <div className="flex items-center gap-2 flex-wrap">
        <Link
          href="/import"
          className="inline-flex items-center justify-center h-9 px-5 rounded-full bg-primary text-primary-foreground text-sm font-medium transition-all duration-150 hover:opacity-85 active:scale-[0.97]"
        >
          Import
        </Link>
        <AddTransactionDialog
          primaryCurrency={displayCurrency}
          onAdded={refresh}
        />
        <AddHoldingDialog
          primaryCurrency={displayCurrency}
          onAdded={refresh}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card className="min-h-[96px] flex flex-col justify-between">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Holdings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tracking-tight tabular-nums">
              {summary?.holdings_count ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card className="min-h-[96px] flex flex-col justify-between">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide flex items-center">
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
            {summary ? (
              <DualCurrencyAmount
                value={{
                  primary: `${parseFloat(summary.total_cost).toLocaleString(undefined, { minimumFractionDigits: 2 })} ${displayCurrency}`,
                  secondary: summary.total_cost_secondary != null
                    ? `≈ ${parseFloat(summary.total_cost_secondary).toLocaleString(undefined, { minimumFractionDigits: 2 })} ${displaySecondaryCurrency}`
                    : null,
                  primaryCurrency: displayCurrency,
                  secondaryCurrency: displaySecondaryCurrency,
                } satisfies DualValue}
                primaryClassName="text-2xl font-semibold font-mono tabular-nums tracking-tight"
              />
            ) : (
              <p className="text-2xl font-semibold font-mono tabular-nums tracking-tight">—</p>
            )}
          </CardContent>
        </Card>
      </div>

      <PlatformBreakdownCards holdings={holdings} />

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <HoldingsTable
          holdings={holdings}
          onDelete={(id) => deleteMutation.mutate(id)}
          onUpdated={refresh}
        />
      )}

      <CashAccountsSection />
    </div>
  );
}
