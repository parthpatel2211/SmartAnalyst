import { useCallback, useEffect, useRef, useState } from "react";

import * as api from "./api/client";
import { ApiError } from "./api/client";
import AnswerCard from "./components/AnswerCard";
import ApiKeyDialog from "./components/ApiKeyDialog";
import Dropzone from "./components/Dropzone";
import LoadingSteps, { type Phase } from "./components/LoadingSteps";
import OverviewPanel from "./components/OverviewPanel";
import SchemaPanel from "./components/SchemaPanel";
import { useApiKey } from "./hooks/useApiKey";
import { useTheme } from "./hooks/useTheme";
import type {
  CorrelationMatrix,
  DatasetProfile,
  Insight,
  Turn,
  UploadResponse,
} from "./types";

const EXAMPLE_QUESTIONS = [
  "What is total revenue by region?",
  "Show monthly revenue over time",
  "Which category has the highest average profit margin?",
  "Compare average delivery days across channels",
  "What is the relationship between revenue and cost?",
  "Top 10 orders by profit",
];

const SAMPLE_URL = "/sample_orders.csv";
const COLD_START_AFTER_MS = 3000;

export default function App() {
  const { theme, toggle } = useTheme();
  const { key, setKey, hasKey } = useApiKey();

  const [dataset, setDataset] = useState<UploadResponse | null>(null);
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [correlations, setCorrelations] = useState<CorrelationMatrix | null>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [phase, setPhase] = useState<Phase | null>(null);

  const [keyDialogOpen, setKeyDialogOpen] = useState(false);
  const [serverWaking, setServerWaking] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const endRef = useRef<HTMLDivElement>(null);

  // Free-tier hosts sleep. Rather than let the first request look broken,
  // ping health on mount and say plainly that the server is waking.
  useEffect(() => {
    let settled = false;
    const timer = setTimeout(() => {
      if (!settled) setServerWaking(true);
    }, COLD_START_AFTER_MS);

    const wake = async () => {
      for (let attempt = 0; attempt < 12; attempt += 1) {
        try {
          await api.health();
          settled = true;
          setServerWaking(false);
          return;
        } catch {
          await new Promise((resolve) => setTimeout(resolve, 4000));
        }
      }
    };

    void wake();
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, phase]);

  const loadAnalysis = useCallback(async (sessionId: string) => {
    const [profileResult, insightsResult, correlationResult] = await Promise.all([
      api.getProfile(sessionId),
      api.getInsights(sessionId),
      api.getCorrelations(sessionId),
    ]);
    setProfile(profileResult);
    setInsights(insightsResult.insights);
    setCorrelations(correlationResult);
  }, []);

  const upload = useCallback(
    async (file: File) => {
      setUploading(true);
      setUploadError(null);
      setTurns([]);
      try {
        const response = await api.uploadDataset(file);
        setDataset(response);
        await loadAnalysis(response.session_id);
        setSidebarOpen(false);
      } catch (error) {
        setUploadError(
          error instanceof ApiError ? error.detail : "Something went wrong reading that file.",
        );
      } finally {
        setUploading(false);
      }
    },
    [loadAnalysis],
  );

  const loadSample = useCallback(async () => {
    setUploading(true);
    setUploadError(null);
    try {
      const response = await fetch(SAMPLE_URL);
      const blob = await response.blob();
      await upload(new File([blob], "sample_orders.csv", { type: "text/csv" }));
    } catch {
      setUploadError("Could not load the sample dataset.");
      setUploading(false);
    }
  }, [upload]);

  const submit = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !dataset || phase) return;

      if (!hasKey) {
        setKeyDialogOpen(true);
        return;
      }

      setQuestion("");
      const id = `${Date.now()}`;
      setTurns((current) => [...current, { id, question: trimmed, answer: null, error: null }]);

      setPhase("generating");
      try {
        // The phase labels track the real request; the backend does not stream
        // progress, so "running" marks the point the call returns.
        const answer = await api.ask(dataset.session_id, trimmed, key);
        setPhase("rendering");
        setTurns((current) =>
          current.map((turn) => (turn.id === id ? { ...turn, answer } : turn)),
        );
      } catch (error) {
        const detail =
          error instanceof ApiError ? error.detail : "The question could not be answered.";
        setTurns((current) =>
          current.map((turn) => (turn.id === id ? { ...turn, error: detail } : turn)),
        );
      } finally {
        setPhase(null);
      }
    },
    [dataset, hasKey, key, phase],
  );

  const sidebar = (
    <div className="space-y-5">
      <Dropzone
        onFile={upload}
        onSample={loadSample}
        busy={uploading}
        onReject={setUploadError}
      />

      {uploadError && (
        <p
          className="rounded-lg px-3 py-2 text-xs"
          style={{ background: "rgba(208,59,59,0.12)", color: "#d03b3b" }}
        >
          {uploadError}
        </p>
      )}

      {profile && <SchemaPanel profile={profile} />}
    </div>
  );

  return (
    <div className="flex h-full flex-col">
      <header
        className="flex shrink-0 items-center gap-3 border-b px-4 py-2.5"
        style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
      >
        <button
          type="button"
          onClick={() => setSidebarOpen((open) => !open)}
          className="rounded px-2 py-1 text-xs lg:hidden"
          style={{ background: "var(--surface-3)", color: "var(--text-secondary)" }}
          aria-label="Toggle dataset panel"
        >
          ☰
        </button>

        <h1 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          SmartAnalyst
        </h1>

        {dataset && (
          <span className="truncate text-xs tabular" style={{ color: "var(--text-muted)" }}>
            {dataset.name} · {dataset.row_count.toLocaleString()} × {dataset.column_count}
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => setKeyDialogOpen(true)}
            className="rounded-full px-2.5 py-1 text-[10px] font-medium"
            style={{
              background: hasKey ? "rgba(12,163,12,0.14)" : "var(--surface-3)",
              color: hasKey ? "#0ca30c" : "var(--text-muted)",
            }}
            title={hasKey ? "API key set for this tab" : "No API key set"}
          >
            {hasKey ? "● key set" : "○ no key"}
          </button>

          <button
            type="button"
            onClick={toggle}
            className="rounded px-2 py-1 text-xs"
            style={{ background: "var(--surface-3)", color: "var(--text-secondary)" }}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </div>
      </header>

      {serverWaking && (
        <div
          className="shrink-0 px-4 py-2 text-xs"
          style={{ background: "rgba(250,178,25,0.14)", color: "var(--text-secondary)" }}
        >
          <span className="animate-pulse-soft">
            Waking the analysis server. Free hosting sleeps when idle, so the first
            request can take up to a minute.
          </span>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside
          className={`w-80 shrink-0 overflow-y-auto border-r p-4 lg:block ${
            sidebarOpen ? "block" : "hidden"
          }`}
          style={{ borderColor: "var(--border)", background: "var(--surface-2)" }}
        >
          {sidebar}
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto p-4">
            {!dataset ? (
              <div className="mx-auto flex h-full max-w-lg flex-col items-center justify-center text-center">
                <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
                  Ask questions about a CSV
                </h2>
                <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                  SmartAnalyst turns each question into SQL, runs it against your
                  data, and shows you the query it wrote.
                </p>
                <button
                  type="button"
                  onClick={loadSample}
                  disabled={uploading}
                  className="mt-5 rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                  style={{ background: "var(--accent)" }}
                >
                  {uploading ? "Loading…" : "Try the sample dataset"}
                </button>
                <p className="mt-3 text-xs" style={{ color: "var(--text-muted)" }}>
                  Profiling, insights, and correlations need no API key.
                </p>
              </div>
            ) : (
              <div
                className={`mx-auto space-y-5 ${
                  turns.length === 0 ? "max-w-5xl" : "max-w-3xl"
                }`}
              >
                {/* Before the first question the main column carries the
                    analysis, all of which is computed without an API key.
                    Once a conversation starts it steps aside. */}
                {turns.length === 0 && profile && (
                  <OverviewPanel
                    profile={profile}
                    insights={insights}
                    correlations={correlations}
                    mode={theme}
                  />
                )}

                {turns.length === 0 && (
                  <div>
                    <p className="mb-2 text-xs" style={{ color: "var(--text-muted)" }}>
                      Ask a question
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {EXAMPLE_QUESTIONS.map((example) => (
                        <button
                          key={example}
                          type="button"
                          onClick={() => void submit(example)}
                          className="rounded-full border px-3 py-1.5 text-xs transition-colors hover:opacity-80"
                          style={{
                            borderColor: "var(--border)",
                            color: "var(--text-secondary)",
                            background: "var(--surface-1)",
                          }}
                        >
                          {example}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {turns.map((turn) => (
                  <div key={turn.id} className="space-y-2">
                    <p
                      className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md px-3.5 py-2 text-sm"
                      style={{ background: "var(--accent-soft)", color: "var(--text-primary)" }}
                    >
                      {turn.question}
                    </p>

                    {turn.answer && <AnswerCard answer={turn.answer} mode={theme} />}

                    {turn.error && (
                      <div
                        className="rounded-xl border p-3 text-xs"
                        style={{ borderColor: "rgba(208,59,59,0.4)", background: "rgba(208,59,59,0.08)" }}
                      >
                        <p style={{ color: "#d03b3b" }}>{turn.error}</p>
                        <button
                          type="button"
                          onClick={() => void submit(turn.question)}
                          className="mt-2 rounded px-2 py-1 text-[11px]"
                          style={{ background: "var(--surface-3)", color: "var(--text-secondary)" }}
                        >
                          Try again
                        </button>
                      </div>
                    )}
                  </div>
                ))}

                {phase && <LoadingSteps phase={phase} />}
                <div ref={endRef} />
              </div>
            )}
          </div>

          {dataset && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void submit(question);
              }}
              className="shrink-0 border-t p-3"
              style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
            >
              <div className="mx-auto flex max-w-3xl gap-2">
                <input
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Ask about this dataset…"
                  disabled={Boolean(phase)}
                  aria-label="Question"
                  className="flex-1 rounded-lg border px-3 py-2 text-sm disabled:opacity-50"
                  style={{
                    background: "var(--surface-2)",
                    borderColor: "var(--border)",
                    color: "var(--text-primary)",
                  }}
                />
                <button
                  type="submit"
                  disabled={Boolean(phase) || !question.trim()}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-35"
                  style={{ background: "var(--accent)" }}
                >
                  Ask
                </button>
              </div>
            </form>
          )}
        </main>
      </div>

      <ApiKeyDialog
        open={keyDialogOpen}
        onSave={(value) => {
          setKey(value);
          setKeyDialogOpen(false);
        }}
        onClose={() => setKeyDialogOpen(false)}
      />
    </div>
  );
}
