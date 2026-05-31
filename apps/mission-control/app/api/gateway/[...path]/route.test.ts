import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "./route";

const fetchMock = vi.fn<typeof fetch>();

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("gateway proxy route", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("forwards a successful upstream response with its status", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const response = await GET(
      new Request("http://localhost/api/gateway/health"),
      context(["health"]),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  it("propagates a 404 from the backend instead of masking it as 200", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Mission not found." }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const response = await GET(
      new Request("http://localhost/api/gateway/v1/missions/missing"),
      context(["v1", "missions", "missing"]),
    );

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({ detail: "Mission not found." });
  });

  it("propagates a 500 from the backend", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "boom" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const response = await POST(
      new Request("http://localhost/api/gateway/v1/missions", { method: "POST", body: "{}" }),
      context(["v1", "missions"]),
    );

    expect(response.status).toBe(500);
  });

  it("returns 503 with a detail message when the backend is unreachable", async () => {
    fetchMock.mockRejectedValueOnce(new Error("ECONNREFUSED"));

    const response = await GET(
      new Request("http://localhost/api/gateway/health"),
      context(["health"]),
    );

    expect(response.status).toBe(503);
    const body = (await response.json()) as { detail?: string };
    expect(body.detail).toContain("Local runtime gateway is unavailable");
  });
});
