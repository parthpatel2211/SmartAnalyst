import { useMemo, useState } from "react";

import { formatCell } from "../lib/format";
import type { Mode } from "../lib/palette";

interface Props {
  columns: string[];
  rows: Record<string, unknown>[];
  truncated: boolean;
  mode: Mode;
}

const PAGE_SIZE = 50;

type SortState = { column: string; direction: "asc" | "desc" } | null;

function compare(a: unknown, b: unknown): number {
  if (a === null || a === undefined) return 1; // nulls sink
  if (b === null || b === undefined) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

export default function TableView({ columns, rows, truncated }: Props) {
  const [sort, setSort] = useState<SortState>(null);
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const result = compare(a[sort.column], b[sort.column]);
      return sort.direction === "asc" ? result : -result;
    });
    return copy;
  }, [rows, sort]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const visible = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const toggleSort = (column: string) => {
    setPage(0);
    setSort((current) =>
      current?.column === column
        ? { column, direction: current.direction === "asc" ? "desc" : "asc" }
        : { column, direction: "asc" },
    );
  };

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: "var(--border)" }}>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr style={{ background: "var(--surface-3)" }}>
              {columns.map((column) => {
                const active = sort?.column === column;
                return (
                  <th
                    key={column}
                    scope="col"
                    className="whitespace-nowrap px-3 py-2 text-left font-medium"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    <button
                      type="button"
                      onClick={() => toggleSort(column)}
                      className="inline-flex items-center gap-1 hover:underline"
                      aria-label={`Sort by ${column}`}
                    >
                      {column}
                      <span
                        aria-hidden
                        style={{
                          opacity: active ? 1 : 0.25,
                          fontSize: 10,
                        }}
                      >
                        {active && sort?.direction === "desc" ? "▼" : "▲"}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, index) => (
              <tr
                key={index}
                style={{
                  borderTop: "1px solid var(--border)",
                  background: index % 2 ? "var(--surface-1)" : "transparent",
                }}
              >
                {columns.map((column) => {
                  const value = row[column];
                  const numeric = typeof value === "number";
                  return (
                    <td
                      key={column}
                      className={`px-3 py-1.5 ${numeric ? "text-right tabular" : "text-left"}`}
                      style={{
                        color:
                          value === null || value === undefined
                            ? "var(--text-muted)"
                            : "var(--text-primary)",
                      }}
                    >
                      {formatCell(value)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs"
        style={{ color: "var(--text-muted)" }}
      >
        <span>
          {sorted.length.toLocaleString()} row{sorted.length === 1 ? "" : "s"}
          {truncated && " (capped at the server's row limit)"}
        </span>

        {pageCount > 1 && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded px-2 py-1 disabled:opacity-35"
              style={{ background: "var(--surface-3)" }}
            >
              Previous
            </button>
            <span className="tabular">
              {page + 1} / {pageCount}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
              disabled={page >= pageCount - 1}
              className="rounded px-2 py-1 disabled:opacity-35"
              style={{ background: "var(--surface-3)" }}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
