import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getCurrentUser, updateUserSettings } from "../api/endpoints/auth";

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

export function useUpdateUserSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateUserSettings,
    onSuccess: (user) => {
      queryClient.setQueryData(["auth", "me"], user);
    },
  });
}
