'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { TopDownAnalysisCard } from '@/components/analysis/TopDownAnalysisCard'
import { PipelineFlow, PipelineJob } from '@/components/analysis/PipelineFlow'
import { api } from '@/lib/api'

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

async function fetchLatestAnalysis(symbol: string): Promise<TopDownAnalysisData | null> {
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
  const [data, setData] = useState<TopDownAnalysisData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [pipelineJob, setPipelineJob] = useState<PipelineJob | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    fetchLatestAnalysis(symbol)
      .then((json) => setData(json))
      .finally(() => setInitialLoading(false))
  }, [symbol])

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function trigger() {
    setLoading(true)
    setError(null)
    setPipelineJob(null)
    const prevId = data?.id ?? null

    try {
      await api.post(`/api/v1/analysis/top-down/${symbol}`, {})
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to trigger analysis'
      setError(msg)
      toast.error(msg)
      setLoading(false)
      return
    }

    // Poll pipeline job steps for live visualization, and analysis endpoint for completion
    stopPolling()
    pollRef.current = setInterval(async () => {
      const job = await fetchLatestPipelineJob('run_top_down_analysis')
      if (job) setPipelineJob(job)

      if (job && (job.status === 'done' || job.status === 'failed')) {
        stopPolling()
        if (job.status === 'done') {
          const latest = await fetchLatestAnalysis(symbol)
          if (latest && latest.id !== prevId) {
            setData(latest)
            setError(null)
            toast.success('Top-down analysis complete')
          }
        } else {
          const errMsg = job.error_message ?? 'Analysis failed — check pipeline logs'
          setError(errMsg)
          toast.error(errMsg)
        }
        setLoading(false)
      }
    }, 2000)
  }

  useEffect(() => () => stopPolling(), [])

  if (initialLoading) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-sm text-[var(--color-text-muted)]">
        Loading…
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6">
      {loading && pipelineJob && (
        <PipelineFlow job={pipelineJob} title="Analysis Pipeline" />
      )}

      {!data ? (
        <div className="flex flex-col items-center justify-center gap-4 py-12">
          <p className="text-sm text-[var(--color-text-muted)]">
            {error ?? `No analysis found for`} <strong>{symbol}</strong>
          </p>
          <Button
            onClick={trigger}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium"
          >
            {loading ? 'Running…' : 'Fetch & Analyze'}
          </Button>
        </div>
      ) : (
        <TopDownAnalysisCard
          data={data}
          ticker={symbol}
          onRefresh={trigger}
          loading={loading}
        />
      )}

      {!loading && pipelineJob && (
        <PipelineFlow job={pipelineJob} title="Last Pipeline Run" />
      )}
    </div>
  )
}
