import { api } from "@/lib/api";

export interface AnalyzeResponse {
  signature: string;
  structure: {
    headers: string[];
    sample_rows: Record<string, unknown>[];
    total_rows: number;
  };
  template_status: "match" | "mismatch" | "new";
  template: ImportTemplate | null;
  preview_rows: Record<string, unknown>[] | null;
  matched_platform_id: string | null;
}

export interface ImportTemplate {
  id: string;
  platform_id: string;
  file_format: string;
  json_path: string | null;
  column_signature: string;
  field_map: Record<string, string>;
  asset_type_rules: unknown[];
  asset_type_fallback: string;
  currency_default: string;
  updated_at: string;
}

export async function analyzeFile(file: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch("/api/v1/import/analyze", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${
        typeof window !== "undefined" ? localStorage.getItem("access_token") : ""
      }`,
    },
    body: form,
  });
  if (!r.ok) throw new Error("Failed to analyze file");
  return r.json();
}

export async function generateTemplate(
  platform_id: string,
  file: File,
): Promise<{ template: ImportTemplate; preview_rows: Record<string, unknown>[] }> {
  const form = new FormData();
  form.append("platform_id", platform_id);
  form.append("file", file);
  const r = await fetch("/api/v1/import/generate-template", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${
        typeof window !== "undefined" ? localStorage.getItem("access_token") : ""
      }`,
    },
    body: form,
  });
  if (!r.ok) throw new Error("Failed to generate template");
  return r.json();
}

export async function confirmImportPipeline(
  platform_id: string,
  rows: Record<string, unknown>[],
): Promise<{ imported: number; errors: unknown[] }> {
  const r = await fetch("/api/v1/import/confirm", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${
        typeof window !== "undefined" ? localStorage.getItem("access_token") : ""
      }`,
    },
    body: JSON.stringify({ platform_id, rows }),
  });
  if (!r.ok) throw new Error("Failed to confirm import");
  return r.json();
}
