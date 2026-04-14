import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createOperatorSessionToken,
  OPERATOR_SESSION_COOKIE_NAME,
} from "../../lib/server/operator-session";

const listVaultSlots = vi.fn();
const upsertVaultSlot = vi.fn();
const deleteVaultSlot = vi.fn();

vi.mock("../../lib/server/vault", () => ({
  listVaultSlots,
  upsertVaultSlot,
  deleteVaultSlot,
}));

describe("vault route authorization", () => {
  afterEach(() => {
    listVaultSlots.mockReset();
    upsertVaultSlot.mockReset();
    deleteVaultSlot.mockReset();
    vi.resetModules();
    delete process.env.VAULT_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
  });

  it("allows authenticated operator reads", async () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";
    listVaultSlots.mockResolvedValue([{ slot_id: "AGENT-01-PM-API-KEY" }]);
    const { GET } = await import("./route");
    const cookie = `${OPERATOR_SESSION_COOKIE_NAME}=${createOperatorSessionToken()}`;

    const response = await GET(
      new Request("http://127.0.0.1:3000/api/vault", {
        headers: {
          Cookie: cookie,
        },
      }),
    );

    expect(response.status).toBe(200);
    const payload = (await response.json()) as { slots?: Array<Record<string, unknown>> };
    expect(payload.slots).toEqual([{ slot_id: "AGENT-01-PM-API-KEY" }]);
  });

  it("rejects writes without operator authentication", async () => {
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault", {
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
