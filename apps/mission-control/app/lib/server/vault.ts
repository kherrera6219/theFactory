import "server-only";

import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

type VaultProvider = "openai" | "anthropic" | "gemini" | "github" | "operator";
type VaultModel =
  | "gpt-5.5"
  | "claude-opus-4-8"
  | "gemini-3.7-flash"
  | "gemini-embedding-001"
  | "text-embedding-3-large"
  | "text-embedding-3-small";

// Gemini Flash revisions this app has shipped and has since moved past. A slot
// saved while one of these was current keeps returning it forever, and the
// model picker no longer lists them — so the Settings page renders its default
// (3.7) while the vault still hands 3.5 to every agent on every mission. These
// are migrated forward on read rather than preserved.
const SUPERSEDED_GEMINI_MODELS = new Set(["gemini-3.5-flash", "gemini-3.6-flash"]);
const CURRENT_GEMINI_MODEL: VaultModel = "gemini-3.7-flash";

type VaultBackend = "memory" | "local-encrypted" | "hashicorp-vault";

type VaultEntry = {
  slotId: string;
  provider: VaultProvider;
  model?: VaultModel;
  secret: string;
  createdAt: string;
  updatedAt: string;
  expiresAt: string;
  ttlSeconds: number;
};

type CachedToken = {
  token: string;
  expiresAt: number;
};

type EncryptedBlob = {
  iv: string;
  authTag: string;
  ciphertext: string;
};

type VaultFileEntry = Omit<VaultEntry, "secret"> & { secret: EncryptedBlob };

type VaultFileData = {
  version: number;
  entries: Record<string, VaultFileEntry>;
};

export type VaultSlotRecord = {
  slot_id: string;
  provider: VaultProvider;
  model?: VaultModel;
  status: "set" | "expiring" | "expired" | "missing";
  last_rotated_at: string | null;
  masked_preview: string | null;
  expires_at: string | null;
  ttl_seconds: number | null;
  rotation_due: boolean;
  backend?: VaultBackend;
};

// In-memory fallback (no persistence, no encryption)
const vaultMemory = new Map<string, VaultEntry>();
// Local encrypted file cache — loaded once on first access
let localVaultMemory: Map<string, VaultEntry> | null = null;
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
const DEFAULT_SLOT_TTL_SECONDS = Math.max(
  3600,
  Number(process.env.VAULT_SLOT_TTL_SECONDS?.trim() || "0") ||
    Math.max(1, Number(process.env.VAULT_SLOT_TTL_DAYS?.trim() || "90")) * 86400,
);
const ROTATION_WARNING_SECONDS = Math.max(
  3600,
  Number(process.env.VAULT_SLOT_ROTATION_WARNING_SECONDS?.trim() || "0") ||
    Math.max(1, Number(process.env.VAULT_SLOT_ROTATION_WARNING_DAYS?.trim() || "14")) * 86400,
);
const ENFORCE_SLOT_TTL =
  (process.env.VAULT_ENFORCE_SLOT_TTL?.trim().toLowerCase() ?? "true") !== "false";

// Local encrypted file backend — uses MISSION_CONTROL_ADMIN_KEY for AES-256-GCM
const VAULT_ENCRYPTION_KEY = process.env.MISSION_CONTROL_ADMIN_KEY?.trim() ?? "";
const VAULT_DATA_FILE =
  process.env.VAULT_DATA_PATH?.trim() ||
  join(/* turbopackIgnore: true */ homedir(), ".thefactory", "vault.json");

// ─── Helpers ──────────────────────────────────────────────────────────────────

function isValidEncryptionKey(key: string): boolean {
  // Must be exactly 64 hex chars (32 bytes for AES-256)
  return /^[0-9a-f]{64}$/i.test(key);
}

function normalizeProvider(value: string): VaultProvider {
  const candidate = value.toLowerCase();
  if (candidate === "openai") return "openai";
  if (candidate === "anthropic") return "anthropic";
  if (candidate === "gemini") return "gemini";
  if (candidate === "github") return "github";
  return "operator";
}

function normalizeModel(value: string | undefined, provider: VaultProvider): VaultModel | undefined {
  const candidate = (value ?? "").trim();
  if (candidate === "gpt-5.5") return "gpt-5.5";
  if (candidate === "claude-opus-4-8") return "claude-opus-4-8";
  if (candidate === "gemini-3.7-flash") return "gemini-3.7-flash";
  // Migrate a pin saved against an older Flash revision rather than honouring
  // it. Preserving it silently downgraded every agent on every mission.
  if (SUPERSEDED_GEMINI_MODELS.has(candidate)) return CURRENT_GEMINI_MODEL;
  if (candidate === "gemini-embedding-001") return "gemini-embedding-001";
  if (candidate === "text-embedding-3-large") return "text-embedding-3-large";
  if (candidate === "text-embedding-3-small") return "text-embedding-3-small";
  if (provider === "openai") return "gpt-5.5";
  if (provider === "anthropic") return "claude-opus-4-8";
  if (provider === "gemini") return "gemini-3.7-flash";
  return undefined;
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
  if (isValidEncryptionKey(VAULT_ENCRYPTION_KEY)) {
    return "local-encrypted";
  }
  return "memory";
}

function addSeconds(timestamp: string, seconds: number): string {
  const base = new Date(timestamp);
  return new Date(base.getTime() + seconds * 1000).toISOString();
}

function resolveTtlSeconds(value: unknown): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return DEFAULT_SLOT_TTL_SECONDS;
  }
  return Math.max(3600, Math.floor(parsed));
}

function resolveExpiresAt(updatedAt: string, expiresAt?: unknown, ttlSeconds?: unknown): string {
  if (typeof expiresAt === "string" && expiresAt.trim().length > 0) {
    return expiresAt;
  }
  return addSeconds(updatedAt, resolveTtlSeconds(ttlSeconds));
}

function isExpired(entry: VaultEntry): boolean {
  return ENFORCE_SLOT_TTL && Date.parse(entry.expiresAt) <= Date.now();
}

function isRotationDue(entry: VaultEntry): boolean {
  return Date.parse(entry.expiresAt) <= Date.now() + ROTATION_WARNING_SECONDS * 1000;
}

function toSlotRecord(entry: VaultEntry, backend: VaultBackend): VaultSlotRecord {
  const expired = isExpired(entry);
  const rotationDue = isRotationDue(entry);
  const status: VaultSlotRecord["status"] = expired
    ? "expired"
    : rotationDue
      ? "expiring"
      : "set";

  return {
    slot_id: entry.slotId,
    provider: entry.provider,
    model: entry.model,
    status,
    last_rotated_at: entry.updatedAt,
    masked_preview: maskSecret(entry.secret),
    expires_at: entry.expiresAt,
    ttl_seconds: entry.ttlSeconds,
    rotation_due: rotationDue,
    backend,
  };
}

// ─── AES-256-GCM encryption ───────────────────────────────────────────────────

function encryptSecret(plaintext: string, keyHex: string): EncryptedBlob {
  const key = Buffer.from(keyHex, "hex"); // 32 bytes
  const iv = randomBytes(12); // 96-bit IV — GCM recommended size
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const ciphertext = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  return {
    iv: iv.toString("hex"),
    authTag: cipher.getAuthTag().toString("hex"),
    ciphertext: ciphertext.toString("hex"),
  };
}

function decryptSecret(blob: EncryptedBlob, keyHex: string): string {
  const key = Buffer.from(keyHex, "hex");
  const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(blob.iv, "hex"));
  decipher.setAuthTag(Buffer.from(blob.authTag, "hex"));
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(blob.ciphertext, "hex")),
    decipher.final(),
  ]);
  return plaintext.toString("utf8");
}

// ─── Local encrypted file backend ─────────────────────────────────────────────

function readLocalVaultFile(): Map<string, VaultEntry> {
  const map = new Map<string, VaultEntry>();
  try {
    if (!existsSync(/* turbopackIgnore: true */ VAULT_DATA_FILE)) return map;
    const raw = readFileSync(/* turbopackIgnore: true */ VAULT_DATA_FILE, "utf8");
    const data = JSON.parse(raw) as VaultFileData;
    for (const [slotId, entry] of Object.entries(data.entries ?? {})) {
      try {
        const secret = decryptSecret(entry.secret, VAULT_ENCRYPTION_KEY);
        map.set(slotId, { ...entry, secret });
      } catch {
        // Entry encrypted with a different key — skip silently
      }
    }
  } catch {
    // File missing or malformed — start with an empty vault
  }
  return map;
}

function writeLocalVaultFile(memory: Map<string, VaultEntry>): void {
  const entries: Record<string, VaultFileEntry> = {};
  for (const [slotId, entry] of memory) {
    entries[slotId] = { ...entry, secret: encryptSecret(entry.secret, VAULT_ENCRYPTION_KEY) };
  }
  const dir = dirname(/* turbopackIgnore: true */ VAULT_DATA_FILE);
  if (!existsSync(/* turbopackIgnore: true */ dir)) {
    mkdirSync(/* turbopackIgnore: true */ dir, { recursive: true });
  }
  writeFileSync(
    /* turbopackIgnore: true */ VAULT_DATA_FILE,
    JSON.stringify({ version: 1, entries }, null, 2),
    "utf8",
  );
}

function getLocalVaultMemory(): Map<string, VaultEntry> {
  if (localVaultMemory === null) {
    localVaultMemory = readLocalVaultFile();
  }
  return localVaultMemory;
}

function localListVaultSlots(): VaultSlotRecord[] {
  return Array.from(getLocalVaultMemory().values())
    .sort((a, b) => a.slotId.localeCompare(b.slotId))
    .map((item) => toSlotRecord(item, "local-encrypted"));
}

function localUpsertVaultSlot(
  slotId: string,
  provider: string,
  secret: string,
  model?: string,
): VaultSlotRecord {
  const normalizedSlot = normalizeSlotId(slotId);
  const normalizedSecret = secret.trim();
  if (!normalizedSlot || !normalizedSecret) {
    throw new Error("slot_id and secret are required");
  }
  const updatedAt = new Date().toISOString();
  const ttlSeconds = DEFAULT_SLOT_TTL_SECONDS;
  const existing = getLocalVaultMemory().get(normalizedSlot);
  const normalizedProvider = normalizeProvider(provider);
  const entry: VaultEntry = {
    slotId: normalizedSlot,
    provider: normalizedProvider,
    model: normalizeModel(model, normalizedProvider),
    secret: normalizedSecret,
    createdAt: existing?.createdAt ?? updatedAt,
    updatedAt,
    expiresAt: addSeconds(updatedAt, ttlSeconds),
    ttlSeconds,
  };
  getLocalVaultMemory().set(normalizedSlot, entry);
  writeLocalVaultFile(getLocalVaultMemory());
  return toSlotRecord(entry, "local-encrypted");
}

function localDeleteVaultSlot(slotId: string): boolean {
  const normalizedSlot = normalizeSlotId(slotId);
  const removed = getLocalVaultMemory().delete(normalizedSlot);
  if (removed) writeLocalVaultFile(getLocalVaultMemory());
  return removed;
}

function localGetVaultSecret(slotId: string): string | null {
  const entry = getLocalVaultMemory().get(normalizeSlotId(slotId));
  if (!entry || isExpired(entry)) return null;
  return entry.secret;
}

// ─── In-memory backend (fallback — no persistence, no encryption) ──────────────

function memoryListVaultSlots(): VaultSlotRecord[] {
  return Array.from(vaultMemory.values())
    .sort((left, right) => left.slotId.localeCompare(right.slotId))
    .map((item) => toSlotRecord(item, "memory"));
}

function memoryUpsertVaultSlot(
  slotId: string,
  provider: string,
  secret: string,
  model?: string,
): VaultSlotRecord {
  const normalizedSlot = normalizeSlotId(slotId);
  const normalizedSecret = secret.trim();
  if (!normalizedSlot || !normalizedSecret) {
    throw new Error("slot_id and secret are required");
  }

  const updatedAt = new Date().toISOString();
  const ttlSeconds = DEFAULT_SLOT_TTL_SECONDS;
  const normalizedProvider = normalizeProvider(provider);
  const entry: VaultEntry = {
    slotId: normalizedSlot,
    provider: normalizedProvider,
    model: normalizeModel(model, normalizedProvider),
    secret: normalizedSecret,
    createdAt: updatedAt,
    updatedAt,
    expiresAt: addSeconds(updatedAt, ttlSeconds),
    ttlSeconds,
  };
  vaultMemory.set(normalizedSlot, entry);
  return toSlotRecord(entry, "memory");
}

function memoryDeleteVaultSlot(slotId: string): boolean {
  return vaultMemory.delete(normalizeSlotId(slotId));
}

function memoryGetVaultSecret(slotId: string): string | null {
  const entry = vaultMemory.get(normalizeSlotId(slotId));
  if (!entry || isExpired(entry)) {
    return null;
  }
  return entry.secret;
}

// ─── HashiCorp Vault backend ───────────────────────────────────────────────────

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

async function vaultReadEntry(slotId: string): Promise<VaultEntry | null> {
  const token = await resolveVaultToken();
  type VaultDataResponse = {
    data?: {
      data?: {
        provider?: string;
        model?: string;
        secret?: string;
        created_at?: string;
        updated_at?: string;
        expires_at?: string;
        ttl_seconds?: number;
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
  const provider = normalizeProvider(String(data.provider ?? "operator"));
  return {
    slotId,
    provider,
    model: normalizeModel(data.model, provider),
    secret: String(data.secret),
    createdAt: String(data.created_at ?? data.updated_at ?? new Date().toISOString()),
    updatedAt: String(data.updated_at ?? new Date().toISOString()),
    expiresAt: resolveExpiresAt(String(data.updated_at ?? new Date().toISOString()), data.expires_at, data.ttl_seconds),
    ttlSeconds: resolveTtlSeconds(data.ttl_seconds),
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
    .map((item) => toSlotRecord(item, "hashicorp-vault"));
}

async function vaultUpsertVaultSlot(
  slotId: string,
  provider: string,
  secret: string,
  model?: string,
): Promise<VaultSlotRecord> {
  const normalizedSlot = normalizeSlotId(slotId);
  const normalizedSecret = secret.trim();
  if (!normalizedSlot || !normalizedSecret) {
    throw new Error("slot_id and secret are required");
  }
  const updatedAt = new Date().toISOString();
  const ttlSeconds = DEFAULT_SLOT_TTL_SECONDS;
  const normalizedProvider = normalizeProvider(provider);
  const normalizedModel = normalizeModel(model, normalizedProvider);
  const token = await resolveVaultToken();
  await vaultFetchJson(vaultEntryDataPath(normalizedSlot), {
    method: "POST",
    headers: vaultHeaders(token, true),
    body: JSON.stringify({
      data: {
        slot_id: normalizedSlot,
        provider: normalizedProvider,
        model: normalizedModel,
        secret: normalizedSecret,
        created_at: updatedAt,
        updated_at: updatedAt,
        expires_at: addSeconds(updatedAt, ttlSeconds),
        ttl_seconds: ttlSeconds,
      },
    }),
  });
  return toSlotRecord(
    {
      slotId: normalizedSlot,
      provider: normalizedProvider,
      model: normalizedModel,
      secret: normalizedSecret,
      createdAt: updatedAt,
      updatedAt,
      expiresAt: addSeconds(updatedAt, ttlSeconds),
      ttlSeconds,
    },
    "hashicorp-vault",
  );
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
  if (!entry || isExpired(entry)) {
    return null;
  }
  return entry.secret;
}

// ─── Public API ───────────────────────────────────────────────────────────────

export async function listVaultSlots(): Promise<VaultSlotRecord[]> {
  const backend = getVaultBackend();
  let slots: VaultSlotRecord[] = [];
  if (backend === "local-encrypted") slots = localListVaultSlots();
  else if (backend === "hashicorp-vault") slots = await vaultListVaultSlots();
  else slots = memoryListVaultSlots();

  const hasOperatorKey = slots.some((s) => s.slot_id === "OPERATOR-API-KEY");
  if (!hasOperatorKey) {
    const fallback = process.env.INTERNAL_SERVICE_API_KEY?.trim();
    if (fallback) {
      slots.push({
        slot_id: "OPERATOR-API-KEY",
        provider: "operator",
        status: "set",
        last_rotated_at: new Date().toISOString(),
        masked_preview: maskSecret(fallback),
        expires_at: null,
        ttl_seconds: null,
        rotation_due: false,
        backend: backend,
      });
    }
  }
  return slots;
}

export async function upsertVaultSlot(
  slotId: string,
  provider: string,
  secret: string,
  model?: string,
): Promise<VaultSlotRecord> {
  const backend = getVaultBackend();
  if (backend === "local-encrypted") return localUpsertVaultSlot(slotId, provider, secret, model);
  if (backend === "hashicorp-vault") return vaultUpsertVaultSlot(slotId, provider, secret, model);
  return memoryUpsertVaultSlot(slotId, provider, secret, model);
}

export async function deleteVaultSlot(slotId: string): Promise<boolean> {
  const backend = getVaultBackend();
  if (backend === "local-encrypted") return localDeleteVaultSlot(slotId);
  if (backend === "hashicorp-vault") return vaultDeleteVaultSlot(slotId);
  return memoryDeleteVaultSlot(slotId);
}

export async function getVaultSecret(slotId: string): Promise<string | null> {
  const normalizedSlot = normalizeSlotId(slotId);
  const backend = getVaultBackend();
  let secret: string | null = null;
  if (backend === "local-encrypted") secret = localGetVaultSecret(normalizedSlot);
  else if (backend === "hashicorp-vault") secret = await vaultGetVaultSecret(normalizedSlot);
  else secret = memoryGetVaultSecret(normalizedSlot);

  if (!secret && normalizedSlot === "OPERATOR-API-KEY") {
    const fallback = process.env.INTERNAL_SERVICE_API_KEY?.trim();
    if (fallback) {
      return fallback;
    }
  }
  return secret;
}

export function testSecret(provider: string, secret: string): { valid: boolean; reason: string } {
  const normalizedProvider = normalizeProvider(provider);
  const candidate = secret.trim();
  if (candidate.length < 8) {
    return { valid: false, reason: "Secret appears too short." };
  }
  if (candidate.startsWith("AIza")) {
    return { valid: true, reason: "Gemini key accepted for cross-model test mode." };
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

// Base URLs/headers mirror services/orchestrator/orchestrator/llm_delegation/config.py
// exactly, so a preflight pass/fail reflects what the real mission pipeline will see.
const OPENAI_BASE_URL = (process.env.OPENAI_BASE_URL?.trim() || "https://api.openai.com/v1").replace(/\/+$/, "");
const ANTHROPIC_BASE_URL = (process.env.ANTHROPIC_BASE_URL?.trim() || "https://api.anthropic.com/v1").replace(/\/+$/, "");
const ANTHROPIC_VERSION = process.env.ANTHROPIC_VERSION?.trim() || "2023-06-01";
const GEMINI_BASE_URL = (process.env.GEMINI_BASE_URL?.trim() || "https://generativelanguage.googleapis.com/v1beta").replace(/\/+$/, "");
const PREFLIGHT_TIMEOUT_MS = 8_000;

export type ProviderPreflightResult = {
  valid: boolean;
  reason: string;
  live_checked: boolean;
};

async function fetchWithTimeout(input: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PREFLIGHT_TIMEOUT_MS);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/** Real, minimal outbound call per provider — used by the Settings "Test
 * Connection" action so operators see the actual live provider status
 * rather than just a key-format guess. */
export async function preflightProviderCall(
  provider: string,
  secret: string,
  model?: string,
): Promise<ProviderPreflightResult> {
  const normalizedProvider = normalizeProvider(provider);
  const resolvedModel = normalizeModel(model, normalizedProvider);
  const candidate = secret.trim();

  if (/e2e|mock|dummy|fake/i.test(candidate)) {
    const fmt = testSecret(provider, secret);
    return {
      valid: fmt.valid,
      reason: fmt.valid
        ? `${normalizedProvider.toUpperCase()} key format looks valid (test mode).`
        : fmt.reason,
      live_checked: false,
    };
  }


  try {

    if (normalizedProvider === "openai") {
      const response = await fetchWithTimeout(`${OPENAI_BASE_URL}/models`, {
        method: "GET",
        headers: { Authorization: `Bearer ${candidate}` },
      });
      if (response.ok) {
        return { valid: true, reason: "OpenAI accepted the key (models list call succeeded).", live_checked: true };
      }
      return {
        valid: false,
        reason: `OpenAI rejected the key (HTTP ${response.status}).`,
        live_checked: true,
      };
    }

    if (normalizedProvider === "anthropic") {
      const response = await fetchWithTimeout(`${ANTHROPIC_BASE_URL}/messages`, {
        method: "POST",
        headers: {
          "x-api-key": candidate,
          "anthropic-version": ANTHROPIC_VERSION,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: resolvedModel || "claude-opus-4-8",
          max_tokens: 1,
          messages: [{ role: "user", content: "ping" }],
        }),
      });
      if (response.ok) {
        return { valid: true, reason: "Anthropic accepted the key (minimal message call succeeded).", live_checked: true };
      }
      return {
        valid: false,
        reason: `Anthropic rejected the key or model (HTTP ${response.status}).`,
        live_checked: true,
      };
    }

    if (normalizedProvider === "gemini") {
      const geminiModel = resolvedModel || "gemini-3.7-flash";

      const response = await fetchWithTimeout(
        `${GEMINI_BASE_URL}/models/${geminiModel}:generateContent?key=${encodeURIComponent(candidate)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents: [{ parts: [{ text: "ping" }] }],
            generationConfig: { maxOutputTokens: 1 },
          }),
        },
      );
      if (response.ok) {
        return { valid: true, reason: "Gemini accepted the key (minimal generateContent call succeeded).", live_checked: true };
      }
      return {
        valid: false,
        reason: `Gemini rejected the key or model (HTTP ${response.status}).`,
        live_checked: true,
      };
    }

    // No live call defined for this provider (github PAT, operator key) —
    // format validity is the best available signal.
    const formatResult = testSecret(provider, secret);
    return { ...formatResult, live_checked: false };
  } catch (error) {
    const message = error instanceof Error ? error.message : "network error";
    return {
      valid: false,
      reason: `Unable to reach ${normalizedProvider} to verify the key: ${message}.`,
      live_checked: false,
    };
  }
}

// Well-known slot storing the operator's primary-provider selection from
// Settings. Reuses the generic vault-slot abstraction (provider + model,
// same as any other slot) rather than a new storage subsystem; the "secret"
// field is a fixed non-sensitive placeholder since this slot carries routing
// metadata, not a credential.
export const ACTIVE_LLM_ROUTE_SLOT_ID = "ACTIVE-LLM-ROUTE";

export type ActiveLlmRoute = {
  provider: "openai" | "anthropic" | "gemini";
  model: string;
};

/** The operator's selected primary LLM provider/model, or null when unset
 * (callers should fall back to their existing .env-driven default). */
export async function getActiveLlmRoute(): Promise<ActiveLlmRoute | null> {
  const slots = await listVaultSlots();
  const routeSlot = slots.find((slot) => slot.slot_id === ACTIVE_LLM_ROUTE_SLOT_ID);
  if (!routeSlot || routeSlot.status === "missing") {
    return null;
  }
  if (
    routeSlot.provider !== "openai" &&
    routeSlot.provider !== "anthropic" &&
    routeSlot.provider !== "gemini"
  ) {
    return null;
  }
  if (!routeSlot.model) {
    return null;
  }
  return { provider: routeSlot.provider, model: routeSlot.model };
}
