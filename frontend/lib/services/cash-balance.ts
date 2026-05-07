import { api } from "@/lib/api";

export interface CashBalance {
  id: string;
  asset_id: string;
  balance: number;
  snapshot_date: string;
  notes: string | null;
  created_at: string;
}

export async function createBalance(
  asset_id: string,
  balance: number,
  snapshot_date: string,
  notes?: string,
): Promise<CashBalance> {
  const r = await api.post("/api/v1/cash-balances", {
    asset_id,
    balance,
    snapshot_date,
    notes,
  });
  if (!r.ok) throw new Error("Failed to create balance");
  return r.json();
}

export async function getAllLatestBalances(): Promise<Record<string, CashBalance>> {
  const r = await api.get("/api/v1/cash-balances/latest");
  if (!r.ok) throw new Error("Failed to fetch balances");
  const list: CashBalance[] = await r.json();
  return Object.fromEntries(list.map((b) => [b.asset_id, b]));
}

export async function getLatestBalance(asset_id: string): Promise<CashBalance> {
  const r = await api.get(`/api/v1/cash-balances/${asset_id}/latest`);
  if (!r.ok) throw new Error("No balance found");
  return r.json();
}

export async function getBalanceHistory(asset_id: string): Promise<CashBalance[]> {
  const r = await api.get(`/api/v1/cash-balances/${asset_id}/history`);
  if (!r.ok) throw new Error("Failed to fetch history");
  return r.json();
}
