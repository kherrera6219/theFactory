"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, Suspense } from "react";

import { PageHeader } from "../../../components/page-header";
import { OperatorAuthErrorAction } from "../../../components/operator-auth-error-action";
import { Panel } from "../../../components/panel";
import { useConfirm } from "../../../components/dialog-provider";
import { ErrorBoundary } from "../../../components/error-boundary";
import {
  getMission,
  getMissionChainTrace,
  getMissionEvents,
  getOperationsAgents,
  listMissionAuditReports,
  missionStateStreamUrl,
  parseLiveStateStreamMessage,
  listOperationsLogicNodes,
  missionApiUrl,
  updateMissionStateWithVault,
  updateMissionMetadata,
  getMissionTokenUsage,
} from "../../../lib/api-client";
import { Tooltip } from "../../../components/tooltip";
import { GLOSSARY } from "../../../lib/glossary";
import { humanizeState, normalizeState } from "../../../lib/format";
import { operatorRecoveryMessage } from "../../../lib/operator-auth-error";
import {
  deriveMissionPhaseDescriptor,
} from "../../../lib/smelt-cycle";
import type {
  MissionEvent,
  MissionChainTrace,
  MissionRecord,
  OperationsAgentRecord,
  OperationsAuditReportRecord,
  OperationsLogicNodeRecord,
  FeatureContract,
  LlmUsageSummary,
} from "../../../lib/types";

// Import all 22 panels from the structured subfolders
import {
  MissionSignalsPanel,
  MissionProgressPanel,
  LogicNodeProgressPanel,
  GeneratedOutputPanel,
  DeliveryPanel,
  ChainOfCommandTracePanel,
  RouteProvenancePanel,
  PmFeatureContractPanel,
  MissionCharterPanel,
  MissionContractPanel,
  ActiveAgentsPanel,
  EquivalenceReportPanel,
  SecurityCompliancePanel,
  DependencyAbsorptionPanel,
  RuntimeQcPanel,
  AimPanel,
  FusionPanel,
  LogicClustersPanel,
  PodGroupStandardsPanel,
  KnowledgeLakePanel,
  CostPanel,
  AuditEvidencePanel,
  MissionEventLogPanel,
} from "./panels";

const POLL_INTERVAL_MS = 2500;
const STREAM_REFRESH_DEBOUNCE_MS = 500;

function lifecycleEngineLabel(value: string | null | undefined): string | null {
  const normalized = (value ?? "").trim().toLowerCase();
  if (!normalized) return null;
  if (normalized === "mission_flow_v2" || normalized === "missionflow_v2") return "MissionFlow V2";
  if (normalized === "langgraph") return "LangGraph";
  if (normalized === "legacy_v1") return "Legacy V1";
  return value ?? null;
}

function isAgentActive(agent: OperationsAgentRecord, missionId: string): boolean {
  const state = normalizeState(agent.state);
  return (
    agent.active_mission_ids.includes(missionId) &&
    state !== "IDLE" &&
    state !== "PAUSED" &&
    state !== "ERROR"
  );
}

function nodeConfidence(node: OperationsLogicNodeRecord): number | null {
  const candidate = node.node.confidence;
  if (typeof candidate === "number" && Number.isFinite(candidate)) {
    return candidate > 1 ? candidate / 100 : candidate;
  }
  return null;
}

function MissionDetailPageContent() {
  const searchParams = useSearchParams();
  const missionId = searchParams.get("id") ?? "";
  const confirm = useConfirm();

  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [logicNodes, setLogicNodes] = useState<OperationsLogicNodeRecord[]>([]);
  const [chainTrace, setChainTrace] = useState<MissionChainTrace | null>(null);
  const [activeAgents, setActiveAgents] = useState<OperationsAgentRecord[]>([]);
  const [auditReports, setAuditReports] = useState<OperationsAuditReportRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [pausedMonitor, setPausedMonitor] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [transportMode, setTransportMode] = useState<"stream" | "poll" | "paused">("poll");
  const [streamEventsSeen, setStreamEventsSeen] = useState(0);
  const [streamErrors, setStreamErrors] = useState(0);
  const [pollFallbackTicks, setPollFallbackTicks] = useState(0);
  const [tokenUsage, setTokenUsage] = useState<LlmUsageSummary | null>(null);
  const [activeTab, setActiveTab] = useState<"execution" | "artifacts" | "contracts" | "events">("execution");
  // 6E — Inline name edit state.
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [nameSaving, setNameSaving] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const lastStreamRefreshRef = useRef(0);
  // Monotonic request id — loadDetails also runs on a polling interval, so
  // multiple requests can be in flight at once. A response for a superseded
  // missionId (or a stale poll tick after navigating away) must never
  // overwrite state for the mission actually being viewed.
  const detailsRequestIdRef = useRef(0);

  const loadDetails = useCallback(async () => {
    if (!missionId) {
      return;
    }
    const requestId = ++detailsRequestIdRef.current;
    try {
      const [missionData, missionEvents, missionChain, nodes, agentSnapshot, reports, tokenUsageData] = await Promise.all([
        getMission(missionId),
        getMissionEvents(missionId, 60),
        getMissionChainTrace(missionId),
        listOperationsLogicNodes({ limit: 400, missionId }),
        getOperationsAgents({ missionLimit: 300, assignmentLimit: 300, eventLimit: 200 }),
        listMissionAuditReports(missionId, 50).catch(() => [] as OperationsAuditReportRecord[]),
        getMissionTokenUsage(missionId).catch(() => null),
      ]);
      if (detailsRequestIdRef.current !== requestId) {
        return;
      }
      setMission(missionData);
      setEvents(missionEvents);
      setChainTrace(missionChain);
      setLogicNodes(nodes);
      setActiveAgents(agentSnapshot.agents.filter((agent: OperationsAgentRecord) => isAgentActive(agent, missionId)));
      setAuditReports(reports);
      setTokenUsage(tokenUsageData);
      setError(null);
      setLastUpdatedAt(new Date().toISOString());
    } catch (loadError) {
      if (detailsRequestIdRef.current !== requestId) {
        return;
      }
      setError(
        operatorRecoveryMessage(
          loadError instanceof Error ? loadError.message : "Unable to load mission details.",
        ),
      );
    } finally {
      if (detailsRequestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  }, [missionId]);

  useEffect(() => {
    setLoading(true);
    void loadDetails();
  }, [missionId, loadDetails]);

  useEffect(() => {
    if (!missionId) {
      return;
    }
    if (pausedMonitor) {
      setTransportMode("paused");
      return;
    }

    const startPollingFallback = () => {
      setTransportMode("poll");
      void loadDetails();
      const intervalId = window.setInterval(() => {
        setPollFallbackTicks((count) => count + 1);
        void loadDetails();
      }, POLL_INTERVAL_MS);
      return () => window.clearInterval(intervalId);
    };

    if (typeof window === "undefined" || typeof window.EventSource === "undefined") {
      return startPollingFallback();
    }

    const streamUrl = missionStateStreamUrl({
      missionId,
      includeAgentEvents: true,
    });
    const eventSource = new EventSource(streamUrl);
    let closeFallback: (() => void) | null = null;
    let streamOpen = false;

    eventSource.onopen = () => {
      streamOpen = true;
      setTransportMode("stream");
      setError(null);
      if (closeFallback) {
        closeFallback();
        closeFallback = null;
      }
    };

    eventSource.onerror = () => {
      setStreamErrors((count) => count + 1);
      if (!streamOpen) {
        if (!closeFallback) {
          closeFallback = startPollingFallback();
        }
        return;
      }
      streamOpen = false;
      eventSource.close();
      if (!closeFallback) {
        closeFallback = startPollingFallback();
      }
    };

    eventSource.addEventListener("state_event", (streamEvent: MessageEvent<string>) => {
      const parsed = parseLiveStateStreamMessage(streamEvent.data);
      if (!parsed) {
        return;
      }
      if (parsed.mission_id !== missionId) {
        return;
      }
      setStreamEventsSeen((count) => count + 1);
      const now = Date.now();
      if ((now - lastStreamRefreshRef.current) < STREAM_REFRESH_DEBOUNCE_MS) {
        return;
      }
      lastStreamRefreshRef.current = now;
      void loadDetails();
    });

    return () => {
      eventSource.close();
      if (closeFallback) {
        closeFallback();
      }
    };
  }, [missionId, pausedMonitor, loadDetails]);

  const verifiedCount = useMemo(
    () =>
      logicNodes.filter((node) => {
        const status = node.node.status;
        return typeof status === "string" && normalizeState(status) === "VERIFIED";
      }).length,
    [logicNodes],
  );

  const phaseDescriptor = useMemo(
    () =>
      deriveMissionPhaseDescriptor({
        missionState: mission?.state ?? "QUEUED",
        events,
        logicNodeCount: logicNodes.length,
        verifiedLogicNodeCount: verifiedCount,
        routingVersion:
          chainTrace?.routing_version ??
          (typeof mission?.metadata?.routing_version === "string"
            ? mission.metadata.routing_version
            : null),
      }),
    [chainTrace?.routing_version, events, logicNodes.length, mission?.metadata, mission?.state, verifiedCount],
  );

  const lifecycleEngine = useMemo(() => {
    const authoritative = lifecycleEngineLabel(
      mission?.lifecycle_engine ??
        chainTrace?.lifecycle_engine ??
        (typeof mission?.metadata?.lifecycle_engine === "string"
          ? mission.metadata.lifecycle_engine
          : null),
    );
    if (authoritative) return authoritative;
    if (phaseDescriptor.model === "v2") return "MissionFlow V2";
    const rv = (chainTrace?.routing_version ?? "").toLowerCase();
    if (rv.includes("langgraph")) return "LangGraph";
    return "Legacy V1";
  }, [
    mission?.lifecycle_engine,
    mission?.metadata,
    chainTrace?.lifecycle_engine,
    chainTrace?.routing_version,
    phaseDescriptor.model,
  ]);

  const phaseIndex = phaseDescriptor.phaseIndex;
  const phaseName = phaseDescriptor.phaseName;
  const phaseLabel = phaseDescriptor.model === "v2" ? "Mission phase" : "Smelt phase";
  const phaseStepperTitle =
    phaseDescriptor.model === "v2" ? "Mission Phase Stepper" : "Smelt-Cycle Phase Stepper";
  const phaseStepperAriaLabel =
    phaseDescriptor.model === "v2" ? "Mission flow phases" : "Smelt cycle phases";

  const avgConfidence = useMemo(() => {
    const values = logicNodes.map((node) => nodeConfidence(node)).filter((value): value is number => value !== null);
    if (values.length === 0) {
      return "N/A";
    }
    const average = values.reduce((sum, value) => sum + value, 0) / values.length;
    return `${Math.round(average * 1000) / 10}%`;
  }, [logicNodes]);

  const buildArtifacts = useMemo(
    () => chainTrace?.build_artifacts ?? [],
    [chainTrace],
  );
  const generatedCodeArtifact = useMemo(
    () => buildArtifacts.find((artifact) => artifact.artifact_type === "generated_code") ?? null,
    [buildArtifacts],
  );
  const featureContract = chainTrace?.feature_contract ?? null;
  const missionCharter = chainTrace?.mission_charter ?? null;
  const missionContract = chainTrace?.mission_contract ?? null;
  const logicClusters = chainTrace?.logic_clusters?.clusters ?? [];
  const podGroupStandards = useMemo(
    () => Object.entries(chainTrace?.pod_group_standards ?? {}),
    [chainTrace],
  );
  const fetchResult = chainTrace?.fetch_result ?? null;
  const applicationIntelligenceMap = chainTrace?.application_intelligence_map ?? null;
  const equivalenceReport = chainTrace?.equivalence_report ?? null;
  const securityComplianceReport = chainTrace?.security_compliance_report ?? null;
  const dependencyInventory = chainTrace?.dependency_inventory ?? null;
  const dependencyClassificationReport = chainTrace?.dependency_classification_report ?? null;
  const dependencyAbsorptionReport = chainTrace?.dependency_absorption_report ?? null;
  const depabsExecution = chainTrace?.depabs_execution ?? null;
  const sbomDelta = chainTrace?.sbom_delta ?? null;
  const dependencySurvivalJustifications = useMemo(
    () => chainTrace?.dependency_survival_justifications ?? [],
    [chainTrace],
  );
  const testdataManifest = chainTrace?.testdata_manifest ?? null;
  const runtimeQcReport = chainTrace?.runtime_qc_report ?? null;
  const masterLogicStream = chainTrace?.master_logic_stream ?? null;
  const deliverySummary = chainTrace?.delivery_summary ?? null;

  async function cancelMission() {
    if (!mission) {
      return;
    }
    const confirmed = await confirm({
      title: "Cancel Mission?",
      message:
        `This will immediately stop all active agents for mission ${mission.mission_id.slice(0, 16)}\u2026` +
        " Any work in progress will be lost and the mission will be marked FAILED. This cannot be undone.",
      confirmText: "Yes, Cancel Mission",
      cancelText: "Keep Running",
      dangerous: true,
    });
    if (!confirmed) {
      return;
    }
    setActionError(null);
    try {
      await updateMissionStateWithVault({
        mission_id: mission.mission_id,
        new_state: "FAILED",
        expected_state: mission.state,
      });
      await loadDetails();
    } catch (requestError) {
      setActionError(
        operatorRecoveryMessage(
          requestError instanceof Error ? requestError.message : "Mission state update failed.",
        ),
      );
    }
  }

  /** 6E — Begin editing the mission name. */
  function startEditName() {
    const currentName = String(
      (mission?.metadata as Record<string, unknown> | undefined)?.name ?? "",
    );
    setNameInput(currentName);
    setEditingName(true);
    requestAnimationFrame(() => nameInputRef.current?.focus());
  }

  /** 6E — Commit the edited name to the backend. */
  async function saveName() {
    if (!mission) return;
    const trimmed = nameInput.trim();
    setEditingName(false);
    if (!trimmed || trimmed === String((mission.metadata as Record<string, unknown> | undefined)?.name ?? "")) {
      return;
    }
    setNameSaving(true);
    try {
      const updated = await updateMissionMetadata(mission.mission_id, {
        ...(mission.metadata as Record<string, unknown> | undefined),
        name: trimmed,
      });
      setMission(updated);
    } catch {
      setActionError("Could not save mission name \u2014 the backend may not support PATCH yet.");
    } finally {
      setNameSaving(false);
    }
  }

  async function pauseMonitor() {
    if (pausedMonitor) {
      setPausedMonitor(false);
      return;
    }
    const confirmed = await confirm({
      title: "Pause Monitoring?",
      message: "Pause monitoring? The current backend does not support mission PAUSED state yet. This will freeze UI refresh until resumed.",
      confirmText: "Pause",
      cancelText: "Cancel",
    });
    if (confirmed) {
      setPausedMonitor(true);
    }
  }

  return (
    <div className="page shell-page">
      <PageHeader
        eyebrow="Mission Detail"
        title={
          mission ? (() => {
            const missionName = String(
              (mission.metadata as Record<string, unknown> | undefined)?.name ?? "",
            );
            return (
              <span className="mission-name-edit-wrap">
                {editingName ? (
                  /* Edit mode */
                  <>
                    <input
                      ref={nameInputRef}
                      type="text"
                      className="mission-name-input"
                      value={nameInput}
                      maxLength={120}
                      aria-label="Mission name"
                      onChange={(e) => setNameInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void saveName();
                        if (e.key === "Escape") setEditingName(false);
                      }}
                      onBlur={() => void saveName()}
                    />
                    <button
                      type="button"
                      className="mission-name-edit-btn"
                      aria-label="Cancel editing"
                      onClick={() => setEditingName(false)}
                    >
                      {"\u2715"}
                    </button>
                  </>
                ) : (
                  /* Display mode */
                  <>
                    {missionName ? (
                      <>
                        <span>{missionName}</span>
                        <span className="mono-id" style={{ fontSize: "0.6em", opacity: 0.55 }}>
                          {mission.mission_id.slice(0, 8)}{"\u2026"}
                        </span>

                        {(mission?.metadata as Record<string, unknown> | undefined)?.source === "fallback" && (
                          <span className="status-badge error" role="alert" aria-live="polite" style={{ marginLeft: "1rem", verticalAlign: "middle" }} title="Mission generated via LLM fallback route due to provider outage.">
                            {"\u26A0\uFE0F"} FALLBACK ROUTE
                          </span>
                        )}
                      </>
                    ) : (
                      <>
                        Mission{" "}
                        <span className="mono-id">{mission.mission_id.slice(0, 12)}{"\u2026"}</span>

                        {(mission?.metadata as Record<string, unknown> | undefined)?.source === "fallback" && (
                          <span className="status-badge error" role="alert" aria-live="polite" style={{ marginLeft: "1rem", verticalAlign: "middle" }} title="Mission generated via LLM fallback route due to provider outage.">
                            {"\u26A0\uFE0F"} FALLBACK ROUTE
                          </span>
                        )}
                      </>
                    )}
                    <button
                      type="button"
                      className="mission-name-edit-btn"
                      aria-label="Edit mission name"
                      title="Click to rename this mission"
                      onClick={startEditName}
                    >
                      {nameSaving ? "\u2026" : "\u270E"}
                    </button>
                  </>
                )}
              </span>
            );
          })()
          : "Mission Detail"
        }
        description={
          mission
            ? `Status ${humanizeState(mission.state)}. Live mission diagnostics for phases, active agents, and extracted LogicNodes.`
            : "Loading mission diagnostics."
        }
        actions={
          <div className="inline-actions">
            <Link href="/missions" className="secondary-button shell-link-button">
              Back to Missions
            </Link>
            {mission && (
              <Link
                href={`/chat?continueMissionId=${encodeURIComponent(mission.mission_id)}`}
                className="secondary-button shell-link-button"
              >
                Continue with PM
              </Link>
            )}
            <button type="button" className="secondary-button" onClick={pauseMonitor}>
              {pausedMonitor ? "Resume Monitor" : "Pause Monitor"}
            </button>
            <button type="button" className="danger-button" onClick={() => void cancelMission()}>
              Cancel Mission
            </button>
          </div>
        }
      />

      {error && (
        <div className="error-box">
          {error}
          <OperatorAuthErrorAction error={error} />
        </div>
      )}
      {actionError && (
        <div className="error-box">
          {actionError}
          <OperatorAuthErrorAction error={actionError} />
        </div>
      )}
      {pausedMonitor && (
        <p className="warning-box">Live refresh paused locally. Click "Resume Monitor" to continue.</p>
      )}

      {mission?.state === "COMPLETE" && deliverySummary && (
        <section className="delivery-banner" aria-label="Mission delivery summary">
          <div>
            <p className="eyebrow">Delivered</p>
            <h2>{deliverySummary.delivery_title}</h2>
            <p>{deliverySummary.delivery_summary}</p>
            {deliverySummary.usage_notes && (
              <p className="muted">{deliverySummary.usage_notes}</p>
            )}
          </div>
          <div className="delivery-banner-actions">
            {generatedCodeArtifact && (
              <>
                <Link
                  href={`/missions/output?id=${encodeURIComponent(missionId)}`}
                  className="primary-button shell-link-button"
                >
                  View Generated Code
                </Link>
                <a
                  className="secondary-button shell-link-button"
                  href={missionApiUrl(
                    `/v1/missions/${encodeURIComponent(missionId)}/artifact?artifact_type=generated_code`,
                  )}
                >
                  Download
                </a>
              </>
            )}
            {!generatedCodeArtifact && deliverySummary.primary_artifact_type && (
              <span className="muted">{deliverySummary.primary_artifact_type}</span>
            )}
          </div>
        </section>
      )}

      <ErrorBoundary>
        <MissionProgressPanel
          mission={mission}
          chainTrace={chainTrace}
          events={events}
          phaseLabel={phaseLabel}
          phaseName={phaseName}
          lastUpdatedAt={lastUpdatedAt}
          transportMode={transportMode}
          streamEventsSeen={streamEventsSeen}
          pollFallbackTicks={pollFallbackTicks}
          activeAgentCount={activeAgents.length}
          buildArtifactCount={buildArtifacts.length}
        />
      </ErrorBoundary>

      <Panel title={phaseStepperTitle}>
        <ol className="phase-stepper" aria-label={phaseStepperAriaLabel}>
          {phaseDescriptor.phases.map((phase, index) => {
            const complete = index < phaseIndex;
            const active = index === phaseIndex;
            return (
              <li
                key={phase}
                className={`phase-step ${complete ? "complete" : ""} ${active ? "active" : ""}`}
                aria-current={active ? "step" : undefined}
              >
                <span
                  className="phase-marker"
                  aria-label={complete ? "Completed" : active ? "Active" : "Pending"}
                >
                  {complete ? "\u2713" : active ? "\u25CF" : "\u25CB"}
                </span>
                {GLOSSARY[phase.toUpperCase().replace(/\s/g, "_")] ??
                GLOSSARY[phase] ? (
                  <Tooltip
                    content={
                      (GLOSSARY[phase.toUpperCase().replace(/\s/g, "_")] ?? GLOSSARY[phase])
                        .definition
                    }
                    side="bottom"
                  >
                    <span className="phase-name">{phase}</span>
                  </Tooltip>
                ) : (
                  <span className="phase-name">{phase}</span>
                )}
              </li>
            );
          })}
        </ol>
      </Panel>

      {/* Phase 2B — Tabbed progressive disclosure replacing the flat 22-panel grid */}
      <div className="mission-tabs" role="tablist" aria-label="Mission detail sections">
        {(["execution", "artifacts", "contracts", "events"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            aria-controls={`tab-panel-${tab}`}
            className={`mission-tab${activeTab === tab ? " active" : ""}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Execution tab — live signals, node progress, active agents */}
      <div
        id="tab-panel-execution"
        role="tabpanel"
        aria-labelledby="tab-execution"
        hidden={activeTab !== "execution"}
        className="mission-tab-panels"
      >
        <ErrorBoundary><MissionSignalsPanel loading={loading} mission={mission} chainTrace={chainTrace} lifecycleEngine={lifecycleEngine} phaseLabel={phaseLabel} phaseName={phaseName} lastUpdatedAt={lastUpdatedAt} transportMode={transportMode} streamEventsSeen={streamEventsSeen} streamErrors={streamErrors} pollFallbackTicks={pollFallbackTicks} /></ErrorBoundary>
        <ErrorBoundary><LogicNodeProgressPanel missionId={missionId} missionType={chainTrace?.mission_type ?? missionContract?.mission_type ?? null} logicNodes={logicNodes} verifiedCount={verifiedCount} avgConfidence={avgConfidence} /></ErrorBoundary>
        <ErrorBoundary><ChainOfCommandTracePanel chainTrace={chainTrace} /></ErrorBoundary>
        <ErrorBoundary><ActiveAgentsPanel activeAgents={activeAgents} /></ErrorBoundary>
        <ErrorBoundary>
          <CostPanel
            tokenUsage={tokenUsage}
            quoted={
              featureContract?.cost_estimate ??
              (typeof mission?.metadata?.feature_contract === "object" &&
              mission.metadata.feature_contract &&
              "cost_estimate" in mission.metadata.feature_contract
                ? (mission.metadata.feature_contract as { cost_estimate?: FeatureContract["cost_estimate"] })
                    .cost_estimate
                : null) ??
              null
            }
          />
        </ErrorBoundary>
      </div>

      {/* Artifacts tab — generated output, build artifacts, audit evidence, quality reports */}
      <div
        id="tab-panel-artifacts"
        role="tabpanel"
        aria-labelledby="tab-artifacts"
        hidden={activeTab !== "artifacts"}
        className="mission-tab-panels"
      >
        <ErrorBoundary><GeneratedOutputPanel missionId={missionId} generatedCodeArtifact={generatedCodeArtifact} /></ErrorBoundary>
        <ErrorBoundary><DeliveryPanel missionId={missionId} buildArtifacts={buildArtifacts} /></ErrorBoundary>
        <ErrorBoundary><AuditEvidencePanel auditReports={auditReports} /></ErrorBoundary>
        <ErrorBoundary><AimPanel applicationIntelligenceMap={applicationIntelligenceMap} /></ErrorBoundary>
        <ErrorBoundary><FusionPanel masterLogicStream={masterLogicStream} /></ErrorBoundary>
        <ErrorBoundary><KnowledgeLakePanel fetchResult={fetchResult} /></ErrorBoundary>
        <ErrorBoundary><EquivalenceReportPanel equivalenceReport={equivalenceReport} /></ErrorBoundary>
        <ErrorBoundary><SecurityCompliancePanel securityComplianceReport={securityComplianceReport} /></ErrorBoundary>
        <ErrorBoundary><DependencyAbsorptionPanel dependencyInventory={dependencyInventory} dependencyClassificationReport={dependencyClassificationReport} dependencyAbsorptionReport={dependencyAbsorptionReport} depabsExecution={depabsExecution} sbomDelta={sbomDelta} dependencySurvivalJustifications={dependencySurvivalJustifications} /></ErrorBoundary>
        <ErrorBoundary><RuntimeQcPanel runtimeQcReport={runtimeQcReport} testdataManifest={testdataManifest} /></ErrorBoundary>
      </div>

      {/* Contracts tab — planning artifacts and specifications */}
      <div
        id="tab-panel-contracts"
        role="tabpanel"
        aria-labelledby="tab-contracts"
        hidden={activeTab !== "contracts"}
        className="mission-tab-panels"
      >
        <ErrorBoundary><PmFeatureContractPanel featureContract={featureContract} /></ErrorBoundary>
        <ErrorBoundary><MissionCharterPanel missionCharter={missionCharter} /></ErrorBoundary>
        <ErrorBoundary><MissionContractPanel missionContract={missionContract} /></ErrorBoundary>
        <ErrorBoundary><PodGroupStandardsPanel podGroupStandards={podGroupStandards} /></ErrorBoundary>
        <ErrorBoundary><LogicClustersPanel logicClusters={logicClusters} /></ErrorBoundary>
        <ErrorBoundary><RouteProvenancePanel chainTrace={chainTrace} /></ErrorBoundary>
      </div>

      {/* Events tab — mission event log */}
      <div
        id="tab-panel-events"
        role="tabpanel"
        aria-labelledby="tab-events"
        hidden={activeTab !== "events"}
        className="mission-tab-panels"
      >
        <ErrorBoundary><MissionEventLogPanel events={events} model={phaseDescriptor.model} /></ErrorBoundary>
      </div>
    </div>
  );
}

export default function MissionDetailPage() {
  return (
    <Suspense fallback={<div className="panel-loading-state"><p>Loading mission details...</p></div>}>
      <MissionDetailPageContent />
    </Suspense>
  );
}
