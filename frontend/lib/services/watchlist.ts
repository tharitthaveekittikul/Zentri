import { api } from "@/lib/api";
import { PaginatedResponse } from "@/lib/types";

export interface WatchlistAsset {
  id: string;
  symbol: string;
  name: string;
  currency: string;
  asset_type: string;
  metadata_: Record<string, unknown>;
}

export interface WatchlistItem {
  id: string;
  asset_id: string;
  target_price: string | null;
  currency: string;
  notes: string | null;
  alert_enabled: boolean;
  alerted_at: string | null;
  created_at: string;
  asset: WatchlistAsset;
  current_price: string | null;
  pct_from_target: number | null;
  last_verdict: "BUY" | "SELL" | "HOLD" | null;
  ai_suggested_price: string | null;
  last_scanned_at: string | null;
  ath_drop_pct: number | null;
  ath_alert_threshold: string | null;
  ath_alerted_at: string | null;
}

export interface WatchlistSuggestion {
  id: string;
  symbol: string;
  asset_id: string | null;
  reasoning: string;
  suggested_price: string | null;
  verdict: "BUY" | "SELL" | "HOLD";
  status: "pending" | "accepted" | "dismissed";
  created_at: string;
}

export interface WatchlistParams {
  search?: string;
  asset_type?: string;
  alert_status?: string;
  page?: number;
  page_size?: number;
}

export async function listWatchlist(
  params: WatchlistParams = {},
): Promise<PaginatedResponse<WatchlistItem>> {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.asset_type) qs.set("asset_type", params.asset_type);
  if (params.alert_status) qs.set("alert_status", params.alert_status);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const query = qs.toString();
  const r = await api.get(
    `/api/v1/watchlist${query ? `?${query}` : ""}`,
  );
  if (!r.ok) throw new Error("Failed to fetch watchlist");
  return r.json();
}

export async function addToWatchlist(body: {
  asset_id: string;
  target_price?: string | null;
  currency?: string;
  notes?: string | null;
}): Promise<WatchlistItem> {
  const r = await api.post("/api/v1/watchlist", body);
  if (!r.ok) throw new Error("Failed to add to watchlist");
  return r.json();
}

export async function updateWatchlistItem(
  id: string,
  patch: {
    target_price?: string | null;
    notes?: string | null;
    alert_enabled?: boolean;
    ath_alert_threshold?: string | null;
  },
): Promise<WatchlistItem> {
  const r = await api.patch(`/api/v1/watchlist/${id}`, patch);
  if (!r.ok) throw new Error("Failed to update watchlist item");
  return r.json();
}

export async function deleteWatchlistItem(id: string): Promise<void> {
  await api.delete(`/api/v1/watchlist/${id}`);
}

export async function rearmWatchlistItem(id: string): Promise<WatchlistItem> {
  const r = await api.post(`/api/v1/watchlist/${id}/rearm`, {});
  if (!r.ok) throw new Error("Failed to rearm alert");
  return r.json();
}

export async function scanItem(id: string): Promise<void> {
  await api.post(`/api/v1/watchlist/${id}/scan`, {});
}

export async function scanAll(): Promise<void> {
  await api.post("/api/v1/watchlist/scan-all", {});
}

export async function discoverWatchlist(): Promise<void> {
  const r = await api.post("/api/v1/watchlist/discover", {});
  if (r.status === 422) {
    const data = await r.json();
    if (data?.detail === "no_llm_config") throw new Error("no_llm_config");
  }
  if (!r.ok) throw new Error("Failed to trigger discovery");
}

export async function listSuggestions(): Promise<WatchlistSuggestion[]> {
  const r = await api.get("/api/v1/watchlist/suggestions");
  if (!r.ok) throw new Error("Failed to fetch suggestions");
  return r.json();
}

export async function acceptSuggestion(id: string): Promise<WatchlistItem> {
  const r = await api.post(`/api/v1/watchlist/suggestions/${id}/accept`, {});
  if (!r.ok) throw new Error("Failed to accept suggestion");
  return r.json();
}

export async function dismissSuggestion(id: string): Promise<void> {
  await api.post(`/api/v1/watchlist/suggestions/${id}/dismiss`, {});
}
