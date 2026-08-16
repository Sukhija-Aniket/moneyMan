import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getCurrentSync,
  getGmailStatus,
  getSyncRequest,
  triggerRangeSync,
  triggerSync,
  SyncRange,
} from "../api/endpoints/gmail";

export function useGmailStatus() {
  return useQuery({
    queryKey: ["gmail", "status"],
    queryFn: getGmailStatus,
  });
}

export function useGmailSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (range?: SyncRange) => triggerSync(range),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gmail", "status"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["summary"] });
    },
  });
}

/** Starts an async range sync (processed by the worker) and returns the created request,
 * with its computed (possibly empty, if already fully covered) list of gap segments. */
export function useStartRangeSync() {
  return useMutation({
    mutationFn: (range: SyncRange) => triggerRangeSync(range),
  });
}

/** Polls a sync request's status every 3s while it's in_progress, stops once it settles. */
export function useSyncRequestStatus(requestId: string | null) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["gmail", "sync-request", requestId],
    queryFn: () => getSyncRequest(requestId as string),
    enabled: requestId !== null,
    refetchInterval: (q) => (q.state.data?.status === "in_progress" ? 3000 : false),
  });

  useEffect(() => {
    if (query.data && query.data.status !== "in_progress") {
      queryClient.invalidateQueries({ queryKey: ["gmail", "status"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["summary"] });
    }
  }, [query.data?.status, queryClient]);

  return query;
}

/** Is any sync segment in_progress for this user right now, regardless of which request
 * started it — used to disable "Sync range" even after a page reload loses the request id. */
export function useCurrentSync() {
  return useQuery({
    queryKey: ["gmail", "current-sync"],
    queryFn: getCurrentSync,
    refetchInterval: (q) => (q.state.data?.in_progress ? 3000 : false),
  });
}
