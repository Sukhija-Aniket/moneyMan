import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getGmailStatus,
  getSyncTrigger,
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

/** Starts an async range sync (processed by the worker) and returns the created trigger. */
export function useStartRangeSync() {
  return useMutation({
    mutationFn: (range: SyncRange) => triggerRangeSync(range),
  });
}

/** Polls a sync trigger's status every 3s while it's in_progress, stops once it settles. */
export function useSyncTriggerStatus(triggerId: string | null) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["gmail", "sync-trigger", triggerId],
    queryFn: () => getSyncTrigger(triggerId as string),
    enabled: triggerId !== null,
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
