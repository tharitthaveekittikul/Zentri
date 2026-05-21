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

          {/* Price targets */}
          {(data.entry_price != null || data.target_price != null || data.stop_loss != null) && (
            <div className="grid grid-cols-4 gap-2 rounded-lg border border-[var(--border)] p-3">
              <div className="text-center">
                <p className="text-xs text-[var(--color-text-muted)] mb-0.5">Entry</p>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                  {data.entry_price != null ? `$${data.entry_price.toFixed(2)}` : "—"}
                </p>
              </div>
              <div className="text-center">
                <p className="text-xs text-[var(--color-text-muted)] mb-0.5">Target</p>
                <p className="text-sm font-semibold text-[var(--color-signal-gain)]">
                  {data.target_price != null ? `$${data.target_price.toFixed(2)}` : "—"}
                </p>
                {data.entry_price != null && data.target_price != null && (
                  <p className="text-xs text-[var(--color-signal-gain)]">
                    +{(((data.target_price - data.entry_price) / data.entry_price) * 100).toFixed(1)}%
                  </p>
                )}
              </div>
              <div className="text-center">
                <p className="text-xs text-[var(--color-text-muted)] mb-0.5">Stop</p>
                <p className="text-sm font-semibold text-[var(--brand-danger)]">
                  {data.stop_loss != null ? `$${data.stop_loss.toFixed(2)}` : "—"}
                </p>
                {data.entry_price != null && data.stop_loss != null && (
                  <p className="text-xs text-[var(--brand-danger)]">
                    {(((data.stop_loss - data.entry_price) / data.entry_price) * 100).toFixed(1)}%
                  </p>
                )}
              </div>
              <div className="text-center">
                <p className="text-xs text-[var(--color-text-muted)] mb-0.5">R/R</p>
                <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                  {data.risk_reward != null ? `${data.risk_reward.toFixed(1)}x` : "—"}
                </p>
              </div>
            </div>
          )}

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
