import { api } from "@/lib/api";

export interface Platform {
  id: string;
  name: string;
  asset_types_supported: string[];
  notes: string | null;
  created_at: string;
}

export async function fetchPlatforms(): Promise<Platform[]> {
  const res = await api.get("/api/v1/platforms");
  if (!res.ok) return [];
  return res.json();
}

export async function createPlatform(body: {
  name: string;
  asset_types_supported: string[];
  notes?: string;
}): Promise<Platform> {
  const res = await api.post("/api/v1/platforms", body);
  if (!res.ok) throw new Error("Failed to create platform");
  return res.json();
}

export async function deletePlatform(id: string): Promise<void> {
  await api.delete(`/api/v1/platforms/${id}`);
}
