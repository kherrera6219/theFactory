import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deleteVaultSlot, upsertVaultSlot } from "../../../lib/server/vault";
import { GET, POST } from "./route";

const fetchMock = vi.fn<typeof fetch>();
const ORIGINAL_BYPASS = process.env.MISSION_CONTROL_BYPASS_AUTH;
const ORIGINAL_SESSION_SECRET = process.env.MISSION_CONTROL_SESSION_SECRET;
const ORIGINAL_ADMIN_KEY = process.env.MISSION_CONTROL_ADMIN_KEY;

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("gateway proxy route", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    if (ORIGINAL_BYPASS === undefined) {
      delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    } else {
      process.env.MISSION_CONTROL_BYPASS_AUTH = ORIGINAL_BYPASS;
    }
    if (ORIGINAL_SESSION_SECRET === undefined) {
      delete process.env.MISSION_CONTROL_SESSION_SECRET;
    } else {
      process.env.MISSION_CONTROL_SESSION_SECRET = ORIGINAL_SESSION_SECRET;
    }
    if (ORIGINAL_ADMIN_KEY === undefined) {
      delete process.env.MISSION_CONTROL_ADMIN_KEY;
    } else {
      process.env.MISSION_CONTROL_ADMIN_KEY = ORIGINAL_ADMIN_KEY;
    }
  });

  it("rejects requests without an operator session, before contacting the backend", async () => {
    // Regression: this catch-all proxy handles nearly all backend traffic
    // (mission creation, /internal/* routes) and previously had no operator
    // session gate at all, unlike every sibling privileged route.
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;

    const response = await GET(
      new Request("http://localhost/api/gateway/v1/missions"),
      context(["v1", "missions"]),
    );

    expect(response.status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
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

  describe("mission-creation vault injection", () => {
    afterEach(async () => {
      await deleteVaultSlot("ACTIVE-LLM-ROUTE");
    });

    it("injects the operator's active LLM route alongside provider keys on mission creation", async () => {
      await upsertVaultSlot("ACTIVE-LLM-ROUTE", "anthropic", "active-route", "claude-opus-4-8");
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify({ mission_id: "mission-1" }), { status: 201 }),
      );

      await POST(
        new Request("http://localhost/api/gateway/v1/missions", {
          method: "POST",
          body: JSON.stringify({ prompt: "build a thing" }),
        }),
        context(["v1", "missions"]),
      );

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [, init] = fetchMock.mock.calls[0];
      const sentPayload = JSON.parse(new TextDecoder().decode(init?.body as ArrayBuffer)) as {
        metadata?: { vault?: Record<string, unknown> };
      };
      expect(sentPayload.metadata?.vault?.llm_provider).toBe("anthropic");
      expect(sentPayload.metadata?.vault?.llm_model).toBe("claude-opus-4-8");
    });

    it("omits llm_provider/llm_model when no active route is configured", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify({ mission_id: "mission-1" }), { status: 201 }),
      );

      await POST(
        new Request("http://localhost/api/gateway/v1/missions", {
          method: "POST",
          body: JSON.stringify({ prompt: "build a thing" }),
        }),
        context(["v1", "missions"]),
      );

      const [, init] = fetchMock.mock.calls[0];
      const sentPayload = JSON.parse(new TextDecoder().decode(init?.body as ArrayBuffer)) as {
        metadata?: { vault?: Record<string, unknown> };
      };
      expect(sentPayload.metadata?.vault).not.toHaveProperty("llm_provider");
      expect(sentPayload.metadata?.vault).not.toHaveProperty("llm_model");
    });
  });
});
