"use client";

import { useEffect, useMemo, useState } from "react";
import {
  isElectron,
  electronGetAppVersion,
} from "../../lib/electron-bridge";

import { OperatorUnlockForm } from "../../components/operator-unlock-form";
import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, StatusBadge, SystemMessage } from "../../components/status";
import { getOperationsAgentIntegrations, createDiagnosticBundle, triggerBackup } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { clampNumber, isAllowedLocalApiBase, safeJsonParse } from "../../lib/security";
import type { OperationsAgentIntegrationsSnapshot } from "../../lib/types";

// Static agent registry — fallback when orchestrator is offline.
const STATIC_AGENT_SLOTS: Array<{ agentId: string; name: string; provider: string; model: string }> = [
  { agentId: "AGENT-01-PM", name: "PM Agent", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-02-CEO", name: "CEO Agent", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-03-BROKER", name: "API Broker", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-04-ACCOUNTANT", name: "Accountant", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-05-SECURITY", name: "Security Agent", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-06-IS", name: "IS Agent", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-07-VC", name: "Version Control Agent", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-08-COMPLIANCE", name: "Compliance Agent", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-09-HW", name: "Hardware-Mapping Injector", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-10-TESTER", name: "System Integration Tester", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-11-DEPLOY", name: "Deployment Agent", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-12-PODA-MGR", name: "Pod A Sub-Manager", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-13-PODA-AUDIT", name: "Pod A QC/Audit", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-14-PYTHON", name: "Python Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-15-JAVASCRIPT", name: "JavaScript Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-16-RUBY", name: "Ruby Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-17-PHP", name: "PHP Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-18-PODB-MGR", name: "Pod B Sub-Manager", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-19-PODB-AUDIT", name: "Pod B QC/Audit", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-20-C", name: "C Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-21-CPP", name: "C++ Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-22-RUST", name: "Rust Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-23-ZIG", name: "Zig Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-24-PODC-MGR", name: "Pod C Sub-Manager", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-25-PODC-AUDIT", name: "Pod C QC/Audit", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-26-JAVA", name: "Java Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-27-CSHARP", name: "C# Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-28-SCALA", name: "Scala Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-29-KOTLIN", name: "Kotlin Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-30-PODD-MGR", name: "Pod D Sub-Manager", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-31-PODD-AUDIT", name: "Pod D QC/Audit", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-32-MATLAB", name: "MATLAB Specialist", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-33-R", name: "R Specialist", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-34-JULIA", name: "Julia Specialist", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-35-MATHEMATICA", name: "Mathematica Specialist", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-36-GO", name: "Go Specialist", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-37-HASKELL", name: "Haskell Specialist", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-38-OCAML", name: "OCaml Specialist", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-39-DEPABS", name: "Dependency Absorption Agent", provider: "openai", model: "gpt-5.5" },
  { agentId: "AGENT-40-TESTDATA", name: "Database and Test Data Agent", provider: "gemini", model: "gemini-3.5-flash" },
  { agentId: "AGENT-41-RQCA", name: "Runtime QC Agent", provider: "openai", model: "gpt-5.5" },
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
    } catch (err: any) {
      setMaintenanceError(err.message || "Failed to generate diagnostics.");
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
    } catch (err: any) {
      setMaintenanceError(err.message || "Failed to trigger backup.");
    } finally {
      setMaintenanceLoading(false);
    }
  }

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
  const [savePending, setSavePending] = useState(false);
  const [slotSearch, setSlotSearch] = useState("");
  const [orchestratorOffline, setOrchestratorOffline] = useState(false);
  // FIX #4: Slide-in edit panel visibility — opens when a row is clicked
  const [editPanelOpen, setEditPanelOpen] = useState(false);
  const [appVersion, setAppVersion] = useState<string | null>(null);

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
      const response = await fetch("/api/vault", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slot_id: selectedSlot.slotId, provider: selectedSlot.provider, secret }),
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(payload.detail || "Unable to save vault slot.");
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
      if (!response.ok) throw new Error(payload.detail || "Key test failed.");
      setSlotMessage(payload.valid ? `Valid: ${payload.reason}` : `Invalid: ${payload.reason}`);
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
      const response = await fetch("/api/vault", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slot_id: selectedSlot.slotId }),
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(payload.detail || "Unable to delete slot.");
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

  // FIX #4: Open edit panel and scroll to it
  function openEditPanel(slotId: string) {
    setSelectedSlotId(slotId);
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
              {/* FIX #1: Fixed column widths prevent overflow and mid-word breaks */}
              <col style={{ width: "30%" }} />   {/* Slot ID */}
              <col style={{ width: "10%" }} />   {/* Provider */}
              <col style={{ width: "16%" }} />   {/* Model */}
              <col style={{ width: "10%" }} />   {/* Status */}
              {hasAnyKeyData && <col style={{ width: "14%" }} />} {/* Masked */}
              {hasAnyKeyData && <col style={{ width: "10%" }} />} {/* Last Rotated */}
              {hasAnyKeyData && <col style={{ width: "10%" }} />} {/* Expires */}
              <col style={{ width: "10%" }} />   {/* Actions */}
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
                <li><strong>Provider</strong><span>{selectedSlot.provider}</span></li>
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

      {/* SECTION 3 — Software Version */}
      <Panel title={SECTION(3, "Software Version")}>
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

      {/* SECTION 4 — Maintenance */}
      <Panel title={SECTION(4, "System Maintenance")}>
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
