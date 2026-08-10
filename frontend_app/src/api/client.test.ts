import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, ask, getProfile } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("throws an ApiError carrying the server's detail message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: "Drop is not permitted anywhere in the query." }),
      }),
    );

    await expect(getProfile("abc")).rejects.toMatchObject({
      status: 400,
      detail: "Drop is not permitted anywhere in the query.",
    });
  });

  it("sends the API key in a header and never in the URL", async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    vi.stubGlobal("fetch", spy);

    await ask("sid", "question", "sk-secret-value");

    const [url, init] = spy.mock.calls[0];
    expect(String(url)).not.toContain("sk-secret-value");
    expect((init.headers as Record<string, string>)["X-OpenAI-Key"]).toBe("sk-secret-value");
  });

  it("reports a network failure as status 0 so the UI can blame a cold start", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const error = await getProfile("abc").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
    expect(error.isNetworkFailure).toBe(true);
  });

  it("survives an error body that is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => {
          throw new Error("not json");
        },
      }),
    );

    await expect(getProfile("abc")).rejects.toMatchObject({ status: 502 });
  });
});
