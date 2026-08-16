import { apiFetch } from "../client";

export interface SyncRange {
  date_from: string;
  date_to: string;
}

export interface SyncResult {
  fetched: number;
  gate1_rejected: number;
  classify_failed: number;
  classified_non_transaction: number;
  extracted_accepted: number;
  extracted_needs_review: number;
  extracted_discarded: number;
  extract_failed: number;
}

export interface GmailStatus {
  connected: boolean;
  scope: string | null;
  token_expiry: string | null;
  earliest_synced_at: string | null;
  latest_synced_at: string | null;
}

export type SyncTriggerStatus = "in_progress" | "success" | "failed";

export interface SyncTrigger {
  id: string;
  date_from: string;
  date_to: string;
  status: SyncTriggerStatus;
  error: string | null;
  started_at: string;
  completed_at: string | null;
}

export async function triggerSync(range?: SyncRange): Promise<SyncResult> {
  return apiFetch<SyncResult>("/gmail/sync", { method: "POST", body: range ?? {} });
}

/** Starts an async range sync (runs on the worker) — returns immediately with a trigger to poll. */
export async function triggerRangeSync(range: SyncRange): Promise<SyncTrigger> {
  return apiFetch<SyncTrigger>("/gmail/sync/range", { method: "POST", body: range });
}

export async function getSyncTrigger(triggerId: string): Promise<SyncTrigger> {
  return apiFetch<SyncTrigger>(`/gmail/sync/triggers/${triggerId}`);
}

export async function getGmailStatus(): Promise<GmailStatus> {
  return apiFetch<GmailStatus>("/gmail/status");
}
