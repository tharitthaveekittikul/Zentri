"use client";

import { useState, useRef } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { previewImport, confirmImport } from "@/lib/services/portfolio";
import { Upload } from "lucide-react";

const ASSET_TYPES = ["us_stock", "thai_stock", "th_fund", "crypto", "gold"];

interface Props {
  onImported: () => void;
}

export function ImportDrawer({ onImported }: Props) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<"upload" | "preview">("upload");
  const [assetType, setAssetType] = useState("us_stock");
  const [preview, setPreview] = useState<{
    columns: string[];
    rows: Record<string, string>[];
  } | null>(null);
  const [mappedRows, setMappedRows] = useState<
    Array<{
      date: string;
      symbol: string;
      type: string;
      quantity: string;
      price: string;
      fee: string;
    }>
  >([]);
  const [loading, setLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function colMap(name: string): string | null {
    const n = name.toLowerCase();
    if (n.includes("date") || n.includes("time")) return "date";
    if (n.includes("symbol") || n.includes("ticker")) return "symbol";
    if (n.includes("action") || n.includes("type") || n.includes("side"))
      return "type";
    if (n.includes("qty") || n.includes("quantity") || n.includes("shares"))
      return "quantity";
    if (n.includes("price") || n.includes("unit")) return "price";
    if (n.includes("fee") || n.includes("commission")) return "fee";
    return null;
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const data = await previewImport(file);
      setPreview(data);
      const mapped = data.rows.map((row) => {
        const out: Record<string, string> = {};
        for (const [col, val] of Object.entries(row)) {
          const field = colMap(col);
          if (field) out[field] = val;
        }
        if (!out.type) out.type = "buy";
        if (!out.fee) out.fee = "0";
        return out as {
          date: string;
          symbol: string;
          type: string;
          quantity: string;
          price: string;
          fee: string;
        };
      });
      setMappedRows(mapped);
      setStep("preview");
    } catch {
      toast.error("Could not parse CSV");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    setLoading(true);
    try {
      const result = await confirmImport({
        rows: mappedRows,
        asset_type: assetType,
        save_profile: false,
        broker_name: null,
      });
      toast.success(
        `Imported ${result.imported} transactions. Skipped: ${result.skipped}`
      );
      setOpen(false);
      setStep("upload");
      setPreview(null);
      onImported();
    } catch {
      toast.error("Import failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger render={<Button variant="outline" size="sm"><Upload className="h-4 w-4 mr-1" />Import CSV</Button>} />
      <SheetContent className="w-[480px]">
        <SheetHeader>
          <SheetTitle>Import from CSV</SheetTitle>
        </SheetHeader>

        {step === "upload" && (
          <div className="space-y-4 mt-4">
            <div className="space-y-1">
              <Label>Asset Type</Label>
              <Select value={assetType} onValueChange={(v) => { if (v !== null) setAssetType(v); }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ASSET_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div
              className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:bg-muted/50"
              onClick={() => fileRef.current?.click()}
            >
              <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Click to upload CSV
              </p>
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>
          </div>
        )}

        {step === "preview" && preview && (
          <div className="space-y-4 mt-4">
            <p className="text-sm text-muted-foreground">
              Found {mappedRows.length} row(s). Columns:{" "}
              {preview.columns.join(", ")}
            </p>
            <div className="border rounded overflow-auto max-h-48 text-xs">
              <table className="w-full">
                <thead className="bg-muted">
                  <tr>
                    {["date", "symbol", "type", "quantity", "price", "fee"].map(
                      (c) => (
                        <th key={c} className="px-2 py-1 text-left">
                          {c}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  {mappedRows.slice(0, 5).map((row, i) => (
                    <tr key={i} className="border-t">
                      {["date", "symbol", "type", "quantity", "price", "fee"].map(
                        (c) => (
                          <td key={c} className="px-2 py-1">
                            {row[c as keyof typeof row] ?? "—"}
                          </td>
                        )
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => setStep("upload")}
                className="flex-1"
              >
                Back
              </Button>
              <Button
                onClick={handleConfirm}
                disabled={loading}
                className="flex-1"
              >
                {loading ? "Importing..." : `Import ${mappedRows.length} rows`}
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
