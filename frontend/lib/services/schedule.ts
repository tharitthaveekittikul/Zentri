import { api } from "@/lib/api";

export interface ScheduleConfig {
  job_key: string;
  enabled: boolean;
  days: number[];       // 0=Mon … 6=Sun
  run_at_hour: number;
  run_at_minute: number;
  interval_minutes: number | null;
}

export async function fetchScheduleConfigs(): Promise<ScheduleConfig[]> {
  const res = await api.get("/api/v1/settings/schedule");
  if (!res.ok) throw new Error("Failed to fetch schedule configs");
  return res.json();
}

export async function saveScheduleConfigs(
  configs: ScheduleConfig[]
): Promise<ScheduleConfig[]> {
  const res = await api.put("/api/v1/settings/schedule", configs);
  if (!res.ok) throw new Error("Failed to save schedule configs");
  return res.json();
}

export async function fetchScheduleTimezone(): Promise<string> {
  const res = await api.get("/api/v1/settings/profile");
  if (!res.ok) throw new Error("Failed to fetch profile");
  const data = await res.json();
  return data.schedule_timezone ?? "Asia/Bangkok";
}

export async function saveScheduleTimezone(timezone: string): Promise<void> {
  const res = await api.patch("/api/v1/settings/profile", { schedule_timezone: timezone });
  if (!res.ok) throw new Error("Failed to save timezone");
}
