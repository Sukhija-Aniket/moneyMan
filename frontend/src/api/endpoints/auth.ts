import { API_BASE_URL, apiFetch } from "../client";

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
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

export async function logout(): Promise<void> {
  await apiFetch<void>("/auth/logout", { method: "POST" });
}
