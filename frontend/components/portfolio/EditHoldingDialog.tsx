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
import { updateHolding, HoldingRow } from "@/lib/services/portfolio";

interface Props {
  holding: HoldingRow | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function EditHoldingDialog({
  holding,
  open,
  onOpenChange,
  onUpdated,
}: Props) {
  const [quantity, setQuantity] = useState("");
  const [costPerShare, setCostPerShare] = useState("");
  const [currency, setCurrency] = useState("");
  const [platform, setPlatform] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (holding) {
      setQuantity(holding.outstanding_shares);
      setCostPerShare(holding.cost_per_share);
      setCurrency(holding.currency);
      setPlatform(holding.platform ?? "");
    }
  }, [holding, open]);

  if (!holding) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!holding) return;
    setLoading(true);
    try {
      await updateHolding(holding.id, {
        quantity,
        avg_cost_price: costPerShare,
        currency,
        platform: platform || null,
      });
      toast.success(`${holding.symbol} updated`);
      onOpenChange(false);
      onUpdated();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {holding.symbol}</DialogTitle>
        </DialogHeader>
        <div className="text-sm text-muted-foreground mb-2">
          {holding.asset_type}
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Outstanding Shares</Label>
              <Input
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Cost per Share</Label>
              <Input
                value={costPerShare}
                onChange={(e) => setCostPerShare(e.target.value)}
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Currency</Label>
              <Input
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Platform (optional)</Label>
              <Input
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                placeholder="Interactive Brokers"
              />
            </div>
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Saving…" : "Save Changes"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
