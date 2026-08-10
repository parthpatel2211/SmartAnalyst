import { useCallback } from "react";
import { useDropzone } from "react-dropzone";

const MAX_BYTES = 10 * 1024 * 1024;

interface Props {
  onFile: (file: File) => void;
  onSample: () => void;
  busy: boolean;
  onReject: (message: string) => void;
}

export default function Dropzone({ onFile, onSample, busy, onReject }: Props) {
  const onDrop = useCallback(
    (accepted: File[], rejected: { file: File }[]) => {
      if (rejected.length > 0) {
        onReject("That file is not a CSV. Upload a .csv file.");
        return;
      }
      const file = accepted[0];
      if (!file) return;
      // Checked here as well as server-side so the user is not made to wait
      // for an upload that is going to be refused.
      if (file.size > MAX_BYTES) {
        onReject(
          `That file is ${(file.size / 1_048_576).toFixed(1)} MB; the limit is 10 MB.`,
        );
        return;
      }
      onFile(file);
    },
    [onFile, onReject],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    maxFiles: 1,
    disabled: busy,
  });

  return (
    <div>
      <div
        {...getRootProps()}
        className="cursor-pointer rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors"
        style={{
          borderColor: isDragActive ? "var(--accent)" : "var(--axis)",
          background: isDragActive ? "var(--accent-soft)" : "transparent",
          opacity: busy ? 0.5 : 1,
        }}
      >
        <input {...getInputProps()} />
        <p className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
          {busy ? "Reading…" : isDragActive ? "Drop it here" : "Drop a CSV, or click to browse"}
        </p>
        <p className="mt-1 text-[10px]" style={{ color: "var(--text-muted)" }}>
          Up to 10 MB · stays in memory, never written to disk
        </p>
      </div>

      <button
        type="button"
        onClick={onSample}
        disabled={busy}
        className="mt-2 w-full rounded-lg px-3 py-2 text-xs font-medium transition-opacity hover:opacity-85 disabled:opacity-40"
        style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
      >
        Load sample dataset
      </button>
    </div>
  );
}
