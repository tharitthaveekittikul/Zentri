import { api } from "@/lib/api";

export type JobType =
  | "price_fetch_us"
  | "price_fetch_crypto"
  | "price_fetch_gold"
  | "price_fetch_benchmark"
  | "price_fetch_thai_stock"
  | "price_fetch_th_fund"
  | "watchlist_discovery"
  | "watchlist_scan"
  | "run_analysis"
  | "ingest_document";

export type JobStatus = "queued" | "running" | "done" | "failed";
export type StepStatus = "running" | "done" | "failed";

export interface PipelineStep {
  id: string;
  pipeline_log_id: string;
  step_name: string;
  status: StepStatus;
  started_at: string;
  finished_at: string | null;
  metadata: Record<string, unknown> | null;
  error_message: string | null;
}

export interface PipelineJob {
  id: string;
  job_type: JobType;
  status: JobStatus;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  steps: PipelineStep[];
}

export async function fetchJobs(limit = 50): Promise<PipelineJob[]> {
  const res = await api.get(`/api/v1/pipeline/jobs?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch pipeline jobs");
  return res.json();
}

export async function triggerJob(
  job_type: JobType,
): Promise<{ enqueued: boolean; job_id: string | null }> {
  const res = await api.post(`/api/v1/pipeline/trigger/${job_type}`, {});
  if (!res.ok) throw new Error("Failed to trigger job");
  return res.json();
}
