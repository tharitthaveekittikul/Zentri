"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
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
import { Pencil, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";

type TransactionRow = {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  platform: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  created_at: string;
};

const TYPE_COLORS: Record<string, string> = {
  buy: "bg-green-100 text-green-800",
  sell: "bg-red-100 text-red-800",
  dividend: "bg-blue-100 text-blue-800",
  reward: "bg-purple-100 text-purple-800",
  fee: "bg-yellow-100 text-yellow-800",
  transfer: "bg-gray-100 text-gray-800",
};

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [editTarget, setEditTarget] = useState<TransactionRow | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TransactionRow | null>(null);
  const [editForm, setEditForm] = useState<Partial<TransactionRow>>({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const fetchTransactions = async () => {
    setLoading(true);
    const res = await api.get("/api/v1/portfolio/transactions");
    if (res.ok) setTransactions(await res.json());
    setLoading(false);
  };

  useEffect(() => {
    fetchTransactions();
  }, []);

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
      }
    );
    setSaving(false);
    if (res.ok) {
      setEditTarget(null);
      fetchTransactions();
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    await api.delete(`/api/v1/portfolio/transactions/${deleteTarget.id}`);
    setDeleting(false);
    setDeleteTarget(null);
    fetchTransactions();
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Transactions" />

      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <div className="rounded-md border overflow-x-auto">
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
              {transactions.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="text-center text-muted-foreground py-8"
                  >
                    No transactions yet
                  </TableCell>
                </TableRow>
              )}
              {transactions.map((tx) => (
                <TableRow key={tx.id}>
                  <TableCell className="text-sm">
                    {new Date(tx.executed_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="font-medium">{tx.symbol}</TableCell>
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
                    {parseFloat(tx.price).toFixed(2)}
                  </TableCell>
                  <TableCell className="text-right">
                    {parseFloat(tx.fee).toFixed(2)}
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
