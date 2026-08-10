import { formatNumber, formatPercent } from "../lib/format";
import type { Mode } from "../lib/palette";
import type { CorrelationMatrix, DatasetProfile, Insight } from "../types";
import CorrelationHeatmap from "./CorrelationHeatmap";
import InsightsPanel from "./InsightsPanel";

interface Props {
  profile: DatasetProfile;
  insights: Insight[];
  correlations: CorrelationMatrix | null;
  mode: Mode;
}

/**
 * What a visitor sees before asking anything.
 *
 * All of it is computed in pandas with no model involved, so it renders with
 * no API key: the point is that the tool has already done real work by the
 * time anyone is asked for a credential.
 */

function StatTile({
  value,
  label,
  tone,
}: {
  value: string;
  label: string;
  tone?: "warn";
}) {
  return (
    <div
      className="rounded-xl border px-4 py-3"
      style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
    >
      <p
        className="text-xl font-semibold leading-none"
        style={{ color: tone === "warn" ? "#ec835a" : "var(--text-primary)" }}
      >
        {value}
      </p>
      <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
        {label}
      </p>
    </div>
  );
}

export default function OverviewPanel({ profile, insights, correlations, mode }: Props) {
  const dateColumn = profile.columns.find(
    (column) => column.semantic_type === "datetime" && column.min_label,
  );

  const totalCells = profile.row_count * profile.column_count;
  const missingCells = profile.columns.reduce(
    (sum, column) => sum + (profile.row_count - column.non_null_count),
    0,
  );
  const missingPct = totalCells > 0 ? (missingCells / totalCells) * 100 : 0;

  const measures = profile.columns.filter((c) => c.semantic_type === "numeric").length;
  const strongest = correlations?.pairs[0];

  return (
    <div className="space-y-5">
      <section>
        <h2
          className="mb-2 text-xs font-semibold uppercase tracking-wide"
          style={{ color: "var(--text-muted)" }}
        >
          Overview
        </h2>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          <StatTile value={formatNumber(profile.row_count)} label="rows" />
          <StatTile
            value={`${profile.column_count}`}
            label={`columns · ${measures} measures`}
          />
          <StatTile
            value={formatPercent(missingPct, 1)}
            label="cells missing"
            tone={missingPct >= 5 ? "warn" : undefined}
          />
          <StatTile
            value={formatNumber(profile.duplicate_rows)}
            label="duplicate rows"
            tone={profile.duplicate_rows > 0 ? "warn" : undefined}
          />
          {dateColumn ? (
            <StatTile
              value={`${dateColumn.min_label!.slice(0, 7)} → ${dateColumn.max_label!.slice(0, 7)}`}
              label={`${dateColumn.name} range`}
            />
          ) : (
            <StatTile
              value={strongest ? strongest.value.toFixed(2) : "—"}
              label={
                strongest ? `strongest r · ${strongest.x}~${strongest.y}` : "no correlations"
              }
            />
          )}
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[1fr_minmax(0,420px)]">
        <section>
          <h2
            className="mb-2 text-xs font-semibold uppercase tracking-wide"
            style={{ color: "var(--text-muted)" }}
          >
            What stands out
          </h2>
          <InsightsPanel insights={insights} />
        </section>

        {correlations && correlations.columns.length >= 2 && (
          <section>
            <h2
              className="mb-2 text-xs font-semibold uppercase tracking-wide"
              style={{ color: "var(--text-muted)" }}
            >
              Correlations
            </h2>
            <div
              className="rounded-xl border p-3"
              style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
            >
              <CorrelationHeatmap data={correlations} mode={mode} />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
