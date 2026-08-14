import { useState } from "react";

interface Props {
  open: boolean;
  onSave: (key: string) => void;
  onClose: () => void;
}

export default function ApiKeyDialog({ open, onSave, onClose }: Props) {
  const [value, setValue] = useState("");

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.55)" }}
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="key-dialog-title"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md rounded-xl border p-5"
        style={{ background: "var(--surface-1)", borderColor: "var(--border)" }}
      >
        <h2
          id="key-dialog-title"
          className="text-sm font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          Add an API key
        </h2>

        <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          Natural-language questions need a key. Profiling, insights, and
          correlations do not — those already work.
        </p>

        <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          OpenAI (<code>sk-…</code>) and OpenRouter (<code>sk-or-…</code>) keys
          both work. The provider is chosen from the key itself.
        </p>

        <p className="mt-2 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          The key is held in this browser tab's session storage and is cleared
          when you close the tab. It is sent with each question, used to make
          the call, and never stored on the server.
        </p>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (value.trim()) onSave(value);
          }}
        >
          <input
            type="password"
            autoFocus
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="sk-…"
            aria-label="OpenAI API key"
            className="mt-3 w-full rounded-lg border px-3 py-2 text-xs"
            style={{
              background: "var(--surface-2)",
              borderColor: "var(--border)",
              color: "var(--text-primary)",
            }}
          />

          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-3 py-1.5 text-xs"
              style={{ color: "var(--text-secondary)" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!value.trim()}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
              style={{ background: "var(--accent)" }}
            >
              Save key
            </button>
          </div>
        </form>

        <p className="mt-3 text-[10px]" style={{ color: "var(--text-muted)" }}>
          platform.openai.com/api-keys · openrouter.ai/keys
        </p>
      </div>
    </div>
  );
}
