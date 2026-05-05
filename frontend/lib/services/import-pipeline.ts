export interface CanonicalRow {
  trade_date: string | null;
  type: string | null;
  symbol: string | null;
  unit: string | null;
  price: string | null;
  currency: string | null;
  exchange: string | null;
  gross_amount: string | null;
  fee: string | null;
  gross_thb: string | null;
  fee_thb: string | null;
  exchange_rate: string | null;
  asset_type: string | null;
  platform: string | null;
  notes: string | null;
  [key: string]: unknown;
}

export interface UploadResponse {
  rows: CanonicalRow[];
  method: "direct" | "llm_translated";
  total: number;
}

function authHeader(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
  return { Authorization: `Bearer ${token}` };
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch("/api/v1/import/upload", {
    method: "POST",
    headers: authHeader(),
    body: form,
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Upload failed");
  }
  return r.json();
}

export async function confirmImport(
  rows: CanonicalRow[]
): Promise<{ imported: number; errors: unknown[] }> {
  const r = await fetch("/api/v1/import/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({ rows }),
  });
  if (!r.ok) throw new Error("Confirm failed");
  return r.json();
}
