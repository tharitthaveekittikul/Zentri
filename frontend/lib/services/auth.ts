import { api } from "@/lib/api";
import { saveTokens } from "@/lib/auth";

export interface HardwareRecommendation {
  can_run_local_llm: boolean;
  recommended_model: string;
  setup_command: string;
  note: string;
}

type AuthResult =
  | { ok: true; hardware: HardwareRecommendation | null }
  | { ok: false; conflict: boolean; error: string };

export async function setupAccount(
  username: string,
  password: string
): Promise<AuthResult> {
  const res = await api.post("/api/v1/auth/setup", { username, password });
  if (res.status === 409) {
    return { ok: false, conflict: true, error: "Account already exists." };
  }
  if (!res.ok) {
    return { ok: false, conflict: false, error: "Setup failed. Check logs." };
  }
  const data = await res.json();
  saveTokens(data.access_token, data.refresh_token);

  const hwRes = await api.get("/api/v1/settings/hardware");
  const hardware: HardwareRecommendation | null = hwRes.ok
    ? (await hwRes.json()).recommendation
    : null;

  return { ok: true, hardware };
}

type LoginResult = { ok: true } | { ok: false; unauthorized: boolean; error: string };

export async function login(
  username: string,
  password: string
): Promise<LoginResult> {
  const res = await api.post("/api/v1/auth/login", { username, password });
  if (res.status === 401) {
    return { ok: false, unauthorized: true, error: "Invalid username or password." };
  }
  if (!res.ok) {
    return { ok: false, unauthorized: false, error: "Login failed. Try /setup if this is a fresh install." };
  }
  const data = await res.json();
  saveTokens(data.access_token, data.refresh_token);
  return { ok: true };
}

export interface ProfileSettings {
  birth_date: string | null;   // ISO date "YYYY-MM-DD"
  plan_to_age: number | null;
  current_age: number | null;
  years_remaining: number | null;
  target_year: number | null;
}

export async function getProfile(): Promise<ProfileSettings | null> {
  const res = await api.get("/api/v1/settings/profile");
  return res.ok ? res.json() : null;
}

export async function saveProfile(data: {
  birth_date?: string | null;
  plan_to_age?: number | null;
}): Promise<ProfileSettings | null> {
  const res = await api.patch("/api/v1/settings/profile", data);
  return res.ok ? res.json() : null;
}
