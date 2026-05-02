import { api } from "@/lib/api";

export interface ProviderConfig {
  id: string;
  provider: string;
  host_url: string | null;
  is_connected: boolean;
  models_cache: string[];
  models_fetched_at: string | null;
  created_at: string;
}

export type Provider =
  | "anthropic"
  | "openai"
  | "gemini"
  | "ollama"
  | "openrouter";

export async function listProviderConfigs(): Promise<ProviderConfig[]> {
  const r = await api.get("/api/v1/provider-configs");
  if (!r.ok) throw new Error("Failed to fetch provider configs");
  return r.json();
}

export async function createProviderConfig(
  provider: Provider,
  api_key?: string,
  host_url?: string,
): Promise<ProviderConfig> {
  const r = await api.post("/api/v1/provider-configs", {
    provider,
    api_key,
    host_url,
  });
  if (!r.ok) throw new Error("Failed to create provider config");
  return r.json();
}

export async function testConnection(id: string): Promise<ProviderConfig> {
  const r = await api.post(
    `/api/v1/provider-configs/${id}/test-connection`,
    {},
  );
  if (!r.ok) throw new Error("Connection test failed");
  return r.json();
}

export async function fetchModels(id: string): Promise<ProviderConfig> {
  const r = await api.post(`/api/v1/provider-configs/${id}/fetch-models`, {});
  if (!r.ok) throw new Error("Failed to fetch models");
  return r.json();
}

export async function deleteProviderConfig(id: string): Promise<void> {
  const r = await api.delete(`/api/v1/provider-configs/${id}`);
  if (!r.ok) throw new Error("Failed to delete");
}
