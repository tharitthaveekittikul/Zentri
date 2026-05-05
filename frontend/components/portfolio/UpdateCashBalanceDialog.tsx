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
import { toast } from "sonner";
import { createBalance } from "@/lib/services/cash-balance";

interface Props {
  assetId: string;
  assetSymbol: string;
  currentBalance: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function UpdateCashBalanceDialog({
  assetId,
  assetSymbol,
  currentBalance,
  open,
  onOpenChange,
  onUpdated,
}: Props) {
  const [balance, setBalance] = useState(String(currentBalance));
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setBalance(String(currentBalance));
    setDate(new Date().toISOString().slice(0, 10));
  }, [currentBalance, open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await createBalance(assetId, parseFloat(balance), date);
      toast.success(`${assetSymbol} balance updated`);
      onOpenChange(false);
      onUpdated();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update balance");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update {assetSymbol} Balance</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <Label>Balance</Label>
            <Input
              type="number"
              value={balance}
              onChange={(e) => setBalance(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1">
            <Label>Date</Label>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Saving…" : "Update Balance"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
