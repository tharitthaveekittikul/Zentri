import { api } from "@/lib/api";

export interface FeatureLLMConfig {
  id: string;
  feature_key: string;
  provider_config_id: string;
  model: string;
  system_prompt: string;
  is_prompt_customized: boolean;
  updated_at: string;
}

export const FEATURE_LABELS: Record<string, string> = {
  import_translator: "Import Translator",
  portfolio_analysis: "Portfolio Analysis",
  chat: "Chat Assistant",
  watchlist_scan: "Watchlist Scanner",
  watchlist_discovery: "Watchlist Discovery",
};

export async function listFeatureConfigs(): Promise<FeatureLLMConfig[]> {
  const r = await api.get("/api/v1/feature-llm-configs");
  if (!r.ok) throw new Error("Failed to fetch feature configs");
  return r.json();
}

export async function createFeatureConfig(
  feature_key: string,
  provider_config_id: string,
  model: string,
  system_prompt?: string,
): Promise<FeatureLLMConfig> {
  const r = await api.post("/api/v1/feature-llm-configs", {
    feature_key,
    provider_config_id,
    model,
    system_prompt,
  });
  if (!r.ok) throw new Error("Failed to create feature config");
  return r.json();
}

export async function updateFeatureConfig(
  id: string,
  patch: {
    provider_config_id?: string;
    model?: string;
    system_prompt?: string;
  },
): Promise<FeatureLLMConfig> {
  const r = await api.patch(`/api/v1/feature-llm-configs/${id}`, patch);
  if (!r.ok) throw new Error("Failed to update feature config");
  return r.json();
}

export async function resetPrompt(id: string): Promise<FeatureLLMConfig> {
  const r = await api.post(
    `/api/v1/feature-llm-configs/${id}/reset-prompt`,
    {},
  );
  if (!r.ok) throw new Error("Failed to reset prompt");
  return r.json();
}
