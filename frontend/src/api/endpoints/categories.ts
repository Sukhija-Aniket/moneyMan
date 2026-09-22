import { apiFetch } from "../client";
import { TxnType } from "./transactions";

export interface Category {
  id: string;
  name: string;
  parent_id: string | null;
  is_system: boolean;
  txn_type: TxnType;
}

export interface CategoryCreate {
  name: string;
  parent_id?: string | null;
  txn_type: TxnType;
}

export async function listCategories(): Promise<Category[]> {
  return apiFetch<Category[]>("/categories");
}

export async function createCategory(payload: CategoryCreate): Promise<Category> {
  return apiFetch<Category>("/categories", { method: "POST", body: payload });
}

export async function deleteCategory(id: string): Promise<void> {
  await apiFetch<void>(`/categories/${id}`, { method: "DELETE" });
}
