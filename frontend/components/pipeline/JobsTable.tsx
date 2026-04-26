"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type PipelineJob,
  type JobType,
  triggerJob,
} from "@/lib/services/pipeline";
import { toast } from "sonner";

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  done: "default",
  running: "secondary",
  queued: "outline",
  failed: "destructive",
};

const JOB_LABELS: Record<JobType, string> = {
  price_fetch_us: "US Stocks",
  price_fetch_crypto: "Crypto",
  price_fetch_gold: "Gold",
  price_fetch_benchmark: "Benchmarks",
};

const ALL_JOB_TYPES: JobType[] = [
  "price_fetch_us",
  "price_fetch_crypto",
  "price_fetch_gold",
  "price_fetch_benchmark",
];

interface JobsTableProps {
  jobs: PipelineJob[];
}

export function JobsTable({ jobs }: JobsTableProps) {
  async function handleTrigger(jobType: JobType) {
    try {
      await triggerJob(jobType);
      toast.success(`${JOB_LABELS[jobType]} job enqueued`);
    } catch {
      toast.error(`Failed to trigger ${JOB_LABELS[jobType]} job`);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Pipeline Jobs</CardTitle>
        <div className="flex gap-2 flex-wrap">
          {ALL_JOB_TYPES.map((jt) => (
            <Button
              key={jt}
              size="sm"
              variant="outline"
              onClick={() => handleTrigger(jt)}
            >
              Run {JOB_LABELS[jt]}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-muted-foreground">
              <th className="text-left py-2 pr-4">Job</th>
              <th className="text-left py-2 pr-4">Status</th>
              <th className="text-left py-2 pr-4">Started</th>
              <th className="text-left py-2">Duration</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  className="py-8 text-center text-muted-foreground"
                >
                  No jobs have run yet. Use the buttons above to trigger a fetch.
                </td>
              </tr>
            )}
            {jobs.map((job) => {
              const duration =
                job.finished_at && job.started_at
                  ? `${((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000).toFixed(1)}s`
                  : job.status === "running"
                    ? "running…"
                    : "—";
              return (
                <tr key={job.id} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-medium">
                    {JOB_LABELS[job.job_type as JobType] ?? job.job_type}
                  </td>
                  <td className="py-2 pr-4">
                    <Badge variant={STATUS_VARIANT[job.status] ?? "outline"}>
                      {job.status}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4 text-muted-foreground">
                    {new Date(job.started_at).toLocaleString()}
                  </td>
                  <td className="py-2 text-muted-foreground">{duration}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {jobs.some((j) => j.status === "failed") && (
          <div className="mt-4 space-y-2">
            {jobs
              .filter((j) => j.status === "failed" && j.error_message)
              .map((j) => (
                <p
                  key={j.id}
                  className="text-xs text-destructive font-mono bg-destructive/10 p-2 rounded"
                >
                  [{JOB_LABELS[j.job_type as JobType]}] {j.error_message}
                </p>
              ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
