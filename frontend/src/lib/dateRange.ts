function toIsoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function currentMonthRange(): { date_from: string; date_to: string } {
  const now = new Date();
  const from = new Date(now.getFullYear(), now.getMonth(), 1);
  const to = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { date_from: toIsoDate(from), date_to: toIsoDate(to) };
}

export function formatMoney(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}
