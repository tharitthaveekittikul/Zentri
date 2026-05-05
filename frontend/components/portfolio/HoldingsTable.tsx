"use client";

import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
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
import { Trash2 } from "lucide-react";
import { HoldingRow } from "@/lib/services/portfolio";
import { PrivacyValue } from "@/components/ui/PrivacyValue";

interface Props {
  holdings: HoldingRow[];
  primaryCurrency: string;
  onDelete: (id: string) => void;
}

export function HoldingsTable({ holdings, primaryCurrency, onDelete }: Props) {
  function fmtMoney(val: string | null | undefined): string {
    if (val == null) return "—";
    return `${primaryCurrency} ${Number(val).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  const columns: ColumnDef<HoldingRow>[] = [
    {
      accessorKey: "symbol",
      header: "Symbol / Fund Code",
    },
    {
      accessorKey: "outstanding_shares",
      header: "Outstanding Shares",
      cell: ({ row }) =>
        Number(row.original.outstanding_shares).toLocaleString(),
    },
    {
      accessorKey: "cost_per_share",
      header: "Cost per Share",
      cell: ({ row }) => (
        <PrivacyValue value={fmtMoney(row.original.cost_per_share)} />
      ),
    },
    {
      accessorKey: "total_cost",
      header: "Total Cost",
      cell: ({ row }) => (
        <PrivacyValue value={fmtMoney(row.original.total_cost)} />
      ),
    },
    {
      accessorKey: "current_price",
      header: "Current Price",
      cell: ({ row }) =>
        row.original.current_price ? (
          <PrivacyValue value={fmtMoney(row.original.current_price)} />
        ) : (
          "—"
        ),
    },
    {
      accessorKey: "price_1d_change",
      header: "1D Change",
      cell: ({ row }) => {
        const val = row.original.price_1d_change;
        if (val == null) return "—";
        const num = Number(val);
        const color = num >= 0 ? "text-green-600" : "text-red-600";
        return (
          <span className={color}>
            {num >= 0 ? "+" : ""}
            {num.toFixed(2)}%
          </span>
        );
      },
    },
    {
      accessorKey: "holding_value",
      header: "Holding Value",
      cell: ({ row }) =>
        row.original.holding_value ? (
          <PrivacyValue value={fmtMoney(row.original.holding_value)} />
        ) : (
          "—"
        ),
    },
    {
      accessorKey: "unrealized_pnl",
      header: "Unrealized P/L",
      cell: ({ row }) => {
        const val = row.original.unrealized_pnl;
        if (val == null) return "—";
        const num = Number(val);
        const color = num >= 0 ? "text-green-600" : "text-red-600";
        return (
          <span className={color}>
            <PrivacyValue value={fmtMoney(val)} />
          </span>
        );
      },
    },
    {
      id: "actions",
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onDelete(row.original.id)}
        >
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      ),
    },
  ];

  const table = useReactTable({
    data: holdings,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="rounded-md border">
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
          {table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                className="text-center text-muted-foreground py-8"
              >
                No holdings. Add one or import from the Import page.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
