import { apiFetch, buildDownloadUrl } from "../client";

export type TxnType = "debit" | "credit";

export type ReviewStatus = "pending" | "confirmed" | "not_transaction" | "duplicate";

export interface Transaction {
  id: string;
  amount: number;
  currency: string;
  txn_type: TxnType;
  merchant_normalized: string;
  category_id: string | null;
  category_name: string | null;
  account_id: string;
  account_display_name: string;
  txn_date: string;
  confidence_score: number;
  review_status: ReviewStatus;
  duplicate_of_transaction_id: string | null;
  ambiguity_notes: string | null;
}

export interface TransactionListResponse {
  items: Transaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface TransactionFilters {
  date_from?: string;
  date_to?: string;
  category_id?: string;
  account_id?: string;
  txn_type?: TxnType;
  min_amount?: number;
  max_amount?: number;
  search?: string;
  review_status?: ReviewStatus;
  include_dismissed?: boolean;
  page?: number;
  page_size?: number;
  sort?: string;
}

export interface TransactionUpdate {
  category_id?: string;
  merchant_normalized?: string;
  review_status?: ReviewStatus;
  duplicate_of_transaction_id?: string;
}

export async function listTransactions(
  filters: TransactionFilters = {},
): Promise<TransactionListResponse> {
  return apiFetch<TransactionListResponse>("/transactions", { params: filters });
}

export async function getTransaction(id: string): Promise<Transaction> {
  return apiFetch<Transaction>(`/transactions/${id}`);
}

export async function updateTransaction(
  id: string,
  update: TransactionUpdate,
): Promise<Transaction> {
  return apiFetch<Transaction>(`/transactions/${id}`, {
    method: "PATCH",
    body: update,
  });
}

export async function deleteTransaction(id: string): Promise<void> {
  await apiFetch<void>(`/transactions/${id}`, { method: "DELETE" });
}

export function exportTransactionsCsvUrl(filters: TransactionFilters = {}): string {
  return buildDownloadUrl("/export/transactions.csv", filters);
}
