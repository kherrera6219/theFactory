import { afterEach, describe, expect, it, vi } from "vitest";

const listVaultSlots = vi.fn();
const upsertVaultSlot = vi.fn();
const deleteVaultSlot = vi.fn();

vi.mock("../../lib/server/vault", () => ({
  listVaultSlots,
  upsertVaultSlot,
  deleteVaultSlot,
}));

describe("vault route", () => {
  afterEach(() => {
    listVaultSlots.mockReset();
    upsertVaultSlot.mockReset();
    deleteVaultSlot.mockReset();
    vi.resetModules();
  });

  it("GET returns all vault slots without authentication", async () => {
    listVaultSlots.mockResolvedValue([{ slot_id: "AGENT-01-PM-API-KEY" }]);
    const { GET } = await import("./route");

    const response = await GET();

    expect(response.status).toBe(200);
    const payload = (await response.json()) as { slots?: Array<Record<string, unknown>> };
    expect(payload.slots).toEqual([{ slot_id: "AGENT-01-PM-API-KEY" }]);
  });

  it("POST saves a vault slot without requiring authentication", async () => {
    upsertVaultSlot.mockResolvedValue({
      slot_id: "AGENT-01-PM-API-KEY",
      backend: "local-encrypted",
    });
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault", {
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
    expect(upsertVaultSlot).toHaveBeenCalledWith(
      "AGENT-01-PM-API-KEY",
      "anthropic",
      "sk-ant-test-123456",
    );
  });

  it("POST returns 400 when required fields are missing", async () => {
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://127.0.0.1:3000/api/vault", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slot_id: "AGENT-01-PM-API-KEY" }),
      }),
    );

    expect(response.status).toBe(400);
  });
});
