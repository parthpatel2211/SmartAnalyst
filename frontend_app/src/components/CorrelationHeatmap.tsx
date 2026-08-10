import { correlationColor, type Mode } from "../lib/palette";
import type { CorrelationMatrix } from "../types";

interface Props {
  data: CorrelationMatrix;
  mode: Mode;
}

/**
 * Diverging scale: blue at -1, gray at 0, red at +1. Never a single hue --
 * negative and positive correlation have to read as opposites, not as two
 * intensities of the same thing.
 *
 * Every cell also carries its coefficient as text, so the reading never
 * depends on discriminating colour.
 */
export default function CorrelationHeatmap({ data, mode }: Props) {
  if (data.columns.length < 2) {
    return (
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        At least two numeric columns are needed to compute correlations.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 2 }}>
        <caption className="sr-only">
          Pearson correlation between numeric columns, from -1 to 1
        </caption>
        <thead>
          <tr>
            <th />
            {data.columns.map((column) => (
              <th
                key={column}
                scope="col"
                className="px-1 pb-1 text-[10px] font-medium"
                style={{ color: "var(--text-muted)", writingMode: "vertical-rl" }}
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.matrix.map((row, i) => (
            <tr key={data.columns[i]}>
              <th
                scope="row"
                className="whitespace-nowrap pr-2 text-right text-[10px] font-medium"
                style={{ color: "var(--text-muted)" }}
              >
                {data.columns[i]}
              </th>
              {row.map((value, j) => {
                // The matrix is symmetric and its diagonal is all 1.00. Drawing
                // both triangles doubles every pair, and the diagonal puts the
                // heaviest colour in the grid on the least informative cells.
                if (j > i) return <td key={`${i}-${j}`} className="h-8 w-12" />;

                if (j === i) {
                  return (
                    <td
                      key={`${i}-${j}`}
                      className="h-8 w-12 rounded text-center text-[10px]"
                      style={{ background: "var(--surface-3)", color: "var(--text-muted)" }}
                      aria-hidden
                    >
                      ·
                    </td>
                  );
                }

                const strong = value !== null && Math.abs(value) > 0.6;
                return (
                  <td
                    key={`${i}-${j}`}
                    tabIndex={0}
                    title={`${data.columns[i]} vs ${data.columns[j]}: r = ${
                      value === null ? "n/a" : value.toFixed(3)
                    }`}
                    aria-label={`${data.columns[i]} versus ${data.columns[j]}, r equals ${
                      value === null ? "not available" : value.toFixed(2)
                    }`}
                    className="h-8 w-12 rounded text-center text-[10px] tabular"
                    style={{
                      background: correlationColor(value, mode),
                      // On a saturated cell, ink flips to keep the number legible.
                      color: strong
                        ? "#ffffff"
                        : value === null
                          ? "var(--text-muted)"
                          : "var(--text-primary)",
                    }}
                  >
                    {value === null ? "—" : value.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <div
        className="mt-3 flex items-center gap-2 text-[10px]"
        style={{ color: "var(--text-muted)" }}
      >
        <span>−1</span>
        <div
          className="h-2 w-28 rounded"
          style={{
            background: `linear-gradient(to right, ${correlationColor(-1, mode)}, ${correlationColor(
              0,
              mode,
            )}, ${correlationColor(1, mode)})`,
          }}
        />
        <span>+1</span>
        <span className="ml-1">Pearson r</span>
      </div>
    </div>
  );
}
