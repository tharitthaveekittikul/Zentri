# Analysis AI Features — Part 2: Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Deep Dive, Peer Comparison, Bear Case, and Combined Verdict cards to the Analysis symbol page, with auto-polling after each trigger.

**Architecture:** Each card is a standalone component. All cards share a `useAnalysisPolling` hook that polls the result endpoint every 3s after triggering. The symbol page is refactored to render all 5 cards (Combined Verdict at top + 4 analysis cards below). Combined Verdict shows "X/4 analyses available" count.

**Tech Stack:** Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui, CSS design tokens from `globals.css`

**Prerequisites:** Part 1 backend must be complete (all 4 API routers running).

**Part 1:** `docs/superpowers/plans/2026-05-21-analysis-ai-features-part1-backend.md`

---

## File Map

**Create:**
- `frontend/lib/services/analysis-ai.ts` — fetch functions + TypeScript types for all 4 features
- `frontend/hooks/useAnalysisPolling.ts` — shared polling hook
- `frontend/components/analysis/DeepDiveCard.tsx`
- `frontend/components/analysis/BearCaseCard.tsx`
- `frontend/components/analysis/PeerComparisonCard.tsx`
- `frontend/components/analysis/CombinedVerdictCard.tsx`

**Modify:**
- `frontend/app/(auth)/analysis/[symbol]/page.tsx` — add all 5 cards, refactor layout

---

## Task 1: TypeScript types and fetch functions

**Files:**
- Create: `frontend/lib/services/analysis-ai.ts`

- [ ] **Step 1: Create the file**

```typescript
// frontend/lib/services/analysis-ai.ts
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
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost_usd: number
  created_at: string
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
```

---

## Task 2: Shared polling hook

**Files:**
- Create: `frontend/hooks/useAnalysisPolling.ts`

- [ ] **Step 1: Create the hook**

```typescript
// frontend/hooks/useAnalysisPolling.ts
"use client"

import { useCallback, useEffect, useRef, useState } from "react"

interface UseAnalysisPollingOptions<T> {
  fetchFn: () => Promise<T | null>
  interval?: number
}

interface UseAnalysisPollingReturn<T> {
  data: T | null
  loading: boolean
  error: string | null
  trigger: () => Promise<void>
  setData: (d: T | null) => void
}

export function useAnalysisPolling<T extends { id: string }>(
  triggerFn: () => Promise<void>,
  { fetchFn, interval = 3000 }: UseAnalysisPollingOptions<T>,
): UseAnalysisPollingReturn<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const prevIdRef = useRef<string | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const trigger = useCallback(async () => {
    setLoading(true)
    setError(null)
    prevIdRef.current = data?.id ?? null

    try {
      await triggerFn()
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to trigger"
      setError(msg)
      setLoading(false)
      return
    }

    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const result = await fetchFn()
        if (result && result.id !== prevIdRef.current) {
          setData(result)
          setError(null)
          setLoading(false)
          stopPolling()
        }
      } catch {
        setError("Polling failed")
        setLoading(false)
        stopPolling()
      }
    }, interval)
  }, [triggerFn, fetchFn, interval, data?.id, stopPolling])

  useEffect(() => () => stopPolling(), [stopPolling])

  return { data, loading, error, trigger, setData }
}
```

---

## Task 3: DeepDiveCard component

**Files:**
- Create: `frontend/components/analysis/DeepDiveCard.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/analysis/DeepDiveCard.tsx
"use client"

import { Button } from "@/components/ui/button"
import type { DeepDiveData } from "@/lib/services/analysis-ai"

const IMPACT_COLOR: Record<string, string> = {
  high: "text-[var(--color-signal-gain)]",
  medium: "text-[var(--color-ink-muted)]",
  low: "text-[var(--color-ink-muted)]",
}

const ASYMMETRY_COLOR: Record<string, string> = {
  yes: "text-[var(--color-signal-gain)]",
  no: "text-[var(--brand-danger)]",
  mixed: "text-[var(--color-ink-muted)]",
}

interface Props {
  ticker: string
  data: DeepDiveData | null
  loading: boolean
  error: string | null
  onTrigger: () => void
}

export function DeepDiveCard({ ticker, data, loading, error, onTrigger }: Props) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
            {ticker} Deep Dive
          </h2>
          {data && (
            <p className="text-xs text-[var(--color-text-muted)]">
              {new Date(data.created_at).toLocaleString()} · {data.model}
            </p>
          )}
        </div>
        <Button
          onClick={onTrigger}
          disabled={loading}
          className="px-3 py-1 text-xs font-medium"
        >
          {loading ? "Analyzing…" : data ? "Re-run" : "Run Analysis"}
        </Button>
      </div>

      {error && (
        <p className="text-xs text-[var(--brand-danger)]">{error}</p>
      )}

      {loading && !data && (
        <div className="flex items-center gap-2 py-6 justify-center">
          <span className="animate-pulse text-sm text-[var(--color-text-muted)]">
            Running deep dive analysis…
          </span>
        </div>
      )}

      {!data && !loading && !error && (
        <p className="text-sm text-[var(--color-text-muted)] text-center py-6">
          No analysis yet. Click Run Analysis to start.
        </p>
      )}

      {data && (
        <div className="space-y-4">
          {/* Business Model */}
          <section>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
              Business Model
            </p>
            <p className="text-sm text-[var(--color-text-primary)]">{data.business_model}</p>
          </section>

          {/* Moat */}
          <section>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
              Moat · <span className="normal-case font-normal">{data.moat.edge_type.replace(/_/g, " ")}</span>
            </p>
            <p className="text-sm text-[var(--color-text-primary)] mb-1">{data.moat.summary}</p>
            <div className="flex gap-2 flex-wrap">
              {data.moat.competitors.map((c) => (
                <span
                  key={c}
                  className="text-xs px-2 py-0.5 rounded-md border border-[var(--border)] text-[var(--color-text-muted)]"
                >
                  {c}
                </span>
              ))}
            </div>
          </section>

          {/* Catalysts */}
          <section>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
              Catalysts (next 12 months)
            </p>
            <ul className="space-y-1">
              {data.catalysts.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className={`mt-0.5 text-xs font-medium ${IMPACT_COLOR[c.impact]}`}>
                    {c.impact.toUpperCase()}
                  </span>
                  <span className="text-[var(--color-text-primary)]">
                    {c.title} <span className="text-[var(--color-text-muted)]">· {c.timeframe}</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {/* Asymmetry */}
          <section>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
              Asymmetry ·{" "}
              <span className={`normal-case font-semibold ${ASYMMETRY_COLOR[data.asymmetry.verdict]}`}>
                {data.asymmetry.verdict.toUpperCase()}
              </span>
            </p>
            <div className="grid grid-cols-2 gap-3 text-sm mb-2">
              <div>
                <p className="text-xs text-[var(--color-text-muted)]">Floor</p>
                <p className="text-[var(--color-text-primary)]">{data.asymmetry.floor}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--color-text-muted)]">Ceiling</p>
                <p className="text-[var(--color-text-primary)]">{data.asymmetry.ceiling}</p>
              </div>
            </div>
            <p className="text-sm text-[var(--color-text-muted)]">{data.asymmetry.reasoning}</p>
          </section>
        </div>
      )}
    </div>
  )
}
```

---

## Task 4: BearCaseCard component

**Files:**
- Create: `frontend/components/analysis/BearCaseCard.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/analysis/BearCaseCard.tsx
"use client"

import { Button } from "@/components/ui/button"
import type { BearCaseData } from "@/lib/services/analysis-ai"

const SEVERITY_STYLE: Record<string, string> = {
  high: "bg-[var(--color-signal-loss-bg)] text-[var(--brand-danger)] border-[var(--brand-danger)]/30",
  medium: "bg-[var(--color-signal-gain-bg)] text-[var(--color-ink-muted)] border-[var(--border)]",
  low: "bg-[var(--card)] text-[var(--color-ink-muted)] border-[var(--border)]",
}

const SOURCE_LABEL: Record<string, string> = {
  yfinance: "Data",
  llm_knowledge: "LLM",
}

interface Props {
  ticker: string
  data: BearCaseData | null
  loading: boolean
  error: string | null
  onTrigger: () => void
}

export function BearCaseCard({ ticker, data, loading, error, onTrigger }: Props) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
            {ticker} Bear Case
          </h2>
          {data && (
            <p className="text-xs text-[var(--color-text-muted)]">
              {new Date(data.created_at).toLocaleString()} · {data.model}
            </p>
          )}
        </div>
        <Button
          onClick={onTrigger}
          disabled={loading}
          className="px-3 py-1 text-xs font-medium"
        >
          {loading ? "Analyzing…" : data ? "Re-run" : "Run Analysis"}
        </Button>
      </div>

      {error && <p className="text-xs text-[var(--brand-danger)]">{error}</p>}

      {loading && !data && (
        <div className="flex items-center gap-2 py-6 justify-center">
          <span className="animate-pulse text-sm text-[var(--color-text-muted)]">
            Analyzing risks…
          </span>
        </div>
      )}

      {!data && !loading && !error && (
        <p className="text-sm text-[var(--color-text-muted)] text-center py-6">
          No analysis yet. Click Run Analysis to start.
        </p>
      )}

      {data && (
        <div className="space-y-3">
          {data.red_flags.map((flag) => (
            <div
              key={flag.rank}
              className={`rounded-lg border p-4 space-y-1 ${SEVERITY_STYLE[flag.severity]}`}
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold">
                  #{flag.rank} {flag.title}
                </p>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs px-1.5 py-0.5 rounded border border-current/30 uppercase font-medium">
                    {flag.severity}
                  </span>
                  <span className="text-xs px-1.5 py-0.5 rounded border border-current/20 opacity-70">
                    {SOURCE_LABEL[flag.data_source]}
                  </span>
                </div>
              </div>
              <p className="text-xs font-medium opacity-80">{flag.evidence}</p>
              <p className="text-xs opacity-70">{flag.detail}</p>
            </div>
          ))}

          <div className="pt-2 border-t border-[var(--border)]">
            <p className="text-xs text-[var(--color-text-muted)]">{data.summary}</p>
          </div>
        </div>
      )}
    </div>
  )
}
```

---

## Task 5: PeerComparisonCard component

**Files:**
- Create: `frontend/components/analysis/PeerComparisonCard.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/analysis/PeerComparisonCard.tsx
"use client"

import { Button } from "@/components/ui/button"
import type { PeerComparisonData, PeerRow } from "@/lib/services/analysis-ai"

const LABEL_STYLE: Record<string, string> = {
  BEST: "bg-[var(--color-signal-gain-bg)] text-[var(--color-signal-gain)] border-[var(--color-signal-gain)]/30",
  FAIR: "bg-[var(--card)] text-[var(--color-ink-muted)] border-[var(--border)]",
  AVOID: "bg-[var(--color-signal-loss-bg)] text-[var(--brand-danger)] border-[var(--brand-danger)]/30",
}

function fmt(v: number | null | undefined, decimals = 1, suffix = ""): string {
  if (v === null || v === undefined) return "N/A"
  return `${v.toFixed(decimals)}${suffix}`
}

function PeerTableRow({ row }: { row: PeerRow }) {
  return (
    <tr className="border-t border-[var(--border)]">
      <td className="py-3 pr-4">
        <div className="flex items-center gap-2">
          <span
            className={`text-xs px-2 py-0.5 rounded border font-semibold ${LABEL_STYLE[row.label]}`}
          >
            {row.label}
          </span>
          <div>
            <p className="text-sm font-semibold text-[var(--color-text-primary)]">{row.ticker}</p>
            <p className="text-xs text-[var(--color-text-muted)]">{row.company_name}</p>
          </div>
        </div>
      </td>
      <td className="py-3 px-2 text-right text-sm text-[var(--color-text-primary)]">
        {fmt(row.ps_ttm, 1, "x")}
        {row.ps_forward != null && (
          <span className="text-xs text-[var(--color-text-muted)] block">
            Fwd {fmt(row.ps_forward, 1, "x")}
          </span>
        )}
      </td>
      <td className="py-3 px-2 text-right text-sm text-[var(--color-text-primary)]">
        {fmt(row.ev_ebitda, 0, "x")}
      </td>
      <td className="py-3 px-2 text-right text-sm text-[var(--color-text-primary)]">
        {fmt(row.gross_margin_pct, 1, "%")}
      </td>
      <td className="py-3 px-2 text-right text-sm text-[var(--color-text-primary)]">
        {row.yoy_revenue_growth_pct != null
          ? `+${fmt(row.yoy_revenue_growth_pct, 0, "%")}`
          : "N/A"}
        {row.revenue_trend && (
          <span className="text-xs text-[var(--color-text-muted)] block">{row.revenue_trend}</span>
        )}
      </td>
      <td className="py-3 pl-2 text-right">
        <span className={`text-sm font-bold ${LABEL_STYLE[row.label].split(" ")[1]}`}>
          {fmt(row.value_growth_score, 2)}
        </span>
      </td>
    </tr>
  )
}

interface Props {
  ticker: string
  data: PeerComparisonData | null
  loading: boolean
  error: string | null
  onTrigger: () => void
}

export function PeerComparisonCard({ ticker, data, loading, error, onTrigger }: Props) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
            Peer Comparison
          </p>
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
            Relative Valuation
            {data?.sector_label ? ` — ${data.sector_label}` : ""}
          </h2>
          {data && (
            <p className="text-xs text-[var(--color-text-muted)]">
              {new Date(data.created_at).toLocaleString()} · {data.model}
            </p>
          )}
        </div>
        <Button
          onClick={onTrigger}
          disabled={loading}
          className="px-3 py-1 text-xs font-medium"
        >
          {loading ? "Analyzing…" : data ? "Re-run" : "Run Analysis"}
        </Button>
      </div>

      {error && <p className="text-xs text-[var(--brand-danger)]">{error}</p>}

      {loading && !data && (
        <div className="flex items-center gap-2 py-6 justify-center">
          <span className="animate-pulse text-sm text-[var(--color-text-muted)]">
            Discovering peers and fetching financial data…
          </span>
        </div>
      )}

      {!data && !loading && !error && (
        <p className="text-sm text-[var(--color-text-muted)] text-center py-6">
          No analysis yet. Click Run Analysis to start.
        </p>
      )}

      {data && (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr>
                <th className="pb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  Ticker
                </th>
                <th className="pb-2 px-2 text-right text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  P/S (TTM)
                </th>
                <th className="pb-2 px-2 text-right text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  EV/EBITDA
                </th>
                <th className="pb-2 px-2 text-right text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  Gross Margin
                </th>
                <th className="pb-2 px-2 text-right text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  YoY Rev Growth
                </th>
                <th className="pb-2 pl-2 text-right text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  Value/Growth
                </th>
              </tr>
            </thead>
            <tbody>
              {data.ranked.map((row) => (
                <PeerTableRow key={row.ticker} row={row} />
              ))}
            </tbody>
          </table>
          <p className="text-xs text-[var(--color-text-muted)] mt-3">
            {data.methodology_note} — Lowest score = best value per dollar of growth.
          </p>
        </div>
      )}
    </div>
  )
}
```

---

## Task 6: CombinedVerdictCard component

**Files:**
- Create: `frontend/components/analysis/CombinedVerdictCard.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/analysis/CombinedVerdictCard.tsx
"use client"

import { Button } from "@/components/ui/button"
import type { CombinedVerdictData, VerdictLabel } from "@/lib/services/analysis-ai"

const VERDICT_STYLE: Record<VerdictLabel, { bg: string; text: string; label: string }> = {
  strong_buy: { bg: "bg-[var(--color-signal-gain-bg)]", text: "text-[var(--color-signal-gain)]", label: "Strong Buy" },
  buy:        { bg: "bg-[var(--color-signal-gain-bg)]", text: "text-[var(--color-signal-gain)]", label: "Buy" },
  hold:       { bg: "bg-[var(--card)]",                 text: "text-[var(--color-text-muted)]",  label: "Hold" },
  sell:       { bg: "bg-[var(--color-signal-loss-bg)]", text: "text-[var(--brand-danger)]",      label: "Sell" },
  strong_sell:{ bg: "bg-[var(--color-signal-loss-bg)]", text: "text-[var(--brand-danger)]",      label: "Strong Sell" },
}

const TOTAL_ANALYSES = 4

const ANALYSIS_LABELS: Record<string, string> = {
  top_down_analysis: "Top-Down",
  deep_dive: "Deep Dive",
  peer_comparison: "Peer Comparison",
  bear_case: "Bear Case",
}

interface Props {
  ticker: string
  data: CombinedVerdictData | null
  availableCount: number
  loading: boolean
  error: string | null
  onTrigger: () => void
}

export function CombinedVerdictCard({
  ticker,
  data,
  availableCount,
  loading,
  error,
  onTrigger,
}: Props) {
  const style = data ? VERDICT_STYLE[data.verdict] : null

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
            Combined Verdict
          </p>
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">{ticker}</h2>
          {data && (
            <p className="text-xs text-[var(--color-text-muted)]">
              {new Date(data.created_at).toLocaleString()} · {data.model}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[var(--color-text-muted)]">
            {availableCount}/{TOTAL_ANALYSES} analyses available
          </span>
          <Button
            onClick={onTrigger}
            disabled={loading || availableCount === 0}
            className="px-3 py-1 text-xs font-medium"
          >
            {loading ? "Synthesizing…" : data ? "Re-run" : "Synthesize"}
          </Button>
        </div>
      </div>

      {error && <p className="text-xs text-[var(--brand-danger)]">{error}</p>}

      {availableCount === 0 && !data && (
        <p className="text-sm text-[var(--color-text-muted)] text-center py-6">
          Run at least one analysis below first.
        </p>
      )}

      {loading && !data && (
        <div className="flex items-center gap-2 py-6 justify-center">
          <span className="animate-pulse text-sm text-[var(--color-text-muted)]">
            Synthesizing all analyses…
          </span>
        </div>
      )}

      {data && style && (
        <div className="space-y-4">
          {/* Verdict + conviction */}
          <div className={`rounded-lg p-4 ${style.bg} flex items-center justify-between`}>
            <span className={`text-2xl font-bold ${style.text}`}>
              {style.label}
            </span>
            <div className="text-right">
              <p className="text-xs text-[var(--color-text-muted)]">Conviction</p>
              <p className={`text-xl font-bold ${style.text}`}>{data.conviction}/10</p>
            </div>
          </div>

          {/* Based on */}
          <div className="flex gap-1.5 flex-wrap">
            {data.based_on.map((key) => (
              <span
                key={key}
                className="text-xs px-2 py-0.5 rounded border border-[var(--border)] text-[var(--color-text-muted)]"
              >
                {ANALYSIS_LABELS[key] ?? key}
              </span>
            ))}
          </div>

          {/* Bull / Bear */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-[var(--color-signal-gain)] uppercase tracking-wide">
                Bull Thesis
              </p>
              <p className="text-sm text-[var(--color-text-primary)]">{data.bull_thesis}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs font-semibold text-[var(--brand-danger)] uppercase tracking-wide">
                Bear Thesis
              </p>
              <p className="text-sm text-[var(--color-text-primary)]">{data.bear_thesis}</p>
            </div>
          </div>

          {/* Key risks */}
          {data.key_risks.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
                Key Risks
              </p>
              <ul className="list-disc list-inside space-y-0.5">
                {data.key_risks.map((r, i) => (
                  <li key={i} className="text-sm text-[var(--color-text-primary)]">{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Reasoning */}
          <div className="pt-2 border-t border-[var(--border)]">
            <p className="text-xs text-[var(--color-text-muted)]">{data.reasoning}</p>
          </div>
        </div>
      )}
    </div>
  )
}
```

---

## Task 7: Refactor symbol page to include all cards

**Files:**
- Modify: `frontend/app/(auth)/analysis/[symbol]/page.tsx`

Replace the entire file content:

- [ ] **Step 1: Replace page.tsx**

```tsx
// frontend/app/(auth)/analysis/[symbol]/page.tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { toast } from 'sonner'

import { TopDownAnalysisCard } from '@/components/analysis/TopDownAnalysisCard'
import { PipelineFlow, PipelineJob } from '@/components/analysis/PipelineFlow'
import { DeepDiveCard } from '@/components/analysis/DeepDiveCard'
import { BearCaseCard } from '@/components/analysis/BearCaseCard'
import { PeerComparisonCard } from '@/components/analysis/PeerComparisonCard'
import { CombinedVerdictCard } from '@/components/analysis/CombinedVerdictCard'

import { useAnalysisPolling } from '@/hooks/useAnalysisPolling'
import {
  fetchDeepDive, triggerDeepDive,
  fetchBearCase, triggerBearCase,
  fetchPeerComparison, triggerPeerComparison,
  fetchCombinedVerdict, triggerCombinedVerdict,
  type DeepDiveData, type BearCaseData,
  type PeerComparisonData, type CombinedVerdictData,
} from '@/lib/services/analysis-ai'
import { api } from '@/lib/api'

// ── Top-down types (existing) ─────────────────────────────────

type TopDownAnalysisData = {
  id: string
  mega_trend: string
  financial_health: string
  swot: {
    strengths: string[]
    weaknesses: string[]
    opportunities: string[]
    threats: string[]
  }
  verdict: 'BUY' | 'SELL' | 'HOLD'
  target_price: number | null
  created_at: string
  documents: {
    id: string
    filename: string
    file_path: string
    source_url: string | null
    status: string
  }[]
}

async function fetchLatestTopDown(symbol: string): Promise<TopDownAnalysisData | null> {
  try {
    const res = await api.get(`/api/v1/analysis/top-down/${symbol}/latest`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

async function fetchLatestPipelineJob(jobType: string): Promise<PipelineJob | null> {
  try {
    const res = await api.get(`/api/v1/pipeline/jobs?job_type=${jobType}&limit=1`)
    if (!res.ok) return null
    const jobs: PipelineJob[] = await res.json()
    return jobs[0] ?? null
  } catch {
    return null
  }
}

export default function AnalysisPage() {
  const { symbol } = useParams<{ symbol: string }>()

  // ── Top-down (existing pattern, unchanged) ────────────────
  const [topDownData, setTopDownData] = useState<TopDownAnalysisData | null>(null)
  const [topDownLoading, setTopDownLoading] = useState(false)
  const [topDownError, setTopDownError] = useState<string | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [pipelineJob, setPipelineJob] = useState<PipelineJob | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    fetchLatestTopDown(symbol)
      .then((json) => setTopDownData(json))
      .finally(() => setInitialLoading(false))
  }, [symbol])

  function stopTopDownPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  async function triggerTopDown() {
    setTopDownLoading(true)
    setTopDownError(null)
    setPipelineJob(null)
    const prevId = topDownData?.id ?? null
    try {
      await api.post(`/api/v1/analysis/top-down/${symbol}`, {})
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to trigger analysis'
      setTopDownError(msg)
      toast.error(msg)
      setTopDownLoading(false)
      return
    }
    stopTopDownPolling()
    pollRef.current = setInterval(async () => {
      const job = await fetchLatestPipelineJob('run_top_down_analysis')
      if (job) setPipelineJob(job)
      if (job && (job.status === 'done' || job.status === 'failed')) {
        stopTopDownPolling()
        if (job.status === 'done') {
          const latest = await fetchLatestTopDown(symbol)
          if (latest && latest.id !== prevId) { setTopDownData(latest); setTopDownError(null) }
        } else {
          const msg = job.error_message ?? 'Analysis failed'
          setTopDownError(msg)
          toast.error(msg)
        }
        setTopDownLoading(false)
      }
    }, 2000)
  }

  useEffect(() => () => stopTopDownPolling(), [])

  // ── New features via useAnalysisPolling ───────────────────

  const deepDive = useAnalysisPolling<DeepDiveData>(
    () => triggerDeepDive(symbol),
    { fetchFn: () => fetchDeepDive(symbol) },
  )

  const bearCase = useAnalysisPolling<BearCaseData>(
    () => triggerBearCase(symbol),
    { fetchFn: () => fetchBearCase(symbol) },
  )

  const peerComparison = useAnalysisPolling<PeerComparisonData>(
    () => triggerPeerComparison(symbol),
    { fetchFn: () => fetchPeerComparison(symbol) },
  )

  const combinedVerdict = useAnalysisPolling<CombinedVerdictData>(
    () => triggerCombinedVerdict(symbol),
    { fetchFn: () => fetchCombinedVerdict(symbol) },
  )

  // Load initial data for all 4 new features
  useEffect(() => {
    fetchDeepDive(symbol).then((d) => deepDive.setData(d))
    fetchBearCase(symbol).then((d) => bearCase.setData(d))
    fetchPeerComparison(symbol).then((d) => peerComparison.setData(d))
    fetchCombinedVerdict(symbol).then((d) => combinedVerdict.setData(d))
  }, [symbol])

  const availableCount = [topDownData, deepDive.data, bearCase.data, peerComparison.data]
    .filter(Boolean).length

  if (initialLoading) {
    return (
      <div className="flex min-h-[200px] items-center justify-center">
        <span className="text-sm text-[var(--color-text-muted)]">Loading…</span>
      </div>
    )
  }

  return (
    <div className="space-y-4 p-4 max-w-5xl mx-auto">

      {/* Combined Verdict — top, prominent */}
      <CombinedVerdictCard
        ticker={symbol}
        data={combinedVerdict.data}
        availableCount={availableCount}
        loading={combinedVerdict.loading}
        error={combinedVerdict.error}
        onTrigger={combinedVerdict.trigger}
      />

      {/* 4 analysis cards in 2-column grid on large screens */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top-Down (existing) */}
        {!topDownData ? (
          <div className="flex flex-col items-center justify-center gap-4 py-12 rounded-xl border border-[var(--border)] bg-[var(--card)]">
            <p className="text-sm text-[var(--color-text-muted)]">
              {topDownError ?? `No top-down analysis for`} <strong>{symbol}</strong>
            </p>
            <button
              onClick={triggerTopDown}
              disabled={topDownLoading}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-[var(--brand-accent)] text-white disabled:opacity-50"
            >
              {topDownLoading ? 'Running…' : 'Fetch & Analyze'}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <TopDownAnalysisCard
              data={topDownData}
              ticker={symbol}
              onRefresh={triggerTopDown}
              loading={topDownLoading}
            />
            {!topDownLoading && pipelineJob && (
              <PipelineFlow job={pipelineJob} title="Last Pipeline Run" />
            )}
          </div>
        )}

        {/* Deep Dive */}
        <DeepDiveCard
          ticker={symbol}
          data={deepDive.data}
          loading={deepDive.loading}
          error={deepDive.error}
          onTrigger={deepDive.trigger}
        />

        {/* Peer Comparison */}
        <PeerComparisonCard
          ticker={symbol}
          data={peerComparison.data}
          loading={peerComparison.loading}
          error={peerComparison.error}
          onTrigger={peerComparison.trigger}
        />

        {/* Bear Case */}
        <BearCaseCard
          ticker={symbol}
          data={bearCase.data}
          loading={bearCase.loading}
          error={bearCase.error}
          onTrigger={bearCase.trigger}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors

- [ ] **Step 3: Start dev server and test manually**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/analysis/AMD` (or any ticker in your holdings).

Verify:
1. Combined Verdict card shows at top with "X/4 analyses available"
2. Top-Down card renders (existing behavior unchanged)
3. Deep Dive card shows "No analysis yet" with Run button
4. Peer Comparison card shows "No analysis yet" with Run button
5. Bear Case card shows "No analysis yet" with Run button
6. Click "Run Analysis" on Deep Dive — button changes to "Analyzing…"
7. After ~30s the card populates with data (no manual refresh needed)
8. Check `http://localhost:3000/ai-usage` — new `deep_dive` entries appear in the log

---

## Completion Checklist

- [ ] `frontend/lib/services/analysis-ai.ts` created with all types + fetch functions
- [ ] `frontend/hooks/useAnalysisPolling.ts` created
- [ ] `DeepDiveCard.tsx` created and renders correctly
- [ ] `BearCaseCard.tsx` created with severity styles and data_source badges
- [ ] `PeerComparisonCard.tsx` created with BEST/FAIR/AVOID labels
- [ ] `CombinedVerdictCard.tsx` created with verdict display and conviction meter
- [ ] `analysis/[symbol]/page.tsx` updated with all 5 cards
- [ ] `tsc --noEmit` passes with no errors
- [ ] Manual test: trigger one analysis, confirm auto-update without refresh
- [ ] Manual test: check AI Usage page shows new feature_key entries
- [ ] Manual test: Settings → AI shows all 4 new feature rows
