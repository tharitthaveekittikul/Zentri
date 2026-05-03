"use client";

import { useState, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { fetchPlatforms, createPlatform } from "@/lib/services/platforms";
import {
  analyzeFile,
  generateTemplate,
  LLMQuotaError,
  confirmImportPipeline,
  type AnalyzeResponse,
} from "@/lib/services/import-pipeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

type Step = "upload" | "name-source" | "review" | "done";

export default function ImportPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(null);
  const [platformId, setPlatformId] = useState<string>("");
  const [newPlatformName, setNewPlatformName] = useState("");
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [importedCount, setImportedCount] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: platforms = [], refetch: refetchPlatforms } = useQuery({
    queryKey: ["platforms"],
    queryFn: fetchPlatforms,
  });

  async function handleAnalyze() {
    if (!file) {
      toast.error("Please select a file.");
      return;
    }
    setAnalyzing(true);
    try {
      const result = await analyzeFile(file);
      setAnalyzeResult(result);

      if (result.template_status === "match" && result.preview_rows && result.matched_platform_id) {
        setPlatformId(result.matched_platform_id);
        setPreviewRows(result.preview_rows);
        setStep("review");
      } else {
        setStep("name-source");
      }
    } catch {
      toast.error("Failed to analyze file. Please try again.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleConfirmSource() {
    if (!file || !analyzeResult) return;

    let resolvedPlatformId = platformId;

    if (!resolvedPlatformId && newPlatformName.trim()) {
      try {
        const created = await createPlatform({
          name: newPlatformName.trim(),
          asset_types_supported: [],
        });
        resolvedPlatformId = created.id;
        setPlatformId(created.id);
        await refetchPlatforms();
      } catch {
        toast.error("Failed to create platform.");
        return;
      }
    }

    if (!resolvedPlatformId) {
      toast.error("Please select or name a source platform.");
      return;
    }

    setGenerating(true);
    try {
      const result = await generateTemplate(resolvedPlatformId, file);
      setPreviewRows(result.preview_rows);
      setStep("review");
      toast.success("Template generated successfully.");
    } catch (err) {
      if (err instanceof LLMQuotaError) {
        toast.error(`${err.provider} credits exhausted.`, {
          description: "Your prepayment balance is depleted.",
          action: {
            label: "Recharge →",
            onClick: () => window.open(err.billingUrl, "_blank"),
          },
        });
      } else {
        toast.error("Failed to generate template. Please try again.");
      }
    } finally {
      setGenerating(false);
    }
  }

  async function handleConfirmImport() {
    if (!platformId || previewRows.length === 0) return;
    setConfirming(true);
    try {
      const result = await confirmImportPipeline(platformId, previewRows);
      setImportedCount(result.imported);
      setStep("done");
      if (result.errors && result.errors.length > 0) {
        toast(`${result.errors.length} row(s) had errors during import.`);
      }
    } catch {
      toast.error("Failed to confirm import.");
    } finally {
      setConfirming(false);
    }
  }

  async function handleRemap() {
    if (!platformId) return;
    if (!confirm("Delete the saved mapping for this platform? The next upload will ask the AI to re-learn the format.")) return;
    try {
      await api.delete(`/api/v1/import/template/${platformId}`);
      handleReset();
    } catch {
      toast.error("Failed to delete template.");
    }
  }

  function handleReset() {
    setStep("upload");
    setFile(null);
    setAnalyzeResult(null);
    setPlatformId("");
    setNewPlatformName("");
    setPreviewRows([]);
    setImportedCount(0);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const previewHeaders = previewRows.length > 0 ? Object.keys(previewRows[0]) : [];
  const displayRows = previewRows.slice(0, 20);
  const matchedPlatformName = platforms.find((p) => p.id === platformId)?.name;

  const STEPS: Step[] = ["upload", "name-source", "review", "done"];
  const STEP_LABELS: Record<Step, string> = {
    "upload": "Upload",
    "name-source": "Source",
    "review": "Review",
    "done": "Done",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Import</h1>

      {/* Step indicator */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {STEPS.map((s, i) => (
          <span key={s} className="flex items-center gap-2">
            <span className={step === s ? "font-semibold text-foreground" : ""}>
              {i + 1}. {STEP_LABELS[s]}
            </span>
            {i < STEPS.length - 1 && <span>›</span>}
          </span>
        ))}
      </div>

      {/* Step: Upload */}
      {step === "upload" && (
        <Card>
          <CardHeader>
            <CardTitle>Upload File</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">File (CSV or JSON)</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.json"
                className="w-full border rounded-md px-3 py-2 text-sm bg-background file:mr-2 file:border-0 file:bg-transparent file:text-sm file:font-medium"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <button
              onClick={handleAnalyze}
              disabled={analyzing || !file}
              className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
            >
              {analyzing ? "Analyzing…" : "Analyze"}
            </button>
          </CardContent>
        </Card>
      )}

      {/* Step: Name Source */}
      {step === "name-source" && (
        <Card>
          <CardHeader>
            <CardTitle>Name the Source</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              No saved template matched this file. Select an existing source or type a new name.
            </p>

            {platforms.length > 0 && (
              <div className="space-y-1">
                <label className="text-sm font-medium">Existing platforms</label>
                <div className="flex flex-wrap gap-2">
                  {platforms.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => {
                        setPlatformId(p.id);
                        setNewPlatformName("");
                      }}
                      className={`px-3 py-1 rounded-full border text-sm ${
                        platformId === p.id
                          ? "bg-primary text-primary-foreground border-primary"
                          : "text-muted-foreground hover:bg-accent"
                      }`}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-1">
              <label className="text-sm font-medium">
                {platforms.length > 0 ? "Or create a new one" : "Platform / broker name"}
              </label>
              <input
                type="text"
                placeholder="e.g. Finnomena, IBKR, Bitkub"
                value={newPlatformName}
                onChange={(e) => {
                  setNewPlatformName(e.target.value);
                  setPlatformId("");
                }}
                className="w-full border rounded-md px-3 py-2 text-sm bg-background"
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleConfirmSource}
                disabled={generating || (!platformId && !newPlatformName.trim())}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
              >
                {generating ? "Generating template…" : "Continue"}
              </button>
              <button
                onClick={handleReset}
                className="px-4 py-2 rounded-md border text-sm font-medium"
              >
                Back
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step: Review */}
      {step === "review" && (
        <Card>
          <CardHeader>
            <CardTitle>Review Preview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {matchedPlatformName && (
              <p className="text-sm">
                Source: <span className="font-medium">{matchedPlatformName}</span>
              </p>
            )}
            <p className="text-sm text-muted-foreground">
              Showing first {displayRows.length} of {previewRows.length} rows. Confirm to import all.
            </p>

            {previewHeaders.length > 0 ? (
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-xs">
                  <thead className="bg-muted">
                    <tr>
                      {previewHeaders.map((h) => (
                        <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {displayRows.map((row, i) => (
                      <tr key={i} className="border-t">
                        {previewHeaders.map((h) => (
                          <td key={h} className="px-3 py-2 whitespace-nowrap text-muted-foreground">
                            {String(row[h] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No preview data available.</p>
            )}

            <div className="flex gap-2">
              <button
                onClick={handleConfirmImport}
                disabled={confirming}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
              >
                {confirming ? "Importing…" : "Confirm Import"}
              </button>
              <button onClick={handleReset} className="px-4 py-2 rounded-md border text-sm font-medium">
                Cancel
              </button>
              {analyzeResult?.template_status === "match" && (
                <button
                  onClick={handleRemap}
                  className="text-sm text-destructive underline ml-2"
                >
                  Re-map (re-learn format)
                </button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step: Done */}
      {step === "done" && (
        <Card>
          <CardHeader>
            <CardTitle>Import Complete</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Successfully imported{" "}
              <span className="font-semibold text-foreground">{importedCount}</span>{" "}
              row{importedCount !== 1 ? "s" : ""} into your portfolio.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => router.push("/portfolio")}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium"
              >
                Go to Portfolio
              </button>
              <button onClick={handleReset} className="px-4 py-2 rounded-md border text-sm font-medium">
                Import Another File
              </button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
