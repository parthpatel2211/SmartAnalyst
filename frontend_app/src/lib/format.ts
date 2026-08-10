/** Display formatting. Nulls read as an em dash, never as "null" or blank. */

export const NULL_DISPLAY = "—";

export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return NULL_DISPLAY;
  const magnitude = Math.abs(value);

  if (Number.isInteger(value) && magnitude < 1e6) {
    return value.toLocaleString();
  }
  if (magnitude >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (magnitude >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (magnitude >= 1e4) return `${(value / 1e3).toFixed(1)}k`;
  if (magnitude < 0.01 && magnitude > 0) return value.toExponential(1);
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === "") return NULL_DISPLAY;
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "boolean") return value ? "true" : "false";

  const text = String(value);
  // Trim the time off ISO timestamps that are midnight-aligned dates.
  const isoDate = /^(\d{4}-\d{2}-\d{2})T00:00:00/.exec(text);
  return isoDate ? isoDate[1] : text;
}

export function formatPercent(value: number, digits = 0): string {
  return `${value.toFixed(digits)}%`;
}

export function formatBytes(bytes: number): string {
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}

/** Recharts hands axis ticks raw values; keep them short. */
export function formatAxisTick(value: unknown): string {
  if (typeof value === "number") return formatNumber(value);
  const text = formatCell(value);
  return text.length > 12 ? `${text.slice(0, 11)}…` : text;
}

export function toCsv(columns: string[], rows: Record<string, unknown>[]): string {
  const escape = (value: unknown) => {
    if (value === null || value === undefined) return "";
    const text = String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [
    columns.join(","),
    ...rows.map((row) => columns.map((column) => escape(row[column])).join(",")),
  ].join("\n");
}
