"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { getAllLatestBalances, CashBalance } from "@/lib/services/cash-balance";
import { Pencil, Trash2, Copy } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { AddCashAccountDialog } from "./AddCashAccountDialog";
import { UpdateCashBalanceDialog } from "./UpdateCashBalanceDialog";
import { EditCashAccountDialog } from "./EditCashAccountDialog";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { toast } from "sonner";

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
  const [updateTarget, setUpdateTarget] = useState<CashAccountState | null>(
    null,
  );
  const [updateOpen, setUpdateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<CashAsset | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CashAsset | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const { formatNative } = useDualCurrency();

  const load = useCallback(async () => {
    const res = await api.get("/api/v1/assets");
    if (!res.ok) return;
    const all: CashAsset[] = await res.json();
    const cashAssets = all.filter((a) => a.asset_type === "cash");

    const balanceMap = await getAllLatestBalances();
    const states = cashAssets.map((asset) => ({
      asset,
      latest: balanceMap[asset.id] ?? null,
    }));
    setAccounts(states);
  }, []);

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      const res = await api.delete(`/api/v1/assets/${deleteTarget.id}`);
      if (!res.ok) throw new Error("Failed to delete account");
      toast.success(`${deleteTarget.symbol} deleted`);
      setDeleteOpen(false);
      setDeleteTarget(null);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete account");
    } finally {
      setDeleteLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Cash &amp; Bank Accounts
        </h2>
        <AddCashAccountDialog onAdded={load} />
      </div>

      {accounts.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-6 text-muted-foreground">
          <span className="text-sm font-medium">No cash accounts yet</span>
          <span className="text-xs">Add one to track bank balances.</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {accounts.map(({ asset, latest }) => (
            <Card key={asset.id} className="rounded-2xl">
              <CardHeader className="pb-2 px-5 pt-5">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base font-semibold text-foreground">
                      {asset.symbol}
                    </CardTitle>
                    {asset.metadata_?.account_number && (
                      <div className="flex items-center gap-1">
                        <p className="text-xs text-muted-foreground">
                          {asset.metadata_.account_number}
                        </p>
                        <button
                          className="text-muted-foreground hover:text-foreground transition-colors"
                          onClick={() => {
                            navigator.clipboard.writeText(asset.metadata_!.account_number!);
                            toast.success("Account number copied");
                          }}
                        >
                          <Copy className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => {
                        setEditTarget(asset);
                        setEditOpen(true);
                      }}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => {
                        setDeleteTarget(asset);
                        setDeleteOpen(true);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 px-5 pb-5">
                <div className="text-2xl font-semibold tracking-tight">
                  {latest ? (
                    <DualCurrencyAmount
                      value={formatNative(latest.balance, asset.currency)}
                      primaryClassName="text-2xl font-semibold"
                    />
                  ) : (
                    <span className="font-mono tabular-nums">—</span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {latest
                    ? `Updated: ${latest.snapshot_date}`
                    : "No balance recorded"}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full transition-colors duration-150"
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
          currentBalance={
            updateTarget.latest ? Number(updateTarget.latest.balance) : 0
          }
          open={updateOpen}
          onOpenChange={setUpdateOpen}
          onUpdated={load}
        />
      )}

      {editTarget && (
        <EditCashAccountDialog
          asset={editTarget}
          open={editOpen}
          onOpenChange={setEditOpen}
          onEdited={load}
        />
      )}

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleteTarget?.symbol}?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the account and all its balance history.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleteLoading}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteLoading ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
