import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getVaultSecret = vi.fn();
const testSecret = vi.fn();

vi.mock("../../../lib/server/vault", () => ({
  getVaultSecret,
  testSecret,
}));

const ORIGINAL_BYPASS = process.env.MISSION_CONTROL_BYPASS_AUTH;
const ORIGINAL_SESSION_SECRET = process.env.MISSION_CONTROL_SESSION_SECRET;
const ORIGINAL_ADMIN_KEY = process.env.MISSION_CONTROL_ADMIN_KEY;

function request(body: unknown): Request {
  return new Request("http://127.0.0.1:3000/api/vault/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("vault test route", () => {
  beforeEach(() => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
  });

  afterEach(() => {
    getVaultSecret.mockReset();
    testSecret.mockReset();
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

  it("validates a provider key format for an authorized caller", async () => {
    testSecret.mockReturnValue({ valid: true, reason: "format looks correct" });
    const { POST } = await import("./route");

    const response = await POST(
      request({
        slot_id: "AGENT-01-PM-API-KEY",
        provider: "anthropic",
        secret: "sk-ant-test-123456",
      }),
    );

    expect(response.status).toBe(200);
    const payload = (await response.json()) as { valid?: boolean };
    expect(payload.valid).toBe(true);
  });

  it("returns 400 when provider is missing", async () => {
    const { POST } = await import("./route");

    const response = await POST(request({ secret: "sk-ant-test-123456" }));

    expect(response.status).toBe(400);
  });

  it("rejects requests without vault authorization, before probing any stored secret", async () => {
    // Regression: isAuthorizedVaultRequest existed but was never wired into
    // this route -- an unauthenticated caller could probe whether a slot
    // was populated and get back its format-validity verdict.
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    const { POST } = await import("./route");

    const response = await POST(
      request({ slot_id: "AGENT-01-PM-API-KEY", provider: "anthropic" }),
    );

    expect(response.status).toBe(401);
    expect(getVaultSecret).not.toHaveBeenCalled();
    expect(testSecret).not.toHaveBeenCalled();
  });
});
