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
