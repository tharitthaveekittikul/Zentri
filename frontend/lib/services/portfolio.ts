import { api } from "@/lib/api";
import { PaginatedResponse } from "@/lib/types";

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
  metadata_: Record<string, unknown>;
}

export interface PlatformGroup {
  platform: string;
  count: number;
  currencyGroups: {
    currency: string;
    totalValue: number | null;
    totalPnl: number | null;
  }[];
}

export function groupHoldingsByPlatform(holdings: HoldingRow[]): PlatformGroup[] {
  const map = new Map<string, HoldingRow[]>();
  for (const h of holdings) {
    if (h.asset_type === "cash" || Number(h.outstanding_shares) < 1e-6) continue;
    const key = h.platform ?? "No Platform";
    const existing = map.get(key) ?? [];
    existing.push(h);
    map.set(key, existing);
  }

  return Array.from(map.entries()).map(([platform, rows]) => {
    const currencyMap = new Map<string, { value: number | null; pnl: number | null }>();
    for (const row of rows) {
      const curr = row.currency;
      const entry = currencyMap.get(curr) ?? { value: null, pnl: null };
      if (row.holding_value != null) {
        entry.value = (entry.value ?? 0) + Number(row.holding_value);
      }
      if (row.unrealized_pnl != null) {
        entry.pnl = (entry.pnl ?? 0) + Number(row.unrealized_pnl);
      }
      currencyMap.set(curr, entry);
    }
    return {
      platform,
      count: rows.length,
      currencyGroups: Array.from(currencyMap.entries()).map(
        ([currency, { value, pnl }]) => ({
          currency,
          totalValue: value,
          totalPnl: pnl,
        }),
      ),
    };
  });
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

export interface TransactionRow {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  currency?: string;
  platform: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  created_at: string;
  metadata_: Record<string, unknown>;
}

export interface TransactionParams {
  search?: string;
  asset_id?: string;
  type?: string;
  platform?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function fetchTransactions(
  params: TransactionParams = {},
): Promise<PaginatedResponse<TransactionRow>> {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.asset_id) qs.set("asset_id", params.asset_id);
  if (params.type) qs.set("type", params.type);
  if (params.platform) qs.set("platform", params.platform);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const query = qs.toString();
  const res = await api.get(
    `/api/v1/portfolio/transactions${query ? `?${query}` : ""}`,
  );
  if (!res.ok) throw new Error("Failed to fetch transactions");
  return res.json();
}

export interface AssetDetail {
  id: string;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
  metadata_: Record<string, unknown>;
}

export async function fetchAsset(assetId: string): Promise<AssetDetail> {
  const res = await api.get(`/api/v1/assets/${assetId}`);
  if (!res.ok) throw new Error("Failed to fetch asset");
  return res.json();
}

export async function updateAsset(
  assetId: string,
  data: { symbol?: string; name?: string; asset_type?: string; metadata_?: Record<string, unknown> },
): Promise<AssetDetail> {
  const res = await api.patch(`/api/v1/assets/${assetId}`, data);
  if (!res.ok) throw new Error("Failed to update asset");
  return res.json();
}

export async function refreshAssetNames(): Promise<{ updated: number; total: number }> {
  const res = await api.post("/api/v1/assets/refresh-names", {});
  if (!res.ok) throw new Error("Failed to refresh names");
  return res.json();
}

export interface ThFundMatch {
  proj_id: string;
  proj_abbr_name: string;
  proj_name_en: string;
  proj_name_th: string;
  fund_status: string;
  management_style: string;
  policy_desc: string;
}

export async function lookupThFund(q: string): Promise<ThFundMatch[]> {
  const res = await api.get(`/api/v1/assets/th-fund/lookup?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
  return res.json();
}

export interface CoinGeckoResult {
  id: string;
  symbol: string;
  name: string;
  thumb: string;
}

export async function searchCoinGecko(q: string): Promise<CoinGeckoResult[]> {
  if (!q || q.length < 2) return [];
  const res = await api.get(`/api/v1/assets/search-coingecko?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
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

export interface HoldingsParams {
  search?: string;
  platform?: string;
  asset_type?: string;
  page?: number;
  page_size?: number;
}

export async function fetchHoldings(
  params: HoldingsParams = {},
): Promise<PaginatedResponse<HoldingRow>> {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.platform) qs.set("platform", params.platform);
  if (params.asset_type) qs.set("asset_type", params.asset_type);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const query = qs.toString();
  const res = await api.get(
    `/api/v1/portfolio/holdings${query ? `?${query}` : ""}`,
  );
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
  metadata_?: Record<string, unknown>;
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
