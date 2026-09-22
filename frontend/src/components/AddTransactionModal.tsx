import { useState } from "react";
import { ApiError } from "../api/client";
import { accountDisplayName, TxnType } from "../api/endpoints/transactions";
import { useAccounts } from "../hooks/useAccounts";
import { useCreateManualTransaction } from "../hooks/useTransactions";

function errorMessage(err: Error | null): string | null {
  if (!err) return null;
  return err instanceof ApiError ? err.detail : "Something went wrong. Please try again.";
}

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

export function AddTransactionModal({ onClose }: { onClose: () => void }) {
  const { data: accounts } = useAccounts();
  const createTransaction = useCreateManualTransaction();

  const [txnType, setTxnType] = useState<TxnType>("debit");
  const [amount, setAmount] = useState("");
  const [accountId, setAccountId] = useState("");
  const [txnDate, setTxnDate] = useState(todayIsoDate());
  const [merchant, setMerchant] = useState("");
  const [note, setNote] = useState("");

  const amountValue = Number(amount);
  const isValid = amount.trim() !== "" && amountValue > 0 && accountId !== "" && txnDate !== "";

  function handleSubmit() {
    if (!isValid) return;
    createTransaction.mutate(
      {
        txn_type: txnType,
        amount: amountValue,
        account_id: accountId,
        txn_date: txnDate,
        merchant: merchant.trim() || undefined,
        note: note.trim() || undefined,
      },
      { onSuccess: onClose },
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-md bg-white p-5 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Add transaction</h3>
            <p className="mt-1 text-sm text-gray-500">
              For a transaction with no source email — e.g. a cash payment. Marked as added
              by you, not extracted from an email.
            </p>
          </div>
          <button onClick={onClose} className="text-sm text-gray-400 hover:text-gray-700">
            Close
          </button>
        </div>

        <div className="mt-4 space-y-3">
          <div className="flex gap-3">
            <label className="flex-1 text-sm text-gray-600">
              Type
              <select
                value={txnType}
                onChange={(e) => setTxnType(e.target.value as TxnType)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-2 text-sm"
              >
                <option value="debit">Debit</option>
                <option value="credit">Credit</option>
                <option value="self_transfer">Self Transfer</option>
              </select>
            </label>

            <label className="flex-1 text-sm text-gray-600">
              Amount
              <input
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-2 text-sm"
              />
            </label>
          </div>

          <label className="block text-sm text-gray-600">
            Account
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-2 text-sm"
            >
              <option value="">Select an account…</option>
              {accounts?.map((a) => (
                <option key={a.id} value={a.id}>
                  {accountDisplayName(a)}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm text-gray-600">
            Date
            <input
              type="date"
              value={txnDate}
              onChange={(e) => setTxnDate(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-2 text-sm"
            />
          </label>

          <label className="block text-sm text-gray-600">
            Merchant / counterparty (optional)
            <input
              type="text"
              value={merchant}
              onChange={(e) => setMerchant(e.target.value)}
              placeholder="e.g. Local vendor"
              className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-2 text-sm"
            />
          </label>

          <label className="block text-sm text-gray-600">
            Note (optional)
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Paid cash, no bank notification"
              className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-2 text-sm"
            />
          </label>
        </div>

        {createTransaction.isError && (
          <p className="mt-3 text-sm text-red-600">{errorMessage(createTransaction.error)}</p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!isValid || createTransaction.isPending}
            className="rounded-md border border-gray-900 bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          >
            {createTransaction.isPending ? "Adding…" : "Add transaction"}
          </button>
        </div>
      </div>
    </div>
  );
}
