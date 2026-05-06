"use client";

import { useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Trash2, Pencil, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { HoldingRow } from "@/lib/services/portfolio";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { EditHoldingDialog } from "./EditHoldingDialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface Props {
  holdings: HoldingRow[];
  primaryCurrency: string;
  secondaryCurrency?: string;
  primaryToSecondaryRate?: number;
  onDelete: (id: string) => void;
  onUpdated: () => void;
}

export function HoldingsTable({
  holdings,
  primaryCurrency,
  secondaryCurrency,
  primaryToSecondaryRate,
  onDelete,
  onUpdated,
}: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [platformFilter, setPlatformFilter] = useState<string>("all");
  const [pageSize, setPageSize] = useState(25);
  const [pageIndex, setPageIndex] = useState(0);
  const [editHolding, setEditHolding] = useState<HoldingRow | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<HoldingRow | null>(null);

  // Filter out cash assets and zero-share positions
  const nonCashHoldings = useMemo(
    () => holdings.filter((h) => h.asset_type !== "cash" && Number(h.outstanding_shares) >= 1e-6),
    [holdings],
  );

  // Unique non-null platforms for dropdown
  const platforms = useMemo(() => {
    const seen = new Set<string>();
    for (const h of nonCashHoldings) {
      if (h.platform) seen.add(h.platform);
    }
    return Array.from(seen).sort();
  }, [nonCashHoldings]);

  // Apply platform filter
  const filteredHoldings = useMemo(() => {
    if (platformFilter === "all") return nonCashHoldings;
    return nonCashHoldings.filter((h) => h.platform === platformFilter);
  }, [nonCashHoldings, platformFilter]);

  function fmt(
    val: string | number | null | undefined,
    currency: string,
  ): string {
    if (val == null) return "—";
    return `${Number(val).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })} ${currency}`;
  }

  function MoneyCell({
    val,
    nativeCurrency,
  }: {
    val: string | null | undefined;
    nativeCurrency: string;
  }) {
    if (val == null) return <span>—</span>;
    const num = Number(val);
    const native = nativeCurrency.toUpperCase();
    const primary = primaryCurrency.toUpperCase();
    const secondary = secondaryCurrency?.toUpperCase();

    let primaryVal: number = num;
    let secondaryVal: number | null = null;

    if (native === primary) {
      primaryVal = num;
      if (primaryToSecondaryRate != null && secondaryCurrency) {
        secondaryVal = num * primaryToSecondaryRate;
      }
    } else if (
      native === secondary &&
      primaryToSecondaryRate != null &&
      primaryToSecondaryRate > 0
    ) {
      primaryVal = num / primaryToSecondaryRate;
      secondaryVal = num;
    } else {
      return <span>{fmt(num, nativeCurrency)}</span>;
    }

    return (
      <span>
        {fmt(primaryVal, primaryCurrency)}
        {secondaryCurrency && secondaryVal != null && (
          <span className="block text-xs text-muted-foreground">
            ≈ {fmt(secondaryVal, secondaryCurrency)}
          </span>
        )}
      </span>
    );
  }

  function SortIcon({ isSorted }: { isSorted: false | "asc" | "desc" }) {
    if (!isSorted)
      return <ArrowUpDown className="ml-1 h-3 w-3 inline opacity-40" />;
    if (isSorted === "asc") return <ArrowUp className="ml-1 h-3 w-3 inline" />;
    return <ArrowDown className="ml-1 h-3 w-3 inline" />;
  }

  const columns: ColumnDef<HoldingRow>[] = [
    {
      accessorKey: "symbol",
      header: ({ column }) => (
        <button
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Symbol <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
    },
    {
      accessorKey: "outstanding_shares",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <button
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Shares <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <span className="font-mono tabular-nums">
          {Number(row.original.outstanding_shares).toLocaleString()}
        </span>
      ),
    },
    {
      accessorKey: "cost_per_share",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <button
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Cost/Share <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <span className="font-mono tabular-nums">
          <PrivacyValue
            value={
              <MoneyCell
                val={row.original.cost_per_share}
                nativeCurrency={row.original.currency}
              />
            }
          />
        </span>
      ),
    },
    {
      accessorKey: "total_cost",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <button
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Total Cost <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <span className="font-mono tabular-nums">
          <PrivacyValue
            value={
              <MoneyCell
                val={row.original.total_cost}
                nativeCurrency={row.original.currency}
              />
            }
          />
        </span>
      ),
    },
    {
      accessorKey: "current_price",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <button
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Price <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <span className="font-mono tabular-nums">
          <PrivacyValue
            value={
              <MoneyCell
                val={row.original.current_price}
                nativeCurrency={row.original.currency}
              />
            }
          />
        </span>
      ),
    },
    {
      accessorKey: "price_1d_change",
      header: () => (
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          1D Change
        </span>
      ),
      cell: ({ row }) => {
        const val = row.original.price_1d_change;
        if (val == null)
          return (
            <span className="font-mono tabular-nums text-muted-foreground">
              —
            </span>
          );
        const num = Number(val);
        const color =
          num >= 0
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-destructive";
        return (
          <span className={`${color} font-mono tabular-nums`}>
            {num >= 0 ? "+" : ""}
            {num.toFixed(2)}%
          </span>
        );
      },
    },
    {
      accessorKey: "holding_value",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <button
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Value <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <span className="font-mono tabular-nums">
          <PrivacyValue
            value={
              <MoneyCell
                val={row.original.holding_value}
                nativeCurrency={row.original.currency}
              />
            }
          />
        </span>
      ),
    },
    {
      accessorKey: "unrealized_pnl",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <button
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          P/L <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => {
        const val = row.original.unrealized_pnl;
        if (val == null)
          return (
            <span className="font-mono tabular-nums text-muted-foreground">
              —
            </span>
          );
        const num = Number(val);
        const color =
          num >= 0
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-destructive";
        return (
          <span className={`${color} font-mono tabular-nums`}>
            <PrivacyValue
              value={
                <MoneyCell val={val} nativeCurrency={row.original.currency} />
              }
            />
          </span>
        );
      },
    },
    {
      id: "actions",
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              setEditHolding(row.original);
              setEditOpen(true);
            }}
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setDeleteTarget(row.original)}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      ),
    },
  ];

  const table = useReactTable({
    data: filteredHoldings,
    columns,
    state: { sorting, pagination: { pageIndex, pageSize } },
    onSortingChange: setSorting,
    onPaginationChange: (updater) => {
      const next =
        typeof updater === "function"
          ? updater({ pageIndex, pageSize })
          : updater;
      setPageIndex(next.pageIndex);
      setPageSize(next.pageSize);
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    manualPagination: false,
  });

  return (
    <div className="space-y-2">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Platform:</span>
          <Select
            value={platformFilter}
            onValueChange={(v) => {
              if (v !== null) {
                setPlatformFilter(v);
                setPageIndex(0);
              }
            }}
          >
            <SelectTrigger className="h-8 w-[180px]">
              <SelectValue />
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
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Rows:</span>
          <Select
            value={String(pageSize)}
            onValueChange={(v) => {
              if (v !== null) {
                setPageSize(Number(v));
                setPageIndex(0);
              }
            }}
          >
            <SelectTrigger className="h-8 w-[80px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[25, 50, 100].map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-card card-surface rounded-2xl border border-border overflow-x-auto">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => (
                  <TableHead key={h.id}>
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length > 0 ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="hover:bg-muted/40 transition-colors duration-150"
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-12">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <span className="text-2xl">📋</span>
                    <span className="text-sm font-medium">No holdings yet</span>
                    <span className="text-xs">
                      Add one above or import from the Import page.
                    </span>
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Page {table.getState().pagination.pageIndex + 1} of{" "}
          {Math.max(1, table.getPageCount())}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            ← Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next →
          </Button>
        </div>
      </div>

      <EditHoldingDialog
        holding={editHolding}
        open={editOpen}
        onOpenChange={setEditOpen}
        onUpdated={onUpdated}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete holding?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove{" "}
              <span className="font-semibold">{deleteTarget?.symbol}</span> from
              your portfolio. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget) {
                  onDelete(deleteTarget.id);
                  setDeleteTarget(null);
                }
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
