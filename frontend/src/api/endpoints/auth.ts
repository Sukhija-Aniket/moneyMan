import { API_BASE_URL, apiFetch } from "../client";

export type LlmProvider = "anthropic" | "ollama";

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
  picture_url: string | null;
  llm_provider: LlmProvider;
  timezone: string;
}

export interface UserSettingsUpdate {
  llm_provider?: LlmProvider;
  timezone?: string;
}

export const googleLoginUrl = `${API_BASE_URL}/auth/google/login`;

export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await apiFetch<CurrentUser>("/auth/me");
  } catch (err: any) {
    if (err?.status === 401) return null;
    throw err;
  }
}

/** The backend's own canonical IANA timezone list — use this for any timezone picker
 * instead of the browser's Intl.supportedValuesOf, which can include names (e.g. deprecated
 * aliases like "Asia/Calcutta") that the backend's tzdata build doesn't recognize. */
export async function getAvailableTimezones(): Promise<string[]> {
  return apiFetch<string[]>("/auth/timezones");
}

export async function updateUserSettings(update: UserSettingsUpdate): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me", { method: "PATCH", body: update });
}

export async function logout(): Promise<void> {
  await apiFetch<void>("/auth/logout", { method: "POST" });
}
