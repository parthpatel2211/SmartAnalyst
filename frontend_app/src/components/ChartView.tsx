import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatAxisTick, formatCell, formatNumber } from "../lib/format";
import { CHROME, type Mode, SERIES, seriesColor } from "../lib/palette";
import type { ChartSpec } from "../types";
import TableView from "./TableView";

interface Props {
  spec: ChartSpec;
  columns: string[];
  rows: Record<string, unknown>[];
  truncated: boolean;
  mode: Mode;
}

const HISTOGRAM_BINS = 20;
const AXIS_FONT = 12;

/** Bars and lines are read against neighbours, so every validated slot is usable. */
const MAX_ADJACENT_SERIES = SERIES.light.length;

/** Recharts hands us the raw payload; this keeps tooltip styling in one place. */
function ChartTooltip({ mode }: { mode: Mode }) {
  const chrome = CHROME[mode];
  return (
    <Tooltip
      cursor={{ fill: chrome.grid, fillOpacity: 0.35 }}
      contentStyle={{
        background: chrome.surface,
        border: `1px solid ${chrome.axis}`,
        borderRadius: 8,
        fontSize: 12,
        color: chrome.textPrimary,
        boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
      }}
      labelStyle={{ color: chrome.textSecondary, marginBottom: 4 }}
      formatter={(value: unknown, name: string) => [formatCell(value), name]}
      labelFormatter={(label: unknown) => formatCell(label)}
    />
  );
}

/**
 * Reshape long rows into one row per x value, with a column per series.
 *
 * A grouped comparison arrives as (region, category, revenue) triples. Fed
 * straight to Recharts that renders four bars all labelled "East", because
 * the second dimension has nowhere to go. Pivoting turns each category into
 * its own keyed measure so the bars group and the legend names them.
 */
function pivotBySeries(
  rows: Record<string, unknown>[],
  x: string,
  seriesKey: string,
  measure: string,
): { data: Record<string, unknown>[]; keys: string[] } {
  const byX = new Map<string, Record<string, unknown>>();
  const keys: string[] = [];

  for (const row of rows) {
    const xValue = String(row[x] ?? "");
    const name = String(row[seriesKey] ?? "");
    if (!byX.has(xValue)) byX.set(xValue, { [x]: row[x] });
    byX.get(xValue)![name] = row[measure];
    if (!keys.includes(name)) keys.push(name);
  }

  return { data: [...byX.values()], keys };
}

/**
 * Bin a numeric column for a histogram. Recharts has no histogram mark, so
 * the binning happens here and renders as a bar chart.
 */
function toHistogram(rows: Record<string, unknown>[], column: string) {
  const values = rows
    .map((row) => Number(row[column]))
    .filter((value) => Number.isFinite(value));

  if (values.length === 0) return [];

  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return [{ bin: formatNumber(min), count: values.length }];

  const width = (max - min) / HISTOGRAM_BINS;
  const counts = new Array(HISTOGRAM_BINS).fill(0);

  for (const value of values) {
    const index = Math.min(Math.floor((value - min) / width), HISTOGRAM_BINS - 1);
    counts[index] += 1;
  }

  return counts.map((count, index) => ({
    bin: formatNumber(min + index * width),
    count,
  }));
}

export default function ChartView({ spec, columns, rows, truncated, mode }: Props) {
  const chrome = CHROME[mode];

  if (rows.length === 0) {
    return (
      <p className="py-10 text-center text-sm" style={{ color: chrome.muted }}>
        The query returned no rows.
      </p>
    );
  }

  if (spec.kind === "table") {
    return <TableView columns={columns} rows={rows} truncated={truncated} mode={mode} />;
  }

  const axisProps = {
    stroke: chrome.axis,
    tick: { fill: chrome.muted, fontSize: AXIS_FONT },
    tickLine: false,
  };

  const grid = <CartesianGrid stroke={chrome.grid} strokeDasharray="3 3" vertical={false} />;

  // A grouped chart pivots long rows into one column per series; otherwise the
  // measures named in the spec are the series.
  const grouped =
    spec.series && spec.x && spec.y[0]
      ? pivotBySeries(rows, spec.x, spec.series, spec.y[0])
      : null;

  const plotRows = grouped ? grouped.data : rows;
  const seriesKeys = grouped ? grouped.keys : spec.y;

  // Identity must never rest on colour alone, so anything past one series
  // carries a legend. A lone series is already named by the title.
  const legend =
    seriesKeys.length > 1 ? (
      <Legend
        wrapperStyle={{ fontSize: 12, color: chrome.textSecondary, paddingTop: 8 }}
        iconType="plainline"
        iconSize={14}
      />
    ) : null;

  const common = { data: plotRows, margin: { top: 8, right: 16, bottom: 4, left: 0 } };

  if (spec.kind === "histogram" && spec.x) {
    const bins = toHistogram(rows, spec.x);
    return (
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={bins} margin={common.margin}>
          {grid}
          <XAxis dataKey="bin" {...axisProps} interval="preserveStartEnd" />
          <YAxis {...axisProps} tickFormatter={formatAxisTick} width={52} />
          <ChartTooltip mode={mode} />
          {/* Rounded data-end, square against the baseline. */}
          <Bar dataKey="count" fill={seriesColor(0, mode)} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (spec.kind === "scatter" && spec.x && spec.y[0]) {
    return (
      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ ...common.margin, bottom: 12 }}>
          {grid}
          <XAxis
            type="number"
            dataKey={spec.x}
            name={spec.x}
            {...axisProps}
            tickFormatter={formatAxisTick}
          />
          <YAxis
            type="number"
            dataKey={spec.y[0]}
            name={spec.y[0]}
            {...axisProps}
            tickFormatter={formatAxisTick}
            width={52}
          />
          <ChartTooltip mode={mode} />
          <Scatter
            data={rows}
            fill={seriesColor(0, mode)}
            fillOpacity={0.62}
            // A 2px surface ring keeps overlapping points readable.
            stroke={chrome.surface}
            strokeWidth={1}
          />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  // Bars and lines are read against their neighbours, so the full validated
  // slot order is available here. The three-slot cap belongs to scatter, which
  // is read all-pairs. Slots are assigned in fixed order and never cycled, so
  // anything past the last one is dropped rather than given an invented hue.
  const measures = seriesKeys.slice(0, MAX_ADJACENT_SERIES);
  const droppedSeries = seriesKeys.length - measures.length;

  // A cap that hides part of the data has to say so, or the chart reads as
  // the whole picture when it is not.
  const truncationNote =
    droppedSeries > 0 ? (
      <p className="mt-2 text-[11px]" style={{ color: chrome.muted }}>
        Showing {measures.length} of {seriesKeys.length} series. Use the Table tab
        for the rest.
      </p>
    ) : null;

  if (spec.kind === "line" || spec.kind === "area") {
    const ChartComponent = spec.kind === "line" ? LineChart : AreaChart;
    return (
      <>
      <ResponsiveContainer width="100%" height={320}>
        <ChartComponent {...common}>
          {grid}
          <XAxis dataKey={spec.x ?? undefined} {...axisProps} tickFormatter={formatAxisTick} />
          <YAxis {...axisProps} tickFormatter={formatAxisTick} width={52} />
          <ChartTooltip mode={mode} />
          {legend}
          {measures.map((measure, index) =>
            spec.kind === "line" ? (
              <Line
                key={measure}
                type="monotone"
                dataKey={measure}
                stroke={seriesColor(index, mode)}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: chrome.surface }}
              />
            ) : (
              <Area
                key={measure}
                type="monotone"
                dataKey={measure}
                stroke={seriesColor(index, mode)}
                strokeWidth={2}
                fill={seriesColor(index, mode)}
                fillOpacity={0.16}
              />
            ),
          )}
        </ChartComponent>
      </ResponsiveContainer>
      {truncationNote}
      </>
    );
  }

  return (
    <>
    <ResponsiveContainer width="100%" height={320}>
      <BarChart {...common}>
        {grid}
        <XAxis dataKey={spec.x ?? undefined} {...axisProps} tickFormatter={formatAxisTick} />
        <YAxis {...axisProps} tickFormatter={formatAxisTick} width={52} />
        <ChartTooltip mode={mode} />
        {legend}
        {measures.map((measure, index) => (
          <Bar
            key={measure}
            dataKey={measure}
            fill={seriesColor(index, mode)}
            radius={[4, 4, 0, 0]}
            // A 2px surface gap between adjacent bars.
            maxBarSize={48}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
    {truncationNote}
    </>
  );
}
