import { useState } from "react";

import { formatBytes, formatNumber, formatPercent } from "../lib/format";
import type { ColumnProfile, DatasetProfile, SemanticType } from "../types";

const TYPE_GLYPH: Record<SemanticType, string> = {
  id: "#",
  numeric: "123",
  categorical: "Ab",
  datetime: "📅",
  boolean: "T/F",
  text: "¶",
};

const TYPE_LABEL: Record<SemanticType, string> = {
  id: "identifier",
  numeric: "numeric",
  categorical: "category",
  datetime: "date",
  boolean: "boolean",
  text: "text",
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt style={{ color: "var(--text-muted)" }}>{label}</dt>
      <dd className="tabular" style={{ color: "var(--text-primary)" }}>
        {value}
      </dd>
    </div>
  );
}

function ColumnRow({ column }: { column: ColumnProfile }) {
  const [open, setOpen] = useState(false);
  const isNumeric = column.median !== null;

  return (
    <li className="border-b last:border-b-0" style={{ borderColor: "var(--border)" }}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:opacity-80"
      >
        <span
          className="w-8 shrink-0 text-[10px] font-semibold"
          style={{ color: "var(--text-muted)" }}
          title={TYPE_LABEL[column.semantic_type]}
        >
          {TYPE_GLYPH[column.semantic_type]}
        </span>

        <span className="flex-1 truncate" style={{ color: "var(--text-primary)" }}>
          {column.name}
        </span>

        {/* Null share as a bar: data quality visible without opening anything. */}
        {column.null_pct > 0 && (
          <span className="flex shrink-0 items-center gap-1" title={`${column.null_pct}% missing`}>
            <span
              className="block h-1 w-10 overflow-hidden rounded-full"
              style={{ background: "var(--surface-3)" }}
            >
              <span
                className="block h-full rounded-full"
                style={{
                  width: `${Math.min(column.null_pct, 100)}%`,
                  background: column.null_pct >= 20 ? "#ec835a" : "var(--axis)",
                }}
              />
            </span>
            <span className="tabular text-[10px]" style={{ color: "var(--text-muted)" }}>
              {formatPercent(column.null_pct)}
            </span>
          </span>
        )}

        <span aria-hidden className="text-[10px]" style={{ color: "var(--text-muted)" }}>
          {open ? "▾" : "▸"}
        </span>
      </button>

      {open && (
        <dl
          className="space-y-1 px-3 pb-3 pl-11 text-[11px]"
          style={{ color: "var(--text-secondary)" }}
        >
          <Stat label="type" value={`${TYPE_LABEL[column.semantic_type]} (${column.dtype})`} />
          <Stat label="distinct" value={formatNumber(column.distinct_count)} />
          <Stat label="non-null" value={formatNumber(column.non_null_count)} />

          {isNumeric && (
            <>
              <Stat label="min / max" value={`${formatNumber(column.min!)} … ${formatNumber(column.max!)}`} />
              <Stat
                label="Q1 / median / Q3"
                value={`${formatNumber(column.q1!)} · ${formatNumber(column.median!)} · ${formatNumber(column.q3!)}`}
              />
              <Stat label="mean" value={formatNumber(column.mean!)} />
              <Stat label="std dev" value={formatNumber(column.std!)} />
              <Stat label="skew" value={column.skew!.toFixed(2)} />
              <Stat label="outliers (IQR)" value={formatNumber(column.outlier_count!)} />
            </>
          )}

          {column.top_values.length > 0 && (
            <div className="pt-1">
              <p style={{ color: "var(--text-muted)" }}>most frequent</p>
              <ul className="mt-1 space-y-0.5">
                {column.top_values.map((entry) => (
                  <li key={entry.value} className="flex justify-between gap-2">
                    <span className="truncate">{entry.value}</span>
                    <span className="tabular shrink-0">{formatNumber(entry.count)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </dl>
      )}
    </li>
  );
}

export default function SchemaPanel({ profile }: { profile: DatasetProfile }) {
  return (
    <section>
      <header className="mb-2 flex items-baseline justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          Columns
        </h2>
        <span className="tabular text-[10px]" style={{ color: "var(--text-muted)" }}>
          {profile.row_count.toLocaleString()} × {profile.column_count} ·{" "}
          {formatBytes(profile.memory_bytes)}
        </span>
      </header>

      <ul
        className="overflow-hidden rounded-lg border"
        style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
      >
        {profile.columns.map((column) => (
          <ColumnRow key={column.name} column={column} />
        ))}
      </ul>
    </section>
  );
}
