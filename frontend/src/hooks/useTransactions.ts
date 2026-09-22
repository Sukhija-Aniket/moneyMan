import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createManualTransaction,
  deleteTransaction,
  getTransactionRawEmail,
  listTransactions,
  TransactionCreate,
  TransactionFilters,
  TransactionUpdate,
  updateTransaction,
} from "../api/endpoints/transactions";

export function useTransactions(filters: TransactionFilters) {
  return useQuery({
    queryKey: ["transactions", filters],
    queryFn: () => listTransactions(filters),
    placeholderData: (prev) => prev,
  });
}

/** Only fetches the (potentially large) raw email body when `transactionId` is set —
 * pass null until the user actually clicks "View raw". Cached per transaction id so
 * reopening the same one doesn't re-fetch. */
export function useTransactionRawEmail(transactionId: string | null) {
  return useQuery({
    queryKey: ["transactions", transactionId, "raw-email"],
    queryFn: () => getTransactionRawEmail(transactionId as string),
    enabled: transactionId !== null,
    staleTime: Infinity,
  });
}

export function useUpdateTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, update }: { id: string; update: TransactionUpdate }) =>
      updateTransaction(id, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useCreateManualTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TransactionCreate) => createManualTransaction(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useDeleteTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTransaction(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}
