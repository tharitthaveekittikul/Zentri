"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  BellOff,
  Check,
  Plus,
  Scan,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  acceptSuggestion,
  addToWatchlist,
  deleteWatchlistItem,
  discoverWatchlist,
  dismissSuggestion,
  listSuggestions,
  listWatchlist,
  rearmWatchlistItem,
  scanAll,
  scanItem,
  updateWatchlistItem,
  type WatchlistItem,
  type WatchlistParams,
  type WatchlistSuggestion,
} from "@/lib/services/watchlist";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/layout/PageHeader";
import { TickerLogo } from "@/components/ui/TickerLogo";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { useTableParams } from "@/hooks/useTableParams";
import type { PaginatedResponse } from "@/lib/types";

const VERDICT_STYLE: Record<string, string> = {
  BUY: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  SELL: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  HOLD: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
};

type AssetResult = {
  id: string;
  symbol: string;
  name: string;
  currency: string;
};

function AddDialog({
  open,
  onClose,
  onAdded,
}: {
  open: boolean;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AssetResult[]>([]);
  const [selected, setSelected] = useState<AssetResult | null>(null);
  const [targetPrice, setTargetPrice] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      const r = await api.get(
        `/api/v1/assets/search?q=${encodeURIComponent(query)}`,
      );
      if (r.ok) setResults(await r.json());
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  const handleAdd = async () => {
    if (!selected) return;
    setAdding(true);
    try {
      await addToWatchlist({
        asset_id: selected.id,
        target_price: targetPrice || null,
      });
      toast.success(`${selected.symbol} added to watchlist`);
      onAdded();
      onClose();
      setQuery("");
      setSelected(null);
      setTargetPrice("");
    } catch {
      toast.error("Failed to add to watchlist");
    } finally {
      setAdding(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add to Watchlist</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <input
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder="Search ticker or name…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelected(null);
            }}
          />
          {results.length > 0 && !selected && (
            <div className="border rounded divide-y max-h-48 overflow-y-auto">
              {results.map((a) => (
                <button
                  key={a.id}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-accent"
                  onClick={() => {
                    setSelected(a);
                    setQuery(a.symbol);
                    setResults([]);
                  }}
                >
                  <span className="font-medium">{a.symbol}</span>{" "}
                  <span className="text-muted-foreground">{a.name}</span>
                </button>
              ))}
            </div>
          )}
          {selected && (
            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Target price (optional)
              </label>
              <input
                type="number"
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="e.g. 150.00"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleAdd} disabled={!selected || adding}>
            {adding ? "Adding…" : "Add"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function WatchlistPage() {
  const router = useRouter();
  const { formatNative } = useDualCurrency();
  const { get, getInt, setParam } = useTableParams();
  const [itemsPage, setItemsPage] = useState<PaginatedResponse<WatchlistItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 25,
  });
  const [searchInput, setSearchInput] = useState(get("search"));
  const [suggestions, setSuggestions] = useState<WatchlistSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanningAll, setScanningAll] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [scanningId, setScanningId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const fetchAll = useCallback(async () => {
    const params: WatchlistParams = {
      search: get("search") || undefined,
      asset_type: get("asset_type") || undefined,
      alert_status: get("alert_status") || undefined,
      page: getInt("page", 1),
      page_size: getInt("page_size", 25),
    };
    setLoading(true);
    const [w, s] = await Promise.all([
      listWatchlist(params).catch(() => ({
        items: [],
        total: 0,
        page: 1,
        page_size: 25,
      })),
      listSuggestions().catch(() => []),
    ]);
    setItemsPage(w as PaginatedResponse<WatchlistItem>);
    setSuggestions(s);
    setLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [get("search"), get("asset_type"), get("alert_status"), getInt("page", 1), getInt("page_size", 25)]);

  // Re-fetch when URL params change
  useEffect(() => {
    fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    get("search"),
    get("asset_type"),
    get("alert_status"),
    getInt("page", 1),
    getInt("page_size", 25),
  ]);

  // Sync local search from URL
  useEffect(() => {
    setSearchInput(get("search"));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [get("search")]);

  // Debounce search → URL
  useEffect(() => {
    const t = setTimeout(() => {
      const current = get("search");
      if (searchInput !== current) {
        setParam({ search: searchInput || null });
      }
    }, 300);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput]);

  const handleScanAll = async () => {
    setScanningAll(true);
    await scanAll();
    toast.success("Scan queued — results will appear shortly");
    setScanningAll(false);
    setTimeout(fetchAll, 5000);
  };

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      await discoverWatchlist();
      toast.success("Discovery queued — suggestions will appear shortly");
      setTimeout(fetchAll, 6000);
    } catch (e) {
      if (e instanceof Error && e.message === "no_llm_config") {
        toast.error("No LLM configured for Watchlist Discovery", {
          description: "Go to Settings → AI & LLM to assign a provider and model.",
          action: { label: "Configure", onClick: () => router.push("/settings") },
        });
      } else {
        toast.error("Failed to start discovery");
      }
    } finally {
      setDiscovering(false);
    }
  };

  const handleScanItem = async (id: string) => {
    setScanningId(id);
    await scanItem(id);
    toast.success("Scan queued");
    setScanningId(null);
    setTimeout(fetchAll, 5000);
  };

  const handleApplyPrice = async (item: WatchlistItem) => {
    if (!item.ai_suggested_price) return;
    await updateWatchlistItem(item.id, {
      target_price: item.ai_suggested_price,
      alert_enabled: true,
    });
    toast.success("Target price set and alert enabled");
    fetchAll();
  };

  const handleToggleAlert = async (item: WatchlistItem) => {
    if (item.alerted_at && !item.alert_enabled) {
      await rearmWatchlistItem(item.id);
    } else {
      await updateWatchlistItem(item.id, {
        alert_enabled: !item.alert_enabled,
      });
    }
    fetchAll();
  };

  const handleDelete = async (id: string) => {
    await deleteWatchlistItem(id);
    toast.success("Removed from watchlist");
    fetchAll();
  };

  const handleAccept = async (s: WatchlistSuggestion) => {
    try {
      await acceptSuggestion(s.id);
      toast.success(`${s.symbol} added to watchlist`);
      fetchAll();
    } catch {
      toast.error("Failed to accept suggestion");
    }
  };

  const handleDismiss = async (id: string) => {
    await dismissSuggestion(id);
    setSuggestions((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <div className="space-y-8">
      <PageHeader title="Watchlist" />

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8 h-9"
            placeholder="Search symbol or name…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <Select
          value={get("asset_type") || "all"}
          onValueChange={(v) => setParam({ asset_type: v === "all" ? null : v })}
        >
          <SelectTrigger className="h-9 w-[150px]">
            <SelectValue placeholder="Asset Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {["us_stock", "thai_stock", "crypto", "etf", "bond", "fund"].map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={get("alert_status") || "all"}
          onValueChange={(v) => setParam({ alert_status: v === "all" ? null : v })}
        >
          <SelectTrigger className="h-9 w-[150px]">
            <SelectValue placeholder="Alert Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="enabled">Enabled</SelectItem>
            <SelectItem value="triggered">Triggered</SelectItem>
            <SelectItem value="disabled">Disabled</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleScanAll}
            disabled={scanningAll}
          >
            <Scan
              className={`h-4 w-4 mr-2 ${scanningAll ? "animate-pulse" : ""}`}
            />
            {scanningAll ? "Scanning…" : "Scan All"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDiscover}
            disabled={discovering}
          >
            <Sparkles
              className={`h-4 w-4 mr-2 ${discovering ? "animate-pulse" : ""}`}
            />
            {discovering ? "Discovering…" : "Discover New"}
          </Button>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="rounded-md border">
          <div className="p-4 space-y-3">
            <div className="flex gap-4 pb-2 border-b">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-4 flex-1" />
              ))}
            </div>
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex gap-4">
                {Array.from({ length: 8 }).map((_, j) => (
                  <Skeleton key={j} className="h-4 flex-1" />
                ))}
              </div>
            ))}
          </div>
        </div>
      ) : itemsPage.items.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No items on your watchlist. Click Add to start watching an asset, or
          Discover New for AI suggestions.
        </p>
      ) : (
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticker</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">Target</TableHead>
                <TableHead className="text-right">% to Target</TableHead>
                <TableHead>AI Verdict</TableHead>
                <TableHead className="text-right">AI Price</TableHead>
                <TableHead>Last Scanned</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {itemsPage.items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <TickerLogo symbol={item.asset.symbol} logoUrl={item.asset.metadata_?.logo_url as string | undefined} />
                      <span className="font-medium">{item.asset.symbol}</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {item.asset.name}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    {item.current_price
                      ? <DualCurrencyAmount
                          value={formatNative(item.current_price, item.currency)}
                        />
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    {item.target_price
                      ? <DualCurrencyAmount
                          value={formatNative(item.target_price, item.currency)}
                        />
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    {item.pct_from_target !== null ? (
                      <span
                        className={
                          item.pct_from_target <= 0
                            ? "text-green-600"
                            : "text-muted-foreground"
                        }
                      >
                        {item.pct_from_target > 0 ? "+" : ""}
                        {item.pct_from_target.toFixed(1)}%
                      </span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>
                    {item.last_verdict ? (
                      <span
                        className={`text-xs font-medium px-2 py-1 rounded-full ${VERDICT_STYLE[item.last_verdict]}`}
                      >
                        {item.last_verdict}
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {item.ai_suggested_price
                      ? <DualCurrencyAmount
                          value={formatNative(item.ai_suggested_price, item.currency ?? "USD")}
                        />
                      : "—"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {item.last_scanned_at
                      ? new Date(item.last_scanned_at).toLocaleDateString("en-GB")
                      : "Never"}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Scan"
                        disabled={scanningId === item.id}
                        onClick={() => handleScanItem(item.id)}
                      >
                        <Scan
                          className={`h-4 w-4 ${scanningId === item.id ? "animate-pulse" : ""}`}
                        />
                      </Button>
                      {item.ai_suggested_price && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs h-8 px-2"
                          title="Apply AI price as target alert"
                          onClick={() => handleApplyPrice(item)}
                        >
                          Apply
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        title={
                          item.alert_enabled ? "Disable alert" : "Enable alert"
                        }
                        onClick={() => handleToggleAlert(item)}
                      >
                        {item.alert_enabled ? (
                          <Bell className="h-4 w-4 text-blue-500" />
                        ) : (
                          <BellOff className="h-4 w-4 text-muted-foreground" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Remove"
                        onClick={() => handleDelete(item.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination */}
      {itemsPage.total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {`${(itemsPage.page - 1) * itemsPage.page_size + 1}–${Math.min(
              itemsPage.page * itemsPage.page_size,
              itemsPage.total,
            )} of ${itemsPage.total}`}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setParam({ page: itemsPage.page - 1 }, false)}
              disabled={itemsPage.page <= 1}
            >
              ← Prev
            </Button>
            <span className="flex items-center px-2">
              Page {itemsPage.page} of{" "}
              {Math.max(1, Math.ceil(itemsPage.total / itemsPage.page_size))}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setParam({ page: itemsPage.page + 1 }, false)}
              disabled={
                itemsPage.page >= Math.ceil(itemsPage.total / itemsPage.page_size)
              }
            >
              Next →
            </Button>
          </div>
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-500" />
            AI Suggestions
          </h2>
          <div className="grid gap-3">
            {suggestions.map((s) => (
              <div
                key={s.id}
                className="border rounded-lg p-4 flex items-start justify-between gap-4"
              >
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{s.symbol}</span>
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${VERDICT_STYLE[s.verdict]}`}
                    >
                      {s.verdict}
                    </span>
                    {s.suggested_price && (
                      <span className="text-xs text-muted-foreground">
                        suggested ${parseFloat(s.suggested_price).toFixed(2)}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{s.reasoning}</p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleAccept(s)}
                  >
                    <Check className="h-4 w-4 mr-1" />
                    Watch
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDismiss(s.id)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <AddDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onAdded={fetchAll}
      />
    </div>
  );
}
