'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { PipelineFlow, PipelineJob } from '@/components/analysis/PipelineFlow'
import { TickerSearchInput } from '@/components/analysis/TickerSearchInput'

type AnalysisSummary = {
  symbol: string
  verdict: 'BUY' | 'SELL' | 'HOLD'
  target_price: number | null
  ath_drop_pct: number | null
  created_at: string
}

const verdictColor: Record<string, string> = {
  BUY: 'var(--color-success)',
  SELL: 'var(--color-destructive)',
  HOLD: 'var(--color-warning)',
}

async function fetchJob(jobType: string): Promise<PipelineJob | null> {
  try {
    const res = await api.get(`/api/v1/pipeline/jobs?job_type=${jobType}&limit=1`)
    if (!res.ok) return null
    const jobs: PipelineJob[] = await res.json()
    return jobs[0] ?? null
  } catch {
    return null
  }
}

export default function AnalysisIndexPage() {
  const [rows, setRows] = useState<AnalysisSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [discovering, setDiscovering] = useState(false)
  const [showTickerSearch, setShowTickerSearch] = useState(false)
  const [discoveryJob, setDiscoveryJob] = useState<PipelineJob | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  async function load() {
    try {
      const res = await api.get('/api/v1/analysis/top-down/all')
      const data = await res.json()
      setRows(Array.isArray(data) ? data : [])
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function discover() {
    setDiscovering(true)
    setDiscoveryJob(null)

    try {
      await api.post('/api/v1/analysis/top-down/discover', null)
      toast.success('Discovery started — identifying mega-trend sectors…')
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to trigger discovery'
      toast.error(msg)
      setDiscovering(false)
      return
    }

    stopPolling()
    pollRef.current = setInterval(async () => {
      const job = await fetchJob('top_down_discovery')
      if (job) setDiscoveryJob(job)

      if (job && (job.status === 'done' || job.status === 'failed')) {
        stopPolling()
        setDiscovering(false)
        if (job.status === 'done') {
          toast.success('Discovery complete — analysis jobs queued')
          setTimeout(() => load(), 5000)
        } else {
          toast.error(job.error_message ?? 'Discovery failed')
        }
      }
    }, 2000)
  }

  useEffect(() => {
    load()
    return () => stopPolling()
  }, [])

  return (
    <div className="mx-auto max-w-3xl py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
          Top-Down Analysis
        </h1>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => setShowTickerSearch(v => !v)}
            variant="outline"
            className="px-4 py-2 text-sm font-medium"
          >
            Analyze Ticker
          </Button>
          <Button
            onClick={discover}
            disabled={discovering}
            className="px-4 py-2 text-sm font-medium"
          >
            {discovering ? 'Scanning…' : '⟳ Discover Candidates'}
          </Button>
        </div>
      </div>

      {showTickerSearch && (
        <TickerSearchInput onClose={() => setShowTickerSearch(false)} />
      )}

      {(discovering || discoveryJob) && discoveryJob && (
        <PipelineFlow job={discoveryJob} title="Discovery Pipeline" />
      )}

      {loading ? (
        <div className="text-sm text-[var(--color-text-muted)]">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-8 text-center">
          <p className="text-sm text-[var(--color-text-muted)]">
            No analyses yet. Click <strong>⟳ Discover Candidates</strong> to screen mega-trend sectors for ATH pullbacks,
            or go to a stock in{' '}
            <Link href="/portfolio" className="text-[var(--color-brand)] underline">
              Portfolio
            </Link>{' '}
            and click <strong>Top-Down Analysis →</strong>.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)]">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">Symbol</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">Verdict</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">Target</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">ATH Drop</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">Date</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.symbol}
                  className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--color-brand)]/5 transition-colors"
                >
                  <td className="px-4 py-3 font-semibold text-[var(--color-text-primary)]">{row.symbol}</td>
                  <td className="px-4 py-3">
                    <span
                      className="rounded-full px-2.5 py-0.5 text-xs font-bold text-white"
                      style={{ backgroundColor: verdictColor[row.verdict] ?? 'var(--color-text-muted)' }}
                    >
                      {row.verdict}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-[var(--color-text-secondary)]">
                    {row.target_price != null ? row.target_price.toFixed(2) : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {row.ath_drop_pct != null ? (
                      <span className="text-[var(--color-destructive)] font-medium">
                        -{row.ath_drop_pct.toFixed(1)}%
                      </span>
                    ) : (
                      <span className="text-[var(--color-text-muted)]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-[var(--color-text-muted)]">
                    {new Date(row.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/analysis/${row.symbol}`}
                      className="text-xs text-[var(--color-brand)] underline hover:no-underline"
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
