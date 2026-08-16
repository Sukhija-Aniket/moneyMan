import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addBlacklistedSender, listBlacklistedSenders, removeBlacklistedSender } from "../api/endpoints/blacklist";

export function useBlacklistedSenders() {
  return useQuery({
    queryKey: ["gmail", "blacklist"],
    queryFn: listBlacklistedSenders,
  });
}

export function useAddBlacklistedSender() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sender: string) => addBlacklistedSender(sender),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gmail", "blacklist"] });
    },
  });
}

export function useRemoveBlacklistedSender() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => removeBlacklistedSender(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["gmail", "blacklist"] });
    },
  });
}
