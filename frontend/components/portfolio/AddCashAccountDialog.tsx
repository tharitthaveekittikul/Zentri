"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { createBalance } from "@/lib/services/cash-balance";

const CURRENCIES = ["THB", "USD", "EUR", "GBP", "JPY", "SGD"];

interface Props {
  onAdded: () => void;
}

export function AddCashAccountDialog({ onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [currency, setCurrency] = useState("THB");
  const [balance, setBalance] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [loading, setLoading] = useState(false);

  function reset() {
    setSymbol("");
    setCurrency("");
    setBalance("");
    setAccountNumber("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      // 1. Create the cash asset
      const assetRes = await api.post("/api/v1/assets", {
        symbol: symbol.toUpperCase(),
        asset_type: "cash",
        name: symbol.toUpperCase(),
        currency: currency,
        metadata_: accountNumber ? { account_number: accountNumber } : {},
      });
      if (!assetRes.ok) throw new Error("Failed to create account");
      const asset = await assetRes.json();

      // 2. Record initial balance snapshot
      await createBalance(
        asset.id,
        parseFloat(balance),
        new Date().toISOString().slice(0, 10),
      );

      toast.success(`${symbol.toUpperCase()} account added`);
      setOpen(false);
      reset();
      onAdded();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add account");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm">
            <Plus className="h-4 w-4 mr-1" />
            Add Account
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Cash Account</DialogTitle>
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
          <div className="space-y-1">
            <Label>Initial Balance</Label>
            <Input
              type="number"
              value={balance}
              onChange={(e) => setBalance(e.target.value)}
              placeholder="0"
              required
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Adding…" : "Add Account"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
