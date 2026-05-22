import { api } from "@/lib/api";

export interface OverviewSummary {
  total_value: string;
  total_cost: string;
  total_pnl: string;
  total_pnl_pct: string;
  daily_change: string;
  daily_change_pct: string;
}

export interface AllocationItem {
  asset_type: string;
  value: string;
  pct: string;
}

export interface SectorAllocationItem {
  sector: string;
  value: string;
  pct: string;
}

export interface PerformancePoint {
  date: string;
  value: string;
}

export interface PerformanceData {
  portfolio: PerformancePoint[];
  benchmark: PerformancePoint[];
}

export interface PriceBar {
  timestamp: string;
  open: string | null;
  high: string | null;
  low: string | null;
  close: string;
  volume: string | null;
}

export interface AssetHistory {
  asset_id: string;
  bars: PriceBar[];
}

export async function fetchOverviewSummary(): Promise<OverviewSummary> {
  const res = await api.get("/api/v1/overview/summary");
  if (!res.ok) throw new Error("Failed to fetch overview summary");
  return res.json();
}

export async function fetchAllocation(): Promise<AllocationItem[]> {
  const res = await api.get("/api/v1/overview/allocation");
  if (!res.ok) throw new Error("Failed to fetch allocation");
  return res.json();
}

export async function fetchSectorAllocation(): Promise<SectorAllocationItem[]> {
  const res = await api.get("/api/v1/overview/allocation/sector");
  if (!res.ok) throw new Error("Failed to fetch sector allocation");
  return res.json();
}

export async function triggerEnrichMetadata(): Promise<{ enriched: number; total: number }> {
  const res = await api.post("/api/v1/assets/enrich-metadata", null);
  if (!res.ok) throw new Error("Failed to enrich metadata");
  return res.json();
}

export async function fetchPerformance(range: string): Promise<PerformanceData> {
  const res = await api.get(`/api/v1/overview/performance?range=${range}`);
  if (!res.ok) throw new Error("Failed to fetch performance");
  return res.json();
}

export async function fetchAssetHistory(symbol: string, range: string): Promise<AssetHistory> {
  const res = await api.get(`/api/v1/assets/symbol/${encodeURIComponent(symbol)}/history?range=${range}`);
  if (!res.ok) throw new Error("Failed to fetch asset history");
  return res.json();
}

export interface NetWorthPoint {
  date: string;
  value_usd: string;
  cost_usd: string;
}

export async function fetchNetWorthTimeline(range: string): Promise<NetWorthPoint[]> {
  const res = await api.get(`/api/v1/overview/net-worth?range=${range}`);
  if (!res.ok) throw new Error("Failed to fetch net worth timeline");
  return res.json();
}
