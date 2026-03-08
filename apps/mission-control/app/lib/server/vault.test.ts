import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type VaultModule = typeof import("./vault");

async function importVaultModule(): Promise<VaultModule> {
  vi.resetModules();
  return import("./vault");
}

describe("vault backend", () => {
  beforeEach(() => {
    delete process.env.VAULT_ADDR;
    delete process.env.VAULT_TOKEN;
    delete process.env.VAULT_ROLE_ID;
    delete process.env.VAULT_SECRET_ID;
    delete process.env.VAULT_NAMESPACE;
    delete process.env.VAULT_KV_MOUNT;
    delete process.env.VAULT_KV_PREFIX;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("falls back to in-memory storage when Vault is not configured", async () => {
    const vault = await importVaultModule();

    const saved = await vault.upsertVaultSlot("agent-01-pm-api-key", "anthropic", "sk-ant-test-123456");
    expect(saved.backend).toBe("memory");

    const secret = await vault.getVaultSecret("AGENT-01-PM-API-KEY");
    const slots = await vault.listVaultSlots();

    expect(secret).toBe("sk-ant-test-123456");
    expect(slots[0]).toMatchObject({
      slot_id: "AGENT-01-PM-API-KEY",
      provider: "anthropic",
      backend: "memory",
    });
  });

  it("uses HashiCorp Vault KV when Vault env is configured", async () => {
    process.env.VAULT_ADDR = "http://vault:8200";
    process.env.VAULT_TOKEN = "root-token";

    const records = new Map<string, { provider: string; secret: string; updated_at: string }>();
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      const slotId = decodeURIComponent(url.pathname.split("/").pop() ?? "");

      if (method === "POST" && url.pathname.includes("/data/")) {
        const payload = JSON.parse(String(init?.body ?? "{}")) as {
          data?: { provider?: string; secret?: string; updated_at?: string };
        };
        records.set(slotId, {
          provider: String(payload.data?.provider ?? "operator"),
          secret: String(payload.data?.secret ?? ""),
          updated_at: String(payload.data?.updated_at ?? "2026-03-08T00:00:00.000Z"),
        });
        return new Response(JSON.stringify({ data: { version: 1 } }), { status: 200 });
      }

      if (method === "GET" && url.pathname.includes("/data/")) {
        const record = records.get(slotId);
        if (!record) {
          return new Response("{}", { status: 404 });
        }
        return new Response(
          JSON.stringify({
            data: {
              data: record,
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }

      if (method === "LIST" && url.pathname.endsWith("/metadata/thefactory/mission-control")) {
        return new Response(
          JSON.stringify({
            data: {
              keys: Array.from(records.keys()),
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }

      if (method === "DELETE" && url.pathname.includes("/metadata/")) {
        const existed = records.delete(slotId);
        return new Response(null, { status: existed ? 204 : 404 });
      }

      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const vault = await importVaultModule();
    const saved = await vault.upsertVaultSlot("github-token", "github", "github_pat_test_123456");
    const secret = await vault.getVaultSecret("GITHUB-TOKEN");
    const slots = await vault.listVaultSlots();
    const removed = await vault.deleteVaultSlot("GITHUB-TOKEN");

    expect(saved.backend).toBe("hashicorp-vault");
    expect(secret).toBe("github_pat_test_123456");
    expect(slots[0]).toMatchObject({
      slot_id: "GITHUB-TOKEN",
      provider: "github",
      backend: "hashicorp-vault",
    });
    expect(removed).toBe(true);
    expect(fetchMock).toHaveBeenCalled();
  });
});
