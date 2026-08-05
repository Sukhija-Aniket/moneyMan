import { useQuery } from "@tanstack/react-query";
import { listAccounts } from "../api/endpoints/accounts";

export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    queryFn: listAccounts,
    staleTime: 5 * 60_000,
  });
}
