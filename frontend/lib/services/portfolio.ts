import { api } from "@/lib/api";

export interface Holding {
  id: string;
  asset_id: string;
  quantity: string;
  avg_cost_price: string;
  currency: string;
  updated_at: string;
}

export interface Transaction {
  id: string;
  asset_id: string;
  platform_id: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  created_at: string;
}

export interface PortfolioSummary {
  holdings_count: number;
  total_cost_usd: string;
}

export async function fetchHoldings(): Promise<Holding[]> {
  const res = await api.get("/api/v1/portfolio/holdings");
  if (!res.ok) throw new Error("Failed to fetch holdings");
  return res.json();
}

export async function addHolding(body: {
  asset_id: string;
  quantity: string;
  avg_cost_price: string;
  currency: string;
}): Promise<Holding> {
  const res = await api.post("/api/v1/portfolio/holdings", body);
  if (!res.ok) throw new Error("Failed to add holding");
  return res.json();
}

export async function deleteHolding(id: string): Promise<void> {
  await api.delete(`/api/v1/portfolio/holdings/${id}`);
}

export async function fetchSummary(): Promise<PortfolioSummary> {
  const res = await api.get("/api/v1/portfolio/summary");
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}

export async function previewImport(file: File): Promise<{ columns: string[]; rows: Record<string, string>[] }> {
  const formData = new FormData();
  formData.append("file", file);
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
  const res = await fetch(`${API_BASE}/api/v1/portfolio/import/preview`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) throw new Error("Preview failed");
  return res.json();
}

export async function confirmImport(payload: {
  rows: Array<{ date: string; symbol: string; type: string; quantity: string; price: string; fee: string }>;
  asset_type: string;
  save_profile: boolean;
  broker_name: string | null;
}): Promise<{ imported: number; skipped: number; errors: string[] }> {
  const res = await api.post("/api/v1/portfolio/import/confirm", payload);
  if (!res.ok) throw new Error("Import failed");
  return res.json();
}
