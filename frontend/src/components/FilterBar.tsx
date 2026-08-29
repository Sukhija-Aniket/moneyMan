import { TransactionFilters, TxnType } from "../api/endpoints/transactions";
import { useCategories } from "../hooks/useCategories";
import { useAccounts } from "../hooks/useAccounts";
import { DateRangePicker } from "./DateRangePicker";

export function FilterBar({
  filters,
  onChange,
  showIncludeDismissedToggle = true,
}: {
  filters: TransactionFilters;
  onChange: (filters: TransactionFilters) => void;
  showIncludeDismissedToggle?: boolean;
}) {
  const { data: categories } = useCategories();
  const { data: accounts } = useAccounts();

  function update(patch: Partial<TransactionFilters>) {
    onChange({ ...filters, ...patch, offset: 0 });
  }

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-md border border-gray-200 bg-white p-3">
      <DateRangePicker
        value={{
          date_from: filters.date_from ?? "",
          date_to: filters.date_to ?? "",
        }}
        onChange={(range) => update(range)}
      />

      <label className="text-sm text-gray-600">
        Category
        <select
          value={filters.category_id ?? ""}
          onChange={(e) => update({ category_id: e.target.value || undefined })}
          className="ml-2 rounded-md border border-gray-300 px-2 py-1 text-sm"
        >
          <option value="">All</option>
          {categories?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      <label className="text-sm text-gray-600">
        Account
        <select
          value={filters.account_id ?? ""}
          onChange={(e) => update({ account_id: e.target.value || undefined })}
          className="ml-2 rounded-md border border-gray-300 px-2 py-1 text-sm"
        >
          <option value="">All</option>
          {accounts?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.display_name}
            </option>
          ))}
        </select>
      </label>

      <label className="text-sm text-gray-600">
        Type
        <select
          value={filters.txn_type ?? ""}
          onChange={(e) =>
            update({ txn_type: (e.target.value || undefined) as TxnType | undefined })
          }
          className="ml-2 rounded-md border border-gray-300 px-2 py-1 text-sm"
        >
          <option value="">All</option>
          <option value="debit">Debit</option>
          <option value="credit">Credit</option>
        </select>
      </label>

      <label className="text-sm text-gray-600">
        Search
        <input
          type="text"
          placeholder="Merchant, notes..."
          value={filters.search ?? ""}
          onChange={(e) => update({ search: e.target.value || undefined })}
          className="ml-2 rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </label>

      {showIncludeDismissedToggle && (
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={!!filters.include_dismissed}
            onChange={(e) => update({ include_dismissed: e.target.checked || undefined })}
          />
          Include dismissed
        </label>
      )}
    </div>
  );
}
