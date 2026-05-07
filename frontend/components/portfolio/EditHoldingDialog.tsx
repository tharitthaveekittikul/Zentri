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
import { updateHolding, fetchAsset, updateAsset, lookupThFund, ThFundMatch, HoldingRow } from "@/lib/services/portfolio";

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
  const [projId, setProjId] = useState("");
  const [lookupResults, setLookupResults] = useState<ThFundMatch[]>([]);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [assetLoading, setAssetLoading] = useState(false);

  async function triggerLookup(query: string) {
    if (!query) return;
    setLookupLoading(true);
    setLookupResults([]);
    try {
      const results = await lookupThFund(query);
      if (results.length === 1) {
        setProjId(results[0].proj_id);
      } else {
        setLookupResults(results);
      }
    } catch {
      toast.error("Fund lookup failed");
    } finally {
      setLookupLoading(false);
    }
  }

  useEffect(() => {
    if (!holding || !open) return;
    let cancelled = false;
    setQuantity(holding.outstanding_shares);
    setCostPerShare(holding.cost_per_share);
    setCurrency(holding.currency);
    setPlatform(holding.platform ?? "");
    setSymbol(holding.symbol);
    setAssetName("");
    setProjId("");
    setLookupResults([]);
    setAssetLoading(true);
    fetchAsset(holding.asset_id)
      .then((asset) => {
        if (cancelled) return;
        const fetchedSymbol = asset.symbol;
        const fetchedProjId = (asset.metadata_?.proj_id as string) ?? "";
        setSymbol(fetchedSymbol);
        setAssetName(asset.name);
        setProjId(fetchedProjId);
        if (!fetchedProjId && holding.asset_type === "th_fund") {
          lookupThFund(fetchedSymbol).then((results) => {
            if (cancelled) return;
            if (results.length === 1) {
              setProjId(results[0].proj_id);
            } else if (results.length > 1) {
              setLookupResults(results);
            }
          }).catch(() => {});
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
      const assetUpdate: Parameters<typeof updateAsset>[1] = { symbol, name: assetName };
      if (holding.asset_type === "th_fund") {
        assetUpdate.metadata_ = { proj_id: projId.trim() };
      }
      await Promise.all([
        updateAsset(holding.asset_id, assetUpdate),
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
            {holding.asset_type === "th_fund" && (
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <Label>SEC Project ID</Label>
                  <button
                    type="button"
                    onClick={() => triggerLookup(symbol)}
                    disabled={lookupLoading || assetLoading || !symbol}
                    className="text-xs text-primary hover:underline disabled:opacity-40"
                  >
                    {lookupLoading ? "Searching…" : "Lookup by symbol"}
                  </button>
                </div>
                <Input
                  value={projId}
                  onChange={(e) => { setProjId(e.target.value); setLookupResults([]); }}
                  disabled={assetLoading}
                  placeholder="e.g. M0000_2552"
                />
                {lookupResults.length > 0 && (
                  <div className="border rounded-md divide-y text-xs max-h-40 overflow-y-auto">
                    {lookupResults.map((r) => (
                      <button
                        key={r.proj_id}
                        type="button"
                        onClick={() => {
                          setProjId(r.proj_id);
                          if (!assetName) setAssetName(r.proj_name_en || r.proj_abbr_name);
                          setLookupResults([]);
                        }}
                        className="w-full text-left px-3 py-2 hover:bg-muted"
                      >
                        <span className="font-medium">{r.proj_abbr_name}</span>
                        <span className="text-muted-foreground ml-2">{r.proj_id}</span>
                        {r.proj_name_en && (
                          <div className="text-muted-foreground truncate">{r.proj_name_en}</div>
                        )}
                      </button>
                    ))}
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  Required for NAV price fetching.
                </p>
              </div>
            )}
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
