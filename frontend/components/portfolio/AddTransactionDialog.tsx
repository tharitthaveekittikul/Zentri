"use client";

import { useMemo, useState } from "react";
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
import { toast } from "sonner";
import { addManualTransaction } from "@/lib/services/portfolio";
import { ArrowRightLeft } from "lucide-react";
import { DatePicker } from "@/components/ui/date-picker";

const ASSET_TYPES = [
  "us_stock",
  "thai_stock",
  "th_fund",
  "etf",
  "crypto",
  "gold",
  "cash",
];

const TX_TYPES = ["buy", "sell", "dividend", "reward", "fee", "transfer"];

interface Props {
  primaryCurrency: string;
  onAdded: () => void;
}

export function AddTransactionDialog({ primaryCurrency, onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [assetType, setAssetType] = useState("us_stock");
  const [txType, setTxType] = useState("buy");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [fee, setFee] = useState("");
  const [currency, setCurrency] = useState(primaryCurrency);
  const [platform, setPlatform] = useState("");
  const [executedAt, setExecutedAt] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [loading, setLoading] = useState(false);

  const totalCost = useMemo(() => {
    const q = parseFloat(quantity);
    const p = parseFloat(price);
    if (!isNaN(q) && !isNaN(p))
      return (q * p).toLocaleString(undefined, { minimumFractionDigits: 2 });
    return "—";
  }, [quantity, price]);

  function reset() {
    setSymbol("");
    setAssetType("us_stock");
    setTxType("buy");
    setQuantity("");
    setPrice("");
    setFee("");
    setPlatform("");
    setExecutedAt(new Date().toISOString().slice(0, 10));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await addManualTransaction({
        symbol,
        asset_type: assetType,
        currency,
        platform: platform || null,
        type: txType,
        quantity,
        price,
        fee: fee || "0",
        executed_at: new Date(executedAt).toISOString(),
      });
      toast.success(`${txType.charAt(0).toUpperCase() + txType.slice(1)} ${symbol} recorded`);
      setOpen(false);
      reset();
      onAdded();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add transaction");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline" className="h-9 rounded-full text-sm font-medium">
            <ArrowRightLeft className="h-4 w-4 mr-1" />
            Add Transaction
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Transaction</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Symbol</Label>
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="AAPL"
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Asset Type</Label>
              <Select value={assetType} onValueChange={(v) => { if (v) setAssetType(v); }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ASSET_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Type</Label>
              <Select value={txType} onValueChange={(v) => { if (v) setTxType(v); }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TX_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Date</Label>
              <DatePicker
                value={executedAt}
                onChange={setExecutedAt}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Quantity</Label>
              <Input
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="10"
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Price per Unit</Label>
              <Input
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="150.00"
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Fee (optional)</Label>
              <Input
                value={fee}
                onChange={(e) => setFee(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="space-y-1">
              <Label>Currency</Label>
              <Input
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                placeholder="THB"
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Platform (optional)</Label>
            <Input
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              placeholder="Interactive Brokers"
            />
          </div>
          <div className="rounded-md bg-muted px-3 py-2 text-sm flex justify-between">
            <span className="text-muted-foreground">Total Value</span>
            <span className="font-medium">
              {currency} {totalCost}
            </span>
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Saving…" : "Add Transaction"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
