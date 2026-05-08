"use client";

import { useMemo, useState, useEffect } from "react";
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
import { addHolding, searchCoinGecko, CoinGeckoResult } from "@/lib/services/portfolio";
import { Plus } from "lucide-react";
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

interface Props {
  primaryCurrency: string;
  onAdded: () => void;
}

export function AddHoldingDialog({ primaryCurrency, onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [assetType, setAssetType] = useState("us_stock");
  const [purchasedAt, setPurchasedAt] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [currency, setCurrency] = useState(primaryCurrency);
  const [loading, setLoading] = useState(false);
  const [coingeckoId, setCoingeckoId] = useState("");
  const [coinThumb, setCoinThumb] = useState("");
  const [coinResults, setCoinResults] = useState<CoinGeckoResult[]>([]);

  useEffect(() => {
    if (assetType !== "crypto" || coingeckoId.length < 2) {
      setCoinResults([]);
      return;
    }
    const timer = setTimeout(() => {
      searchCoinGecko(coingeckoId).then(setCoinResults).catch(() => {});
    }, 500);
    return () => clearTimeout(timer);
  }, [coingeckoId, assetType]);

  const totalCost = useMemo(() => {
    const q = parseFloat(quantity);
    const c = parseFloat(avgCost);
    if (!isNaN(q) && !isNaN(c))
      return (q * c).toLocaleString(undefined, { minimumFractionDigits: 2 });
    return "—";
  }, [quantity, avgCost]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await addHolding({
        symbol,
        asset_type: assetType,
        purchased_at: purchasedAt || null,
        quantity,
        avg_cost_price: avgCost,
        currency,
        ...(assetType === "crypto" && coingeckoId
          ? { metadata_: { coingecko_id: coingeckoId, ...(coinThumb ? { logo_url: coinThumb } : {}) } }
          : {}),
      });
      toast.success(`Added ${symbol} to portfolio`);
      setOpen(false);
      setSymbol("");
      setQuantity("");
      setAvgCost("");
      setPurchasedAt("");
      setCoingeckoId("");
      setCoinThumb("");
      setCoinResults([]);
      onAdded();
    } catch {
      toast.error("Failed to add holding");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm" className="h-9 rounded-full text-sm font-medium">
            <Plus className="h-4 w-4 mr-1" />
            Add Holding
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Holding</DialogTitle>
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
              <Select
                value={assetType}
                onValueChange={(v) => {
                  if (v !== null) {
                    setAssetType(v);
                    if (v === "crypto") setCurrency("USD");
                    setCoingeckoId("");
                    setCoinThumb("");
                    setCoinResults([]);
                  }
                }}
              >
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
          {assetType === "crypto" && (
            <div className="space-y-1 relative">
              <Label>CoinGecko ID</Label>
              <Input
                value={coingeckoId}
                onChange={(e) => { setCoingeckoId(e.target.value); }}
                placeholder="e.g. bitcoin"
                required
              />
              {coinResults.length > 0 && (
                <div className="absolute z-10 w-full bg-background border rounded shadow-md top-full mt-1">
                  {coinResults.map((coin) => (
                    <button
                      key={coin.id}
                      type="button"
                      className="w-full text-left px-3 py-2 hover:bg-muted text-sm flex items-center gap-2"
                      onClick={() => {
                        setSymbol(coin.symbol.toUpperCase());
                        setCoingeckoId(coin.id);
                        setCoinThumb(coin.thumb || "");
                        setCoinResults([]);
                      }}
                    >
                      {coin.thumb && <img src={coin.thumb} alt="" className="w-4 h-4 shrink-0" />}
                      {coin.name} <span className="text-muted-foreground">({coin.symbol})</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="space-y-1">
            <Label>First Purchase Date (optional)</Label>
            <DatePicker
              value={purchasedAt}
              onChange={setPurchasedAt}
              placeholder="Select date (optional)"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Outstanding Shares</Label>
              <Input
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="10"
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Cost per Share</Label>
              <Input
                value={avgCost}
                onChange={(e) => setAvgCost(e.target.value)}
                placeholder="150.00"
                required
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Currency</Label>
            <Input
              value={currency}
              onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              placeholder="THB"
            />
          </div>
          <div className="rounded-md bg-muted px-3 py-2 text-sm flex justify-between">
            <span className="text-muted-foreground">Total Cost</span>
            <span className="font-medium">
              {currency} {totalCost}
            </span>
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Adding…" : "Add Holding"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
