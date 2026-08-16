import { useState } from "react";
import { Transaction } from "../api/endpoints/transactions";
import { useCategories } from "../hooks/useCategories";
import { useUpdateTransaction, useDeleteTransaction } from "../hooks/useTransactions";
import { formatMoney } from "../lib/dateRange";

const STATUS_BADGE: Record<Transaction["review_status"], { label: string; className: string }> = {
  pending: { label: "Needs review", className: "bg-amber-100 text-amber-800" },
  confirmed: { label: "Confirmed", className: "bg-green-100 text-green-700" },
  not_transaction: { label: "Not a transaction", className: "bg-gray-200 text-gray-600" },
  duplicate: { label: "Duplicate", className: "bg-orange-100 text-orange-700" },
};

export function TransactionTable({
  transactions,
  mode = "transactions",
}: {
  transactions: Transaction[];
  /** "transactions": shows a "Move to review" action. "review": shows mark-as-X actions
   * instead of delete, since dismissed items are soft-classified, not removed. */
  mode?: "transactions" | "review";
}) {
  const { data: categories } = useCategories();
  const updateTxn = useUpdateTransaction();
  const deleteTxn = useDeleteTransaction();
  const [editingMerchantId, setEditingMerchantId] = useState<string | null>(null);
  const [merchantDraft, setMerchantDraft] = useState("");

  function startEditMerchant(txn: Transaction) {
    setEditingMerchantId(txn.id);
    setMerchantDraft(txn.merchant_normalized);
  }

  function commitMerchant(id: string) {
    updateTxn.mutate({ id, update: { merchant_normalized: merchantDraft } });
    setEditingMerchantId(null);
  }

  if (transactions.length === 0) {
    return (
      <div className="rounded-md border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
        No transactions found.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-gray-200 bg-white">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Date</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Merchant</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Category</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Account</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Amount</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Type</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500"></th>
            <th className="px-3 py-2 text-right font-medium text-gray-500"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {transactions.map((txn) => {
            const badge = STATUS_BADGE[txn.review_status];
            return (
              <tr key={txn.id} className={txn.review_status === "pending" ? "bg-amber-50" : undefined}>
                <td className="whitespace-nowrap px-3 py-2 text-gray-700">{txn.txn_date}</td>
                <td className="px-3 py-2 text-gray-700">
                  {editingMerchantId === txn.id ? (
                    <input
                      autoFocus
                      value={merchantDraft}
                      onChange={(e) => setMerchantDraft(e.target.value)}
                      onBlur={() => commitMerchant(txn.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitMerchant(txn.id);
                        if (e.key === "Escape") setEditingMerchantId(null);
                      }}
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                  ) : (
                    <button
                      onClick={() => startEditMerchant(txn)}
                      className="text-left hover:underline"
                      title="Click to edit"
                    >
                      {txn.merchant_normalized}
                    </button>
                  )}
                </td>
                <td className="px-3 py-2 text-gray-700">
                  <select
                    value={txn.category_id ?? ""}
                    onChange={(e) =>
                      updateTxn.mutate({
                        id: txn.id,
                        update: { category_id: e.target.value || undefined },
                      })
                    }
                    className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                  >
                    <option value="">Uncategorized</option>
                    {categories?.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2 text-gray-700">{txn.account_display_name}</td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-medium text-gray-900">
                  {formatMoney(txn.amount, txn.currency)}
                </td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      txn.txn_type === "credit"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {txn.txn_type}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}
                    title={txn.ambiguity_notes ?? undefined}
                  >
                    {badge.label}
                  </span>
                  {txn.review_status === "pending" && txn.ambiguity_notes && (
                    <p className="mt-1 max-w-xs text-xs text-gray-500">{txn.ambiguity_notes}</p>
                  )}
                </td>
                <td className="px-3 py-2 text-right">
                  {mode === "review" ? (
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => updateTxn.mutate({ id: txn.id, update: { review_status: "confirmed" } })}
                        className="text-xs text-gray-500 hover:text-green-700"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() =>
                          updateTxn.mutate({ id: txn.id, update: { review_status: "not_transaction" } })
                        }
                        className="text-xs text-gray-500 hover:text-gray-800"
                      >
                        Not a transaction
                      </button>
                      <button
                        onClick={() => updateTxn.mutate({ id: txn.id, update: { review_status: "duplicate" } })}
                        className="text-xs text-gray-500 hover:text-orange-700"
                      >
                        Duplicate
                      </button>
                    </div>
                  ) : (
                    <div className="flex justify-end gap-2">
                      {txn.review_status !== "pending" && (
                        <button
                          onClick={() => updateTxn.mutate({ id: txn.id, update: { review_status: "pending" } })}
                          className="text-xs text-gray-400 hover:text-amber-700"
                        >
                          Move to review
                        </button>
                      )}
                      <button
                        onClick={() => {
                          if (confirm("Delete this transaction? This cannot be undone.")) {
                            deleteTxn.mutate(txn.id);
                          }
                        }}
                        className="text-xs text-gray-400 hover:text-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
