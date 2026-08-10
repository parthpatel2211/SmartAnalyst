export type Phase = "generating" | "running" | "rendering";

const STEPS: { id: Phase; label: string }[] = [
  { id: "generating", label: "Writing SQL" },
  { id: "running", label: "Running the query" },
  { id: "rendering", label: "Building the chart" },
];

/**
 * The wait on a model call is a few seconds. A stepped indicator shows what
 * is happening during it, which reads as progress rather than as a hang.
 */
export default function LoadingSteps({ phase }: { phase: Phase }) {
  const activeIndex = STEPS.findIndex((step) => step.id === phase);

  return (
    <div
      className="rounded-xl border p-4"
      style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
    >
      <ol className="space-y-2">
        {STEPS.map((step, index) => {
          const done = index < activeIndex;
          const active = index === activeIndex;
          return (
            <li key={step.id} className="flex items-center gap-2 text-xs">
              <span
                aria-hidden
                className={`inline-flex h-4 w-4 items-center justify-center rounded-full text-[9px] ${
                  active ? "animate-pulse-soft" : ""
                }`}
                style={{
                  background: done || active ? "var(--accent)" : "var(--surface-3)",
                  color: done || active ? "#ffffff" : "var(--text-muted)",
                }}
              >
                {done ? "✓" : index + 1}
              </span>
              <span
                style={{
                  color: active
                    ? "var(--text-primary)"
                    : done
                      ? "var(--text-secondary)"
                      : "var(--text-muted)",
                }}
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
