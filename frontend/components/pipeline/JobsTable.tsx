"use client";

import React, { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type PipelineJob,
  type JobType,
  triggerJob,
} from "@/lib/services/pipeline";
import { StepList } from "@/components/pipeline/StepList";
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
  watchlist_discovery: "Watchlist Discovery",
  watchlist_scan: "Watchlist Scan",
  run_analysis: "AI Analysis",
  ingest_document: "Ingest Document",
};

const ALL_TRIGGER_TYPES: JobType[] = [
  "price_fetch_us",
  "price_fetch_crypto",
  "price_fetch_gold",
  "price_fetch_benchmark",
];

interface JobsTableProps {
  jobs: PipelineJob[];
}

export function JobsTable({ jobs }: JobsTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  function toggleExpand(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

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
          {ALL_TRIGGER_TYPES.map((jt) => (
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
              <th className="text-left py-2 pr-2 w-4"></th>
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
                  colSpan={5}
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
              const isExpanded = expandedIds.has(job.id);

              return (
                <React.Fragment key={job.id}>
                  <tr
                    className="border-b cursor-pointer hover:bg-muted/40 transition-colors"
                    onClick={() => toggleExpand(job.id)}
                  >
                    <td className="py-2 pr-2 text-muted-foreground text-xs">
                      {isExpanded ? "▴" : "▾"}
                    </td>
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
                  {isExpanded && (
                    <tr className="border-b bg-muted/20">
                      <td colSpan={5} className="py-2 px-2">
                        <StepList steps={job.steps ?? []} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
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
