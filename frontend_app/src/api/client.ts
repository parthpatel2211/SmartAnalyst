import type {
  AskResponse,
  CorrelationMatrix,
  DatasetProfile,
  Insight,
  UploadResponse,
} from "../types";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Every failure reaches the UI as one of these. */
export class ApiError extends Error {
  /** 0 means the request never reached the server. */
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  /** A status of 0 usually means the free-tier backend is still waking. */
  get isNetworkFailure(): boolean {
    return this.status === 0;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(
      0,
      "Could not reach the analysis server. It may still be starting up.",
    );
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // A non-JSON error body is not worth surfacing verbatim.
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

export function health(): Promise<{ status: string }> {
  return request("/health");
}

export function uploadDataset(file: File): Promise<UploadResponse> {
  const body = new FormData();
  body.append("file", file);
  return request("/datasets", { method: "POST", body });
}

export function getProfile(sessionId: string): Promise<DatasetProfile> {
  return request(`/datasets/${sessionId}/profile`);
}

export function getInsights(sessionId: string): Promise<{ insights: Insight[] }> {
  return request(`/datasets/${sessionId}/insights`);
}

export function getCorrelations(sessionId: string): Promise<CorrelationMatrix> {
  return request(`/datasets/${sessionId}/correlations`);
}

/**
 * The key travels in a header, never in the URL: query strings end up in
 * server logs, browser history, and referrer headers.
 */
export function ask(
  sessionId: string,
  question: string,
  apiKey: string,
): Promise<AskResponse> {
  return request(`/datasets/${sessionId}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-OpenAI-Key": apiKey,
    },
    body: JSON.stringify({ question }),
  });
}
