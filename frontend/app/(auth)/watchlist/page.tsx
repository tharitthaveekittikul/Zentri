"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  BellOff,
  Check,
  Pencil,
  Plus,
  RefreshCw,
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
import { createAsset, searchAssets, searchMarketAssets, type MarketResult } from "@/lib/services/assets";
import {
  acceptSuggestion,
  addToWatchlist,
  fetchItemPrices,
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
import { useDualCurrency, type DualValue } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { useTableParams } from "@/hooks/useTableParams";
import type { PaginatedResponse } from "@/lib/types";
import { ConfirmLLMDialog } from "@/components/llm/ConfirmLLMDialog";

const VERDICT_STYLE: Record<string, string> = {
  BUY: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  SELL: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  HOLD: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
};

function athDropColor(pct: number | null, threshold: string | null): string {
  if (pct === null) return "text-muted-foreground";
  if (threshold !== null && pct >= parseFloat(threshold)) return "text-[var(--signal-gain-text)]";
  if (pct >= 20) return "text-[var(--color-warning)]";
  if (pct >= 10) return "text-muted-foreground";
  return "text-muted-foreground";
}

function marketTypeToAssetType(typeDisplay: string, exchange: string): string {
  if (typeDisplay === "ETF") return "etf";
  if (typeDisplay === "CRYPTOCURRENCY") return "crypto";
  return "us_stock";
}

function marketCurrency(exchange: string): string {
  if (exchange === "BKK") return "THB";
  return "USD";
}

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
  const [results, setResults] = useState<MarketResult[]>([]);
  const [selected, setSelected] = useState<MarketResult | null>(null);
  const [targetPrice, setTargetPrice] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      const data = await searchMarketAssets(query);
      setResults(data);
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  const handleAdd = async () => {
    if (!selected) return;
    setAdding(true);
    try {
      const locals = await searchAssets(selected.symbol);
      const exact = locals.find((a) => a.symbol.toUpperCase() === selected.symbol.toUpperCase());
      let assetId: string | null = exact?.id ?? null;
      if (!assetId) {
        const created = await createAsset({
          symbol: selected.symbol,
          name: selected.name,
          asset_type: marketTypeToAssetType(selected.type_display, selected.exchange),
          currency: marketCurrency(selected.exchange),
        });
        assetId = created.id;
      }
      await addToWatchlist({ asset_id: assetId, target_price: targetPrice || null });
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
          <Input
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
                <Button
                  key={a.symbol}
                  variant="ghost"
                  className="w-full text-left px-3 py-2 text-sm hover:bg-accent h-auto justify-start rounded-none"
                  onClick={() => {
                    setSelected(a);
                    setQuery(a.symbol);
                    setResults([]);
                  }}
                >
                  <span className="font-medium">{a.symbol}</span>{" "}
                  <span className="text-muted-foreground">{a.name}</span>
                  {a.exchange && (
                    <span className="ml-auto text-xs text-muted-foreground">{a.exchange}</span>
                  )}
                </Button>
              ))}
            </div>
          )}
          {selected && (
            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Target price (optional)
              </label>
              <Input
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

function EditItemDialog({
  item,
  open,
  onClose,
  onSaved,
}: {
  item: WatchlistItem | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [targetPrice, setTargetPrice] = useState("");
  const [athThreshold, setAthThreshold] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (item) {
      setTargetPrice(item.target_price ?? "");
      setAthThreshold(item.ath_alert_threshold ?? "");
    }
  }, [item]);

  const handleSave = async () => {
    if (!item) return;
    setSaving(true);
    try {
      await updateWatchlistItem(item.id, {
        target_price: targetPrice || null,
        ath_alert_threshold: athThreshold || null,
      });
      toast.success("Saved");
      onSaved();
      onClose();
    } catch {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {item?.asset.symbol}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">
              Target price (optional)
            </label>
            <Input
              type="number"
              placeholder="e.g. 150.00"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">
              ATH drop alert threshold % (optional, e.g. 20 = alert when down 20% from ATH)
            </label>
            <Input
              type="number"
              placeholder="e.g. 20"
              value={athThreshold}
              onChange={(e) => setAthThreshold(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function WatchlistRow({
  item,
  formatNative,
  scanningId,
  fetchingPricesId,
  onScan,
  onFetchPrices,
  onApplyPrice,
  onToggleAlert,
  onEdit,
  onDelete,
}: {
  item: WatchlistItem;
  formatNative: (value: string | number, nativeCurrency: string) => DualValue;
  scanningId: string | null;
  fetchingPricesId: string | null;
  onScan: (id: string) => void;
  onFetchPrices: (id: string) => void;
  onApplyPrice: (item: WatchlistItem) => void;
  onToggleAlert: (item: WatchlistItem) => void;
  onEdit: (item: WatchlistItem) => void;
  onDelete: (id: string) => void;
}) {
  const prevPriceRef = useRef(item.current_price);
  const [pulsing, setPulsing] = useState(false);

  useEffect(() => {
    if (prevPriceRef.current !== item.current_price) {
      prevPriceRef.current = item.current_price;
      setPulsing(true);
      const t = setTimeout(() => setPulsing(false), 400);
      return () => clearTimeout(t);
    }
  }, [item.current_price]);

  return (
    <TableRow
      key={item.id}
      className="hover:bg-muted/50 transition-colors"
    >
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
        <span
          style={{
            display: 'inline-block',
            transition: 'transform 300ms var(--motion-spring)',
            transform: pulsing ? 'scale(1.15)' : 'scale(1)',
          }}
        >
          {item.current_price
            ? <DualCurrencyAmount
                value={formatNative(item.current_price, item.currency)}
              />
            : "—"}
        </span>
      </TableCell>
      <TableCell className="hidden md:table-cell text-right">
        {item.target_price
          ? <DualCurrencyAmount
              value={formatNative(item.target_price, item.currency)}
            />
          : "—"}
      </TableCell>
      <TableCell className="hidden md:table-cell text-right">
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
      <TableCell className="hidden md:table-cell text-right">
        {item.ath_drop_pct !== null ? (
          <span className={athDropColor(item.ath_drop_pct, item.ath_alert_threshold)}>
            -{item.ath_drop_pct.toFixed(1)}%
            {item.ath_alerted_at && (
              <Bell className="inline ml-1 h-3 w-3" />
            )}
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
      <TableCell className="hidden md:table-cell text-xs text-muted-foreground">
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
            onClick={() => onScan(item.id)}
          >
            <Scan
              className={`h-4 w-4 ${scanningId === item.id ? "animate-pulse" : ""}`}
            />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title="Fetch prices"
            disabled={fetchingPricesId === item.id}
            onClick={() => onFetchPrices(item.id)}
          >
            <RefreshCw
              className={`h-4 w-4 ${fetchingPricesId === item.id ? "animate-spin" : ""}`}
            />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title="Edit"
            onClick={() => onEdit(item)}
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title={
              item.alert_enabled ? "Disable alert" : "Enable alert"
            }
            onClick={() => onToggleAlert(item)}
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
            onClick={() => onDelete(item.id)}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
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
  const [fetchingPricesId, setFetchingPricesId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [editItem, setEditItem] = useState<WatchlistItem | null>(null);
  const [llmConfirm, setLlmConfirm] = useState<{ action: "scan" | "discover"; open: boolean }>({ action: "scan", open: false });

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
    setLlmConfirm({ action: "scan", open: false });
    setScanningAll(true);
    await scanAll();
    toast.success("Scan queued — results will appear shortly");
    setScanningAll(false);
    setTimeout(fetchAll, 5000);
  };

  const handleDiscover = async () => {
    setLlmConfirm({ action: "discover", open: false });
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

  const handleFetchPrices = async (id: string) => {
    setFetchingPricesId(id);
    try {
      await fetchItemPrices(id);
      toast.success("Prices updated");
      fetchAll();
    } catch {
      toast.error("Failed to fetch prices");
    } finally {
      setFetchingPricesId(null);
    }
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

  const handleEdit = (item: WatchlistItem) => {
    setEditItem(item);
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

      {/* Filter + actions + table card */}
      <div className="bg-card card-surface rounded-2xl overflow-hidden">
        {/* Filter + actions header */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-border">
          {/* Left: search + type + status selects */}
          <div className="flex flex-wrap items-center gap-3 flex-1">
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
                <span className="truncate">{get("asset_type") || "All Types"}</span>
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
                <span className="truncate">{get("alert_status") || "All Statuses"}</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="enabled">Enabled</SelectItem>
                <SelectItem value="triggered">Triggered</SelectItem>
                <SelectItem value="disabled">Disabled</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {/* Right: Scan All, Discover New, Add buttons */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setLlmConfirm({ action: "scan", open: true })}
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
              onClick={() => setLlmConfirm({ action: "discover", open: true })}
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

        {/* Table or skeleton */}
        {loading ? (
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
        ) : itemsPage.items.length === 0 ? (
          <p className="text-muted-foreground text-sm p-4">
            No items on your watchlist. Click Add to start watching an asset, or
            Discover New for AI suggestions.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader
                className="sticky top-0 z-10"
                style={{
                  background: 'var(--card)',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                <TableRow>
                  <TableHead>Ticker</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="hidden md:table-cell text-right">Target</TableHead>
                  <TableHead className="hidden md:table-cell text-right">% to Target</TableHead>
                  <TableHead className="hidden md:table-cell text-right">ATH Drop</TableHead>
                  <TableHead>AI Verdict</TableHead>
                  <TableHead className="hidden md:table-cell">Last Scanned</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {itemsPage.items.map((item) => (
                  <WatchlistRow
                    key={item.id}
                    item={item}
                    formatNative={formatNative}
                    scanningId={scanningId}
                    fetchingPricesId={fetchingPricesId}
                    onScan={handleScanItem}
                    onFetchPrices={handleFetchPrices}
                    onApplyPrice={handleApplyPrice}
                    onToggleAlert={handleToggleAlert}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                  />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

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
        <div className="bg-card card-surface rounded-2xl p-5 space-y-4">
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
                        suggested {parseFloat(s.suggested_price).toFixed(2)} USD
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

      <EditItemDialog
        item={editItem}
        open={editItem !== null}
        onClose={() => setEditItem(null)}
        onSaved={fetchAll}
      />

      <ConfirmLLMDialog
        open={llmConfirm.open}
        title={llmConfirm.action === "scan" ? "Scan All Watchlist Items" : "Discover New Assets"}
        description={
          llmConfirm.action === "scan"
            ? "Runs AI analysis on every item in your watchlist. Cost depends on the number of items."
            : "Uses AI to suggest new assets based on your current portfolio holdings."
        }
        estimatedCost={llmConfirm.action === "scan" ? "~$0.01 per item" : "< $0.05 est."}
        loading={llmConfirm.action === "scan" ? scanningAll : discovering}
        onConfirm={llmConfirm.action === "scan" ? handleScanAll : handleDiscover}
        onCancel={() => setLlmConfirm((p) => ({ ...p, open: false }))}
      />
    </div>
  );
}
