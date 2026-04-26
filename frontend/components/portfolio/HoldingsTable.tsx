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
import { Holding } from "@/lib/services/portfolio";
import { PrivacyValue } from "@/components/ui/PrivacyValue";

interface Props {
  holdings: Holding[];
  assetMap: Record<string, string>;
  onDelete: (id: string) => void;
}

export function HoldingsTable({ holdings, assetMap, onDelete }: Props) {
  const columns: ColumnDef<Holding>[] = [
    {
      accessorKey: "asset_id",
      header: "Symbol",
      cell: ({ row }) =>
        assetMap[row.original.asset_id] ?? row.original.asset_id.slice(0, 8),
    },
    {
      accessorKey: "quantity",
      header: "Quantity",
      cell: ({ row }) => row.original.quantity,
    },
    {
      accessorKey: "avg_cost_price",
      header: "Avg Cost",
      cell: ({ row }) => (
        <PrivacyValue
          value={`${row.original.currency} ${row.original.avg_cost_price}`}
        />
      ),
    },
    {
      accessorKey: "updated_at",
      header: "Updated",
      cell: ({ row }) =>
        new Date(row.original.updated_at).toLocaleDateString(),
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
                No holdings yet. Add one or import from CSV.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
