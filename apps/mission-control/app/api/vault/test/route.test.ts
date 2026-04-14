import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createOperatorSessionToken,
  OPERATOR_SESSION_COOKIE_NAME,
} from "../../../lib/server/operator-session";

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
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
  });

  it("permits authenticated operator validation", async () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";
    testSecret.mockReturnValue({ valid: true, reason: "format looks correct" });
    const { POST } = await import("./route");
    const cookie = `${OPERATOR_SESSION_COOKIE_NAME}=${createOperatorSessionToken()}`;

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault/test", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: cookie,
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

  it("rejects validation requests without operator authentication", async () => {
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault/test", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
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
