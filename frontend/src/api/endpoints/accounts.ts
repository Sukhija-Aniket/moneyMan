import { apiFetch } from "../client";

export interface Account {
  id: string;
  issuer_name: string;
  last4: string | null;
  account_type: string;
  display_name: string;
}

export async function listAccounts(): Promise<Account[]> {
  return apiFetch<Account[]>("/accounts");
}
