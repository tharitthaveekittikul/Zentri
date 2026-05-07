"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { triggerJob, type JobType } from "@/lib/services/pipeline";
import { toast } from "sonner";

const JOBS: { key: JobType; label: string }[] = [
  { key: "price_fetch_us", label: "US Stock" },
  { key: "price_fetch_crypto", label: "Crypto" },
  { key: "price_fetch_gold", label: "Gold" },
  { key: "price_fetch_thai_stock", label: "Thai Stock/DR" },
  { key: "price_fetch_th_fund", label: "Thai Fund" },
  { key: "price_fetch_benchmark", label: "Benchmark" },
];

export function TriggerButtons() {
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  async function handleTrigger(key: JobType, label: string) {
    setLoading((prev) => ({ ...prev, [key]: true }));
    try {
      await triggerJob(key);
      toast.success(`${label} job enqueued`);
    } catch {
      toast.error(`Failed to trigger ${label}`);
    } finally {
      setLoading((prev) => ({ ...prev, [key]: false }));
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {JOBS.map(({ key, label }) => (
        <Button
          key={key}
          variant="outline"
          size="sm"
          disabled={!!loading[key]}
          onClick={() => handleTrigger(key, label)}
        >
          {loading[key] ? "Running…" : `▶ ${label}`}
        </Button>
      ))}
    </div>
  );
}
