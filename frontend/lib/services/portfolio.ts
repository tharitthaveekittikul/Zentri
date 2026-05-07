import { api } from "@/lib/api";

export interface HoldingRow {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  currency: string;
  platform: string | null;
  purchased_at: string | null;
  outstanding_shares: string;
  cost_per_share: string;
  total_cost: string;
  current_price: string | null;
  holding_value: string | null;
  unrealized_pnl: string | null;
  price_1d_change: string | null;
}

export interface Transaction {
  id: string;
  asset_id: string;
  platform: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  created_at: string;
}

export interface AssetDetail {
  id: string;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
}

export async function fetchAsset(assetId: string): Promise<AssetDetail> {
  const res = await api.get(`/api/v1/assets/${assetId}`);
  if (!res.ok) throw new Error("Failed to fetch asset");
  return res.json();
}

export async function updateAsset(
  assetId: string,
  data: { symbol?: string; name?: string },
): Promise<AssetDetail> {
  const res = await api.patch(`/api/v1/assets/${assetId}`, data);
  if (!res.ok) throw new Error("Failed to update asset");
  return res.json();
}

export interface PortfolioSummary {
  holdings_count: number;
  total_cost: string;
  total_cost_secondary: string | null;
  primary_currency: string;
  secondary_currency: string;
  exchange_rate: string | null;
  exchange_rate_date: string | null;
}

export async function fetchHoldings(): Promise<HoldingRow[]> {
  const res = await api.get("/api/v1/portfolio/holdings");
  if (!res.ok) throw new Error("Failed to fetch holdings");
  return res.json();
}

export async function addHolding(body: {
  symbol: string;
  asset_type: string;
  purchased_at: string | null;
  quantity: string;
  avg_cost_price: string;
  currency: string;
}): Promise<HoldingRow> {
  const res = await api.post("/api/v1/portfolio/holdings", body);
  if (!res.ok) throw new Error("Failed to add holding");
  return res.json();
}

export async function deleteHolding(id: string): Promise<void> {
  await api.delete(`/api/v1/portfolio/holdings/${id}`);
}

export async function updateHolding(
  id: string,
  data: {
    quantity?: string;
    avg_cost_price?: string;
    currency?: string;
    platform?: string | null;
  },
): Promise<HoldingRow> {
  const res = await api.patch(`/api/v1/portfolio/holdings/${id}`, data);
  if (!res.ok) throw new Error("Failed to update holding");
  return res.json();
}

export async function fetchSummary(): Promise<PortfolioSummary> {
  const res = await api.get("/api/v1/portfolio/summary");
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}

export async function addManualTransaction(body: {
  symbol: string;
  asset_type: string;
  currency: string;
  platform: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  executed_at: string;
}): Promise<Transaction> {
  const res = await api.post("/api/v1/portfolio/transactions/manual", body);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Failed to add transaction");
  }
  return res.json();
}
