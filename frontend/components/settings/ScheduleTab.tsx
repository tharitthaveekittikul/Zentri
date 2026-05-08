"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchScheduleConfigs,
  fetchScheduleTimezone,
  saveScheduleConfigs,
  saveScheduleTimezone,
  type ScheduleConfig,
} from "@/lib/services/schedule";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

const JOB_LABELS: Record<string, string> = {
  us_stock: "US Stock",
  thai_stock: "Thai Stock / DR",
  thai_fund: "Thai Fund",
  crypto: "Crypto",
  gold: "Gold",
  benchmark: "Benchmark",
};

const JOB_ORDER = ["us_stock", "thai_stock", "thai_fund", "crypto", "gold", "benchmark"];
const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const INTERVAL_OPTIONS: { value: string; label: string }[] = [
  { value: "once", label: "Once" },
  { value: "15", label: "Every 15 min" },
  { value: "30", label: "Every 30 min" },
  { value: "60", label: "Every hour" },
  { value: "120", label: "Every 2 hours" },
];

const TIMEZONES = [
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Hong_Kong",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Asia/Kolkata",
  "Asia/Dubai",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Australia/Sydney",
  "UTC",
];

function intervalToValue(minutes: number | null): string {
  return minutes === null ? "once" : String(minutes);
}

function valueToInterval(value: string): number | null {
  return value === "once" ? null : Number(value);
}

export function ScheduleTab() {
  const queryClient = useQueryClient();

  const { data: serverConfigs, isLoading: configsLoading } = useQuery({
    queryKey: ["schedule-configs"],
    queryFn: fetchScheduleConfigs,
  });

  const { data: serverTimezone, isLoading: tzLoading } = useQuery({
    queryKey: ["schedule-timezone"],
    queryFn: fetchScheduleTimezone,
  });

  const [configs, setConfigs] = useState<ScheduleConfig[]>([]);
  const [timezone, setTimezone] = useState("Asia/Bangkok");

  useEffect(() => {
    if (serverConfigs) setConfigs(serverConfigs);
  }, [serverConfigs]);

  useEffect(() => {
    if (serverTimezone) setTimezone(serverTimezone);
  }, [serverTimezone]);

  const { mutate: saveConfigs, isPending: savingConfigs } = useMutation({
    mutationFn: async () => {
      await saveScheduleTimezone(timezone);
      return saveScheduleConfigs(configs);
    },
    onSuccess: (data) => {
      setConfigs(data);
      queryClient.invalidateQueries({ queryKey: ["schedule-configs"] });
      queryClient.invalidateQueries({ queryKey: ["schedule-timezone"] });
      toast.success("Schedule saved");
    },
    onError: () => toast.error("Failed to save schedule"),
  });

  function updateConfig(jobKey: string, patch: Partial<ScheduleConfig>) {
    setConfigs((prev) =>
      prev.map((c) => (c.job_key === jobKey ? { ...c, ...patch } : c))
    );
  }

  function toggleDay(jobKey: string, day: number) {
    setConfigs((prev) =>
      prev.map((c) => {
        if (c.job_key !== jobKey) return c;
        const days = c.days.includes(day)
          ? c.days.filter((d) => d !== day)
          : [...c.days, day].sort((a, b) => a - b);
        return { ...c, days };
      })
    );
  }

  if (configsLoading || tzLoading) {
    return <p className="text-muted-foreground text-sm">Loading schedule…</p>;
  }

  const ordered = JOB_ORDER.map((key) =>
    configs.find((c) => c.job_key === key)
  ).filter(Boolean) as ScheduleConfig[];

  return (
    <div className="space-y-6">
      {/* Single list-card containing all schedule items */}
      <div className="bg-card card-surface rounded-2xl overflow-hidden divide-y divide-border">
        {/* Timezone item */}
        <div className="p-5 space-y-3">
          <span className="font-medium">Timezone</span>
          <div className="flex items-center gap-3 mt-2">
            <Label className="text-sm text-muted-foreground w-28 shrink-0">
              Your timezone
            </Label>
            <Select value={timezone} onValueChange={setTimezone}>
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIMEZONES.map((tz) => (
                  <SelectItem key={tz} value={tz}>
                    {tz}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Job items */}
        {ordered.map((config) => (
          <div key={config.job_key} className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-medium">
                {JOB_LABELS[config.job_key] ?? config.job_key}
              </span>
              <Switch
                checked={config.enabled}
                onCheckedChange={(v) => updateConfig(config.job_key, { enabled: v })}
              />
            </div>

            {/* Interval */}
            <div className="flex items-center gap-3">
              <Label className="text-sm text-muted-foreground w-28 shrink-0">
                Interval
              </Label>
              <Select
                value={intervalToValue(config.interval_minutes)}
                onValueChange={(v) =>
                  updateConfig(config.job_key, { interval_minutes: valueToInterval(v) })
                }
              >
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INTERVAL_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Time */}
            <div className="flex items-center gap-3">
              <Label className="text-sm text-muted-foreground w-28 shrink-0">
                Start time
              </Label>
              <Select
                value={String(config.run_at_hour)}
                onValueChange={(v) =>
                  updateConfig(config.job_key, { run_at_hour: Number(v) })
                }
              >
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Array.from({ length: 24 }, (_, i) => (
                    <SelectItem key={i} value={String(i)}>
                      {String(i).padStart(2, "0")}:00
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Days */}
            <div className="flex items-center gap-3">
              <Label className="text-sm text-muted-foreground w-28 shrink-0">
                Days
              </Label>
              <div className="flex gap-1">
                {DAY_LABELS.map((day, i) => (
                  <Button
                    key={day}
                    variant={config.days.includes(i) ? "default" : "outline"}
                    size="sm"
                    className="w-10 px-0 text-xs"
                    onClick={() => toggleDay(config.job_key, i)}
                  >
                    {day}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      <Button onClick={() => saveConfigs()} disabled={savingConfigs}>
        {savingConfigs ? "Saving…" : "Save Schedule"}
      </Button>
    </div>
  );
}
