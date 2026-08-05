import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getGmailStatus, triggerSync } from "../api/endpoints/gmail";

export function useGmailStatus() {
  return useQuery({
    queryKey: ["gmail", "status"],
    queryFn: getGmailStatus,
  });
}

export function useGmailSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: triggerSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gmail", "status"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["summary"] });
    },
  });
}
