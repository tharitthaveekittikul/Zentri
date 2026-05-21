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
