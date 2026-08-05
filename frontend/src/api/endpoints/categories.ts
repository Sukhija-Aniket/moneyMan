import { apiFetch } from "../client";

export interface Category {
  id: string;
  name: string;
  parent_category_id: string | null;
}

export async function listCategories(): Promise<Category[]> {
  return apiFetch<Category[]>("/categories");
}
