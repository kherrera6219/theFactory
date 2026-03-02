import "server-only";

type VaultProvider = "openai" | "anthropic" | "gemini" | "github" | "operator";

type VaultEntry = {
  slotId: string;
  provider: VaultProvider;
  secret: string;
  updatedAt: string;
};

export type VaultSlotRecord = {
  slot_id: string;
  provider: VaultProvider;
  status: "set" | "missing";
  last_rotated_at: string | null;
  masked_preview: string | null;
};

const vaultMemory = new Map<string, VaultEntry>();

function normalizeProvider(value: string): VaultProvider {
  const candidate = value.toLowerCase();
  if (candidate === "openai") return "openai";
  if (candidate === "anthropic") return "anthropic";
  if (candidate === "gemini") return "gemini";
  if (candidate === "github") return "github";
  return "operator";
}

function maskSecret(secret: string): string {
  const trimmed = secret.trim();
  if (trimmed.length <= 4) {
    return "****";
  }
  return `${trimmed.slice(0, 4)}${"*".repeat(Math.max(4, trimmed.length - 4))}`;
}

export function listVaultSlots(): VaultSlotRecord[] {
  return Array.from(vaultMemory.values())
    .sort((left, right) => left.slotId.localeCompare(right.slotId))
    .map((item) => ({
      slot_id: item.slotId,
      provider: item.provider,
      status: "set",
      last_rotated_at: item.updatedAt,
      masked_preview: maskSecret(item.secret),
    }));
}

export function upsertVaultSlot(slotId: string, provider: string, secret: string): VaultSlotRecord {
  const normalizedSlot = slotId.trim().toUpperCase();
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
  };
}

export function deleteVaultSlot(slotId: string): boolean {
  return vaultMemory.delete(slotId.trim().toUpperCase());
}

export function getVaultSecret(slotId: string): string | null {
  const entry = vaultMemory.get(slotId.trim().toUpperCase());
  return entry ? entry.secret : null;
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
