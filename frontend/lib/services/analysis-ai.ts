import { api } from "@/lib/api"

// ── Deep Dive ────────────────────────────────────────────────

export interface DeepDiveData {
  id: string
  asset_id: string | null
  business_model: string
  moat: {
    edge_type: "patent" | "switching_cost" | "network_effect" | "cost_structure" | "none"
    summary: string
    competitors: string[]
  }
  catalysts: { title: string; timeframe: string; impact: "high" | "medium" | "low" }[]
  asymmetry: {
    verdict: "yes" | "no" | "mixed"
    floor: string
    ceiling: string
    reasoning: string
  }
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost_usd: number
  created_at: string
  status?: string
  error_message?: string | null
}

// ── Bear Case ─────────────────────────────────────────────────

export interface BearCaseData {
  id: string
  asset_id: string | null
  red_flags: {
    rank: number
    title: string
    severity: "high" | "medium" | "low"
    data_source: "yfinance" | "llm_knowledge"
    evidence: string
    detail: string
  }[]
  summary: string
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost_usd: number
  created_at: string
  status?: string
  error_message?: string | null
}

// ── Peer Comparison ───────────────────────────────────────────

export interface PeerRow {
  ticker: string
  company_name: string
  ps_ttm: number | null
  ps_forward: number | null
  ev_ebitda: number | null
  gross_margin_pct: number | null
  yoy_revenue_growth_pct: number | null
  revenue_trend: "Reaccelerating" | "Accelerating" | "Stable" | "Decelerating" | "Declining"
  value_growth_score: number | null
  label: "BEST" | "FAIR" | "AVOID"
  notes: string
}

export interface PeerComparisonData {
  id: string
  asset_id: string | null
  sector_label: string
  ranked: PeerRow[]
  methodology_note: string
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost_usd: number
  created_at: string
  status?: string
  error_message?: string | null
}

// ── Combined Verdict ──────────────────────────────────────────

export type VerdictLabel = "strong_buy" | "buy" | "hold" | "sell" | "strong_sell"

export interface CombinedVerdictData {
  id: string
  asset_id: string | null
  verdict: VerdictLabel
  conviction: number
  bull_thesis: string
  bear_thesis: string
  key_risks: string[]
  reasoning: string
  based_on: string[]
  entry_price: number | null
  target_price: number | null
  stop_loss: number | null
  risk_reward: number | null
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost_usd: number
  created_at: string
  status?: string
  error_message?: string | null
}

// ── Fetch functions ───────────────────────────────────────────

async function fetchLatest<T>(endpoint: string): Promise<T | null> {
  try {
    const res = await api.get(endpoint)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

async function trigger(endpoint: string): Promise<void> {
  const res = await api.post(endpoint, {})
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail ?? "Failed to trigger analysis")
  }
}

export const fetchDeepDive = (symbol: string) =>
  fetchLatest<DeepDiveData>(`/api/v1/analysis/deep-dive/${symbol}/latest`)

export const triggerDeepDive = (symbol: string) =>
  trigger(`/api/v1/analysis/deep-dive/${symbol}`)

export const fetchBearCase = (symbol: string) =>
  fetchLatest<BearCaseData>(`/api/v1/analysis/bear-case/${symbol}/latest`)

export const triggerBearCase = (symbol: string) =>
  trigger(`/api/v1/analysis/bear-case/${symbol}`)

export const fetchPeerComparison = (symbol: string) =>
  fetchLatest<PeerComparisonData>(`/api/v1/analysis/peer-comparison/${symbol}/latest`)

export const triggerPeerComparison = (symbol: string) =>
  trigger(`/api/v1/analysis/peer-comparison/${symbol}`)

export const fetchCombinedVerdict = (symbol: string) =>
  fetchLatest<CombinedVerdictData>(`/api/v1/analysis/combined-verdict/${symbol}/latest`)

export const triggerCombinedVerdict = (symbol: string) =>
  trigger(`/api/v1/analysis/combined-verdict/${symbol}`)
