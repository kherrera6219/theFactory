import { afterEach, describe, expect, it, vi } from "vitest";

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
  });

  it("allows same-origin local browser reads", async () => {
    listVaultSlots.mockResolvedValue([{ slot_id: "AGENT-01-PM-API-KEY" }]);
    const { GET } = await import("./route");

    const response = await GET(
      new Request("http://127.0.0.1:3000/api/vault", {
        headers: {
          Origin: "http://127.0.0.1:3000",
          Referer: "http://127.0.0.1:3000/settings",
          "Sec-Fetch-Site": "same-origin",
        },
      }),
    );

    expect(response.status).toBe(200);
    const payload = (await response.json()) as { slots?: Array<Record<string, unknown>> };
    expect(payload.slots).toEqual([{ slot_id: "AGENT-01-PM-API-KEY" }]);
  });

  it("rejects cross-origin writes without a trusted origin or admin key", async () => {
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault", {
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
