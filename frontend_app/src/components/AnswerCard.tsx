import { lazy, Suspense, useState } from "react";

import { toCsv } from "../lib/format";
import type { Mode } from "../lib/palette";
import type { AskResponse } from "../types";
import TableView from "./TableView";

// Recharts is the largest dependency in the app and nothing needs it until an
// answer renders a chart. The overview heatmap is a plain table, so the first
// paint pulls no charting code at all.
const ChartView = lazy(() => import("./ChartView"));

type Tab = "answer" | "chart" | "table" | "sql";

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
  // The written answer is the default. A chart opens first only when the
  // question actually asked to see one -- asking for a number should get a
  // number, with everything else one click away.
  const canChart = answer.chart.kind !== "table";
  const [tab, setTab] = useState<Tab>(
    answer.chart_requested && canChart ? "chart" : "answer",
  );
  const [copied, setCopied] = useState(false);

  const tabs: { id: Tab; label: string }[] = [
    { id: "answer", label: "Answer" },
    ...(canChart ? [{ id: "chart" as Tab, label: "Chart" }] : []),
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
        {tab === "answer" && (
          <div>
            <p
              className="text-[15px] leading-relaxed"
              style={{ color: "var(--text-primary)" }}
            >
              {answer.answer}
            </p>
            <p className="mt-3 text-xs tabular" style={{ color: "var(--text-muted)" }}>
              {answer.explanation && `${answer.explanation} · `}
              {answer.row_count.toLocaleString()} row
              {answer.row_count === 1 ? "" : "s"}
              {answer.truncated && " · truncated at the row limit"}
            </p>
          </div>
        )}

        {tab === "chart" && (
          <Suspense
            fallback={
              <div
                className="h-[320px] animate-pulse-soft rounded-lg"
                style={{ background: "var(--surface-3)" }}
              />
            }
          >
            <ChartView
              spec={answer.chart}
              columns={answer.columns}
              rows={answer.rows}
              truncated={answer.truncated}
              mode={mode}
            />
          </Suspense>
        )}

        {tab === "table" && (
          <TableView
            columns={answer.columns}
            rows={answer.rows}
            truncated={answer.truncated}
            mode={mode}
          />
        )}

        {/* The SQL wraps rather than scrolling. This tab exists so the query
            can be read, and a horizontal scrollbar hides the end of every
            statement wider than the card. The server sends it pre-formatted
            across several lines. */}
        {tab === "sql" && (
          <pre
            className="rounded-lg p-3 text-xs leading-relaxed"
            style={{
              background: "var(--surface-3)",
              color: "var(--text-primary)",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
            }}
          >
            <code>{answer.sql}</code>
          </pre>
        )}
      </div>
    </div>
  );
}
