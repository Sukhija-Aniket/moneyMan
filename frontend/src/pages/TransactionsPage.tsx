import { useState } from "react";
import { FilterBar } from "../components/FilterBar";
import { TransactionTable } from "../components/TransactionTable";
import { Pagination } from "../components/Pagination";
import { ExportButton } from "../components/ExportButton";
import { AddTransactionModal } from "../components/AddTransactionModal";
import { useTransactions } from "../hooks/useTransactions";
import { TransactionFilters } from "../api/endpoints/transactions";
import { currentMonthRange } from "../lib/dateRange";

const DEFAULT_PAGE_SIZE = 25;

export function TransactionsPage() {
  const [filters, setFilters] = useState<TransactionFilters>({
    ...currentMonthRange(),
    offset: 0,
    limit: DEFAULT_PAGE_SIZE,
  });
  const [showAddModal, setShowAddModal] = useState(false);

  const { data, isLoading, isError } = useTransactions(filters);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Transactions</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="rounded-md border border-gray-900 bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
          >
            Add Transaction
          </button>
          <ExportButton filters={filters} />
        </div>
      </div>

      {showAddModal && <AddTransactionModal onClose={() => setShowAddModal(false)} />}

      <FilterBar filters={filters} onChange={setFilters} />

      {isLoading && <div className="py-8 text-center text-sm text-gray-500">Loading...</div>}
      {isError && (
        <div className="py-8 text-center text-sm text-red-600">
          Failed to load transactions.
        </div>
      )}

      {data && (
        <>
          <TransactionTable transactions={data.items} />
          <Pagination
            limit={data.limit}
            offset={data.offset}
            total={data.total}
            onOffsetChange={(offset) => setFilters((f) => ({ ...f, offset }))}
          />
        </>
      )}
    </div>
  );
}
