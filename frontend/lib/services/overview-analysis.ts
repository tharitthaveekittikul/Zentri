import { api } from "@/lib/api";

export interface OverviewAnalysis {
  id: string;
  score: number;
  grade: "A" | "B" | "C" | "D" | "F";
  health: "Excellent" | "Good" | "Moderate" | "Weak" | "Critical";
  portfolio_adherence_pct: number | null;
  insights: string[];
  top_action: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  cost_thb: number;
  created_at: string;
}

export async function getLatestOverviewAnalysis(): Promise<OverviewAnalysis | null> {
  const r = await api.get("/api/v1/overview/ai-analysis/latest");
  if (!r.ok) throw new Error("Failed to fetch overview analysis");
  return r.json();
}

export async function triggerOverviewAnalysis(force = false): Promise<OverviewAnalysis> {
  const url = force
    ? "/api/v1/overview/ai-analysis?force=true"
    : "/api/v1/overview/ai-analysis";
  const r = await api.post(url, null);
  if (r.status === 429) {
    const body = await r.json();
    throw Object.assign(new Error(body.detail?.message ?? "Cooldown active"), {
      code: "cooldown_active",
      lastAnalysis: body.detail?.last_analysis as OverviewAnalysis | undefined,
    });
  }
  if (!r.ok) throw new Error("Failed to run overview analysis");
  return r.json();
}
