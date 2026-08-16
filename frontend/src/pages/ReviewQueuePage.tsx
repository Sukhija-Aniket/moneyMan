import { useState } from "react";
import { TransactionTable } from "../components/TransactionTable";
import { Pagination } from "../components/Pagination";
import { useTransactions } from "../hooks/useTransactions";
import { TransactionFilters } from "../api/endpoints/transactions";

const DEFAULT_PAGE_SIZE = 25;

export function ReviewQueuePage() {
  const [filters, setFilters] = useState<TransactionFilters>({
    review_status: "pending",
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    sort: "-txn_date",
  });

  const { data, isLoading, isError } = useTransactions(filters);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Review Queue</h1>
        <p className="mt-1 text-sm text-gray-500">
          Low-confidence extractions that need a quick check. Confirm, mark as not a
          transaction, or mark as a duplicate — nothing here is deleted.
        </p>
      </div>

      {isLoading && <div className="py-8 text-center text-sm text-gray-500">Loading...</div>}
      {isError && (
        <div className="py-8 text-center text-sm text-red-600">
          Failed to load review queue.
        </div>
      )}

      {data && (
        <>
          {data.items.length === 0 ? (
            <div className="rounded-md border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
              Nothing needs review right now.
            </div>
          ) : (
            <TransactionTable transactions={data.items} mode="review" />
          )}
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
