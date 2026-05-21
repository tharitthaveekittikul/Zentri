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
