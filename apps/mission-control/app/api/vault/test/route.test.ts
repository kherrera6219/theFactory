import { afterEach, describe, expect, it, vi } from "vitest";

const getVaultSecret = vi.fn();
const testSecret = vi.fn();

vi.mock("../../../lib/server/vault", () => ({
  getVaultSecret,
  testSecret,
}));

describe("vault test route authorization", () => {
  afterEach(() => {
    getVaultSecret.mockReset();
    testSecret.mockReset();
    vi.resetModules();
    delete process.env.VAULT_ADMIN_KEY;
  });

  it("permits same-origin local browser validation", async () => {
    testSecret.mockReturnValue({ valid: true, reason: "format looks correct" });
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault/test", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: "http://127.0.0.1:3000",
          Referer: "http://127.0.0.1:3000/settings",
          "Sec-Fetch-Site": "same-origin",
        },
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

  it("rejects cross-origin validation requests without admin access", async () => {
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault/test", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: "https://attacker.example",
          Referer: "https://attacker.example/steal",
          "Sec-Fetch-Site": "cross-site",
        },
        body: JSON.stringify({
          slot_id: "AGENT-01-PM-API-KEY",
          provider: "anthropic",
          secret: "sk-ant-test-123456",
        }),
      }),
    );

    expect(response.status).toBe(401);
  });
});
