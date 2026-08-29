import { apiFetch } from "../client";

export interface Category {
  id: string;
  name: string;
  parent_id: string | null;
  is_system: boolean;
}

export interface CategoryCreate {
  name: string;
  parent_id?: string | null;
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
