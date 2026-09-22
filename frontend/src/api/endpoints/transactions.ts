import { apiFetch, buildDownloadUrl } from "../client";

export type TxnType = "debit" | "credit" | "self_transfer";

export type ReviewStatus = "pending" | "confirmed" | "not_transaction" | "duplicate";

export type ReviewedBy = "system" | "human";

export interface RawEmail {
  id: string;
  gmail_message_id: string;
  sender: string | null;
  subject: string | null;
  snippet: string | null;
  body_text: string | null;
  received_at: string | null;
}

export interface TransactionCategory {
  id: string;
  name: string;
  parent_id: string | null;
  is_system: boolean;
}

export interface TransactionAccount {
  id: string;
  issuer_name: string | null;
  last4: string | null;
  account_type: string | null;
  display_name: string | null;
}

export interface Transaction {
  id: string;
  amount: number;
  currency: string;
  txn_type: TxnType;
  merchant_normalized: string;
  category: TransactionCategory | null;
  account: TransactionAccount | null;
  txn_date: string;
  confidence_score: number;
  review_status: ReviewStatus;
  reviewed_by: ReviewedBy | null;
  duplicate_of_transaction_id: string | null;
  ambiguity_notes: string | null;
  /** Lightweight — the full raw email (with body) is fetched separately, on demand, via
   * getTransactionRawEmail(id), so list/table views don't ship every row's email body. */
  raw_email_gmail_message_id: string | null;
}

/** account.display_name is only set if the user renamed it — falls back to
 * "<issuer> ••<last4>" (or whichever of those two parts is available) to match how a bank
 * account is normally identified. */
export function accountDisplayName(account: TransactionAccount | null): string {
  if (!account) return "—";
  if (account.display_name) return account.display_name;
  if (account.issuer_name && account.last4) return `${account.issuer_name} ••${account.last4}`;
  return account.issuer_name ?? (account.last4 ? `••${account.last4}` : "—");
}

export interface TransactionListResponse {
  items: Transaction[];
  total: number;
  limit: number;
  offset: number;
}

export interface TransactionFilters {
  date_from?: string;
  date_to?: string;
  category_id?: string;
  account_id?: string;
  txn_type?: TxnType;
  amount_min?: number;
  amount_max?: number;
  search?: string;
  review_status?: ReviewStatus;
  include_dismissed?: boolean;
  limit?: number;
  offset?: number;
}

export interface TransactionCreate {
  txn_type: TxnType;
  amount: number;
  currency?: string;
  account_id: string;
  txn_date: string;
  merchant?: string;
  note?: string;
}

export interface TransactionUpdate {
  category_id?: string;
  account_id?: string;
  merchant_normalized?: string;
  txn_date?: string;
  amount?: number;
  txn_type?: TxnType;
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

export async function createManualTransaction(payload: TransactionCreate): Promise<Transaction> {
  return apiFetch<Transaction>("/transactions/manual", { method: "POST", body: payload });
}

export async function getTransactionRawEmail(id: string): Promise<RawEmail> {
  return apiFetch<RawEmail>(`/transactions/${id}/raw-email`);
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
