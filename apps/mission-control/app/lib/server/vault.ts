import "server-only";

type VaultProvider = "openai" | "anthropic" | "gemini" | "github" | "operator";
type VaultBackend = "memory" | "hashicorp-vault";

type VaultEntry = {
  slotId: string;
  provider: VaultProvider;
  secret: string;
  updatedAt: string;
};

type CachedToken = {
  token: string;
  expiresAt: number;
};

export type VaultSlotRecord = {
  slot_id: string;
  provider: VaultProvider;
  status: "set" | "missing";
  last_rotated_at: string | null;
  masked_preview: string | null;
  backend?: VaultBackend;
};

const vaultMemory = new Map<string, VaultEntry>();
let cachedVaultToken: CachedToken | null = null;

const VAULT_ADDR = process.env.VAULT_ADDR?.trim() ?? "";
const VAULT_TOKEN = process.env.VAULT_TOKEN?.trim() ?? "";
const VAULT_ROLE_ID = process.env.VAULT_ROLE_ID?.trim() ?? "";
const VAULT_SECRET_ID = process.env.VAULT_SECRET_ID?.trim() ?? "";
const VAULT_NAMESPACE = process.env.VAULT_NAMESPACE?.trim() ?? "";
const VAULT_KV_MOUNT = process.env.VAULT_KV_MOUNT?.trim() || "secret";
const VAULT_KV_PREFIX =
  process.env.VAULT_KV_PREFIX?.trim().replace(/^\/+|\/+$/g, "") || "thefactory/mission-control";
const TOKEN_RENEWAL_WINDOW_MS = 60_000;

function normalizeProvider(value: string): VaultProvider {
  const candidate = value.toLowerCase();
  if (candidate === "openai") return "openai";
  if (candidate === "anthropic") return "anthropic";
  if (candidate === "gemini") return "gemini";
  if (candidate === "github") return "github";
  return "operator";
}

function normalizeSlotId(slotId: string): string {
  return slotId.trim().toUpperCase();
}

function maskSecret(secret: string): string {
  const trimmed = secret.trim();
  if (trimmed.length <= 4) {
    return "****";
  }
  return `${trimmed.slice(0, 4)}${"*".repeat(Math.max(4, trimmed.length - 4))}`;
}

function getVaultBackend(): VaultBackend {
  if (VAULT_ADDR && (VAULT_TOKEN || (VAULT_ROLE_ID && VAULT_SECRET_ID))) {
    return "hashicorp-vault";
  }
  return "memory";
}

function vaultApiUrl(path: string): string {
  return `${VAULT_ADDR.replace(/\/+$/, "")}${path}`;
}

function vaultHeaders(token: string, includeJson = false): HeadersInit {
  const headers: Record<string, string> = {
    "X-Vault-Token": token,
  };
  if (VAULT_NAMESPACE) {
    headers["X-Vault-Namespace"] = VAULT_NAMESPACE;
  }
  if (includeJson) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

function vaultEntryDataPath(slotId: string): string {
  return `/v1/${VAULT_KV_MOUNT}/data/${VAULT_KV_PREFIX}/${encodeURIComponent(slotId)}`;
}

function vaultEntryMetadataPath(slotId: string): string {
  return `/v1/${VAULT_KV_MOUNT}/metadata/${VAULT_KV_PREFIX}/${encodeURIComponent(slotId)}`;
}

function vaultListMetadataPath(): string {
  return `/v1/${VAULT_KV_MOUNT}/metadata/${VAULT_KV_PREFIX}`;
}

async function vaultFetchJson<T>(path: string, init: RequestInit): Promise<T | null> {
  const response = await fetch(vaultApiUrl(path), {
    ...init,
    cache: "no-store",
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Vault request failed with status ${response.status}.`);
  }
  const payload = (await response.json()) as T;
  return payload;
}

async function resolveVaultToken(): Promise<string> {
  if (VAULT_TOKEN) {
    return VAULT_TOKEN;
  }
  if (cachedVaultToken && cachedVaultToken.expiresAt > Date.now() + TOKEN_RENEWAL_WINDOW_MS) {
    return cachedVaultToken.token;
  }
  if (!VAULT_ADDR || !VAULT_ROLE_ID || !VAULT_SECRET_ID) {
    throw new Error("Vault AppRole credentials are not configured.");
  }

  type VaultLoginResponse = {
    auth?: {
      client_token?: string;
      lease_duration?: number;
    };
  };

  const payload = await vaultFetchJson<VaultLoginResponse>("/v1/auth/approle/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(VAULT_NAMESPACE ? { "X-Vault-Namespace": VAULT_NAMESPACE } : {}) },
    body: JSON.stringify({
      role_id: VAULT_ROLE_ID,
      secret_id: VAULT_SECRET_ID,
    }),
  });
  const token = payload?.auth?.client_token?.trim() ?? "";
  if (!token) {
    throw new Error("Vault AppRole login did not return a client token.");
  }
  const leaseDurationSeconds = Number(payload?.auth?.lease_duration ?? 3600);
  cachedVaultToken = {
    token,
    expiresAt: Date.now() + Math.max(60, leaseDurationSeconds) * 1000,
  };
  return token;
}

function memoryListVaultSlots(): VaultSlotRecord[] {
  return Array.from(vaultMemory.values())
    .sort((left, right) => left.slotId.localeCompare(right.slotId))
    .map((item) => ({
      slot_id: item.slotId,
      provider: item.provider,
      status: "set",
      last_rotated_at: item.updatedAt,
      masked_preview: maskSecret(item.secret),
      backend: "memory",
    }));
}

function memoryUpsertVaultSlot(slotId: string, provider: string, secret: string): VaultSlotRecord {
  const normalizedSlot = normalizeSlotId(slotId);
  const normalizedSecret = secret.trim();
  if (!normalizedSlot || !normalizedSecret) {
    throw new Error("slot_id and secret are required");
  }

  const entry: VaultEntry = {
    slotId: normalizedSlot,
    provider: normalizeProvider(provider),
    secret: normalizedSecret,
    updatedAt: new Date().toISOString(),
  };
  vaultMemory.set(normalizedSlot, entry);
  return {
    slot_id: entry.slotId,
    provider: entry.provider,
    status: "set",
    last_rotated_at: entry.updatedAt,
    masked_preview: maskSecret(entry.secret),
    backend: "memory",
  };
}

function memoryDeleteVaultSlot(slotId: string): boolean {
  return vaultMemory.delete(normalizeSlotId(slotId));
}

function memoryGetVaultSecret(slotId: string): string | null {
  const entry = vaultMemory.get(normalizeSlotId(slotId));
  return entry ? entry.secret : null;
}

async function vaultReadEntry(slotId: string): Promise<VaultEntry | null> {
  const token = await resolveVaultToken();
  type VaultDataResponse = {
    data?: {
      data?: {
        provider?: string;
        secret?: string;
        updated_at?: string;
      };
    };
  };

  const payload = await vaultFetchJson<VaultDataResponse>(vaultEntryDataPath(slotId), {
    method: "GET",
    headers: vaultHeaders(token),
  });
  const data = payload?.data?.data;
  if (!data?.secret) {
    return null;
  }
  return {
    slotId,
    provider: normalizeProvider(String(data.provider ?? "operator")),
    secret: String(data.secret),
    updatedAt: String(data.updated_at ?? new Date().toISOString()),
  };
}

async function vaultListVaultSlots(): Promise<VaultSlotRecord[]> {
  const token = await resolveVaultToken();
  type VaultListResponse = {
    data?: {
      keys?: string[];
    };
  };
  const payload = await vaultFetchJson<VaultListResponse>(vaultListMetadataPath(), {
    method: "LIST",
    headers: vaultHeaders(token),
  });
  const keys = Array.isArray(payload?.data?.keys) ? payload.data.keys : [];
  const records = await Promise.all(
    keys
      .map((item) => normalizeSlotId(String(item).replace(/\/+$/, "")))
      .filter((item) => item.length > 0)
      .map(async (slotId) => vaultReadEntry(slotId)),
  );
  return records
    .filter((item): item is VaultEntry => item !== null)
    .sort((left, right) => left.slotId.localeCompare(right.slotId))
    .map((item) => ({
      slot_id: item.slotId,
      provider: item.provider,
      status: "set",
      last_rotated_at: item.updatedAt,
      masked_preview: maskSecret(item.secret),
      backend: "hashicorp-vault",
    }));
}

async function vaultUpsertVaultSlot(
  slotId: string,
  provider: string,
  secret: string,
): Promise<VaultSlotRecord> {
  const normalizedSlot = normalizeSlotId(slotId);
  const normalizedSecret = secret.trim();
  if (!normalizedSlot || !normalizedSecret) {
    throw new Error("slot_id and secret are required");
  }
  const updatedAt = new Date().toISOString();
  const token = await resolveVaultToken();
  await vaultFetchJson(vaultEntryDataPath(normalizedSlot), {
    method: "POST",
    headers: vaultHeaders(token, true),
    body: JSON.stringify({
      data: {
        slot_id: normalizedSlot,
        provider: normalizeProvider(provider),
        secret: normalizedSecret,
        updated_at: updatedAt,
      },
    }),
  });
  return {
    slot_id: normalizedSlot,
    provider: normalizeProvider(provider),
    status: "set",
    last_rotated_at: updatedAt,
    masked_preview: maskSecret(normalizedSecret),
    backend: "hashicorp-vault",
  };
}

async function vaultDeleteVaultSlot(slotId: string): Promise<boolean> {
  const token = await resolveVaultToken();
  const response = await fetch(vaultApiUrl(vaultEntryMetadataPath(normalizeSlotId(slotId))), {
    method: "DELETE",
    headers: vaultHeaders(token),
    cache: "no-store",
  });
  if (response.status === 404) {
    return false;
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Vault delete failed with status ${response.status}.`);
  }
  return true;
}

async function vaultGetVaultSecret(slotId: string): Promise<string | null> {
  const entry = await vaultReadEntry(normalizeSlotId(slotId));
  return entry ? entry.secret : null;
}

export async function listVaultSlots(): Promise<VaultSlotRecord[]> {
  if (getVaultBackend() === "memory") {
    return memoryListVaultSlots();
  }
  return vaultListVaultSlots();
}

export async function upsertVaultSlot(
  slotId: string,
  provider: string,
  secret: string,
): Promise<VaultSlotRecord> {
  if (getVaultBackend() === "memory") {
    return memoryUpsertVaultSlot(slotId, provider, secret);
  }
  return vaultUpsertVaultSlot(slotId, provider, secret);
}

export async function deleteVaultSlot(slotId: string): Promise<boolean> {
  if (getVaultBackend() === "memory") {
    return memoryDeleteVaultSlot(slotId);
  }
  return vaultDeleteVaultSlot(slotId);
}

export async function getVaultSecret(slotId: string): Promise<string | null> {
  if (getVaultBackend() === "memory") {
    return memoryGetVaultSecret(slotId);
  }
  return vaultGetVaultSecret(slotId);
}

export function testSecret(provider: string, secret: string): { valid: boolean; reason: string } {
  const normalizedProvider = normalizeProvider(provider);
  const candidate = secret.trim();
  if (candidate.length < 8) {
    return { valid: false, reason: "Secret appears too short." };
  }

  if (normalizedProvider === "openai") {
    return candidate.startsWith("sk-")
      ? { valid: true, reason: "OpenAI key format looks valid." }
      : { valid: false, reason: "OpenAI keys usually start with sk-." };
  }
  if (normalizedProvider === "anthropic") {
    return candidate.startsWith("sk-ant-")
      ? { valid: true, reason: "Anthropic key format looks valid." }
      : { valid: false, reason: "Anthropic keys usually start with sk-ant-." };
  }
  if (normalizedProvider === "gemini") {
    return candidate.length >= 20
      ? { valid: true, reason: "Gemini key format looks valid." }
      : { valid: false, reason: "Gemini key appears too short." };
  }
  if (normalizedProvider === "github") {
    return candidate.startsWith("ghp_") || candidate.startsWith("github_pat_")
      ? { valid: true, reason: "GitHub token format looks valid." }
      : { valid: false, reason: "GitHub PAT usually starts with ghp_ or github_pat_." };
  }

  return { valid: true, reason: "Operator key stored." };
}
