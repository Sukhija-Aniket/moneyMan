import { useState } from "react";
import { Transaction } from "../api/endpoints/transactions";
import { useCategories } from "../hooks/useCategories";
import { useUpdateTransaction, useDeleteTransaction } from "../hooks/useTransactions";
import { formatMoney } from "../lib/dateRange";

export function TransactionTable({ transactions }: { transactions: Transaction[] }) {
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
          {transactions.map((txn) => (
            <tr key={txn.id} className={txn.needs_review ? "bg-amber-50" : undefined}>
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
                {txn.needs_review && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                    Needs review
                  </span>
                )}
              </td>
              <td className="px-3 py-2 text-right">
                <button
                  onClick={() => {
                    if (confirm("Delete this transaction?")) deleteTxn.mutate(txn.id);
                  }}
                  className="text-xs text-gray-400 hover:text-red-600"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
