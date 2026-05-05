"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { getLatestBalance, CashBalance } from "@/lib/services/cash-balance";
import { AddCashAccountDialog } from "./AddCashAccountDialog";
import { UpdateCashBalanceDialog } from "./UpdateCashBalanceDialog";
import { PrivacyValue } from "@/components/ui/PrivacyValue";

interface CashAsset {
  id: string;
  symbol: string;
  currency: string;
  asset_type: string;
  metadata_?: { account_number?: string };
}

interface CashAccountState {
  asset: CashAsset;
  latest: CashBalance | null;
}

export function CashAccountsSection() {
  const [accounts, setAccounts] = useState<CashAccountState[]>([]);
  const [updateTarget, setUpdateTarget] = useState<CashAccountState | null>(null);
  const [updateOpen, setUpdateOpen] = useState(false);

  const load = useCallback(async () => {
    const res = await api.get("/api/v1/assets");
    if (!res.ok) return;
    const all: CashAsset[] = await res.json();
    const cashAssets = all.filter((a) => a.asset_type === "cash");

    const states = await Promise.all(
      cashAssets.map(async (asset) => {
        let latest: CashBalance | null = null;
        try {
          latest = await getLatestBalance(asset.id);
        } catch {
          // no snapshot yet
        }
        return { asset, latest };
      }),
    );
    setAccounts(states);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Cash &amp; Bank Accounts</h2>
        <AddCashAccountDialog onAdded={load} />
      </div>

      {accounts.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No cash accounts yet. Add one to track bank balances.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {accounts.map(({ asset, latest }) => (
            <Card key={asset.id}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{asset.symbol}</CardTitle>
                {asset.metadata_?.account_number && (
                  <p className="text-xs text-muted-foreground">
                    {asset.metadata_.account_number}
                  </p>
                )}
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="text-2xl font-bold">
                  <PrivacyValue
                    value={
                      latest
                        ? `${Number(latest.balance).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                          })} ${asset.currency}`
                        : "—"
                    }
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  {latest
                    ? `Updated: ${latest.snapshot_date}`
                    : "No balance recorded"}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => {
                    setUpdateTarget({ asset, latest });
                    setUpdateOpen(true);
                  }}
                >
                  Update Balance
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {updateTarget && (
        <UpdateCashBalanceDialog
          assetId={updateTarget.asset.id}
          assetSymbol={updateTarget.asset.symbol}
          currentBalance={updateTarget.latest ? Number(updateTarget.latest.balance) : 0}
          open={updateOpen}
          onOpenChange={setUpdateOpen}
          onUpdated={load}
        />
      )}
    </div>
  );
}
