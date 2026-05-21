'use client'

export type PipelineStep = {
  step_name: string
  status: 'running' | 'done' | 'failed'
  started_at: string
  finished_at: string | null
  metadata: Record<string, unknown> | null
  error_message: string | null
}

export type PipelineJob = {
  id: string
  job_type: string
  status: 'running' | 'done' | 'failed'
  started_at: string
  finished_at: string | null
  error_message: string | null
  steps: PipelineStep[]
}

const STEP_LABELS: Record<string, string> = {
  identify_sectors: 'Identify Sectors',
  screen_ath: 'Screen ATH',
  queue_analysis: 'Queue Jobs',
  load_asset: 'Load Asset',
  fetch_documents: 'Fetch Docs',
  rag_retrieval: 'RAG Search',
  llm_call: 'LLM Analysis',
  save_analysis: 'Save Results',
}

const JOB_STEP_ORDER: Record<string, string[]> = {
  top_down_discovery: ['identify_sectors', 'screen_ath', 'queue_analysis'],
  run_top_down_analysis: ['load_asset', 'fetch_documents', 'rag_retrieval', 'llm_call', 'save_analysis'],
}

function metaSummary(stepName: string, metadata: Record<string, unknown> | null): string | null {
  if (!metadata) return null
  switch (stepName) {
    case 'identify_sectors':
      return Array.isArray(metadata.sectors) && (metadata.sectors as string[]).length > 0
        ? (metadata.sectors as string[]).slice(0, 3).join(', ') + ((metadata.sectors as string[]).length > 3 ? '…' : '')
        : null
    case 'screen_ath':
      return metadata.qualified != null
        ? `${metadata.qualified} qualified / ${metadata.screened} screened`
        : null
    case 'queue_analysis':
      return metadata.queued != null ? `${metadata.queued} jobs queued` : null
    case 'fetch_documents':
      return metadata.new != null ? `${metadata.new} docs fetched` : null
    case 'rag_retrieval':
      return metadata.rag_chunks != null ? `${metadata.rag_chunks} chunks retrieved` : null
    case 'llm_call':
      return metadata.verdict ? `Verdict: ${metadata.verdict as string}` : null
    case 'save_analysis':
      return metadata.verdict ? `Saved: ${metadata.verdict as string}` : null
    default:
      return null
  }
}

function elapsedLabel(step: PipelineStep): string | null {
  const end = step.finished_at ? new Date(step.finished_at) : null
  if (!end) return null
  const ms = end.getTime() - new Date(step.started_at).getTime()
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

interface StepCardProps {
  name: string
  step: PipelineStep | null
  status: 'pending' | 'running' | 'done' | 'failed'
}

function StepCard({ name, step, status }: StepCardProps) {
  const styles = {
    pending: {
      border: 'var(--border)',
      iconColor: 'var(--color-text-muted)',
      icon: '○',
    },
    running: {
      border: 'var(--color-brand)',
      iconColor: 'var(--color-brand)',
      icon: '◌',
    },
    done: {
      border: 'var(--color-success)',
      iconColor: 'var(--color-success)',
      icon: '✓',
    },
    failed: {
      border: 'var(--color-destructive)',
      iconColor: 'var(--color-destructive)',
      icon: '✗',
    },
  }[status]

  const label = STEP_LABELS[name] ?? name
  const summary = step ? metaSummary(name, step.metadata) : null
  const elapsed = step ? elapsedLabel(step) : null

  return (
    <div
      className="rounded-lg border p-3 w-28 min-h-[88px] flex flex-col gap-1 flex-shrink-0"
      style={{ borderColor: styles.border }}
    >
      <div className="flex items-center gap-1.5">
        <span
          className={`text-sm leading-none flex-shrink-0 ${status === 'running' ? 'animate-pulse' : ''}`}
          style={{ color: styles.iconColor }}
        >
          {styles.icon}
        </span>
        <span className="text-xs font-semibold text-[var(--color-text-primary)] leading-tight">
          {label}
        </span>
      </div>
      {summary && (
        <p className="text-[10px] leading-tight text-[var(--color-text-secondary)]">{summary}</p>
      )}
      {elapsed && (
        <p className="text-[10px] text-[var(--color-text-muted)]">{elapsed}</p>
      )}
      {step?.error_message && (
        <p
          className="text-[10px] leading-tight text-[var(--color-destructive)] truncate"
          title={step.error_message}
        >
          {step.error_message.slice(0, 50)}
        </p>
      )}
    </div>
  )
}

interface PipelineFlowProps {
  job: PipelineJob
  title?: string
}

export function PipelineFlow({ job, title }: PipelineFlowProps) {
  const stepOrder = JOB_STEP_ORDER[job.job_type] ?? job.steps.map((s) => s.step_name)
  const stepMap = new Map(job.steps.map((s) => [s.step_name, s]))

  const overallStatus = job.status === 'done'
    ? 'Done'
    : job.status === 'failed'
    ? 'Failed'
    : 'Running…'

  const statusColor =
    job.status === 'done'
      ? 'var(--color-success)'
      : job.status === 'failed'
      ? 'var(--color-destructive)'
      : 'var(--color-brand)'

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
      {title && (
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wide">
            {title}
          </p>
          <span className="text-xs font-medium" style={{ color: statusColor }}>
            {overallStatus}
          </span>
        </div>
      )}

      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {stepOrder.map((name, i) => {
          const step = stepMap.get(name) ?? null
          const status: 'pending' | 'running' | 'done' | 'failed' = step
            ? (step.status as 'running' | 'done' | 'failed')
            : 'pending'

          return (
            <div key={name} className="flex items-center gap-1 flex-shrink-0">
              <StepCard name={name} step={step} status={status} />
              {i < stepOrder.length - 1 && (
                <span className="text-[var(--color-text-muted)] text-base leading-none">→</span>
              )}
            </div>
          )
        })}
      </div>

      {job.error_message && (
        <p className="text-xs text-[var(--color-destructive)]">{job.error_message}</p>
      )}
    </div>
  )
}
