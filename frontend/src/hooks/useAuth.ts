import { useQuery } from "@tanstack/react-query";
import { getCurrentUser } from "../api/endpoints/auth";

export function useAuth() {
  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getCurrentUser,
    retry: false,
  });

  return {
    user: query.data ?? null,
    isLoading: query.isLoading,
    isAuthenticated: !!query.data,
    refetch: query.refetch,
  };
}
