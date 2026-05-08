"use client";

import { useEffect, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
import { Pencil, Search, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { TickerLogo } from "@/components/ui/TickerLogo";
import { PageHeader } from "@/components/layout/PageHeader";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { useTableParams } from "@/hooks/useTableParams";
import { api } from "@/lib/api";
import {
  fetchTransactions,
  type TransactionRow,
  type TransactionParams,
} from "@/lib/services/portfolio";
import type { PaginatedResponse } from "@/lib/types";
import { DateRangePicker } from "@/components/ui/date-range-picker";

const TYPE_COLORS: Record<string, string> = {
  buy: "bg-green-100 text-green-800",
  sell: "bg-red-100 text-red-800",
  dividend: "bg-blue-100 text-blue-800",
  reward: "bg-purple-100 text-purple-800",
  fee: "bg-yellow-100 text-yellow-800",
  transfer: "bg-gray-100 text-gray-800",
};

export default function TransactionsPage() {
  const { formatNative } = useDualCurrency();
  const { get, getInt, setParam } = useTableParams();

  const [data, setData] = useState<PaginatedResponse<TransactionRow>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 25,
  });
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [editTarget, setEditTarget] = useState<TransactionRow | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TransactionRow | null>(null);
  const [editForm, setEditForm] = useState<Partial<TransactionRow>>({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [searchInput, setSearchInput] = useState(get("search"));

  // Build params from URL
  const params: TransactionParams = {
    search: get("search") || undefined,
    type: get("type") || undefined,
    platform: get("platform") || undefined,
    date_from: get("date_from") || undefined,
    date_to: get("date_to") || undefined,
    page: getInt("page", 1),
    page_size: getInt("page_size", 25),
  };

  // Fetch when URL params change
  useEffect(() => {
    setFetching(true);
    fetchTransactions(params)
      .then(setData)
      .finally(() => {
        setLoading(false);
        setFetching(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    get("search"),
    get("type"),
    get("platform"),
    get("date_from"),
    get("date_to"),
    getInt("page", 1),
    getInt("page_size", 25),
  ]);

  // Sync local search input from URL (e.g. browser back)
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

  const reload = () => {
    setFetching(true);
    fetchTransactions(params)
      .then(setData)
      .finally(() => setFetching(false));
  };

  const openEdit = (tx: TransactionRow) => {
    setEditTarget(tx);
    setEditForm({
      type: tx.type,
      quantity: tx.quantity,
      price: tx.price,
      fee: tx.fee,
      executed_at: tx.executed_at.slice(0, 16),
      platform: tx.platform ?? "",
    });
  };

  const saveEdit = async () => {
    if (!editTarget) return;
    setSaving(true);
    const res = await api.patch(
      `/api/v1/portfolio/transactions/${editTarget.id}`,
      {
        type: editForm.type,
        quantity: editForm.quantity ? parseFloat(editForm.quantity) : undefined,
        price: editForm.price ? parseFloat(editForm.price) : undefined,
        fee: editForm.fee ? parseFloat(editForm.fee) : undefined,
        executed_at: editForm.executed_at
          ? new Date(editForm.executed_at).toISOString()
          : undefined,
        platform: editForm.platform || null,
      },
    );
    setSaving(false);
    if (res.ok) {
      setEditTarget(null);
      reload();
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    await api.delete(`/api/v1/portfolio/transactions/${deleteTarget.id}`);
    setDeleting(false);
    setDeleteTarget(null);
    reload();
  };

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  // Derive unique platforms from current page for the platform dropdown
  const platforms = Array.from(
    new Set(data.items.map((t) => t.platform).filter(Boolean) as string[]),
  );

  return (
    <div className="space-y-4">
      <PageHeader title="Transactions" />

      {/* Filter + Table card */}
      <div className="bg-card card-surface rounded-2xl overflow-hidden">
        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-3 p-4 border-b border-border">
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
            value={get("type") || "all"}
            onValueChange={(v) => setParam({ type: v === "all" ? null : v })}
          >
            <SelectTrigger className="h-9 w-[140px]">
              <span className="truncate">{get("type") || "All Types"}</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {["buy", "sell", "dividend", "reward", "fee", "transfer"].map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={get("platform") || "all"}
            onValueChange={(v) => setParam({ platform: v === "all" ? null : v })}
          >
            <SelectTrigger className="h-9 w-[140px]">
              <span className="truncate">{get("platform") || "All Platforms"}</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Platforms</SelectItem>
              {platforms.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <DateRangePicker
            from={get("date_from")}
            to={get("date_to")}
            onChange={({ from, to }) => setParam({ date_from: from, date_to: to })}
          />
        </div>

        {/* Table or skeleton */}
        {loading ? (
          <div className="p-4 space-y-3">
            <div className="flex gap-4 pb-2 border-b">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-4 flex-1" />
              ))}
            </div>
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="flex gap-4">
                {Array.from({ length: 8 }).map((_, j) => (
                  <Skeleton key={j} className="h-4 flex-1" />
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div
            className={`overflow-x-auto transition-opacity ${
              fetching ? "opacity-60" : ""
            }`}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Asset</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Quantity</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">Fee</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={8}
                      className="text-center text-muted-foreground py-8"
                    >
                      No transactions found
                    </TableCell>
                  </TableRow>
                )}
                {data.items.map((tx) => (
                  <TableRow key={tx.id}>
                    <TableCell className="text-sm">
                      {new Date(tx.executed_at).toLocaleDateString("en-GB")}
                    </TableCell>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <TickerLogo symbol={tx.symbol} logoUrl={tx.metadata_?.logo_url as string | undefined} />
                        <span>{tx.symbol}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          TYPE_COLORS[tx.type] ?? "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {tx.type}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {parseFloat(tx.quantity).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <DualCurrencyAmount
                        value={formatNative(tx.price, tx.currency ?? "USD")}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <DualCurrencyAmount
                        value={formatNative(tx.fee, tx.currency ?? "USD")}
                      />
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {tx.platform ?? "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(tx)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteTarget(tx)}
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
      </div>

      {/* Pagination */}
      {!loading && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {data.total > 0
              ? `${(data.page - 1) * data.page_size + 1}–${Math.min(
                  data.page * data.page_size,
                  data.total,
                )} of ${data.total}`
              : "0 results"}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setParam({ page: data.page - 1 }, false)}
              disabled={data.page <= 1}
            >
              ← Prev
            </Button>
            <span className="flex items-center px-2">
              Page {data.page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setParam({ page: data.page + 1 }, false)}
              disabled={data.page >= totalPages}
            >
              Next →
            </Button>
          </div>
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog
        open={!!editTarget}
        onOpenChange={(open) => !open && setEditTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Transaction — {editTarget?.symbol}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label>Type</Label>
              <Select
                value={editForm.type}
                onValueChange={(v) =>
                  setEditForm((f) => ({ ...f, type: v }) as Partial<TransactionRow>)
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["buy", "sell", "dividend", "reward", "fee", "transfer"].map(
                    (t) => (
                      <SelectItem key={t} value={t}>
                        {t}
                      </SelectItem>
                    )
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Quantity</Label>
                <Input
                  value={editForm.quantity ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, quantity: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>Price</Label>
                <Input
                  value={editForm.price ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, price: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>Fee</Label>
                <Input
                  value={editForm.fee ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, fee: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>Platform</Label>
                <Input
                  value={editForm.platform ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, platform: e.target.value }))
                  }
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label>Executed At</Label>
              <Input
                type="datetime-local"
                value={editForm.executed_at ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, executed_at: e.target.value }))
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTarget(null)}>
              Cancel
            </Button>
            <Button onClick={saveEdit} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete transaction?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This will permanently delete the{" "}
            <strong>{deleteTarget?.type}</strong> transaction for{" "}
            <strong>{deleteTarget?.symbol}</strong>. This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleting}
            >
              {deleting ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
