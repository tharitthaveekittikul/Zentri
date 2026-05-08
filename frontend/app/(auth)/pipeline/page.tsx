"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchJobs, type PipelineJob } from "@/lib/services/pipeline";
import { JobsTable } from "@/components/pipeline/JobsTable";
import { TriggerButtons } from "@/components/pipeline/TriggerButtons";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/layout/PageHeader";

export default function PipelinePage() {
  const { data: initialJobs = [], isLoading } = useQuery({
    queryKey: ["pipeline-jobs"],
    queryFn: () => fetchJobs(50),
  });

  const [jobs, setJobs] = useState<PipelineJob[]>([]);

  useEffect(() => {
    if (initialJobs.length > 0) setJobs(initialJobs);
  }, [initialJobs]);

  // SSE live updates — pass JWT as query param since EventSource can't send headers
  const sseRef = useRef<EventSource | null>(null);
  useEffect(() => {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("access_token")
        : null;

    const url = `/api/v1/pipeline/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`;
    const es = new EventSource(url);
    sseRef.current = es;

    es.onmessage = (e) => {
      try {
        const updated: PipelineJob[] = JSON.parse(e.data);
        setJobs(updated);
      } catch {
        // ignore parse errors
      }
    };

    return () => {
      es.close();
    };
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <PageHeader title="Pipeline" />
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Pipeline" />
      <p className="text-muted-foreground text-sm">
        Live price fetch job status. Updates every 3 seconds via SSE.
      </p>
      <TriggerButtons />
      <div className="bg-card card-surface rounded-2xl overflow-hidden overflow-x-auto">
        <JobsTable jobs={jobs} />
      </div>
    </div>
  );
}
