"use client";

import { useEffect, useMemo, useState } from "react";
import {
  isElectron,
  electronGetAppVersion,
  electronGenerateDiagnostics,
} from "../../lib/electron-bridge";

import { OperatorUnlockForm } from "../../components/operator-unlock-form";
import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, StatusBadge, SystemMessage } from "../../components/status";
import { fetchJson, getOperationsAgentIntegrations, createDiagnosticBundle, triggerBackup } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { clampNumber, isAllowedLocalApiBase, safeJsonParse } from "../../lib/security";
import type { OperationsAgentIntegrationsSnapshot } from "../../lib/types";

type ModelOption = {
  label: string;
  provider: "openai" | "anthropic" | "gemini";
  model: "gpt-5.5" | "claude-opus-4-8" | "gemini-3.7-flash";
  endpoint: string;
  effort: "high";
};

const MODEL_OPTIONS: ModelOption[] = [
  {
    label: "Gemini 3.7 Flash",
    provider: "gemini",
    model: "gemini-3.7-flash",
    endpoint: "POST /v1beta/models/gemini-3.7-flash:generateContent",
    effort: "high",
  },
  {
    label: "ChatGPT 5.5",
    provider: "openai",
    model: "gpt-5.5",
    endpoint: "POST /v1/responses",
    effort: "high",
  },
  {
    label: "Claude Opus 4.8",
    provider: "anthropic",
    model: "claude-opus-4-8",
    endpoint: "POST /v1/messages",
    effort: "high",
  },
];


const DEFAULT_MODEL_OPTION = MODEL_OPTIONS[0];

// NOTE: a stored model that is not in MODEL_OPTIONS renders as the default
// rather than as itself, so this page can show "Gemini 3.7 Flash" while the
// vault holds something else entirely — which is exactly how a stale 3.5 pin
// went unnoticed while it routed every live mission. The vault now migrates
// superseded revisions on read (see normalizeModel), so this fallback should
// only ever see genuinely unknown values; keep that migration in step with
// MODEL_OPTIONS whenever an option is retired.
function modelOptionFor(model: string | null | undefined): ModelOption {
  return MODEL_OPTIONS.find((option) => option.model === model) ?? DEFAULT_MODEL_OPTION;
}

// Static agent registry — fallback when orchestrator is offline.
const STATIC_AGENT_SLOTS: Array<{ agentId: string; name: string; provider: string; model: string }> = [
  ["AGENT-01-PM", "PM Agent"],
  ["AGENT-02-CEO", "CEO Agent"],
  ["AGENT-03-BROKER", "API Broker"],
  ["AGENT-04-ACCOUNTANT", "Accountant"],
  ["AGENT-05-SECURITY", "Security Agent"],
  ["AGENT-06-IS", "IS Agent"],
  ["AGENT-07-VC", "Version Control Agent"],
  ["AGENT-08-COMPLIANCE", "Compliance Agent"],
  ["AGENT-09-HW", "Hardware-Mapping Injector"],
  ["AGENT-10-TESTER", "System Integration Tester"],
  ["AGENT-11-DEPLOY", "Deployment Agent"],
  ["AGENT-12-PODA-MGR", "Pod A Sub-Manager"],
  ["AGENT-13-PODA-AUDIT", "Pod A QC/Audit"],
  ["AGENT-14-PYTHON", "Python Specialist"],
  ["AGENT-15-JAVASCRIPT", "JavaScript Specialist"],
  ["AGENT-16-RUBY", "Ruby Specialist"],
  ["AGENT-17-PHP", "PHP Specialist"],
  ["AGENT-18-PODB-MGR", "Pod B Sub-Manager"],
  ["AGENT-19-PODB-AUDIT", "Pod B QC/Audit"],
  ["AGENT-20-C", "C Specialist"],
  ["AGENT-21-CPP", "C++ Specialist"],
  ["AGENT-22-RUST", "Rust Specialist"],
  ["AGENT-23-ZIG", "Zig Specialist"],
  ["AGENT-24-PODC-MGR", "Pod C Sub-Manager"],
  ["AGENT-25-PODC-AUDIT", "Pod C QC/Audit"],
  ["AGENT-26-JAVA", "Java Specialist"],
  ["AGENT-27-CSHARP", "C# Specialist"],
  ["AGENT-28-SCALA", "Scala Specialist"],
  ["AGENT-29-KOTLIN", "Kotlin Specialist"],
  ["AGENT-30-PODD-MGR", "Pod D Sub-Manager"],
  ["AGENT-31-PODD-AUDIT", "Pod D QC/Audit"],
  ["AGENT-32-MATLAB", "MATLAB Specialist"],
  ["AGENT-33-R", "R Specialist"],
  ["AGENT-34-JULIA", "Julia Specialist"],
  ["AGENT-35-MATHEMATICA", "Mathematica Specialist"],
  ["AGENT-36-GO", "Go Specialist"],
  ["AGENT-37-HASKELL", "Haskell Specialist"],
  ["AGENT-38-OCAML", "OCaml Specialist"],
  ["AGENT-39-DEPABS", "Dependency Absorption Agent"],
  ["AGENT-40-TESTDATA", "Database and Test Data Agent"],
  ["AGENT-41-RQCA", "Runtime QC Agent"],
].map(([agentId, name]) => ({
  agentId,
  name,
  provider: DEFAULT_MODEL_OPTION.provider,
  model: DEFAULT_MODEL_OPTION.model,
}));

type LocalPreferences = {
  apiBaseUrl: string;
  maxParallelAgents: number;
  cpuLimitPct: number;
  memoryLimitPct: number;
};

type VaultSlotRecord = {
  slot_id: string;
  provider: string;
  model?: string;
  status: "set" | "expiring" | "expired" | "missing";
  last_rotated_at: string | null;
  masked_preview: string | null;
  expires_at: string | null;
  ttl_seconds: number | null;
  rotation_due: boolean;
};

type VaultListResponse = {
  slots?: VaultSlotRecord[];
};

type VaultMutationResponse = {
  detail?: string;
};

type VaultTestResponse = {
  valid?: boolean;
  reason?: string;
  detail?: string;
  live_checked?: boolean;
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

// FIX #2 / #6: Consistent status description + tone mapping
function describeVaultStatus(status: SlotRow["status"]): string {
  if (status === "expiring") return "Expiring";
  if (status === "expired") return "Expired";
  if (status === "set") return "Set";
  return "Missing";
}

function vaultStatusTone(status: SlotRow["status"]): "healthy" | "warning" | "critical" | "neutral" {
  if (status === "set") return "healthy";
  if (status === "expiring") return "warning";
  if (status === "expired") return "critical";
  // FIX #6: "missing" now maps to "critical" with badge styling so it's immediately visible
  return "critical";
}

export default function SettingsPage() {
  const [maintenanceLoading, setMaintenanceLoading] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState<string | null>(null);
  const [maintenanceError, setMaintenanceError] = useState<string | null>(null);

  async function handleCreateDiagnostics() {
    setMaintenanceLoading(true);
    setMaintenanceMessage(null);
    setMaintenanceError(null);
    try {
      const res = await createDiagnosticBundle();
      setMaintenanceMessage(`Diagnostic bundle generated at: ${res.bundle_path}`);
    } catch (err: unknown) {
      setMaintenanceError(err instanceof Error ? err.message : "Failed to generate diagnostics.");
    } finally {
      setMaintenanceLoading(false);
    }
  }

  // A9 — Offline (desktop-local) diagnostics: works without the backend/internet.
  async function handleOfflineDiagnostics() {
    setMaintenanceLoading(true);
    setMaintenanceMessage(null);
    setMaintenanceError(null);
    try {
      const folder = await electronGenerateDiagnostics();
      if (folder) {
        setMaintenanceMessage(`Offline diagnostics saved locally at: ${folder}`);
      } else {
        setMaintenanceError("Offline diagnostics are only available in the desktop app.");
      }
    } catch (err: unknown) {
      setMaintenanceError(err instanceof Error ? err.message : "Failed to generate offline diagnostics.");
    } finally {
      setMaintenanceLoading(false);
    }
  }

  async function handleTriggerBackup() {
    setMaintenanceLoading(true);
    setMaintenanceMessage(null);
    setMaintenanceError(null);
    try {
      const res = await triggerBackup();
      setMaintenanceMessage(`Backup successfully created at: ${res.backup_path}`);
    } catch (err: unknown) {
      setMaintenanceError(err instanceof Error ? err.message : "Failed to trigger backup.");
    } finally {
      setMaintenanceLoading(false);
    }
  }

  const [preferences, setPreferences] = useState<LocalPreferences>(DEFAULT_PREFERENCES);
  const [snapshot, setSnapshot] = useState<OperationsAgentIntegrationsSnapshot | null>(null);
  const [vaultSlots, setVaultSlots] = useState<VaultSlotRecord[]>([]);
  const [selectedSlotId, setSelectedSlotId] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<ModelOption["model"]>(DEFAULT_MODEL_OPTION.model);
  const [slotSecretInput, setSlotSecretInput] = useState("");
  const [slotLoading, setSlotLoading] = useState(false);
  const [slotMessage, setSlotMessage] = useState<string | null>(null);
  const [slotError, setSlotError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savePending, setSavePending] = useState(false);
  const [slotSearch, setSlotSearch] = useState("");
  const [orchestratorOffline, setOrchestratorOffline] = useState(false);
  // FIX #4: Slide-in edit panel visibility — opens when a row is clicked
  const [editPanelOpen, setEditPanelOpen] = useState(false);
  const [appVersion, setAppVersion] = useState<string | null>(null);
  const [routeSaving, setRouteSaving] = useState(false);
  const [routeMessage, setRouteMessage] = useState<string | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);

  useEffect(() => {
    const raw = window.localStorage.getItem("mission-control:preferences");
    if (raw) {
      const parsed = safeJsonParse<LocalPreferences>(raw, DEFAULT_PREFERENCES);
      setPreferences({ ...DEFAULT_PREFERENCES, ...parsed });
    }
    if (isElectron()) {
      void electronGetAppVersion().then((v) => v && setAppVersion(v));
    }
  }, []);

  async function loadVaultAndAgents() {
    setSlotError(null);
    setOrchestratorOffline(false);
    const [integrationsResult, vaultResult] = await Promise.allSettled([
      getOperationsAgentIntegrations(),
      fetchJson<VaultListResponse>("/api/vault", { method: "GET" }),
    ]);

    if (integrationsResult.status === "fulfilled") {
      setSnapshot(integrationsResult.value);
    } else {
      // Only mark offline for actual network/connection failures (503, fetch error).
      // Auth errors (401/403) mean the backend IS reachable — don't hide the page.
      const reason = integrationsResult.reason;
      const is503 = reason && typeof reason === "object" && "statusCode" in reason && reason.statusCode === 503;
      const isFetchError = reason instanceof Error && (reason.message === "Failed to fetch" || reason.message.includes("NetworkError") || reason.message.includes("ECONNREFUSED"));
      if (is503 || isFetchError) {
        setOrchestratorOffline(true);
      }
    }

    if (vaultResult.status === "fulfilled") {
      const vaultPayload = vaultResult.value;
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
        // Provider/model come from the LIVE snapshot when one is available, not
        // from the vault slot. A slot's stored provider/model is metadata about
        // the key recorded when the slot was written, and nothing refreshes it
        // when routing defaults change — so preferring it showed a stale model
        // indefinitely. It reported the fleet on an older Flash pin long after
        // routing had moved on, with only the one agent lacking a slot
        // showing the truth. The slot still supplies key status, rotation, and
        // masked preview below, which is what it is actually authoritative for.
        provider: snapshot ? agent.provider : (existing?.provider ?? agent.provider),
        model: snapshot ? agent.model : (existing?.model ?? agent.model),
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
        slotId: "KNOWLEDGE-EMBEDDING-API-KEY",
        provider: slotMap.get("KNOWLEDGE-EMBEDDING-API-KEY")?.provider ?? "gemini",
        model: slotMap.get("KNOWLEDGE-EMBEDDING-API-KEY")?.model ?? "gemini-embedding-001",
        title: "Knowledge Embedding Key",
        status: slotMap.get("KNOWLEDGE-EMBEDDING-API-KEY")?.status ?? "missing",
        lastRotatedAt: slotMap.get("KNOWLEDGE-EMBEDDING-API-KEY")?.last_rotated_at ?? null,
        maskedPreview: slotMap.get("KNOWLEDGE-EMBEDDING-API-KEY")?.masked_preview ?? null,
        expiresAt: slotMap.get("KNOWLEDGE-EMBEDDING-API-KEY")?.expires_at ?? null,
        rotationDue: slotMap.get("KNOWLEDGE-EMBEDDING-API-KEY")?.rotation_due ?? false,
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
  const selectedModelOption = modelOptionFor(selectedModel);
  const selectedSlotCanChooseModel = Boolean(selectedSlot?.slotId.startsWith("AGENT-"));

  const hasAnyKeyData = useMemo(
    () => rows.some((row) => row.maskedPreview !== null || row.lastRotatedAt !== null || row.expiresAt !== null),
    [rows],
  );

  // FIX #5: Full-width search, placed directly above table heading
  const filteredRows = useMemo(() => {
    const q = slotSearch.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (row) =>
        row.slotId.toLowerCase().includes(q) ||
        row.provider.toLowerCase().includes(q) ||
        row.model.toLowerCase().includes(q),
    );
  }, [rows, slotSearch]);

  // FIX #9: API URL gets more space; numeric fields narrower
  function updatePreference<K extends keyof LocalPreferences>(key: K, value: LocalPreferences[K]) {
    setPreferences((current) => ({ ...current, [key]: value }));
  }

  // FIX #10: Save confirmation clears after 3 seconds
  function savePreferences() {
    setSaveError(null);
    setSaveMessage(null);
    if (!isAllowedLocalApiBase(preferences.apiBaseUrl)) {
      setSaveError("API base URL must target localhost or 127.0.0.1 for local secure mode.");
      return;
    }

    const normalized: LocalPreferences = {
      apiBaseUrl: preferences.apiBaseUrl.trim(),
      maxParallelAgents: clampNumber(preferences.maxParallelAgents, 1, 35),
      cpuLimitPct: clampNumber(preferences.cpuLimitPct, 10, 100),
      memoryLimitPct: clampNumber(preferences.memoryLimitPct, 10, 100),
    };

    setSavePending(true);
    try {
      setPreferences(normalized);
      window.localStorage.setItem("mission-control:preferences", JSON.stringify(normalized));
      setSaveMessage("Preferences saved.");
      // Auto-clear success message
      setTimeout(() => setSaveMessage(null), 3000);
    } catch {
      setSaveError("Failed to save preferences — localStorage may be unavailable.");
    } finally {
      setSavePending(false);
    }
  }

  async function saveVaultSlot() {
    if (!selectedSlot) { setSlotError("Select a slot before saving."); return; }
    const secret = slotSecretInput.trim();
    if (secret.length < 8) { setSlotError("Secret must contain at least 8 characters."); return; }
    setSlotLoading(true); setSlotError(null); setSlotMessage(null);
    try {
      await fetchJson<VaultMutationResponse>("/api/vault", {
        method: "POST",
        body: JSON.stringify({
          slot_id: selectedSlot.slotId,
          provider: selectedSlotCanChooseModel ? selectedModelOption.provider : selectedSlot.provider,
          model: selectedSlotCanChooseModel ? selectedModelOption.model : selectedSlot.model,
          secret,
        }),
      });
      setSlotSecretInput("");
      setSlotMessage(`Saved ${selectedSlot.slotId}.`);
      // FIX #10: auto-close edit panel on success
      setTimeout(() => { setSlotMessage(null); setEditPanelOpen(false); }, 2000);
      await loadVaultAndAgents();
    } catch (requestError) {
      setSlotError(requestError instanceof Error ? requestError.message : "Unable to save slot.");
    } finally {
      setSlotLoading(false);
    }
  }

  async function testVaultSlot() {
    if (!selectedSlot) { setSlotError("Select a slot before testing."); return; }
    setSlotLoading(true); setSlotError(null); setSlotMessage(null);
    try {
      const payload = await fetchJson<VaultTestResponse>("/api/vault/test", {
        method: "POST",
        body: JSON.stringify({
          slot_id: selectedSlot.slotId,
          provider: selectedSlotCanChooseModel ? selectedModelOption.provider : selectedSlot.provider,
          model: selectedSlotCanChooseModel ? selectedModelOption.model : selectedSlot.model,
          secret: slotSecretInput.trim().length > 0 ? slotSecretInput.trim() : undefined,
        }),
      });
      const suffix = payload.live_checked ? " (live provider check)" : " (format check only)";
      setSlotMessage(
        (payload.valid ? `Valid: ${payload.reason}` : `Invalid: ${payload.reason}`) + suffix,
      );
    } catch (requestError) {
      setSlotError(requestError instanceof Error ? requestError.message : "Unable to test slot.");
    } finally {
      setSlotLoading(false);
    }
  }

  async function clearVaultSlot() {
    if (!selectedSlot) return;
    setSlotLoading(true); setSlotError(null); setSlotMessage(null);
    try {
      await fetchJson<VaultMutationResponse>("/api/vault", {
        method: "DELETE",
        body: JSON.stringify({ slot_id: selectedSlot.slotId }),
      });
      setSlotSecretInput("");
      setSlotMessage(`Cleared ${selectedSlot.slotId}.`);
      setTimeout(() => { setSlotMessage(null); setEditPanelOpen(false); }, 2000);
      await loadVaultAndAgents();
    } catch (requestError) {
      setSlotError(requestError instanceof Error ? requestError.message : "Unable to clear slot.");
    } finally {
      setSlotLoading(false);
    }
  }

  const activeLlmRouteSlot = useMemo(
    () => vaultSlots.find((slot) => slot.slot_id === "ACTIVE-LLM-ROUTE") ?? null,
    [vaultSlots],
  );

  async function saveActiveLlmRoute(option: ModelOption) {
    setRouteSaving(true);
    setRouteError(null);
    setRouteMessage(null);
    try {
      await fetchJson<VaultMutationResponse>("/api/vault", {
        method: "POST",
        body: JSON.stringify({
          slot_id: "ACTIVE-LLM-ROUTE",
          provider: option.provider,
          model: option.model,
          // Not a credential — this slot carries routing metadata only, per
          // the vault-slot abstraction's existing generic (provider, model)
          // shape. A fixed placeholder satisfies the vault schema's required
          // secret field.
          secret: "active-route",
        }),
      });
      setRouteMessage(`Primary provider set to ${option.label}.`);
      setTimeout(() => setRouteMessage(null), 3000);
      await loadVaultAndAgents();
    } catch (requestError) {
      setRouteError(
        requestError instanceof Error ? requestError.message : "Unable to set primary provider.",
      );
    } finally {
      setRouteSaving(false);
    }
  }

  // FIX #4: Open edit panel and scroll to it
  function openEditPanel(slotId: string) {
    const row = rows.find((candidate) => candidate.slotId === slotId);
    setSelectedSlotId(slotId);
    setSelectedModel(modelOptionFor(row?.model).model);
    setSlotMessage(null);
    setSlotError(null);
    setSlotSecretInput("");
    setEditPanelOpen(true);
    // Scroll edit panel into view on next tick
    setTimeout(() => {
      document.getElementById("vault-edit-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }, 50);
  }

  // FIX #3: Section numbering helper for visual hierarchy
  const SECTION = (n: number, title: string) => `${n}. ${title}`;
  const vaultColumnWidths = hasAnyKeyData
    ? ["30%", "10%", "16%", "10%", "14%", "10%", "10%", "10%"]
    : ["30%", "10%", "16%", "10%", "10%"];

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Settings"
        title="Local Runtime and Integrations"
        description="Configure API endpoints, execution limits, and local integration credentials for enterprise operations."
      />

      {/* FIX #3: Clear section hierarchy — numbered panels */}
      {/* FIX #7: Offline status in header area with strong visual treatment */}
      {orchestratorOffline && (
        <SystemMessage tone="warning" title="Runtime offline">
          Orchestrator unreachable at port 8100. Vault keys can still be configured using the static agent roster below. The live roster will load automatically when services restart.
        </SystemMessage>
      )}

      <OperatorUnlockForm />

      {/* SECTION 1 — Runtime */}
      <Panel title={SECTION(1, "Runtime Preferences")}>
        {/* FIX #9: API URL field is wider; numeric fields share the remaining space */}
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: "16px", alignItems: "end" }}>
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
                updatePreference("maxParallelAgents", parseNumberInput(event.target.value, preferences.maxParallelAgents))
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
                updatePreference("cpuLimitPct", parseNumberInput(event.target.value, preferences.cpuLimitPct))
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
                updatePreference("memoryLimitPct", parseNumberInput(event.target.value, preferences.memoryLimitPct))
              }
            />
          </label>
        </div>
        {/* FIX #10: Save button and inline feedback in same panel as the fields */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "16px" }}>
          <button
            type="button"
            className="primary-button"
            disabled={savePending}
            onClick={savePreferences}
          >
            {savePending ? "Saving…" : "Save preferences"}
          </button>
          {saveMessage && (
            <span style={{ fontSize: "13px", color: "var(--color-success)" }}>
              {saveMessage}
            </span>
          )}
          {saveError && (
            <span style={{ fontSize: "13px", color: "var(--color-danger)" }}>
              {saveError}
            </span>
          )}
        </div>
      </Panel>

      {/* SECTION 2 — Vault */}
      <Panel
        title={SECTION(2, "API Key Vault Slots")}
        actions={
          <button type="button" className="secondary-button" onClick={() => void loadVaultAndAgents()}>
            Refresh
          </button>
        }
      >
        {slotError && !orchestratorOffline && (
          <SystemMessage tone="critical" title="Vault metadata could not be loaded">
            {slotError}
          </SystemMessage>
        )}
        <p className="help-text">
          Provider and GitHub keys are stored server-side in the configured vault backend and never
          returned in plaintext. Click <strong>Configure</strong> on any row to set or rotate a key.
        </p>

        {/* FIX #5: Full-width search spanning the table width */}
        <input
          type="search"
          className="table-search"
          placeholder="Filter by slot ID, provider, or model…"
          aria-label="Search vault slots"
          value={slotSearch}
          onChange={(e) => setSlotSearch(e.target.value)}
          style={{ width: "100%", marginBottom: "10px" }}
        />

        {/* FIX #1: table-wrap enables horizontal scroll; column widths prevent mid-word wrapping */}
        <div
          className="table-wrap"
          tabIndex={0}
          aria-label="Scrollable API key vault slots table"
          style={{ overflowX: "auto", width: "100%" }}
        >
          <table className="data-table" style={{ tableLayout: "fixed", width: "100%", minWidth: "700px" }}>
            <caption className="sr-only">Vault slots for all agents and operator integrations.</caption>
            <colgroup>
              {vaultColumnWidths.map((width, index) => (
                <col key={`${width}-${index}`} style={{ width }} />
              ))}
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Slot ID</th>
                <th scope="col">Provider</th>
                <th scope="col">Model</th>
                <th scope="col">Status</th>
                {hasAnyKeyData && <th scope="col">Masked</th>}
                {hasAnyKeyData && <th scope="col">Last rotated</th>}
                {hasAnyKeyData && <th scope="col">Expires</th>}
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr
                  key={row.slotId}
                  style={row.slotId === selectedSlotId ? { background: "var(--color-background-secondary)" } : undefined}
                >
                  {/* FIX #1: overflow-hidden + text-overflow on ID cell */}
                  <td className="mono-id" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {row.slotId}
                  </td>
                  <td>{row.provider}</td>
                  <td style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.model}</td>
                  <td>
                    {/* FIX #6: "missing" now shows as critical badge — visually distinct */}
                    <StatusBadge tone={vaultStatusTone(row.status)}>
                      {describeVaultStatus(row.status)}
                    </StatusBadge>
                  </td>
                  {/* FIX #1: Masked value truncated, not an asterisk overflow */}
                  {hasAnyKeyData && (
                    <td style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontFamily: "monospace", fontSize: "12px" }}>
                      {row.maskedPreview ?? "—"}
                    </td>
                  )}
                  {hasAnyKeyData && <td style={{ fontSize: "12px" }}>{row.lastRotatedAt ? formatDateTime(row.lastRotatedAt) : "—"}</td>}
                  {hasAnyKeyData && <td style={{ fontSize: "12px" }}>{row.expiresAt ? formatDateTime(row.expiresAt) : "—"}</td>}
                  <td>
                    {/* FIX #2: All Configure buttons styled consistently as secondary-button */}
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => openEditPanel(row.slotId)}
                    >
                      Configure
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* FIX #4: Edit panel is inline directly below the table — no scroll to bottom of page.
          It is hidden until the user clicks Configure on a row. */}
      {editPanelOpen && (
        <Panel
          id="vault-edit-panel"
          title={selectedSlot ? `Configure: ${selectedSlot.slotId}` : "Configure vault slot"}
          actions={
            <button
              type="button"
              className="secondary-button"
              onClick={() => { setEditPanelOpen(false); setSlotMessage(null); setSlotError(null); setSlotSecretInput(""); }}
            >
              Close
            </button>
          }
        >
          {!selectedSlot && (
            <EmptyState title="No vault slot selected" compact>
              Click Configure on a row in the table above.
            </EmptyState>
          )}
          {selectedSlot && (
            <>
              <ul className="summary-list">
                <li><strong>Slot</strong><span>{selectedSlot.slotId}</span></li>
                <li>
                  <strong>Provider</strong>
                  <span>{selectedSlotCanChooseModel ? selectedModelOption.provider : selectedSlot.provider}</span>
                </li>
                <li>
                  <strong>Model</strong>
                  <span>{selectedSlotCanChooseModel ? selectedModelOption.model : selectedSlot.model}</span>
                </li>
                <li>
                  <strong>Status</strong>
                  <span>
                    <StatusBadge tone={vaultStatusTone(selectedSlot.status)}>
                      {describeVaultStatus(selectedSlot.status)}
                    </StatusBadge>
                  </span>
                </li>
                <li><strong>Expires</strong><span>{selectedSlot.expiresAt ? formatDateTime(selectedSlot.expiresAt) : "n/a"}</span></li>
                <li><strong>Rotation due</strong><span>{selectedSlot.rotationDue ? "Yes" : "No"}</span></li>
              </ul>
              {selectedSlotCanChooseModel && (
                <label htmlFor="vault-model" style={{ display: "block", marginTop: "12px" }}>
                  Model
                  <select
                    id="vault-model"
                    value={selectedModel}
                    onChange={(event) =>
                      setSelectedModel(modelOptionFor(event.target.value).model)
                    }
                    style={{ width: "100%", marginTop: "6px" }}
                  >
                    {MODEL_OPTIONS.map((option) => (
                      <option key={option.model} value={option.model}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {selectedSlotCanChooseModel && (
                <p className="help-text" style={{ marginTop: "8px" }}>
                  {selectedModelOption.provider} / {selectedModelOption.endpoint} / effort {selectedModelOption.effort}
                </p>
              )}
              <label htmlFor="vault-secret" style={{ display: "block", marginTop: "12px" }}>
                New secret
              </label>
              <input
                id="vault-secret"
                type="password"
                value={slotSecretInput}
                onChange={(event) => setSlotSecretInput(event.target.value)}
                autoComplete="off"
                placeholder={`Paste new secret for ${selectedSlot.slotId}`}
                style={{ width: "100%", marginTop: "6px" }}
              />
              <div className="inline-actions" style={{ marginTop: "12px" }}>
                <button type="button" onClick={() => void saveVaultSlot()} disabled={slotLoading}>
                  {slotLoading ? "Saving…" : "Save"}
                </button>
                <button type="button" className="secondary-button" onClick={() => void testVaultSlot()} disabled={slotLoading}>
                  Test
                </button>
                <button type="button" className="secondary-button" onClick={() => void clearVaultSlot()} disabled={slotLoading}>
                  Clear
                </button>
              </div>
            </>
          )}
          {/* FIX #10: Inline feedback immediately below the action buttons */}
          {slotMessage && (
            <SystemMessage tone="success" title="Vault updated">
              {slotMessage}
            </SystemMessage>
          )}
          {slotError && editPanelOpen && (
            <SystemMessage tone="critical" title="Vault action failed">
              {slotError}
            </SystemMessage>
          )}
        </Panel>
      )}

      {/* SECTION 3 — Primary LLM Provider (vault-path override of LLM_PROVIDER/*_MODEL env defaults) */}
      <Panel title={SECTION(3, "Primary LLM Provider")}>
        <p className="help-text">
          Choose which provider/model every agent routes to by default. This selection is stored
          in the vault and takes priority over the runtime&apos;s .env defaults
          (<code>LLM_PROVIDER</code>, <code>OPENAI_MODEL</code>, <code>GEMINI_MODEL</code>,{" "}
          <code>ANTHROPIC_MODEL</code>) for every new mission. Leave unset to keep using the
          runtime&apos;s .env configuration.
        </p>
        <div className="inline-actions" role="group" aria-label="Primary LLM provider selection">
          {MODEL_OPTIONS.map((option) => {
            const isActive =
              activeLlmRouteSlot?.provider === option.provider && activeLlmRouteSlot?.model === option.model;
            return (
              <button
                key={option.model}
                type="button"
                className={isActive ? "primary-button" : "secondary-button"}
                disabled={routeSaving}
                aria-pressed={isActive}
                onClick={() => void saveActiveLlmRoute(option)}
              >
                {option.label}
                {isActive ? " (active)" : ""}
              </button>
            );
          })}
        </div>
        <p className="help-text">
          {activeLlmRouteSlot
            ? `Current selection: ${activeLlmRouteSlot.provider} / ${activeLlmRouteSlot.model}.`
            : "No vault override set — using the runtime's .env default."}
        </p>
        {routeMessage && (
          <SystemMessage tone="success" title="Primary provider updated">
            {routeMessage}
          </SystemMessage>
        )}
        {routeError && (
          <SystemMessage tone="critical" title="Unable to update primary provider">
            {routeError}
          </SystemMessage>
        )}
      </Panel>

      {/* SECTION 4 — Knowledge Embeddings */}
      <Panel title={SECTION(4, "Knowledge Embeddings")}>
        <p className="help-text">
          The orchestrator embeds knowledge-lake documents so agents can perform semantic similarity
          search over library documentation. Store the embedding key in the vault slot below for
          operator setup tracking, and mirror it to the orchestrator environment when containers are
          started.
        </p>
        <ul className="summary-list">
          <li>
            <strong>Vault slot</strong>
            <span className="mono-id">KNOWLEDGE-EMBEDDING-API-KEY</span>
          </li>
          <li>
            <strong>Provider env var</strong>
            <span className="mono-id">KNOWLEDGE_EMBEDDING_PROVIDER</span>
          </li>
          <li>
            <strong>Compose default</strong>
            <span>
              <code>deterministic</code> — SHA-256 hash vectors, not semantically meaningful
            </span>
          </li>
          <li>
            <strong>Dedicated key env var</strong>
            <span className="mono-id">KNOWLEDGE_EMBEDDING_API_KEY</span>
          </li>
          <li>
            <strong>Key fallback</strong>
            <span>
              <code>GEMINI_API_KEY</code> or <code>OPENAI_API_KEY</code> (matched to provider)
            </span>
          </li>
          <li>
            <strong>Vector dimensions</strong>
            <span>
              <code>QDRANT_VECTOR_SIZE</code> — default 256 (minimum recommended for semantic separation)
            </span>
          </li>
        </ul>
        <div className="inline-actions" style={{ marginTop: "12px" }}>
          <button
            type="button"
            className="secondary-button"
            onClick={() => openEditPanel("KNOWLEDGE-EMBEDDING-API-KEY")}
          >
            Configure embedding key
          </button>
        </div>
        {(() => {
          const embeddingSlot = vaultSlots.find(
            (s) => s.slot_id.toUpperCase() === "KNOWLEDGE-EMBEDDING-API-KEY",
          );
          const embeddingSet = embeddingSlot && embeddingSlot.status !== "missing";
          if (embeddingSet) {
            return (
              <SystemMessage tone="success" title="Embedding key configured">
                The <code>KNOWLEDGE-EMBEDDING-API-KEY</code> vault slot is{" "}
                <strong>{embeddingSlot.status}</strong>. Semantic search is active when the
                orchestrator container is running with this key in its environment.
              </SystemMessage>
            );
          }
          return (
            <SystemMessage tone="warning" title="Real embeddings are off by default">
              To enable semantic search: set <code>KNOWLEDGE_EMBEDDING_PROVIDER=gemini</code> (or{" "}
              <code>openai</code>) and supply an API key via{" "}
              <code>KNOWLEDGE_EMBEDDING_API_KEY</code> (or the matching{" "}
              <code>GEMINI_API_KEY</code> / <code>OPENAI_API_KEY</code>) in your{" "}
              <code>.env</code> file, or use the <strong>Configure embedding key</strong> button
              above to store it in the vault.
            </SystemMessage>
          );
        })()}
      </Panel>

      {/* SECTION 4 — Software Version */}
      <Panel title={SECTION(5, "Software Version")}>
        <div className="filters-grid">
          <div>
            <p className="eyebrow">Current version</p>
            <p className="mono-id">
              {isElectron()
                ? (appVersion ?? "…")
                : (process.env.NEXT_PUBLIC_APP_VERSION ?? "dev")}
            </p>
          </div>
        </div>
        <p className="help-text" style={{ marginTop: "12px" }}>
          Updates are delivered via the <strong>theFactory Mission Control</strong> Windows installer.
          Download the latest installer from your release channel and run it to upgrade.
        </p>
      </Panel>

      {/* SECTION 5 — Maintenance */}
      <Panel title={SECTION(6, "System Maintenance")}>
        <p className="help-text">
          Enterprise tools for data resilience and diagnostics. Export system state for support or
          trigger a full backup of all factory database volumes.
        </p>
        <div className="inline-actions">
          <button type="button" className="secondary-button" onClick={() => void handleCreateDiagnostics()} disabled={maintenanceLoading}>
            {maintenanceLoading ? "Processing…" : "Export diagnostic bundle"}
          </button>
          <button type="button" className="secondary-button" onClick={() => void handleTriggerBackup()} disabled={maintenanceLoading}>
            {maintenanceLoading ? "Processing…" : "Run full stateful backup"}
          </button>
          {isElectron() && (
            <button type="button" className="secondary-button" onClick={() => void handleOfflineDiagnostics()} disabled={maintenanceLoading}>
              {maintenanceLoading ? "Processing…" : "Generate offline diagnostics"}
            </button>
          )}
        </div>
        {maintenanceMessage && (
          <SystemMessage tone="success" title="Maintenance complete">
            {maintenanceMessage}
          </SystemMessage>
        )}
        {maintenanceError && (
          <SystemMessage tone="critical" title="Maintenance failed">
            {maintenanceError}
          </SystemMessage>
        )}
      </Panel>

      {/* FIX #8: Status bar padding — spacer so last panel clears the bottom status bar */}
      <div style={{ height: "56px" }} aria-hidden="true" />
    </div>
  );
}
