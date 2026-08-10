import { useState } from "react";

import { toCsv } from "../lib/format";
import type { Mode } from "../lib/palette";
import type { AskResponse } from "../types";
import ChartView from "./ChartView";
import TableView from "./TableView";

type Tab = "chart" | "table" | "sql";

interface Props {
  answer: AskResponse;
  mode: Mode;
}

function download(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function AnswerCard({ answer, mode }: Props) {
  // A table-kind result has nothing to show on a Chart tab, so open on Table.
  const [tab, setTab] = useState<Tab>(answer.chart.kind === "table" ? "table" : "chart");
  const [copied, setCopied] = useState(false);

  const tabs: { id: Tab; label: string }[] = [
    { id: "chart", label: "Chart" },
    { id: "table", label: "Table" },
    { id: "sql", label: "SQL" },
  ];

  const copySql = async () => {
    await navigator.clipboard.writeText(answer.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div
      className="rounded-xl border"
      style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
    >
      <div className="border-b px-4 py-3" style={{ borderColor: "var(--border)" }}>
        <p className="text-sm" style={{ color: "var(--text-primary)" }}>
          {answer.explanation || answer.chart.title}
        </p>
        <p className="mt-1 text-xs tabular" style={{ color: "var(--text-muted)" }}>
          {answer.row_count.toLocaleString()} row{answer.row_count === 1 ? "" : "s"}
          {answer.truncated && " · truncated at the row limit"}
        </p>
      </div>

      <div
        className="flex items-center justify-between gap-2 border-b px-4 py-2"
        style={{ borderColor: "var(--border)" }}
      >
        <div role="tablist" aria-label="Result view" className="flex gap-1">
          {tabs.map(({ id, label }) => (
            <button
              key={id}
              role="tab"
              type="button"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className="rounded-md px-3 py-1 text-xs font-medium transition-colors"
              style={{
                background: tab === id ? "var(--accent-soft)" : "transparent",
                color: tab === id ? "var(--accent)" : "var(--text-secondary)",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex gap-1">
          {tab === "sql" ? (
            <button
              type="button"
              onClick={copySql}
              className="rounded-md px-2 py-1 text-xs"
              style={{ color: "var(--text-secondary)", background: "var(--surface-3)" }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
          ) : (
            <button
              type="button"
              onClick={() =>
                download(
                  "smartanalyst-result.csv",
                  toCsv(answer.columns, answer.rows),
                  "text/csv",
                )
              }
              className="rounded-md px-2 py-1 text-xs"
              style={{ color: "var(--text-secondary)", background: "var(--surface-3)" }}
            >
              Export CSV
            </button>
          )}
        </div>
      </div>

      <div className="p-4">
        {tab === "chart" && (
          <ChartView
            spec={answer.chart}
            columns={answer.columns}
            rows={answer.rows}
            truncated={answer.truncated}
            mode={mode}
          />
        )}

        {tab === "table" && (
          <TableView
            columns={answer.columns}
            rows={answer.rows}
            truncated={answer.truncated}
            mode={mode}
          />
        )}

        {tab === "sql" && (
          <pre
            className="overflow-x-auto rounded-lg p-3 text-xs leading-relaxed"
            style={{
              background: "var(--surface-3)",
              color: "var(--text-primary)",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
            }}
          >
            <code>{answer.sql}</code>
          </pre>
        )}
      </div>
    </div>
  );
}
