import { useState } from "react";
import { accountDisplayName, Transaction, TxnType } from "../api/endpoints/transactions";
import { useAccounts } from "../hooks/useAccounts";
import { useCategories } from "../hooks/useCategories";
import { useUpdateTransaction, useTransactionRawEmail } from "../hooks/useTransactions";
import { formatMoney } from "../lib/dateRange";

function looksLikeHtml(body: string): boolean {
  return /<(!doctype|html|body|table|div|p|br|img|a)\b/i.test(body);
}

function RawEmailModal({ transactionId, onClose }: { transactionId: string; onClose: () => void }) {
  const { data: rawEmail, isLoading, isError } = useTransactionRawEmail(transactionId);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-md bg-white p-5 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h3 className="text-sm font-semibold text-gray-900">Raw source email</h3>
          <button onClick={onClose} className="text-sm text-gray-400 hover:text-gray-700">
            Close
          </button>
        </div>

        {isLoading && <p className="mt-3 text-sm text-gray-500">Loading...</p>}
        {isError && <p className="mt-3 text-sm text-red-600">Failed to load raw email.</p>}

        {rawEmail && (
          <>
            <dl className="mt-3 space-y-1 text-sm">
              <div className="flex gap-2">
                <dt className="w-16 shrink-0 text-gray-500">From</dt>
                <dd className="text-gray-800">{rawEmail.sender ?? "—"}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-16 shrink-0 text-gray-500">Subject</dt>
                <dd className="text-gray-800">{rawEmail.subject ?? "—"}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-16 shrink-0 text-gray-500">Received</dt>
                <dd className="text-gray-800">
                  {rawEmail.received_at ? new Date(rawEmail.received_at).toLocaleString() : "—"}
                </dd>
              </div>
            </dl>
            {rawEmail.body_text && looksLikeHtml(rawEmail.body_text) ? (
              <iframe
                title="Raw email body"
                sandbox=""
                srcDoc={rawEmail.body_text}
                className="mt-3 h-96 w-full rounded-md border border-gray-200 bg-white"
              />
            ) : (
              <pre className="mt-3 max-h-96 overflow-y-auto whitespace-pre-wrap rounded-md bg-gray-50 p-3 text-xs text-gray-700">
                {rawEmail.body_text ?? rawEmail.snippet ?? "No body available."}
              </pre>
            )}
          </>
        )}
      </div>
    </div>
  );
}

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
  const { data: accounts } = useAccounts();
  const updateTxn = useUpdateTransaction();
  const [editingMerchantId, setEditingMerchantId] = useState<string | null>(null);
  const [merchantDraft, setMerchantDraft] = useState("");
  const [editingDateId, setEditingDateId] = useState<string | null>(null);
  const [dateDraft, setDateDraft] = useState("");
  const [editingAmountId, setEditingAmountId] = useState<string | null>(null);
  const [amountDraft, setAmountDraft] = useState("");
  const [viewingRawEmailFor, setViewingRawEmailFor] = useState<string | null>(null);

  function startEditMerchant(txn: Transaction) {
    setEditingMerchantId(txn.id);
    setMerchantDraft(txn.merchant_normalized);
  }

  function commitMerchant(id: string) {
    updateTxn.mutate({ id, update: { merchant_normalized: merchantDraft } });
    setEditingMerchantId(null);
  }

  function startEditDate(txn: Transaction) {
    setEditingDateId(txn.id);
    setDateDraft(txn.txn_date);
  }

  function commitDate(id: string) {
    updateTxn.mutate({ id, update: { txn_date: dateDraft } });
    setEditingDateId(null);
  }

  function startEditAmount(txn: Transaction) {
    setEditingAmountId(txn.id);
    setAmountDraft(String(txn.amount));
  }

  function commitAmount(id: string) {
    const parsed = Number(amountDraft);
    if (!Number.isNaN(parsed)) {
      updateTxn.mutate({ id, update: { amount: parsed } });
    }
    setEditingAmountId(null);
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
            <th className="px-3 py-2 text-left font-medium text-gray-500">Status</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Message ID</th>
            <th className="px-3 py-2 text-left font-medium text-gray-500">Raw Mail</th>
            <th className="px-3 py-2 text-right font-medium text-gray-500">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {transactions.map((txn) => {
            const badge = STATUS_BADGE[txn.review_status];
            return (
              <tr key={txn.id} className={txn.review_status === "pending" ? "bg-amber-50" : undefined}>
                <td className="whitespace-nowrap px-3 py-2 text-gray-700">
                  {mode === "review" && editingDateId === txn.id ? (
                    <input
                      autoFocus
                      type="date"
                      value={dateDraft}
                      onChange={(e) => setDateDraft(e.target.value)}
                      onBlur={() => commitDate(txn.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitDate(txn.id);
                        if (e.key === "Escape") setEditingDateId(null);
                      }}
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    />
                  ) : mode === "review" ? (
                    <button
                      onClick={() => startEditDate(txn)}
                      className="text-left hover:underline"
                      title="Click to edit"
                    >
                      {txn.txn_date}
                    </button>
                  ) : (
                    txn.txn_date
                  )}
                </td>
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
                    value={txn.category?.id ?? ""}
                    onChange={(e) =>
                      updateTxn.mutate({
                        id: txn.id,
                        update: { category_id: e.target.value || undefined },
                      })
                    }
                    className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                  >
                    <option value="">Uncategorized</option>
                    {txn.txn_type !== "self_transfer" &&
                      categories
                        ?.filter((c) => c.txn_type === txn.txn_type)
                        .map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                  </select>
                </td>
                <td className="px-3 py-2 text-gray-700">
                  {mode === "review" ? (
                    <select
                      value={txn.account?.id ?? ""}
                      onChange={(e) =>
                        updateTxn.mutate({
                          id: txn.id,
                          update: { account_id: e.target.value || undefined },
                        })
                      }
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    >
                      <option value="">—</option>
                      {accounts?.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.display_name || `${a.issuer_name} ••${a.last4 ?? ""}`}
                        </option>
                      ))}
                    </select>
                  ) : (
                    accountDisplayName(txn.account)
                  )}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-medium text-gray-900">
                  {mode === "review" && editingAmountId === txn.id ? (
                    <input
                      autoFocus
                      type="number"
                      step="0.01"
                      value={amountDraft}
                      onChange={(e) => setAmountDraft(e.target.value)}
                      onBlur={() => commitAmount(txn.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitAmount(txn.id);
                        if (e.key === "Escape") setEditingAmountId(null);
                      }}
                      className="w-24 rounded-md border border-gray-300 px-2 py-1 text-right text-sm"
                    />
                  ) : mode === "review" ? (
                    <button
                      onClick={() => startEditAmount(txn)}
                      className="hover:underline"
                      title="Click to edit"
                    >
                      {formatMoney(txn.amount, txn.currency)}
                    </button>
                  ) : (
                    formatMoney(txn.amount, txn.currency)
                  )}
                </td>
                <td className="px-3 py-2">
                  {mode === "review" ? (
                    <select
                      value={txn.txn_type}
                      onChange={(e) =>
                        updateTxn.mutate({
                          id: txn.id,
                          update: { txn_type: e.target.value as TxnType },
                        })
                      }
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                    >
                      <option value="debit">debit</option>
                      <option value="credit">credit</option>
                      <option value="self_transfer">self_transfer</option>
                    </select>
                  ) : (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        txn.txn_type === "credit"
                          ? "bg-green-100 text-green-700"
                          : txn.txn_type === "self_transfer"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {txn.txn_type}
                    </span>
                  )}
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
                <td className="max-w-[10rem] truncate px-3 py-2 font-mono text-xs text-gray-500">
                  {txn.raw_email_gmail_message_id ?? "—"}
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => setViewingRawEmailFor(txn.id)}
                    disabled={!txn.raw_email_gmail_message_id}
                    className="text-xs text-gray-500 hover:text-gray-800 disabled:opacity-40"
                  >
                    View raw
                  </button>
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
                      {txn.review_status === "pending" ? (
                        <button
                          onClick={() =>
                            updateTxn.mutate({ id: txn.id, update: { review_status: "confirmed" } })
                          }
                          className="text-xs text-gray-500 hover:text-green-700"
                        >
                          Confirm
                        </button>
                      ) : (
                        txn.reviewed_by !== "human" && (
                          <button
                            onClick={() => updateTxn.mutate({ id: txn.id, update: { review_status: "pending" } })}
                            className="text-xs text-gray-400 hover:text-amber-700"
                          >
                            Move to review
                          </button>
                        )
                      )}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {viewingRawEmailFor && (
        <RawEmailModal transactionId={viewingRawEmailFor} onClose={() => setViewingRawEmailFor(null)} />
      )}
    </div>
  );
}
