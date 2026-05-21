'use client'

import { SwotGrid } from './SwotGrid'
import { DocumentsList } from './DocumentsList'
import { Button } from '@/components/ui/button'

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

const verdictStyle: Record<string, string> = {
  BUY: 'var(--color-success)',
  SELL: 'var(--color-destructive)',
  HOLD: 'var(--color-warning)',
}

type Props = {
  data: TopDownAnalysisData
  ticker: string
  onRefresh: () => void
  loading: boolean
}

export function TopDownAnalysisCard({ data, ticker, onRefresh, loading }: Props) {
  return (
    <div className="space-y-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
            {ticker} Top-Down Analysis
          </h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            {new Date(data.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {data.target_price && (
            <span className="text-sm text-[var(--color-text-secondary)]">
              Target: {data.target_price.toFixed(2)}
            </span>
          )}
          <span
            className="rounded-full px-3 py-1 text-sm font-bold text-white"
            style={{ backgroundColor: verdictStyle[data.verdict] ?? 'var(--color-text-muted)' }}
          >
            {data.verdict}
          </span>
        </div>
      </div>

      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          Mega Trend
        </p>
        <p className="text-sm text-[var(--color-text-primary)]">{data.mega_trend}</p>
      </div>

      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          Financial Health
        </p>
        <p className="text-sm text-[var(--color-text-primary)]">{data.financial_health}</p>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          SWOT Analysis
        </p>
        <SwotGrid swot={data.swot} />
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
            Documents used ({data.documents.length})
          </p>
          <Button
            onClick={onRefresh}
            disabled={loading}
            className="px-3 py-1 text-xs font-medium"
          >
            {loading ? 'Running…' : 'Fetch & Analyze'}
          </Button>
        </div>
        <DocumentsList documents={data.documents} ticker={ticker} />
      </div>
    </div>
  )
}
