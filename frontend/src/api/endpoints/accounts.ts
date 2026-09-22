import { apiFetch } from "../client";

export interface Account {
  id: string;
  issuer_name: string | null;
  last4: string | null;
  account_type: string | null;
  display_name: string | null;
}

export async function listAccounts(): Promise<Account[]> {
  return apiFetch<Account[]>("/accounts");
}
