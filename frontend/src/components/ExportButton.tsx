import { TransactionFilters, exportTransactionsCsvUrl } from "../api/endpoints/transactions";

export function ExportButton({ filters }: { filters: TransactionFilters }) {
  function handleExport() {
    const url = exportTransactionsCsvUrl(filters);
    // credentials: 'include' isn't available for a plain navigation, but the
    // session cookie is sent automatically by the browser for same-site requests.
    window.open(url, "_blank");
  }

  return (
    <button
      onClick={handleExport}
      className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
    >
      Export CSV
    </button>
  );
}
