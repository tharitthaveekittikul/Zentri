"use client";

import { useState } from "react";
import { CanonicalRow } from "@/lib/services/import-pipeline";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const REQUIRED_FIELDS = ["trade_date", "type", "symbol", "unit", "price"] as const;
const BULK_APPLY_FIELDS = ["type", "exchange", "platform"] as const;
const VISIBLE_FIELDS = [
  "trade_date",
  "type",
  "symbol",
  "unit",
  "price",
  "currency",
  "exchange",
  "gross_amount",
  "fee",
  "gross_thb",
  "fee_thb",
  "exchange_rate",
  "asset_type",
  "platform",
  "notes",
] as const;

interface Props {
  rows: CanonicalRow[];
  onChange: (rows: CanonicalRow[]) => void;
}

export function ReviewTable({ rows, onChange }: Props) {
  const [bulkValues, setBulkValues] = useState<Record<string, string>>({});

  function handleChange(rowIdx: number, field: string, value: string) {
    const updated = rows.map((r, i) =>
      i === rowIdx ? { ...r, [field]: value || null } : r
    );
    onChange(updated);
  }

  function applyBulk(field: string) {
    const value = bulkValues[field]?.trim();
    if (!value) return;
    onChange(rows.map((r) => ({ ...r, [field]: value })));
  }

  function isMissing(row: CanonicalRow, field: string): boolean {
    return (REQUIRED_FIELDS as readonly string[]).includes(field) && !row[field];
  }

  return (
    <div className="overflow-auto max-h-[60vh] rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[50px] text-center text-xs">#</TableHead>
            {VISIBLE_FIELDS.map((f) => (
              <TableHead key={f} className="whitespace-nowrap text-xs">
                {f}
                {(REQUIRED_FIELDS as readonly string[]).includes(f) ? " *" : ""}
              </TableHead>
            ))}
          </TableRow>
          <TableRow className="bg-muted/30 hover:bg-muted/30">
            <TableHead className="text-center text-xs text-muted-foreground py-1">apply all</TableHead>
            {VISIBLE_FIELDS.map((f) => (
              <TableHead key={f} className="p-1">
                {(BULK_APPLY_FIELDS as readonly string[]).includes(f) ? (
                  <Input
                    className="h-6 text-xs min-w-[80px]"
                    placeholder="apply all…"
                    value={bulkValues[f] ?? ""}
                    onChange={(e) =>
                      setBulkValues((prev) => ({ ...prev, [f]: e.target.value }))
                    }
                    onBlur={() => applyBulk(f)}
                    onKeyDown={(e) => { if (e.key === "Enter") applyBulk(f); }}
                  />
                ) : null}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
              <TableCell className="text-center text-xs text-muted-foreground">
                {i + 1}
              </TableCell>
              {VISIBLE_FIELDS.map((f) => (
                <TableCell key={f} className="p-1">
                  <Input
                    className={`h-7 text-xs min-w-[80px] ${
                      isMissing(row, f) ? "border-destructive" : ""
                    }`}
                    value={(row[f] as string) ?? ""}
                    onChange={(e) => handleChange(i, f, e.target.value)}
                  />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
