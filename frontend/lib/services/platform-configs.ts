import { api } from "@/lib/api";

export interface PlatformConfig {
  name: string;
  color: string;
}

export async function fetchPlatformConfigs(): Promise<PlatformConfig[]> {
  const res = await api.get("/api/v1/platforms");
  return res.json();
}

export async function updatePlatformColor(name: string, color: string): Promise<void> {
  await api.put(`/api/v1/platforms/${encodeURIComponent(name)}`, { color });
}

export async function deletePlatformColor(name: string): Promise<void> {
  await api.delete(`/api/v1/platforms/${encodeURIComponent(name)}`);
}
