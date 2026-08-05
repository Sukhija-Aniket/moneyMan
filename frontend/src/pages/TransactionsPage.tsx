import { useState } from "react";
import { FilterBar } from "../components/FilterBar";
import { TransactionTable } from "../components/TransactionTable";
import { Pagination } from "../components/Pagination";
import { ExportButton } from "../components/ExportButton";
import { useTransactions } from "../hooks/useTransactions";
import { TransactionFilters } from "../api/endpoints/transactions";
import { currentMonthRange } from "../lib/dateRange";

const DEFAULT_PAGE_SIZE = 25;

export function TransactionsPage() {
  const [filters, setFilters] = useState<TransactionFilters>({
    ...currentMonthRange(),
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
  });

  const { data, isLoading, isError } = useTransactions(filters);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Transactions</h1>
        <ExportButton filters={filters} />
      </div>

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
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
          />
        </>
      )}
    </div>
  );
}
