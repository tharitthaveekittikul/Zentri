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
