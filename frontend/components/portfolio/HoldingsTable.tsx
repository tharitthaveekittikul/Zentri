"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Trash2,
  Pencil,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ArrowUpRight,
  ArrowDownRight,
  Search,
  AlertTriangle,
} from "lucide-react";
import { HoldingRow } from "@/lib/services/portfolio";
import { PaginatedResponse } from "@/lib/types";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
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
import { TickerLogo } from "@/components/ui/TickerLogo";

interface TableParams {
  search: string;
  platform: string;
  asset_type: string;
  page: number;
  page_size: number;
}

interface Props {
  data: PaginatedResponse<HoldingRow>;
  params: TableParams;
  onParamChange: (
    updates: Record<string, string | number | null>,
    resetPage?: boolean,
  ) => void;
  onDelete: (id: string) => void;
  onUpdated: () => void;
  isFetching?: boolean;
  platformColors?: Record<string, string>;
}

const secondaryCls =
  "text-xs text-muted-foreground font-mono tabular-nums mt-0.5";

const ASSET_TYPES = [
  "us_stock",
  "thai_stock",
  "crypto",
  "etf",
  "bond",
  "th_fund",
];

export function HoldingsTable({
  data,
  params,
  onParamChange,
  onDelete,
  onUpdated,
  isFetching = false,
  platformColors = {},
}: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [searchInput, setSearchInput] = useState(params.search);
  const [editHolding, setEditHolding] = useState<HoldingRow | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<HoldingRow | null>(null);

  const { formatNative } = useDualCurrency();

  // Sync local search input from URL changes (e.g. browser back/forward)
  useEffect(() => {
    setSearchInput(params.search);
  }, [params.search]);

  // Debounce search input → URL (300ms)
  useEffect(() => {
    const t = setTimeout(() => {
      if (searchInput !== params.search) {
        onParamChange({ search: searchInput || null });
      }
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]); // eslint-disable-line react-hooks/exhaustive-deps

  // Derive unique platforms from current page for the platform dropdown
  const platforms = useMemo(
    () =>
      Array.from(
        new Set(data.items.map((h) => h.platform).filter(Boolean) as string[]),
      ).sort(),
    [data.items],
  );

  function contrastColor(hex: string): string {
    if (!/^#[0-9a-fA-F]{6}$/.test(hex)) return "#000000";
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const lin = (c: number) => {
      const s = c / 255;
      return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    return L > 0.179 ? "#000000" : "#ffffff";
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
        <Button
          variant="ghost"
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide p-0 h-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Symbol <SortIcon isSorted={column.getIsSorted()} />
        </Button>
      ),
      cell: ({ row }) => {
        const platform = row.original.platform;
        const bgColor = platform ? platformColors[platform] : undefined;
        return (
          <Link
            href={`/portfolio/${encodeURIComponent(row.original.symbol)}`}
            className="hover:underline"
            prefetch={false}
          >
            <div className="flex items-center gap-2 flex-wrap">
              <TickerLogo
                symbol={row.original.symbol}
                logoUrl={row.original.metadata_?.logo_url as string | undefined}
              />
              <span>{row.original.symbol}</span>
              {row.original.asset_type === "th_fund" &&
                !row.original.metadata_?.proj_id && (
                  <span title="SEC Project ID missing — NAV price won't update">
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                  </span>
                )}
              {platform && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium max-w-[96px] truncate ${
                    bgColor ? "" : "bg-muted text-muted-foreground"
                  }`}
                  style={
                    bgColor
                      ? {
                          backgroundColor: bgColor,
                          color: contrastColor(bgColor),
                        }
                      : undefined
                  }
                >
                  {platform}
                </span>
              )}
            </div>
          </Link>
        );
      },
    },
    {
      accessorKey: "outstanding_shares",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <Button
          variant="ghost"
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide p-0 h-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Shares <SortIcon isSorted={column.getIsSorted()} />
        </Button>
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
        <Button
          variant="ghost"
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide p-0 h-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Cost/Share <SortIcon isSorted={column.getIsSorted()} />
        </Button>
      ),
      cell: ({ row }) =>
        row.original.cost_per_share == null ? (
          <span>—</span>
        ) : (
          <DualCurrencyAmount
            value={formatNative(
              row.original.cost_per_share,
              row.original.currency,
            )}
            secondaryClassName={secondaryCls}
          />
        ),
    },
    {
      accessorKey: "total_cost",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <Button
          variant="ghost"
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide p-0 h-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Total Cost <SortIcon isSorted={column.getIsSorted()} />
        </Button>
      ),
      cell: ({ row }) =>
        row.original.total_cost == null ? (
          <span>—</span>
        ) : (
          <DualCurrencyAmount
            value={formatNative(row.original.total_cost, row.original.currency)}
            secondaryClassName={secondaryCls}
          />
        ),
    },
    {
      accessorKey: "current_price",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <Button
          variant="ghost"
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide p-0 h-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Price <SortIcon isSorted={column.getIsSorted()} />
        </Button>
      ),
      cell: ({ row }) =>
        row.original.current_price == null ? (
          <span>—</span>
        ) : (
          <DualCurrencyAmount
            value={formatNative(
              row.original.current_price,
              row.original.currency,
            )}
            secondaryClassName={secondaryCls}
          />
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
          <span
            className={`${color} font-mono tabular-nums inline-flex items-center gap-0.5`}
          >
            {num >= 0 ? (
              <ArrowUpRight className="h-3 w-3" strokeWidth={2.5} />
            ) : (
              <ArrowDownRight className="h-3 w-3" strokeWidth={2.5} />
            )}
            {Math.abs(num).toFixed(2)}%
          </span>
        );
      },
    },
    {
      accessorKey: "holding_value",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <Button
          variant="ghost"
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide p-0 h-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Value <SortIcon isSorted={column.getIsSorted()} />
        </Button>
      ),
      cell: ({ row }) =>
        row.original.holding_value == null ? (
          <span>—</span>
        ) : (
          <DualCurrencyAmount
            value={formatNative(
              row.original.holding_value,
              row.original.currency,
            )}
            secondaryClassName={secondaryCls}
          />
        ),
    },
    {
      accessorKey: "unrealized_pnl",
      sortingFn: "alphanumeric",
      header: ({ column }) => (
        <Button
          variant="ghost"
          className="flex items-center text-xs font-medium text-muted-foreground uppercase tracking-wide p-0 h-auto"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          P/L <SortIcon isSorted={column.getIsSorted()} />
        </Button>
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
        const totalCost = Number(row.original.total_cost);
        const pct = totalCost !== 0 ? (num / totalCost) * 100 : null;
        const color =
          num >= 0
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-destructive";
        return (
          <div className={color}>
            <DualCurrencyAmount
              value={formatNative(val, row.original.currency, 2, true)}
              primaryClassName={`font-mono tabular-nums ${color}`}
              secondaryClassName={`${secondaryCls} ${color} opacity-75`}
            />
            {pct != null && (
              <span className="flex items-center gap-0.5 text-xs opacity-75">
                {pct >= 0 ? (
                  <ArrowUpRight className="h-3 w-3" strokeWidth={2.5} />
                ) : (
                  <ArrowDownRight className="h-3 w-3" strokeWidth={2.5} />
                )}
                {Math.abs(pct).toFixed(2)}%
              </span>
            )}
          </div>
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
    data: data.items,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="space-y-3">
      {/* Filter + Table card */}
      <div className="bg-card card-surface rounded-2xl overflow-hidden">
        {/* Filter row */}
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
            value={params.platform || "all"}
            onValueChange={(v) =>
              onParamChange({ platform: v === "all" ? null : v })
            }
          >
            <SelectTrigger className="h-9 w-[160px]">
              <span className="truncate">
                {params.platform || "All Platforms"}
              </span>
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
          <Select
            value={params.asset_type || "all"}
            onValueChange={(v) =>
              onParamChange({ asset_type: v === "all" ? null : v })
            }
          >
            <SelectTrigger className="h-9 w-[160px]">
              <span className="truncate">
                {params.asset_type || "All Types"}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {ASSET_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Rows:</span>
            <Select
              value={String(params.page_size)}
              onValueChange={(v) =>
                onParamChange({ page_size: Number(v), page: 1 }, false)
              }
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
        <div
          className={`overflow-x-auto transition-opacity ${isFetching ? "opacity-60" : ""}`}
        >
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
                      <span className="text-sm font-medium">
                        No holdings found
                      </span>
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
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {data.total > 0
            ? `${(params.page - 1) * params.page_size + 1}–${Math.min(params.page * params.page_size, data.total)} of ${data.total}`
            : "0 results"}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onParamChange({ page: params.page - 1 }, false)}
            disabled={params.page <= 1}
          >
            ← Prev
          </Button>
          <span className="flex items-center px-2">
            Page {params.page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onParamChange({ page: params.page + 1 }, false)}
            disabled={params.page >= totalPages}
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
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
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
