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
import { updateHolding, fetchAsset, updateAsset, HoldingRow } from "@/lib/services/portfolio";

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
  const [symbol, setSymbol] = useState("");
  const [assetName, setAssetName] = useState("");
  const [assetLoading, setAssetLoading] = useState(false);

  useEffect(() => {
    if (!holding || !open) return;
    let cancelled = false;
    setQuantity(holding.outstanding_shares);
    setCostPerShare(holding.cost_per_share);
    setCurrency(holding.currency);
    setPlatform(holding.platform ?? "");
    setSymbol(holding.symbol);
    setAssetName("");
    setAssetLoading(true);
    fetchAsset(holding.asset_id)
      .then((asset) => {
        if (!cancelled) {
          setSymbol(asset.symbol);
          setAssetName(asset.name);
        }
      })
      .catch(() => { if (!cancelled) toast.error("Could not load asset details"); })
      .finally(() => { if (!cancelled) setAssetLoading(false); });
    return () => { cancelled = true; };
  }, [holding, open]);

  if (!holding) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!holding) return;
    setLoading(true);
    try {
      await Promise.all([
        updateAsset(holding.asset_id, { symbol, name: assetName }),
        updateHolding(holding.id, {
          quantity,
          avg_cost_price: costPerShare,
          currency,
          platform: platform || null,
        }),
      ]);
      toast.success(`${symbol} updated`);
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
          {/* Asset section */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Asset</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Symbol</Label>
                <Input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                  disabled={assetLoading}
                  required
                />
              </div>
              <div className="space-y-1">
                <Label>Name</Label>
                <Input
                  value={assetName}
                  onChange={(e) => setAssetName(e.target.value)}
                  disabled={assetLoading}
                  placeholder={assetLoading ? "Loading…" : ""}
                />
              </div>
            </div>
          </div>

          {/* Holding section */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Holding</p>
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
          </div>

          <Button type="submit" className="w-full" disabled={loading || assetLoading}>
            {loading ? "Saving…" : "Save Changes"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
