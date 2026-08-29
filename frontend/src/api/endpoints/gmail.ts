import { apiFetch } from "../client";

export interface SyncRange {
  date_from: string;
  date_to: string;
}

export interface GmailStatus {
  connected: boolean;
  scope: string | null;
  token_expiry: string | null;
  earliest_synced_at: string | null;
  latest_synced_at: string | null;
}

export type SyncSegmentStatus = "in_progress" | "extraction_complete" | "extraction_failed" | "failed";
export type SyncRequestStatus = "in_progress" | "success" | "partial_failure" | "failed";

export interface SyncSegment {
  id: string;
  date_from: string | null;
  date_to: string | null;
  status: SyncSegmentStatus;
  total_candidates: number | null;
  processed_candidates: number;
  error: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface SyncRequestOut {
  id: string;
  date_from: string | null;
  date_to: string | null;
  status: SyncRequestStatus;
  created_at: string;
  segments: SyncSegment[];
}

export interface CurrentSync {
  in_progress: boolean;
  segment_id: string | null;
  date_from: string | null;
  date_to: string | null;
}

export interface SyncRequestListResponse {
  items: SyncRequestOut[];
  total: number;
  limit: number;
  offset: number;
}

/** Starts an async range sync (runs on the worker) — returns immediately with the created
 * request (and its computed segments) to poll. */
export async function triggerRangeSync(range: SyncRange): Promise<SyncRequestOut> {
  return apiFetch<SyncRequestOut>("/gmail/sync/range", { method: "POST", body: range });
}

export async function getSyncRequest(requestId: string): Promise<SyncRequestOut> {
  return apiFetch<SyncRequestOut>(`/gmail/sync/requests/${requestId}`);
}

export async function listSyncRequests(
  params: { limit?: number; offset?: number } = {},
): Promise<SyncRequestListResponse> {
  return apiFetch<SyncRequestListResponse>("/gmail/sync/requests", { params });
}

export async function getCurrentSync(): Promise<CurrentSync> {
  return apiFetch<CurrentSync>("/gmail/sync/current");
}

export async function getGmailStatus(): Promise<GmailStatus> {
  return apiFetch<GmailStatus>("/gmail/status");
}
