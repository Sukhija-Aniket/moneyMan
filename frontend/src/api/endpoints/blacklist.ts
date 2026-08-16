import { apiFetch } from "../client";

export interface BlacklistedSender {
  id: string;
  sender: string;
  created_at: string;
}

export async function listBlacklistedSenders(): Promise<BlacklistedSender[]> {
  return apiFetch<BlacklistedSender[]>("/gmail/blacklist");
}

export async function addBlacklistedSender(sender: string): Promise<BlacklistedSender> {
  return apiFetch<BlacklistedSender>("/gmail/blacklist", { method: "POST", body: { sender } });
}

export async function removeBlacklistedSender(id: string): Promise<void> {
  await apiFetch<void>(`/gmail/blacklist/${id}`, { method: "DELETE" });
}
