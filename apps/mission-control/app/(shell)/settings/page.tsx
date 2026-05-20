"use client";

import { useEffect, useMemo, useState } from "react";

import { OperatorUnlockForm } from "../../components/operator-unlock-form";
import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, StatusBadge, SystemMessage } from "../../components/status";
import { getOperationsAgentIntegrations } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { clampNumber, isAllowedLocalApiBase, safeJsonParse } from "../../lib/security";
import type { OperationsAgentIntegrationsSnapshot } from "../../lib/types";

// Static agent registry — used as fallback when the orchestrator is offline so the
// vault slot table always shows all expected rows for key entry.
const STATIC_AGENT_SLOTS: Array<{ agentId: string; name: string; provider: string; model: string }> = [
  { agentId: "AGENT-01-PM", name: "PM Agent", provider: "anthropic", model: "claude-sonnet-4-6" },
  { agentId: "AGENT-02-CEO", name: "CEO Agent", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-03-BROKER", name: "API Broker", provider: "gemini", model: "gemini-3.1-flash-lite" },
  { agentId: "AGENT-04-ACCOUNTANT", name: "Accountant", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-05-SECURITY", name: "Security Agent", provider: "anthropic", model: "claude-opus-4-7" },
  { agentId: "AGENT-06-IS", name: "IS Agent", provider: "gemini", model: "gemini-3.1-pro-preview" },
  { agentId: "AGENT-07-VC", name: "Version Control Agent", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-08-COMPLIANCE", name: "Compliance Agent", provider: "anthropic", model: "claude-opus-4-7" },
  { agentId: "AGENT-09-HW", name: "Hardware-Mapping Injector", provider: "gemini", model: "gemini-3.1-pro-preview" },
  { agentId: "AGENT-10-TESTER", name: "System Integration Tester", provider: "anthropic", model: "claude-opus-4-7" },
  { agentId: "AGENT-11-DEPLOY", name: "Deployment Agent", provider: "gemini", model: "gemini-3.1-flash-lite" },
  { agentId: "AGENT-12-PODA-MGR", name: "Pod A Sub-Manager", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-13-PODA-AUDIT", name: "Pod A QC/Audit", provider: "anthropic", model: "claude-sonnet-4-6" },
  { agentId: "AGENT-14-PYTHON", name: "Python Specialist", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-15-JAVASCRIPT", name: "JavaScript Specialist", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-16-RUBY", name: "Ruby Specialist", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-17-PHP", name: "PHP Specialist", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-18-PODB-MGR", name: "Pod B Sub-Manager", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-19-PODB-AUDIT", name: "Pod B QC/Audit", provider: "anthropic", model: "claude-sonnet-4-6" },
  { agentId: "AGENT-20-C", name: "C Specialist", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-21-CPP", name: "C++ Specialist", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-22-RUST", name: "Rust Specialist", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-23-ZIG", name: "Zig Specialist", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-24-PODC-MGR", name: "Pod C Sub-Manager", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-25-PODC-AUDIT", name: "Pod C QC/Audit", provider: "anthropic", model: "claude-sonnet-4-6" },
  { agentId: "AGENT-26-JAVA", name: "Java Specialist", provider: "anthropic", model: "claude-sonnet-4-6" },
  { agentId: "AGENT-27-CSHARP", name: "C# Specialist", provider: "anthropic", model: "claude-sonnet-4-6" },
  { agentId: "AGENT-28-SCALA", name: "Scala Specialist", provider: "anthropic", model: "claude-sonnet-4-6" },
  { agentId: "AGENT-29-KOTLIN", name: "Kotlin Specialist", provider: "anthropic", model: "claude-sonnet-4-6" },
  { agentId: "AGENT-30-PODD-MGR", name: "Pod D Sub-Manager", provider: "gemini", model: "gemini-3.1-pro-preview" },
  { agentId: "AGENT-31-PODD-AUDIT", name: "Pod D QC/Audit", provider: "anthropic", model: "claude-opus-4-7" },
  { agentId: "AGENT-32-MATLAB", name: "MATLAB Specialist", provider: "gemini", model: "gemini-3.1-pro-preview" },
  { agentId: "AGENT-33-R", name: "R Specialist", provider: "gemini", model: "gemini-3.1-pro-preview" },
  { agentId: "AGENT-34-JULIA", name: "Julia Specialist", provider: "gemini", model: "gemini-3.1-pro-preview" },
  { agentId: "AGENT-35-MATHEMATICA", name: "Mathematica Specialist", provider: "gemini", model: "gemini-3.1-pro-preview" },
  { agentId: "AGENT-36-GO", name: "Go Specialist", provider: "openai", model: "gpt-5.3-codex" },
  { agentId: "AGENT-37-HASKELL", name: "Haskell Specialist", provider: "gemini", model: "gemini-3.1-pro-preview" },
  { agentId: "AGENT-38-OCAML", name: "OCaml Specialist", provider: "gemini", model: "gemini-3.1-pro-preview" },
  { agentId: "AGENT-39-DEPABS", name: "Dependency Absorption Agent", provider: "anthropic", model: "claude-opus-4-7" },
  { agentId: "AGENT-40-TESTDATA", name: "Database and Test Data Agent", provider: "gemini", model: "gemini-3.1-flash-lite" },
  { agentId: "AGENT-41-RQCA", name: "Runtime QC Agent", provider: "anthropic", model: "claude-sonnet-4-6" },
];

type LocalPreferences = {
  apiBaseUrl: string;
  maxParallelAgents: number;
  cpuLimitPct: number;
  memoryLimitPct: number;
};

type VaultSlotRecord = {
  slot_id: string;
  provider: string;
  status: "set" | "expiring" | "expired" | "missing";
  last_rotated_at: string | null;
  masked_preview: string | null;
  expires_at: string | null;
  ttl_seconds: number | null;
  rotation_due: boolean;
};

type SlotRow = {
  slotId: string;
  provider: string;
  model: string;
  title: string;
  status: "set" | "expiring" | "expired" | "missing";
  lastRotatedAt: string | null;
  maskedPreview: string | null;
  expiresAt: string | null;
  rotationDue: boolean;
};

const DEFAULT_PREFERENCES: LocalPreferences = {
  apiBaseUrl: "http://localhost:8100",
  maxParallelAgents: 8,
  cpuLimitPct: 80,
  memoryLimitPct: 80,
};

function parseNumberInput(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function describeVaultStatus(status: SlotRow["status"]): string {
  if (status === "expiring") return "Expiring";
  if (status === "expired") return "Expired";
  if (status === "set") return "Set";
  return "Missing";
}

export default function SettingsPage() {
  const [preferences, setPreferences] = useState<LocalPreferences>(DEFAULT_PREFERENCES);
  const [snapshot, setSnapshot] = useState<OperationsAgentIntegrationsSnapshot | null>(null);
  const [vaultSlots, setVaultSlots] = useState<VaultSlotRecord[]>([]);
  const [selectedSlotId, setSelectedSlotId] = useState<string>("");
  const [slotSecretInput, setSlotSecretInput] = useState("");
  const [slotLoading, setSlotLoading] = useState(false);
  const [slotMessage, setSlotMessage] = useState<string | null>(null);
  const [slotError, setSlotError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [orchestratorOffline, setOrchestratorOffline] = useState(false);

  useEffect(() => {
    const raw = window.localStorage.getItem("mission-control:preferences");
    if (raw) {
      const parsed = safeJsonParse<LocalPreferences>(raw, DEFAULT_PREFERENCES);
      setPreferences({ ...DEFAULT_PREFERENCES, ...parsed });
    }
  }, []);

  async function loadVaultAndAgents() {
    setSlotError(null);
    setOrchestratorOffline(false);
    const [integrationsResult, vaultResult] = await Promise.allSettled([
      getOperationsAgentIntegrations(),
      fetch("/api/vault", { method: "GET", cache: "no-store" }),
    ]);

    if (integrationsResult.status === "fulfilled") {
      setSnapshot(integrationsResult.value);
    } else {
      setOrchestratorOffline(true);
    }

    if (vaultResult.status === "fulfilled") {
      const vaultPayload = (await vaultResult.value.json()) as { slots?: VaultSlotRecord[] };
      setVaultSlots(Array.isArray(vaultPayload.slots) ? vaultPayload.slots : []);
    } else {
      setSlotError(vaultResult.reason instanceof Error ? vaultResult.reason.message : "Unable to load vault metadata.");
    }
  }

  useEffect(() => {
    void loadVaultAndAgents();
  }, []);

  const rows = useMemo<SlotRow[]>(() => {
    const slotMap = new Map<string, VaultSlotRecord>();
    vaultSlots.forEach((slot) => {
      slotMap.set(slot.slot_id.toUpperCase(), slot);
    });

    const agentSource = snapshot
      ? snapshot.agents.map((agent) => ({
          agentId: agent.agent_id,
          name: agent.name,
          provider: String(agent.llm_recommendation.provider ?? "operator"),
          model: String(agent.llm_recommendation.model ?? "n/a"),
        }))
      : STATIC_AGENT_SLOTS;

    const agentRows = agentSource.map((agent) => {
      const slotId = `${agent.agentId}-API-KEY`;
      const existing = slotMap.get(slotId.toUpperCase());
      return {
        slotId,
        provider: agent.provider,
        model: agent.model,
        title: `${agent.agentId} (${agent.name})`,
        status: existing?.status ?? ("missing" as const),
        lastRotatedAt: existing?.last_rotated_at ?? null,
        maskedPreview: existing?.masked_preview ?? null,
        expiresAt: existing?.expires_at ?? null,
        rotationDue: existing?.rotation_due ?? false,
      };
    });

    const extraSlots: SlotRow[] = [
      {
        slotId: "OPERATOR-API-KEY",
        provider: "operator",
        model: "mission-state-control",
        title: "Operator Runtime Key",
        status: slotMap.get("OPERATOR-API-KEY")?.status ?? "missing",
        lastRotatedAt: slotMap.get("OPERATOR-API-KEY")?.last_rotated_at ?? null,
        maskedPreview: slotMap.get("OPERATOR-API-KEY")?.masked_preview ?? null,
        expiresAt: slotMap.get("OPERATOR-API-KEY")?.expires_at ?? null,
        rotationDue: slotMap.get("OPERATOR-API-KEY")?.rotation_due ?? false,
      },
      {
        slotId: "GITHUB-TOKEN",
        provider: "github",
        model: "repo-scope",
        title: "GitHub Personal Access Token",
        status: slotMap.get("GITHUB-TOKEN")?.status ?? "missing",
        lastRotatedAt: slotMap.get("GITHUB-TOKEN")?.last_rotated_at ?? null,
        maskedPreview: slotMap.get("GITHUB-TOKEN")?.masked_preview ?? null,
        expiresAt: slotMap.get("GITHUB-TOKEN")?.expires_at ?? null,
        rotationDue: slotMap.get("GITHUB-TOKEN")?.rotation_due ?? false,
      },
    ];

    return [...agentRows, ...extraSlots].sort((left, right) => left.slotId.localeCompare(right.slotId));
  }, [snapshot, vaultSlots]);

  useEffect(() => {
    if (!selectedSlotId && rows.length > 0) {
      setSelectedSlotId(rows[0].slotId);
    }
  }, [rows, selectedSlotId]);

  const selectedSlot = useMemo(
    () => rows.find((row) => row.slotId === selectedSlotId) ?? null,
    [rows, selectedSlotId],
  );

  function updatePreference<K extends keyof LocalPreferences>(key: K, value: LocalPreferences[K]) {
    setPreferences((current) => ({ ...current, [key]: value }));
  }

  function savePreferences() {
    setSaveError(null);
    setSaveMessage(null);
    if (!isAllowedLocalApiBase(preferences.apiBaseUrl)) {
      setSaveError(
        "API base URL must target localhost or 127.0.0.1 for local secure mode.",
      );
      return;
    }

    const normalized: LocalPreferences = {
      apiBaseUrl: preferences.apiBaseUrl.trim(),
      maxParallelAgents: clampNumber(preferences.maxParallelAgents, 1, 35),
      cpuLimitPct: clampNumber(preferences.cpuLimitPct, 10, 100),
      memoryLimitPct: clampNumber(preferences.memoryLimitPct, 10, 100),
    };

    setPreferences(normalized);
    window.localStorage.setItem("mission-control:preferences", JSON.stringify(normalized));
    setSaveMessage("Local runtime preferences saved.");
  }

  async function saveVaultSlot() {
    if (!selectedSlot) {
      setSlotError("Select a slot before saving.");
      return;
    }
    const secret = slotSecretInput.trim();
    if (secret.length < 8) {
      setSlotError("Secret must contain at least 8 characters.");
      return;
    }
    setSlotLoading(true);
    setSlotError(null);
    setSlotMessage(null);
    try {
      const response = await fetch("/api/vault", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slot_id: selectedSlot.slotId,
          provider: selectedSlot.provider,
          secret,
        }),
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Unable to save vault slot.");
      }
      setSlotSecretInput("");
      setSlotMessage(`Saved ${selectedSlot.slotId}.`);
      await loadVaultAndAgents();
    } catch (requestError) {
      setSlotError(requestError instanceof Error ? requestError.message : "Unable to save slot.");
    } finally {
      setSlotLoading(false);
    }
  }

  async function testVaultSlot() {
    if (!selectedSlot) {
      setSlotError("Select a slot before testing.");
      return;
    }
    setSlotLoading(true);
    setSlotError(null);
    setSlotMessage(null);
    try {
      const response = await fetch("/api/vault/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slot_id: selectedSlot.slotId,
          provider: selectedSlot.provider,
          secret: slotSecretInput.trim().length > 0 ? slotSecretInput.trim() : undefined,
        }),
      });
      const payload = (await response.json()) as { valid?: boolean; reason?: string; detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Key test failed.");
      }
      setSlotMessage(payload.valid ? `Valid: ${payload.reason}` : `Invalid: ${payload.reason}`);
    } catch (requestError) {
      setSlotError(requestError instanceof Error ? requestError.message : "Unable to test slot.");
    } finally {
      setSlotLoading(false);
    }
  }

  async function clearVaultSlot() {
    if (!selectedSlot) {
      return;
    }
    setSlotLoading(true);
    setSlotError(null);
    setSlotMessage(null);
    try {
      const response = await fetch("/api/vault", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slot_id: selectedSlot.slotId }),
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Unable to delete slot.");
      }
      setSlotSecretInput("");
      setSlotMessage(`Cleared ${selectedSlot.slotId}.`);
      await loadVaultAndAgents();
    } catch (requestError) {
      setSlotError(requestError instanceof Error ? requestError.message : "Unable to clear slot.");
    } finally {
      setSlotLoading(false);
    }
  }

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Settings"
        title="Local Runtime and Integrations"
        description="Configure API endpoints, execution limits, and local integration credentials for enterprise operations."
      />

      <Panel title="Runtime Preferences">
        <div className="filters-grid">
          <label>
            API base URL
            <input
              type="url"
              value={preferences.apiBaseUrl}
              onChange={(event) => updatePreference("apiBaseUrl", event.target.value)}
            />
            {preferences.apiBaseUrl &&
              !preferences.apiBaseUrl.startsWith("https://") &&
              !preferences.apiBaseUrl.startsWith("http://localhost") &&
              !preferences.apiBaseUrl.startsWith("http://127.0.0.1") && (
                <p className="warning-box" style={{ marginTop: "6px" }}>
                  Non-HTTPS URLs are not recommended outside local development.
                </p>
              )}
          </label>
          <label>
            Max parallel agents
            <input
              type="number"
              min={1}
              max={35}
              value={preferences.maxParallelAgents}
              onChange={(event) =>
                updatePreference(
                  "maxParallelAgents",
                  parseNumberInput(event.target.value, preferences.maxParallelAgents),
                )
              }
            />
          </label>
          <label>
            CPU limit (%)
            <input
              type="number"
              min={10}
              max={100}
              value={preferences.cpuLimitPct}
              onChange={(event) =>
                updatePreference(
                  "cpuLimitPct",
                  parseNumberInput(event.target.value, preferences.cpuLimitPct),
                )
              }
            />
          </label>
          <label>
            Memory limit (%)
            <input
              type="number"
              min={10}
              max={100}
              value={preferences.memoryLimitPct}
              onChange={(event) =>
                updatePreference(
                  "memoryLimitPct",
                  parseNumberInput(event.target.value, preferences.memoryLimitPct),
                )
              }
            />
          </label>
        </div>
      </Panel>

      <Panel title="API Key Vault Slots">
        {orchestratorOffline && (
          <SystemMessage tone="warning" title="Static roster mode">
            Orchestrator offline (port 8100 unreachable). Vault keys can still be saved, and the live agent roster will replace this table when runtime services are available.
          </SystemMessage>
        )}
        {slotError && (
          <SystemMessage tone="critical" title="Vault metadata could not be loaded">
            {slotError}
          </SystemMessage>
        )}
        <p className="help-text">
          Provider and GitHub keys are stored server-side in the configured vault backend and never
          returned in plaintext.
        </p>
        <div className="table-wrap" tabIndex={0} aria-label="Scrollable API key vault slots table">
          <table className="data-table">
            <caption className="sr-only">Vault slots for all agents and operator integrations.</caption>
            <thead>
              <tr>
                <th scope="col">Slot ID</th>
                <th scope="col">Provider</th>
                <th scope="col">Model</th>
                <th scope="col">Status</th>
                <th scope="col">Masked</th>
                <th scope="col">Last Rotated</th>
                <th scope="col">Expires</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.slotId}>
                  <td>{row.slotId}</td>
                  <td>{row.provider}</td>
                  <td>{row.model}</td>
                  <td>
                    <StatusBadge
                      tone={
                        row.status === "set"
                          ? "healthy"
                          : row.status === "expiring"
                            ? "warning"
                            : row.status === "expired"
                              ? "critical"
                              : "neutral"
                      }
                    >
                      {describeVaultStatus(row.status)}
                    </StatusBadge>
                  </td>
                  <td>{row.maskedPreview ?? "n/a"}</td>
                  <td>{row.lastRotatedAt ? formatDateTime(row.lastRotatedAt) : "n/a"}</td>
                  <td>{row.expiresAt ? formatDateTime(row.expiresAt) : "n/a"}</td>
                  <td>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => {
                        setSelectedSlotId(row.slotId);
                        setSlotMessage(null);
                        setSlotError(null);
                      }}
                    >
                      Select
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Edit Selected Vault Slot">
        {!selectedSlot && (
          <EmptyState title="No vault slot selected" compact>
            Select a slot from the table above to save, test, or clear a provider credential.
          </EmptyState>
        )}
        {selectedSlot && (
          <>
            <ul className="summary-list">
              <li>
                <strong>Slot</strong>
                <span>{selectedSlot.slotId}</span>
              </li>
              <li>
                <strong>Provider</strong>
                <span>{selectedSlot.provider}</span>
              </li>
              <li>
                <strong>Status</strong>
                <span>{describeVaultStatus(selectedSlot.status)}</span>
              </li>
              <li>
                <strong>Expires</strong>
                <span>{selectedSlot.expiresAt ? formatDateTime(selectedSlot.expiresAt) : "n/a"}</span>
              </li>
              <li>
                <strong>Rotation Due</strong>
                <span>{selectedSlot.rotationDue ? "Yes" : "No"}</span>
              </li>
            </ul>
            <label htmlFor="vault-secret">Secret</label>
            <input
              id="vault-secret"
              type="password"
              value={slotSecretInput}
              onChange={(event) => setSlotSecretInput(event.target.value)}
              autoComplete="off"
              placeholder={`Paste new secret for ${selectedSlot.slotId}`}
            />
            <div className="inline-actions">
              <button type="button" onClick={() => void saveVaultSlot()} disabled={slotLoading}>
                {slotLoading ? "Saving..." : "Save"}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void testVaultSlot()}
                disabled={slotLoading}
              >
                Test
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void clearVaultSlot()}
                disabled={slotLoading}
              >
                Clear
              </button>
            </div>
          </>
        )}
        {slotMessage && (
          <SystemMessage tone="success" title="Vault updated">
            {slotMessage}
          </SystemMessage>
        )}
        {slotError && (
          <SystemMessage tone="critical" title="Vault action failed">
            {slotError}
          </SystemMessage>
        )}
      </Panel>

      <Panel title="Operator Admin Session">
        <p className="help-text">
          Create a short-lived operator session using the <code>MISSION_CONTROL_ADMIN_KEY</code> set
          in your environment. This is only required for protected admin operations.
        </p>
        <OperatorUnlockForm />
      </Panel>

      <Panel
        title="Save Configuration"
        actions={
          <button type="button" className="secondary-button" onClick={() => void loadVaultAndAgents()}>
            Refresh Vault Status
          </button>
        }
      >
        <button type="button" onClick={savePreferences}>
          Save Runtime Preferences
        </button>
        {saveError && (
          <SystemMessage tone="critical" title="Preferences were not saved">
            {saveError}
          </SystemMessage>
        )}
        {saveMessage && (
          <SystemMessage tone="success" title="Preferences saved">
            {saveMessage}
          </SystemMessage>
        )}
      </Panel>
    </div>
  );
}
