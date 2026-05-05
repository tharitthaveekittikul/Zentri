"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { CheckCircle, Upload } from "lucide-react";
import { ReviewTable } from "@/components/import/ReviewTable";
import {
  CanonicalRow,
  confirmImport,
  uploadFile,
} from "@/lib/services/import-pipeline";

type Step = "idle" | "uploading" | "review" | "confirming" | "done";

export default function ImportPage() {
  const [step, setStep] = useState<Step>("idle");
  const [rows, setRows] = useState<CanonicalRow[]>([]);
  const [method, setMethod] = useState<"direct" | "llm_translated">("direct");
  const [result, setResult] = useState<{ imported: number; errors: unknown[] } | null>(null);

  async function handleFile(file: File) {
    setStep("uploading");
    try {
      const res = await uploadFile(file);
      setRows(res.rows);
      setMethod(res.method);
      setStep("review");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
      setStep("idle");
    }
  }

  async function handleConfirm() {
    setStep("confirming");
    try {
      const res = await confirmImport(rows);
      setResult(res);
      setStep("done");
      toast.success(`Imported ${res.imported} transactions`);
    } catch {
      toast.error("Import failed");
      setStep("review");
    }
  }

  function reset() {
    setStep("idle");
    setRows([]);
    setResult(null);
  }

  if (step === "done" && result) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16">
        <CheckCircle className="h-12 w-12 text-green-500" />
        <p className="text-xl font-semibold">Import complete</p>
        <p className="text-muted-foreground">{result.imported} transactions imported</p>
        {(result.errors as unknown[]).length > 0 && (
          <p className="text-destructive text-sm">
            {(result.errors as unknown[]).length} rows had errors
          </p>
        )}
        <Button onClick={reset}>Import another file</Button>
      </div>
    );
  }

  if (step === "review" || step === "confirming") {
    return (
      <div className="space-y-4 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">
              Review {rows.length} transactions
            </h2>
            {method === "llm_translated" && (
              <p className="text-sm text-muted-foreground">
                Fields were translated by AI — please verify before importing.
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={reset}
              disabled={step === "confirming"}
            >
              Cancel
            </Button>
            <Button onClick={handleConfirm} disabled={step === "confirming"}>
              {step === "confirming" ? "Importing…" : "Confirm Import"}
            </Button>
          </div>
        </div>
        <ReviewTable rows={rows} onChange={setRows} />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-6 py-16 px-6">
      <h1 className="text-2xl font-bold">Import Transactions</h1>
      <p className="text-muted-foreground text-center max-w-md">
        Upload a CSV or JSON file. If the headers match the canonical format they
        import directly. Other formats are translated by AI.
      </p>
      <div
        className="border-2 border-dashed rounded-xl p-12 flex flex-col items-center gap-4
                   cursor-pointer hover:border-primary transition-colors w-full max-w-md"
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files[0];
          if (f) handleFile(f);
        }}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <Upload className="h-10 w-10 text-muted-foreground" />
        <p className="text-sm text-muted-foreground text-center">
          {step === "uploading"
            ? "Processing…"
            : "Drop CSV or JSON here, or click to browse"}
        </p>
        <input
          id="file-input"
          type="file"
          accept=".csv,.json"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Canonical fields: trade_date · type · symbol · unit · price · currency ·
        asset_type · platform · fee · notes · …
      </p>
    </div>
  );
}
