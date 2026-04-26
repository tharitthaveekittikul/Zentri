import { api } from "./api";

export function saveTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem("access_token", accessToken);
  localStorage.setItem("refresh_token", refreshToken);
  // Cookie read by middleware for server-side route protection
  document.cookie = `access_token=${accessToken}; path=/; SameSite=Strict; max-age=900`;
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  document.cookie = "access_token=; path=/; max-age=0";
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export async function logout() {
  try {
    await api.post("/api/v1/auth/logout", {});
  } finally {
    clearTokens();
  }
}
