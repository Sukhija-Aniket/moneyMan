import { useState } from "react";
import { ApiError } from "../api/client";
import { Category } from "../api/endpoints/categories";
import { useCategories, useCreateCategory, useDeleteCategory } from "../hooks/useCategories";

function errorMessage(err: Error | null): string | null {
  if (!err) return null;
  return err instanceof ApiError ? err.detail : "Something went wrong. Please try again.";
}

export function CategoriesPage() {
  const { data: categories, isLoading } = useCategories();
  const createCategory = useCreateCategory();
  const deleteCategory = useDeleteCategory();
  const [newName, setNewName] = useState("");
  const [deleteError, setDeleteError] = useState<{ categoryName: string; message: string } | null>(null);

  function handleAdd() {
    const name = newName.trim();
    if (!name) return;
    createCategory.mutate({ name }, { onSuccess: () => setNewName("") });
  }

  function handleDelete(category: Category) {
    setDeleteError(null);
    deleteCategory.mutate(category.id, {
      onError: (err) => setDeleteError({ categoryName: category.name, message: errorMessage(err) ?? "" }),
    });
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Categories</h1>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Add a category</h2>
        <p className="mt-1 text-sm text-gray-500">
          Used to classify transactions on the Transactions and Review Queue pages.
        </p>
        <div className="mt-3 flex gap-2">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="e.g. Travel, Medicines, Entertainment"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
          <button
            onClick={handleAdd}
            disabled={createCategory.isPending || !newName.trim()}
            className="rounded-md border border-gray-900 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-100 disabled:opacity-50"
          >
            Add
          </button>
        </div>
        {createCategory.isError && (
          <p className="mt-2 text-sm text-red-600">{errorMessage(createCategory.error)}</p>
        )}
      </section>

      <section className="rounded-md border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-medium text-gray-700">Your categories</h2>

        {isLoading && <p className="mt-3 text-sm text-gray-500">Loading...</p>}

        {categories && categories.length > 0 ? (
          <ul className="mt-3 divide-y divide-gray-100">
            {categories.map((category) => (
              <li key={category.id} className="py-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-700">
                    {category.name}
                    {category.is_system && (
                      <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                        Default
                      </span>
                    )}
                  </span>
                  <button
                    onClick={() => handleDelete(category)}
                    disabled={deleteCategory.isPending}
                    className="text-xs text-gray-400 hover:text-red-600 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </div>
                {deleteError?.categoryName === category.name && (
                  <p className="mt-1 text-xs text-red-600">{deleteError.message}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          !isLoading && <p className="mt-3 text-sm text-gray-500">No categories yet.</p>
        )}
      </section>
    </div>
  );
}
