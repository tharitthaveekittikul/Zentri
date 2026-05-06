"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { api } from "@/lib/api";

const CURRENCIES = ["THB", "USD", "EUR", "GBP", "JPY", "SGD"];

interface CashAsset {
  id: string;
  symbol: string;
  currency: string;
  metadata_?: { account_number?: string };
}

interface Props {
  asset: CashAsset;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onEdited: () => void;
}

export function EditCashAccountDialog({ asset, open, onOpenChange, onEdited }: Props) {
  const [symbol, setSymbol] = useState(asset.symbol);
  const [currency, setCurrency] = useState(asset.currency);
  const [accountNumber, setAccountNumber] = useState(
    asset.metadata_?.account_number ?? ""
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setSymbol(asset.symbol);
      setCurrency(asset.currency);
      setAccountNumber(asset.metadata_?.account_number ?? "");
    }
  }, [open, asset]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.patch(`/api/v1/assets/${asset.id}`, {
        symbol: symbol.toUpperCase(),
        name: symbol.toUpperCase(),
        currency,
        metadata_: accountNumber ? { account_number: accountNumber } : {},
      });
      if (!res.ok) throw new Error("Failed to update account");
      toast.success("Account updated");
      onOpenChange(false);
      onEdited();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update account");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Account</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Account Name</Label>
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="SCB_THB"
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Currency</Label>
              <Select value={currency} onValueChange={(v) => { if (v) setCurrency(v); }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCIES.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Account Number (optional)</Label>
            <Input
              value={accountNumber}
              onChange={(e) => setAccountNumber(e.target.value)}
              placeholder="xxx-x-xxxxx-x"
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Saving…" : "Save Changes"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
