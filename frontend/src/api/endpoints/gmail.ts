import { apiFetch } from "../client";

export interface SyncResult {
  synced_count: number;
  new_transactions_count: number;
}

export interface GmailStatus {
  last_synced_at: string | null;
  status: string;
}

export async function triggerSync(): Promise<SyncResult> {
  return apiFetch<SyncResult>("/gmail/sync", { method: "POST" });
}

export async function getGmailStatus(): Promise<GmailStatus> {
  return apiFetch<GmailStatus>("/gmail/status");
}
