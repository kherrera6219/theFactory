import { existsSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
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
    delete process.env.VAULT_SLOT_TTL_SECONDS;
    delete process.env.VAULT_SLOT_TTL_DAYS;
    delete process.env.VAULT_SLOT_ROTATION_WARNING_SECONDS;
    delete process.env.VAULT_SLOT_ROTATION_WARNING_DAYS;
    delete process.env.VAULT_ENFORCE_SLOT_TTL;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.VAULT_DATA_PATH;
  });

  afterEach(() => {
    vi.useRealTimers();
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
      model: "claude-opus-4-8",
      backend: "memory",
      status: "set",
      rotation_due: false,
    });
  });

  it("preserves knowledge embedding model metadata", async () => {
    const vault = await importVaultModule();

    await vault.upsertVaultSlot(
      "knowledge-embedding-api-key",
      "gemini",
      "AIza-test-123456",
      "gemini-embedding-001",
    );

    const [slot] = await vault.listVaultSlots();

    expect(slot).toMatchObject({
      slot_id: "KNOWLEDGE-EMBEDDING-API-KEY",
      provider: "gemini",
      model: "gemini-embedding-001",
      status: "set",
    });
  });

  it("enforces TTL expiry for in-memory secrets", async () => {
    process.env.VAULT_SLOT_TTL_SECONDS = "3600";
    process.env.VAULT_SLOT_ROTATION_WARNING_SECONDS = "600";

    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-09T00:00:00.000Z"));
    const vault = await importVaultModule();

    await vault.upsertVaultSlot("operator-api-key", "operator", "operator-secret-123456");
    vi.setSystemTime(new Date("2026-03-09T01:01:00.000Z"));

    const secret = await vault.getVaultSecret("OPERATOR-API-KEY");
    const slots = await vault.listVaultSlots();

    expect(secret).toBeNull();
    expect(slots[0]).toMatchObject({
      slot_id: "OPERATOR-API-KEY",
      status: "expired",
      rotation_due: true,
    });
  });

  it("encrypts secrets at rest and persists to file when MISSION_CONTROL_ADMIN_KEY is configured", async () => {
    // 64 hex chars = 32 bytes for AES-256-GCM
    const tempFile = join(tmpdir(), `vault-test-${Date.now()}.json`);
    process.env.MISSION_CONTROL_ADMIN_KEY = "a".repeat(64);
    process.env.VAULT_DATA_PATH = tempFile;

    try {
      const vault = await importVaultModule();

      const saved = await vault.upsertVaultSlot("agent-01-pm-api-key", "anthropic", "sk-ant-test-123456");
      expect(saved.backend).toBe("local-encrypted");

      // Secret is readable from the in-memory cache
      const secret = await vault.getVaultSecret("AGENT-01-PM-API-KEY");
      expect(secret).toBe("sk-ant-test-123456");

      // File was written — secret must not appear in plaintext on disk
      expect(existsSync(tempFile)).toBe(true);
      const raw = readFileSync(tempFile, "utf8");
      expect(raw).not.toContain("sk-ant-test-123456");

      const parsed = JSON.parse(raw) as {
        version: number;
        entries: Record<string, { secret: { iv: string; authTag: string; ciphertext: string } }>;
      };
      expect(parsed.version).toBe(1);
      const storedEntry = parsed.entries["AGENT-01-PM-API-KEY"];
      expect(storedEntry.secret).toHaveProperty("iv");
      expect(storedEntry.secret).toHaveProperty("authTag");
      expect(storedEntry.secret).toHaveProperty("ciphertext");
    } finally {
      if (existsSync(tempFile)) rmSync(tempFile);
    }
  });

  it("uses HashiCorp Vault KV when Vault env is configured", async () => {
    process.env.VAULT_ADDR = "http://vault:8200";
    process.env.VAULT_TOKEN = "root-token";

    const records = new Map<
      string,
      {
        provider: string;
        secret: string;
        created_at: string;
        updated_at: string;
        expires_at: string;
        ttl_seconds: number;
      }
    >();
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      const slotId = decodeURIComponent(url.pathname.split("/").pop() ?? "");

      if (method === "POST" && url.pathname.includes("/data/")) {
        const payload = JSON.parse(String(init?.body ?? "{}")) as {
          data?: {
            provider?: string;
            secret?: string;
            created_at?: string;
            updated_at?: string;
            expires_at?: string;
            ttl_seconds?: number;
          };
        };
        records.set(slotId, {
          provider: String(payload.data?.provider ?? "operator"),
          secret: String(payload.data?.secret ?? ""),
          created_at: String(payload.data?.created_at ?? "2026-03-08T00:00:00.000Z"),
          updated_at: String(payload.data?.updated_at ?? "2026-03-08T00:00:00.000Z"),
          expires_at: String(payload.data?.expires_at ?? "2026-06-06T00:00:00.000Z"),
          ttl_seconds: Number(payload.data?.ttl_seconds ?? 7_776_000),
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
      status: "set",
      rotation_due: false,
    });
    expect(removed).toBe(true);
    expect(fetchMock).toHaveBeenCalled();
  });
});
