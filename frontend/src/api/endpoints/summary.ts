import { apiFetch } from "../client";

export interface DateRangeParams {
  date_from?: string;
  date_to?: string;
}

export interface SummaryOverview {
  total_spend: number;
  total_income: number;
  net: number;
  transaction_count: number;
  needs_review_count: number;
  currency: string;
}

export interface CategorySummary {
  category_id: string | null;
  category_name: string;
  total_amount: number;
  transaction_count: number;
}

export interface AccountSummary {
  account_id: string | null;
  display_name: string;
  total_amount: number;
  transaction_count: number;
}

export interface BankSummary {
  issuer_name: string;
  total_amount: number;
  transaction_count: number;
}

export interface TrendPoint {
  period: string;
  total_spend: number;
  total_income: number;
  transaction_count: number;
}

export async function getOverview(params: DateRangeParams): Promise<SummaryOverview> {
  return apiFetch<SummaryOverview>("/summary/overview", { params });
}

export async function getByCategory(params: DateRangeParams): Promise<CategorySummary[]> {
  return apiFetch<CategorySummary[]>("/summary/by-category", { params });
}

export async function getByAccount(params: DateRangeParams): Promise<AccountSummary[]> {
  return apiFetch<AccountSummary[]>("/summary/by-account", { params });
}

export async function getByBank(params: DateRangeParams): Promise<BankSummary[]> {
  return apiFetch<BankSummary[]>("/summary/by-bank", { params });
}

export async function getTrends(months = 6): Promise<TrendPoint[]> {
  return apiFetch<TrendPoint[]>("/summary/trends", { params: { months } });
}
