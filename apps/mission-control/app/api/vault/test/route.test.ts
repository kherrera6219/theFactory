import { afterEach, describe, expect, it, vi } from "vitest";

const getVaultSecret = vi.fn();
const testSecret = vi.fn();

vi.mock("../../../lib/server/vault", () => ({
  getVaultSecret,
  testSecret,
}));

describe("vault test route", () => {
  afterEach(() => {
    getVaultSecret.mockReset();
    testSecret.mockReset();
    vi.resetModules();
  });

  it("validates a provider key format without requiring authentication", async () => {
    testSecret.mockReturnValue({ valid: true, reason: "format looks correct" });
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slot_id: "AGENT-01-PM-API-KEY",
          provider: "anthropic",
          secret: "sk-ant-test-123456",
        }),
      }),
    );

    expect(response.status).toBe(200);
    const payload = (await response.json()) as { valid?: boolean };
    expect(payload.valid).toBe(true);
  });

  it("returns 400 when provider is missing", async () => {
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret: "sk-ant-test-123456" }),
      }),
    );

    expect(response.status).toBe(400);
  });
});
