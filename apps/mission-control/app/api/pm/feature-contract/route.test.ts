import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deleteVaultSlot, upsertVaultSlot } from "../../../lib/server/vault";
import { POST } from "./route";

const fetchMock = vi.fn<typeof fetch>();
const ORIGINAL_BYPASS = process.env.MISSION_CONTROL_BYPASS_AUTH;
const ORIGINAL_SESSION_SECRET = process.env.MISSION_CONTROL_SESSION_SECRET;
const ORIGINAL_ADMIN_KEY = process.env.MISSION_CONTROL_ADMIN_KEY;
const ORIGINAL_INTERNAL_KEY = process.env.INTERNAL_SERVICE_API_KEY;

function request(body: unknown): Request {
  return new Request("http://localhost/api/pm/feature-contract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("pm feature-contract route", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
    process.env.INTERNAL_SERVICE_API_KEY = "test-internal-key";
  });

  afterEach(async () => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    await deleteVaultSlot("ACTIVE-LLM-ROUTE");
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
    if (ORIGINAL_INTERNAL_KEY === undefined) {
      delete process.env.INTERNAL_SERVICE_API_KEY;
    } else {
      process.env.INTERNAL_SERVICE_API_KEY = ORIGINAL_INTERNAL_KEY;
    }
  });

  it("injects the operator's active LLM route into the forwarded vault payload", async () => {
    await upsertVaultSlot("ACTIVE-LLM-ROUTE", "gemini", "active-route", "gemini-3.7-flash");
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ feature_contract: {} }), { status: 200 }),
    );

    await POST(request({ prompt: "build a snake game" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    const sentPayload = JSON.parse(init?.body as string) as {
      vault?: Record<string, unknown>;
    };
    expect(sentPayload.vault?.llm_provider).toBe("gemini");
    expect(sentPayload.vault?.llm_model).toBe("gemini-3.7-flash");
  });

  it("forwards a superseded Gemini pin as the current model", async () => {
    // Regression for mission-128c77fd: a slot saved against gemini-3.5-flash
    // kept routing every agent on every mission to it, while the Settings page
    // — which no longer lists 3.5 — displayed the 3.7 default.
    await upsertVaultSlot("ACTIVE-LLM-ROUTE", "gemini", "active-route", "gemini-3.5-flash");
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ feature_contract: {} }), { status: 200 }),
    );

    await POST(request({ prompt: "build a snake game" }));

    const [, init] = fetchMock.mock.calls[0];
    const sentPayload = JSON.parse(init?.body as string) as {
      vault?: Record<string, unknown>;
    };
    expect(sentPayload.vault?.llm_model).toBe("gemini-3.7-flash");
  });

  it("omits llm_provider/llm_model when no active route is configured", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ feature_contract: {} }), { status: 200 }),
    );

    await POST(request({ prompt: "build a snake game" }));

    const [, init] = fetchMock.mock.calls[0];
    const sentPayload = JSON.parse(init?.body as string) as {
      vault?: Record<string, unknown>;
    };
    expect(sentPayload.vault).not.toHaveProperty("llm_provider");
    expect(sentPayload.vault).not.toHaveProperty("llm_model");
  });

  it("returns 400 when the prompt is too short", async () => {
    const response = await POST(request({ prompt: "ab" }));
    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
