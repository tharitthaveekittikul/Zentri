"use client";

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

const REQUIRED_FIELDS = ["trade_date", "type", "symbol", "unit"] as const;
const VISIBLE_FIELDS = [
  "trade_date",
  "type",
  "symbol",
  "unit",
  "price",
  "currency",
  "asset_type",
  "platform",
  "fee",
  "notes",
] as const;

interface Props {
  rows: CanonicalRow[];
  onChange: (rows: CanonicalRow[]) => void;
}

export function ReviewTable({ rows, onChange }: Props) {
  function handleChange(rowIdx: number, field: string, value: string) {
    const updated = rows.map((r, i) =>
      i === rowIdx ? { ...r, [field]: value || null } : r
    );
    onChange(updated);
  }

  function isMissing(row: CanonicalRow, field: string): boolean {
    return (REQUIRED_FIELDS as readonly string[]).includes(field) && !row[field];
  }

  return (
    <div className="overflow-auto max-h-[60vh] rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            {VISIBLE_FIELDS.map((f) => (
              <TableHead key={f} className="whitespace-nowrap text-xs">
                {f}
                {(REQUIRED_FIELDS as readonly string[]).includes(f) ? " *" : ""}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
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
