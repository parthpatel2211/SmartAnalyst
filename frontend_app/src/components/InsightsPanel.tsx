import { STATUS } from "../lib/palette";
import type { Insight, Severity } from "../types";

const SEVERITY_LABEL: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

/**
 * Severity is carried by a text label as well as a colour dot. Status colour
 * never conveys meaning on its own.
 */
function SeverityTag({ severity }: { severity: Severity }) {
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
      style={{ background: "var(--surface-3)", color: "var(--text-secondary)" }}
    >
      <span
        aria-hidden
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: STATUS[severity] }}
      />
      {SEVERITY_LABEL[severity]}
    </span>
  );
}

export default function InsightsPanel({ insights }: { insights: Insight[] }) {
  if (insights.length === 0) {
    return (
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        No data-quality issues found. Nothing missing, constant, duplicated, or
        unusually distributed.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {insights.map((insight, index) => (
        <li
          key={`${insight.kind}-${index}`}
          className="rounded-lg border p-3"
          style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
              {insight.title}
            </p>
            <SeverityTag severity={insight.severity} />
          </div>

          <p className="mt-1 text-[11px] leading-snug" style={{ color: "var(--text-secondary)" }}>
            {insight.detail}
          </p>

          {insight.columns.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {insight.columns.map((column) => (
                <span
                  key={column}
                  className="rounded px-1.5 py-0.5 text-[10px]"
                  style={{ background: "var(--surface-3)", color: "var(--text-muted)" }}
                >
                  {column}
                </span>
              ))}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
