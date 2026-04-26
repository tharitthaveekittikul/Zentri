import { api } from "@/lib/api";

export interface Asset {
  id: string;
  symbol: string;
  asset_type: string;
  name: string;
  currency: string;
  created_at: string;
}

export async function searchAssets(q: string): Promise<Asset[]> {
  const res = await api.get(`/api/v1/assets/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchAllAssets(): Promise<Asset[]> {
  const res = await api.get("/api/v1/assets/search?q=");
  if (!res.ok) return [];
  return res.json();
}

export async function createAsset(body: {
  symbol: string;
  asset_type: string;
  name: string;
  currency: string;
}): Promise<Asset> {
  const res = await api.post("/api/v1/assets", body);
  if (!res.ok) throw new Error("Failed to create asset");
  return res.json();
}
