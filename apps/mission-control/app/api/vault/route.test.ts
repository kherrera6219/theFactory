import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const listVaultSlots = vi.fn();
const upsertVaultSlot = vi.fn();
const deleteVaultSlot = vi.fn();

vi.mock("../../lib/server/vault", () => ({
  listVaultSlots,
  upsertVaultSlot,
  deleteVaultSlot,
}));

const ORIGINAL_BYPASS = process.env.MISSION_CONTROL_BYPASS_AUTH;
const ORIGINAL_SESSION_SECRET = process.env.MISSION_CONTROL_SESSION_SECRET;
const ORIGINAL_ADMIN_KEY = process.env.MISSION_CONTROL_ADMIN_KEY;

function request(method: string, body?: unknown): Request {
  return new Request("http://127.0.0.1:3000/api/vault", {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

describe("vault route", () => {
  beforeEach(() => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
  });

  afterEach(() => {
    listVaultSlots.mockReset();
    upsertVaultSlot.mockReset();
    deleteVaultSlot.mockReset();
    vi.resetModules();
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

  it("GET returns all vault slots for an authorized caller", async () => {
    listVaultSlots.mockResolvedValue([{ slot_id: "AGENT-01-PM-API-KEY" }]);
    const { GET } = await import("./route");

    const response = await GET(request("GET"));

    expect(response.status).toBe(200);
    const payload = (await response.json()) as { slots?: Array<Record<string, unknown>> };
    expect(payload.slots).toEqual([{ slot_id: "AGENT-01-PM-API-KEY" }]);
  });

  it("POST saves a vault slot for an authorized caller", async () => {
    upsertVaultSlot.mockResolvedValue({
      slot_id: "AGENT-01-PM-API-KEY",
      backend: "local-encrypted",
    });
    const { POST } = await import("./route");

    const response = await POST(
      request("POST", {
        slot_id: "AGENT-01-PM-API-KEY",
        provider: "anthropic",
        model: "claude-opus-4-8",
        secret: "sk-ant-test-123456",
      }),
    );

    expect(response.status).toBe(200);
    expect(upsertVaultSlot).toHaveBeenCalledWith(
      "AGENT-01-PM-API-KEY",
      "anthropic",
      "sk-ant-test-123456",
      "claude-opus-4-8",
    );
  });

  it("POST returns 400 when required fields are missing", async () => {
    const { POST } = await import("./route");

    const response = await POST(request("POST", { slot_id: "AGENT-01-PM-API-KEY" }));

    expect(response.status).toBe(400);
  });

  it("rejects GET/POST/DELETE requests without vault authorization", async () => {
    // Regression: isAuthorizedVaultRequest existed but was never wired into
    // these route handlers -- any unauthenticated caller could list,
    // overwrite, or delete every vault secret (including OPERATOR-API-KEY).
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    const { GET, POST, DELETE } = await import("./route");

    const getResponse = await GET(request("GET"));
    expect(getResponse.status).toBe(401);
    expect(listVaultSlots).not.toHaveBeenCalled();

    const postResponse = await POST(
      request("POST", {
        slot_id: "AGENT-01-PM-API-KEY",
        provider: "anthropic",
        secret: "sk-ant-test-123456",
      }),
    );
    expect(postResponse.status).toBe(401);
    expect(upsertVaultSlot).not.toHaveBeenCalled();

    const deleteResponse = await DELETE(request("DELETE", { slot_id: "AGENT-01-PM-API-KEY" }));
    expect(deleteResponse.status).toBe(401);
    expect(deleteVaultSlot).not.toHaveBeenCalled();
  });
});
