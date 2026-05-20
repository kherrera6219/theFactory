"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "../../../components/page-header";
import { Panel } from "../../../components/panel";
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
} from "../../../lib/api-client";
import { formatDateTime, formatTime, humanizeState, normalizeState } from "../../../lib/format";
import {
  deriveMissionPhaseDescriptor,
  smeltPhaseFromEventType,
} from "../../../lib/smelt-cycle";
import type {
  MissionEvent,
  MissionChainTrace,
  MissionRecord,
  OperationsAgentRecord,
  OperationsAuditReportRecord,
  OperationsLogicNodeRecord,
} from "../../../lib/types";

const POLL_INTERVAL_MS = 2500;
const STREAM_REFRESH_DEBOUNCE_MS = 500;

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

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => item.length > 0);
}

export default function MissionDetailPage() {
  const params = useParams<{ id: string }>();
  const missionId = String(params.id ?? "").trim();

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
  const lastStreamRefreshRef = useRef(0);

  const loadDetails = useCallback(async () => {
    if (!missionId) {
      return;
    }
    try {
      const [missionData, missionEvents, missionChain, nodes, agentSnapshot, reports] = await Promise.all([
        getMission(missionId),
        getMissionEvents(missionId, 60),
        getMissionChainTrace(missionId),
        listOperationsLogicNodes({ limit: 400, missionId }),
        getOperationsAgents({ missionLimit: 300, assignmentLimit: 300, eventLimit: 200 }),
        listMissionAuditReports(missionId, 50).catch(() => [] as OperationsAuditReportRecord[]),
      ]);
      setMission(missionData);
      setEvents(missionEvents);
      setChainTrace(missionChain);
      setLogicNodes(nodes);
      setActiveAgents(agentSnapshot.agents.filter((agent: OperationsAgentRecord) => isAgentActive(agent, missionId)));
      setAuditReports(reports);
      setError(null);
      setLastUpdatedAt(new Date().toISOString());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load mission details.");
    } finally {
      setLoading(false);
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
    if (phaseDescriptor.model === "v2") return "MissionFlow V2";
    const rv = (chainTrace?.routing_version ?? "").toLowerCase();
    if (rv.includes("langgraph")) return "LangGraph";
    return "Legacy V1";
  }, [phaseDescriptor.model, chainTrace?.routing_version]);

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

  const routeStages = useMemo(() => {
    const provenance = chainTrace?.route_provenance;
    if (!provenance) {
      return [];
    }
    return [
      { key: "ceo", title: "CEO Delegation", value: provenance.ceo ?? null },
      { key: "pod_manager", title: "Pod Manager Delegation", value: provenance.pod_manager ?? null },
      { key: "specialist", title: "Specialist Planning", value: provenance.specialist ?? null },
    ].filter((item) => item.value);
  }, [chainTrace]);

  const artifactEntries = useMemo(
    () => Object.entries(chainTrace?.artifact_summary ?? {}),
    [chainTrace],
  );
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
  const podGroupStandards = Object.entries(chainTrace?.pod_group_standards ?? {});
  const fetchResult = chainTrace?.fetch_result ?? null;
  const applicationIntelligenceMap = chainTrace?.application_intelligence_map ?? null;
  const equivalenceReport = chainTrace?.equivalence_report ?? null;
  const securityComplianceReport = chainTrace?.security_compliance_report ?? null;
  const dependencyInventory = chainTrace?.dependency_inventory ?? null;
  const dependencyClassificationReport = chainTrace?.dependency_classification_report ?? null;
  const dependencyAbsorptionReport = chainTrace?.dependency_absorption_report ?? null;
  const depabsExecution = chainTrace?.depabs_execution ?? null;
  const sbomDelta = chainTrace?.sbom_delta ?? null;
  const dependencySurvivalJustifications =
    chainTrace?.dependency_survival_justifications ?? [];
  const testdataManifest = chainTrace?.testdata_manifest ?? null;
  const runtimeQcReport = chainTrace?.runtime_qc_report ?? null;
  const masterLogicStream = chainTrace?.master_logic_stream ?? null;
  const deliverySummary = chainTrace?.delivery_summary ?? null;

  async function cancelMission() {
    if (!mission) {
      return;
    }
    const confirmed = window.confirm(
      "Cancel mission? This operation marks the mission as FAILED in the current backend workflow.",
    );
    if (!confirmed) {
      return;
    }
    setActionError(null);
    try {
      await updateMissionStateWithVault({
        missionId: mission.mission_id,
        newState: "FAILED",
        expectedState: mission.state,
      });
      await loadDetails();
    } catch (requestError) {
      setActionError(
        requestError instanceof Error
          ? requestError.message
          : "Mission state update failed.",
      );
    }
  }

  function pauseMonitor() {
    const confirmed = window.confirm(
      "Pause monitoring? The current backend does not support mission PAUSED state yet. " +
        "This will freeze UI refresh until resumed.",
    );
    if (!confirmed) {
      return;
    }
    setPausedMonitor((current) => !current);
  }

  return (
    <div className="page shell-page">
      <PageHeader
        eyebrow="Mission Detail"
        title={mission ? `Mission ${mission.mission_id}` : "Mission Detail"}
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
            <button type="button" className="secondary-button" onClick={pauseMonitor}>
              {pausedMonitor ? "Resume Monitor" : "Pause Monitor"}
            </button>
            <button type="button" onClick={() => void cancelMission()}>
              Cancel Mission
            </button>
          </div>
        }
      />

      {error && <p className="error-box">{error}</p>}
      {actionError && <p className="error-box">{actionError}</p>}
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
              <a
                className="primary-button shell-link-button"
                href={missionApiUrl(
                  `/v1/missions/${encodeURIComponent(missionId)}/artifact?artifact_type=generated_code`,
                )}
              >
                Download Generated Code
              </a>
            )}
            {!generatedCodeArtifact && deliverySummary.primary_artifact_type && (
              <span className="muted">{deliverySummary.primary_artifact_type}</span>
            )}
          </div>
        </section>
      )}

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
                <span className="phase-marker">{complete ? "✓" : active ? "●" : "○"}</span>
                <span>{phase}</span>
              </li>
            );
          })}
        </ol>
      </Panel>

      <div className="mission-detail-grid">
        <Panel title="Mission Signals">
          {loading && <p className="muted">Loading mission signals...</p>}
          {!loading && mission && (
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{humanizeState(mission.state)}</dd>
              </div>
              <div>
                <dt>Lifecycle engine</dt>
                <dd>
                  <span
                    className={`connection-chip ${
                      lifecycleEngine === "MissionFlow V2"
                        ? "live"
                        : lifecycleEngine === "LangGraph"
                          ? "retrying"
                          : "stale"
                    }`}
                    title={`Active lifecycle engine: ${lifecycleEngine}`}
                  >
                    {lifecycleEngine}
                  </span>
                </dd>
              </div>
              <div>
                <dt>{phaseLabel}</dt>
                <dd>{phaseName}</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{formatDateTime(mission.created_at)}</dd>
              </div>
              <div>
                <dt>Target language</dt>
                <dd>{mission.requested_target_language ?? "n/a"}</dd>
              </div>
              {/* PORT two-phase indicator */}
              {chainTrace?.mission_type === "PORT" &&
                chainTrace?.port_source_language && (
                  <div>
                    <dt>PORT phases</dt>
                    <dd>
                      <span
                        className={`connection-chip ${chainTrace?.port_source_logicnodes?.length ? "live" : "retrying"}`}
                        title="Source extraction phase"
                      >
                        EXTRACTION: {String(chainTrace?.port_source_language ?? "?")}
                        {chainTrace?.port_source_logicnodes?.length ? " ✓" : " ●"}
                      </span>
                      {" → "}
                      <span
                        className={`connection-chip ${chainTrace?.port_phase === "generation" ? "retrying" : chainTrace?.generated_output ? "live" : "stale"}`}
                        title="Target generation phase"
                      >
                        GENERATION: {String(chainTrace?.port_target_language ?? mission.requested_target_language ?? "?")}
                        {chainTrace?.generated_output ? " ✓" : " ●"}
                      </span>
                    </dd>
                  </div>
                )}
              <div>
                <dt>Last refresh</dt>
                <dd>{lastUpdatedAt ? formatTime(lastUpdatedAt) : "n/a"}</dd>
              </div>
              <div>
                <dt>Transport mode</dt>
                <dd>{transportMode}</dd>
              </div>
              <div>
                <dt>Stream events</dt>
                <dd>{streamEventsSeen}</dd>
              </div>
              <div>
                <dt>Stream errors</dt>
                <dd>{streamErrors}</dd>
              </div>
              <div>
                <dt>Poll fallback ticks</dt>
                <dd>{pollFallbackTicks}</dd>
              </div>
            </dl>
          )}
        </Panel>

        <Panel title="LogicNode Progress">
          <dl>
            <div>
              <dt>Extracted</dt>
              <dd>{logicNodes.length} LogicNodes</dd>
            </div>
            <div>
              <dt>Verified</dt>
              <dd>{verifiedCount}</dd>
            </div>
            <div>
              <dt>Average confidence</dt>
              <dd>{avgConfidence}</dd>
            </div>
          </dl>
          <div className="inline-actions">
            <Link
              href={`/logicnodes?mission=${encodeURIComponent(missionId)}`}
              className="secondary-button shell-link-button"
            >
              Open LogicNode Explorer
            </Link>
          </div>
        </Panel>
      </div>

      <Panel title="Chain of Command Trace">
        {!chainTrace && <p className="muted">Chain trace not available yet.</p>}
        {chainTrace && (
          <>
            <dl>
              <div>
                <dt>Routing enforced</dt>
                <dd>{chainTrace.routing_enforced ? "yes" : "no"}</dd>
              </div>
              <div>
                <dt>Routing version</dt>
                <dd>{chainTrace.routing_version ?? "n/a"}</dd>
              </div>
              <div>
                <dt>Selected agent</dt>
                <dd>{chainTrace.selected_agent_id ?? "n/a"}</dd>
              </div>
              <div>
                <dt>Pod manager</dt>
                <dd>{chainTrace.assigned_pod_manager_agent_id ?? "n/a"}</dd>
              </div>
              <div>
                <dt>Specialist</dt>
                <dd>{chainTrace.assigned_specialist_agent_id ?? "n/a"}</dd>
              </div>
            </dl>
            {chainTrace.events.length === 0 && (
              <p className="muted">No chain events recorded yet.</p>
            )}
            {chainTrace.events.length > 0 && (
              <ul className="summary-list">
                {chainTrace.events.slice(0, 20).map((event) => (
                  <li key={`${event.event_type}-${event.ts}`}>
                    <strong>{formatTime(event.ts)}</strong>
                    <span>{event.event_type}</span>
                    <span className="muted">{event.agent_id ?? "unassigned"}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Panel>

      <Panel title="Route Provenance">
        {!chainTrace?.route_provenance && <p className="muted">Route provenance not available yet.</p>}
        {chainTrace?.route_provenance && (
          <>
            <dl>
              <div>
                <dt>Fallback used</dt>
                <dd>{chainTrace.route_provenance.fallback_used ? "yes" : "no"}</dd>
              </div>
            </dl>
            {routeStages.length === 0 && <p className="muted">No delegation snapshots recorded yet.</p>}
            {routeStages.length > 0 && (
              <ul className="card-list">
                {routeStages.map((stage) => {
                  const deliverables = asStringArray(stage.value?.deliverables);
                  const riskNotes = asStringArray(stage.value?.risk_notes);
                  return (
                    <li key={stage.key} className="info-card">
                      <h3>{stage.title}</h3>
                      <dl>
                        <div>
                          <dt>Source</dt>
                          <dd>{stage.value?.source ?? "n/a"}</dd>
                        </div>
                        <div>
                          <dt>LLM route</dt>
                          <dd>{stage.value?.llm_route ?? "n/a"}</dd>
                        </div>
                        <div>
                          <dt>Model</dt>
                          <dd>
                            {stage.value?.model_provider ?? "n/a"} / {stage.value?.model ?? "n/a"}
                          </dd>
                        </div>
                        {stage.value?.target_agent_id && (
                          <div>
                            <dt>Target agent</dt>
                            <dd>{stage.value.target_agent_id}</dd>
                          </div>
                        )}
                        {stage.value?.specialist_agent_id && (
                          <div>
                            <dt>Specialist</dt>
                            <dd>{stage.value.specialist_agent_id}</dd>
                          </div>
                        )}
                        {stage.value?.pod_manager_agent_id && (
                          <div>
                            <dt>Pod manager</dt>
                            <dd>{stage.value.pod_manager_agent_id}</dd>
                          </div>
                        )}
                      </dl>
                      {stage.value?.rationale && <p>{stage.value.rationale}</p>}
                      {stage.value?.plan_summary && <p>{stage.value.plan_summary}</p>}
                      {deliverables.length > 0 && (
                        <>
                          <p className="muted">Deliverables</p>
                          <ul className="summary-list">
                            {deliverables.map((item) => (
                              <li key={`${stage.key}-deliverable-${item}`}>
                                <span>{item}</span>
                              </li>
                            ))}
                          </ul>
                        </>
                      )}
                      {riskNotes.length > 0 && (
                        <>
                          <p className="muted">Risk notes</p>
                          <ul className="summary-list">
                            {riskNotes.map((item) => (
                              <li key={`${stage.key}-risk-${item}`}>
                                <span>{item}</span>
                              </li>
                            ))}
                          </ul>
                        </>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            {artifactEntries.length > 0 && (
              <>
                <p className="muted">Stage artifacts</p>
                <ul className="summary-list">
                  {artifactEntries.map(([stage, artifact]) => (
                    <li key={stage}>
                      <strong>{stage}</strong>
                      <span>{String(artifact.event_type ?? "artifact")}</span>
                      <span className="muted">{String(artifact.agent_id ?? "unassigned")}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </Panel>

      <Panel title="PM Feature Contract">
        {!featureContract && <p className="muted">No PM feature contract recorded yet.</p>}
        {featureContract && (
          <>
            <dl>
              <div>
                <dt>Title</dt>
                <dd>{featureContract.title}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{featureContract.source}</dd>
              </div>
              <div>
                <dt>Complexity</dt>
                <dd>{featureContract.estimated_complexity}</dd>
              </div>
              <div>
                <dt>Approval</dt>
                <dd>{featureContract.human_approval_required ? "required" : "not required"}</dd>
              </div>
            </dl>
            <p>{featureContract.summary}</p>
            {featureContract.acceptance_criteria.length > 0 && (
              <ul className="summary-list">
                {featureContract.acceptance_criteria.map((criterion) => (
                  <li key={`feature-criterion-${criterion}`}>
                    <span>{criterion}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Panel>

      <Panel title="Mission Charter">
        {!missionCharter && <p className="muted">No mission charter recorded yet.</p>}
        {missionCharter && (
          <>
            <dl>
              <div>
                <dt>Mode</dt>
                <dd>{missionCharter.mission_mode_label ?? missionCharter.mission_mode}</dd>
              </div>
              <div>
                <dt>Depth</dt>
                <dd>{missionCharter.depth_mode}</dd>
              </div>
              <div>
                <dt>Output</dt>
                <dd>{missionCharter.output_mode}</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{formatDateTime(missionCharter.created_at)}</dd>
              </div>
            </dl>
            <p>{missionCharter.objective}</p>
            {missionCharter.success_criteria.length > 0 && (
              <ul className="summary-list">
                {missionCharter.success_criteria.map((criterion) => (
                  <li key={`charter-criterion-${criterion}`}>
                    <span>{criterion}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Panel>

      {applicationIntelligenceMap && (
        <Panel title="Application Intelligence Map">
          <dl>
            <div>
              <dt>Primary language</dt>
              <dd>{applicationIntelligenceMap.primary_language ?? "n/a"}</dd>
            </div>
            <div>
              <dt>Complexity</dt>
              <dd>{applicationIntelligenceMap.complexity_assessment}</dd>
            </div>
            <div>
              <dt>Functions</dt>
              <dd>{applicationIntelligenceMap.total_functions}</dd>
            </div>
            <div>
              <dt>Classes</dt>
              <dd>{applicationIntelligenceMap.total_classes}</dd>
            </div>
            <div>
              <dt>Files analyzed</dt>
              <dd>
                {applicationIntelligenceMap.extraction_summary?.files_analyzed ?? 0} /{" "}
                {applicationIntelligenceMap.extraction_summary?.files_seen ?? 0}
              </dd>
            </div>
            <div>
              <dt>Approval</dt>
              <dd>
                {applicationIntelligenceMap.human_approval_recommended
                  ? "recommended"
                  : "not recommended"}
              </dd>
            </div>
          </dl>
          <p>{applicationIntelligenceMap.repository_summary}</p>
          {applicationIntelligenceMap.detected_languages.length > 0 && (
            <>
              <p className="muted">Detected languages</p>
              <ul className="chip-list">
                {applicationIntelligenceMap.detected_languages.map((language) => (
                  <li key={`aim-language-${language}`} className="chip-item">
                    {language}
                  </li>
                ))}
              </ul>
            </>
          )}
          {applicationIntelligenceMap.detected_dependencies.length > 0 && (
            <>
              <p className="muted">Detected dependencies</p>
              <ul className="chip-list">
                {applicationIntelligenceMap.detected_dependencies.slice(0, 16).map((dependency) => (
                  <li key={`aim-dependency-${dependency}`} className="chip-item">
                    {dependency}
                  </li>
                ))}
              </ul>
            </>
          )}
          {applicationIntelligenceMap.risks.length > 0 && (
            <>
              <p className="muted">Risks</p>
              <ul className="summary-list">
                {applicationIntelligenceMap.risks.map((risk) => (
                  <li key={`aim-risk-${risk}`}>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {applicationIntelligenceMap.recommended_approach && (
            <p>{applicationIntelligenceMap.recommended_approach}</p>
          )}
        </Panel>
      )}

      <Panel title="Mission Contract">
        {!missionContract && <p className="muted">No CEO mission contract recorded yet.</p>}
        {missionContract && (
          <>
            <dl>
              <div>
                <dt>Type</dt>
                <dd>{missionContract.mission_type}</dd>
              </div>
              <div>
                <dt>Output mode</dt>
                <dd>{missionContract.output_mode}</dd>
              </div>
              <div>
                <dt>Format</dt>
                <dd>{missionContract.output_format}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{missionContract.source}</dd>
              </div>
            </dl>
            <p>{missionContract.contract_summary}</p>
            {missionContract.logicnode_requirements.length > 0 && (
              <ul className="card-list">
                {missionContract.logicnode_requirements.map((requirement) => (
                  <li
                    key={`${requirement.domain}-${requirement.concept}-${requirement.intent}`}
                    className="info-card"
                  >
                    <h3>{requirement.concept}</h3>
                    <p>{requirement.intent}</p>
                    <p className="muted">
                      {requirement.domain} - {requirement.priority}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Panel>

      <Panel title="Logic Clusters">
        {logicClusters.length === 0 && <p className="muted">No logic clusters recorded yet.</p>}
        {logicClusters.length > 0 && (
          <ul className="card-list">
            {logicClusters.map((cluster) => (
              <li key={cluster.cluster_id} className="info-card">
                <h3>{cluster.title}</h3>
                <dl>
                  <div>
                    <dt>Domain</dt>
                    <dd>{cluster.domain}</dd>
                  </div>
                  <div>
                    <dt>Priority</dt>
                    <dd>{cluster.priority}</dd>
                  </div>
                  <div>
                    <dt>Pod manager</dt>
                    <dd>{cluster.pod_manager_agent_id}</dd>
                  </div>
                  <div>
                    <dt>Specialist</dt>
                    <dd>{cluster.specialist_agent_id}</dd>
                  </div>
                </dl>
                <p>{cluster.rationale}</p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Pod Group Standards">
        {podGroupStandards.length === 0 && (
          <p className="muted">No pod group standards recorded yet.</p>
        )}
        {podGroupStandards.length > 0 && (
          <ul className="card-list">
            {podGroupStandards.map(([pod, standard]) => (
              <li key={pod} className="info-card">
                <h3>{pod}</h3>
                <dl>
                  <div>
                    <dt>Pod manager</dt>
                    <dd>{standard.pod_manager_agent_id}</dd>
                  </div>
                  <div>
                    <dt>Canonical LogicNodes</dt>
                    <dd>{standard.canonical_logicnodes.length}</dd>
                  </div>
                  <div>
                    <dt>Duplicates removed</dt>
                    <dd>{standard.eliminated_duplicates}</dd>
                  </div>
                  <div>
                    <dt>Source</dt>
                    <dd>{standard.source}</dd>
                  </div>
                </dl>
                <p>{standard.summary}</p>
                {standard.canonical_logicnodes.length > 0 && (
                  <ul className="summary-list">
                    {standard.canonical_logicnodes.slice(0, 8).map((node) => (
                      <li key={node.standard_node_id}>
                        <strong>{node.concept}</strong>
                        <span>{node.domain}</span>
                        <span className="muted">
                          {node.languages.length > 0 ? node.languages.join(", ") : "language n/a"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {fetchResult && (
        <Panel title="Knowledge Lake (FETCH)">
          <dl>
            <div>
              <dt>Indexed languages</dt>
              <dd>
                {fetchResult.indexed_languages?.length > 0
                  ? fetchResult.indexed_languages.join(", ")
                  : "none"}
              </dd>
            </div>
            {fetchResult.skipped_languages?.length > 0 && (
              <div>
                <dt>Skipped (no bootstrap docs)</dt>
                <dd>{fetchResult.skipped_languages.join(", ")}</dd>
              </div>
            )}
            <div>
              <dt>Knowledge ready</dt>
              <dd>{fetchResult.knowledge_ready ? "Yes" : "No"}</dd>
            </div>
            <div>
              <dt>Embedding model</dt>
              <dd>
                {fetchResult.embedding_provider && fetchResult.embedding_model
                  ? `${fetchResult.embedding_provider}/${fetchResult.embedding_model}`
                  : "deterministic"}
              </dd>
            </div>
            <div>
              <dt>Refresh</dt>
              <dd>{fetchResult.refresh_enabled === false ? "disabled" : "enabled"}</dd>
            </div>
            {(fetchResult.refreshed_languages?.length ?? 0) > 0 && (
              <div>
                <dt>Refreshed</dt>
                <dd>{fetchResult.refreshed_languages?.join(", ")}</dd>
              </div>
            )}
            {(fetchResult.unchanged_languages?.length ?? 0) > 0 && (
              <div>
                <dt>Unchanged</dt>
                <dd>{fetchResult.unchanged_languages?.join(", ")}</dd>
              </div>
            )}
            {fetchResult.errors?.length > 0 && (
              <div>
                <dt>Errors</dt>
                <dd className="error-text">{fetchResult.errors.join("; ")}</dd>
              </div>
            )}
          </dl>
        </Panel>
      )}

      {masterLogicStream != null &&
        (masterLogicStream.master_logic_stream?.length ?? 0) > 0 && (
          <Panel title="Master Logic Stream (FUSION)">
            <dl>
              <div>
                <dt>Unified nodes</dt>
                <dd>{masterLogicStream.total_unified_nodes}</dd>
              </div>
              <div>
                <dt>Duplicates eliminated across pods</dt>
                <dd>{masterLogicStream.eliminated_across_pods}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{masterLogicStream.source}</dd>
              </div>
            </dl>
            <ul className="summary-list">
              {masterLogicStream.master_logic_stream.map((node) => (
                <li key={node.node_id}>
                  <strong>{node.concept}</strong>
                  <span>{node.domain}</span>
                  <span className="muted">{(node.source_pods ?? []).join(", ")}</span>
                </li>
              ))}
            </ul>
          </Panel>
        )}

      <Panel title="Active Agents">
        {activeAgents.length === 0 && <p className="muted">No active agents currently assigned.</p>}
        {activeAgents.length > 0 && (
          <ul className="card-list">
            {activeAgents.map((agent) => (
              <li key={agent.agent_id} className="info-card">
                <h3>{agent.agent_id}</h3>
                <p>{agent.name}</p>
                <p className="muted">
                  {agent.pod} - {agent.tier} - {agent.state}
                </p>
                <p className="muted">Workload: {agent.workload_pct}%</p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Generated Output">
        {!generatedCodeArtifact && <p className="muted">No generated-code artifact recorded yet.</p>}
        {generatedCodeArtifact && (
          <>
            <dl>
              <div>
                <dt>File</dt>
                <dd>{String(generatedCodeArtifact.manifest?.filename ?? generatedCodeArtifact.artifact_id)}</dd>
              </div>
              <div>
                <dt>Digest</dt>
                <dd>{generatedCodeArtifact.digest_sha256 ?? "n/a"}</dd>
              </div>
              <div>
                <dt>Size</dt>
                <dd>{generatedCodeArtifact.size_bytes} bytes</dd>
              </div>
            </dl>
            <div className="inline-actions">
              <a
                className="secondary-button shell-link-button"
                href={missionApiUrl(
                  `/v1/missions/${encodeURIComponent(missionId)}/artifact?artifact_type=generated_code`,
                )}
              >
                Download Generated Code
              </a>
            </div>
            {generatedCodeArtifact.artifact_text && (
              <div className="code-block">
                <pre>{generatedCodeArtifact.artifact_text}</pre>
              </div>
            )}
          </>
        )}
      </Panel>

      <Panel title="Build Artifacts">
        {buildArtifacts.length === 0 && (
          <p className="muted">No build or package artifacts recorded for this mission yet.</p>
        )}
        {buildArtifacts.length > 0 && (
          <ul className="card-list">
            {buildArtifacts.map((artifact) => (
              <li key={artifact.artifact_id} className="info-card">
                <h3>{artifact.artifact_type}</h3>
                <dl>
                  <div>
                    <dt>Status</dt>
                    <dd>{artifact.status}</dd>
                  </div>
                  <div>
                    <dt>Stage</dt>
                    <dd>{artifact.stage}</dd>
                  </div>
                  <div>
                    <dt>Storage</dt>
                    <dd>{artifact.storage_backend}</dd>
                  </div>
                  <div>
                    <dt>Digest</dt>
                    <dd>{artifact.digest_sha256 ?? "n/a"}</dd>
                  </div>
                  <div>
                    <dt>Size</dt>
                    <dd>{artifact.size_bytes} bytes</dd>
                  </div>
                  <div>
                    <dt>Updated</dt>
                    <dd>{formatDateTime(artifact.updated_at)}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {equivalenceReport && (
        <Panel title="Equivalence Verification">
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{equivalenceReport.status}</dd>
            </div>
            <div>
              <dt>Passed</dt>
              <dd>{equivalenceReport.passed ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Blocking</dt>
              <dd>{equivalenceReport.blocking ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Risk</dt>
              <dd>{equivalenceReport.risk_level}</dd>
            </div>
            <div>
              <dt>Target language</dt>
              <dd>{equivalenceReport.target_language ?? "n/a"}</dd>
            </div>
            <div>
              <dt>Enforcement</dt>
              <dd>{equivalenceReport.enforcement_enabled ? "enabled" : "advisory"}</dd>
            </div>
          </dl>
          {equivalenceReport.findings.length > 0 && (
            <>
              <p className="muted">Findings</p>
              <ul className="summary-list">
                {equivalenceReport.findings.map((finding) => (
                  <li key={`equivalence-finding-${finding}`}>
                    <span>{finding}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {equivalenceReport.checks.length > 0 && (
            <ul className="card-list">
              {equivalenceReport.checks.map((check) => (
                <li key={check.check_id} className="info-card">
                  <h3>{check.title}</h3>
                  <dl>
                    <div>
                      <dt>Status</dt>
                      <dd>{check.status}</dd>
                    </div>
                    <div>
                      <dt>Required</dt>
                      <dd>{check.required ? "yes" : "no"}</dd>
                    </div>
                  </dl>
                  <p>{check.message}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}

      {securityComplianceReport && (
        <Panel title="Security and Compliance">
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{securityComplianceReport.status}</dd>
            </div>
            <div>
              <dt>Passed</dt>
              <dd>{securityComplianceReport.passed ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Blocking</dt>
              <dd>{securityComplianceReport.blocking ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>Risk</dt>
              <dd>{securityComplianceReport.risk_level}</dd>
            </div>
            <div>
              <dt>Enforcement</dt>
              <dd>{securityComplianceReport.enforcement_enabled ? "enabled" : "advisory"}</dd>
            </div>
            <div>
              <dt>Regulated context</dt>
              <dd>{securityComplianceReport.regulated_context ? "yes" : "no"}</dd>
            </div>
          </dl>
          {securityComplianceReport.findings.length > 0 && (
            <>
              <p className="muted">Findings</p>
              <ul className="summary-list">
                {securityComplianceReport.findings.map((finding) => (
                  <li key={`security-compliance-finding-${finding}`}>
                    <span>{finding}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {securityComplianceReport.recommendations.length > 0 && (
            <>
              <p className="muted">Recommendations</p>
              <ul className="summary-list">
                {securityComplianceReport.recommendations.map((recommendation) => (
                  <li key={`security-compliance-recommendation-${recommendation}`}>
                    <span>{recommendation}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <ul className="card-list">
            {[...securityComplianceReport.security.checks, ...securityComplianceReport.compliance.checks].map((check) => (
              <li key={check.check_id} className="info-card">
                <h3>{check.title}</h3>
                <dl>
                  <div>
                    <dt>Status</dt>
                    <dd>{check.status}</dd>
                  </div>
                  <div>
                    <dt>Required</dt>
                    <dd>{check.required ? "yes" : "no"}</dd>
                  </div>
                </dl>
                <p>{check.message}</p>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {(dependencyInventory || dependencyClassificationReport || dependencyAbsorptionReport) && (
        <Panel title="Dependency Absorption">
          {dependencyInventory && (
            <dl>
              <div>
                <dt>Dependencies</dt>
                <dd>{dependencyInventory.dependency_count}</dd>
              </div>
              <div>
                <dt>Sources</dt>
                <dd>
                  {dependencyInventory.sources.length > 0
                    ? dependencyInventory.sources.join(", ")
                    : "none"}
                </dd>
              </div>
              <div>
                <dt>Inventory</dt>
                <dd>{dependencyInventory.inventory_id}</dd>
              </div>
            </dl>
          )}
          {dependencyAbsorptionReport && (
            <>
              <dl>
                <div>
                  <dt>Status</dt>
                  <dd>{dependencyAbsorptionReport.status}</dd>
                </div>
                <div>
                  <dt>Blocking</dt>
                  <dd>{dependencyAbsorptionReport.blocking ? "yes" : "no"}</dd>
                </div>
                <div>
                  <dt>Safety blocks</dt>
                  <dd>{dependencyAbsorptionReport.safety_block_count}</dd>
                </div>
                <div>
                  <dt>Modified output</dt>
                  <dd>{dependencyAbsorptionReport.modified_output_created ? "yes" : "no"}</dd>
                </div>
                <div>
                  <dt>Equivalence</dt>
                  <dd>{dependencyAbsorptionReport.equivalence_passed ? "passed" : "gated"}</dd>
                </div>
                <div>
                  <dt>Security</dt>
                  <dd>
                    {dependencyAbsorptionReport.security_compliance_passed
                      ? "passed"
                      : "gated"}
                  </dd>
                </div>
              </dl>
              {dependencyAbsorptionReport.recommendations.length > 0 && (
                <>
                  <p className="muted">Recommendations</p>
                  <ul className="summary-list">
                    {dependencyAbsorptionReport.recommendations.map((recommendation) => (
                      <li key={`dependency-recommendation-${recommendation}`}>
                        <span>{recommendation}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
          {dependencyClassificationReport &&
            dependencyClassificationReport.classifications.length > 0 && (
              <ul className="card-list">
                {dependencyClassificationReport.classifications.map((dependency) => (
                  <li key={dependency.dependency_id} className="info-card">
                    <h3>{dependency.name}</h3>
                    <dl>
                      <div>
                        <dt>Decision</dt>
                        <dd>{dependency.decision}</dd>
                      </div>
                      <div>
                        <dt>Risk</dt>
                        <dd>{dependency.risk_level}</dd>
                      </div>
                      <div>
                        <dt>Safety block</dt>
                        <dd>{dependency.safety_blocked ? "yes" : "no"}</dd>
                      </div>
                      <div>
                        <dt>Blocking</dt>
                        <dd>{dependency.blocking ? "yes" : "no"}</dd>
                      </div>
                    </dl>
                    <p>{dependency.rationale}</p>
                    {dependency.source_refs.length > 0 && (
                      <p className="muted">{dependency.source_refs.join(", ")}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          {dependencyAbsorptionReport &&
            dependencyAbsorptionReport.planned_replacements.length > 0 && (
              <>
                <p className="muted">Planned replacements</p>
                <ul className="summary-list">
                  {dependencyAbsorptionReport.planned_replacements.map((plan) => (
                    <li key={`dependency-plan-${plan.dependency_id}`}>
                      <strong>{plan.name}</strong>
                      <span>{plan.status}</span>
                      {plan.blocked_by.length > 0 && (
                        <span className="muted">Gated by {plan.blocked_by.join(", ")}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
          {depabsExecution && (
            <>
              <p className="muted">DEPABS execution</p>
              <dl>
                <div>
                  <dt>Status</dt>
                  <dd>{depabsExecution.status}</dd>
                </div>
                <div>
                  <dt>Absorbed</dt>
                  <dd>{depabsExecution.absorption_count}</dd>
                </div>
              </dl>
              {depabsExecution.splices.length > 0 && (
                <ul className="summary-list">
                  {depabsExecution.splices.map((splice) => (
                    <li key={`depabs-splice-${splice.library}-${splice.status}`}>
                      <strong>{splice.library}</strong>
                      <span>{splice.status}</span>
                      {splice.reason && <span className="muted">{splice.reason}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          {sbomDelta && (
            <>
              <p className="muted">SBOM delta</p>
              <dl>
                <div>
                  <dt>Reduction</dt>
                  <dd>{sbomDelta.reduction_percent}%</dd>
                </div>
                <div>
                  <dt>Original</dt>
                  <dd>{sbomDelta.original_dependency_count}</dd>
                </div>
                <div>
                  <dt>Removed</dt>
                  <dd>{sbomDelta.removed.length ? sbomDelta.removed.join(", ") : "none"}</dd>
                </div>
                <div>
                  <dt>Remaining</dt>
                  <dd>
                    {sbomDelta.remaining.length ? sbomDelta.remaining.join(", ") : "none"}
                  </dd>
                </div>
              </dl>
            </>
          )}
          {dependencySurvivalJustifications.length > 0 && (
            <>
              <p className="muted">Survival justifications</p>
              <ul className="summary-list">
                {dependencySurvivalJustifications.slice(0, 12).map((justification) => (
                  <li key={justification.justification_id}>
                    <strong>{justification.name}</strong>
                    <span>{justification.decision}</span>
                    <span className="muted">{justification.rationale}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
      )}

      {(testdataManifest || runtimeQcReport) && (
        <Panel title="Runtime QC">
          {runtimeQcReport && (
            <>
              <dl>
                <div>
                  <dt>Execution</dt>
                  <dd>{runtimeQcReport.verdict}</dd>
                </div>
                <div>
                  <dt>QC verdict</dt>
                  <dd>{runtimeQcReport.qc_assessment?.qc_verdict ?? "pending"}</dd>
                </div>
                <div>
                  <dt>Execution type</dt>
                  <dd>{runtimeQcReport.execution_type}</dd>
                </div>
                <div>
                  <dt>Deployment safe</dt>
                  <dd>{runtimeQcReport.qc_assessment?.deployment_safe ? "yes" : "no"}</dd>
                </div>
              </dl>
              {runtimeQcReport.stdout_preview && (
                <pre className="code-preview">{runtimeQcReport.stdout_preview}</pre>
              )}
              {(runtimeQcReport.qc_assessment?.findings ?? []).length > 0 && (
                <ul className="summary-list">
                  {runtimeQcReport.qc_assessment?.findings.map((finding) => (
                    <li key={`runtime-qc-finding-${finding}`}>
                      <span>{finding}</span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          {testdataManifest && (
            <>
              <p className="muted">Test environment</p>
              <dl>
                <div>
                  <dt>Base image</dt>
                  <dd>{testdataManifest.base_image}</dd>
                </div>
                <div>
                  <dt>Framework</dt>
                  <dd>{testdataManifest.test_framework}</dd>
                </div>
                <div>
                  <dt>Run command</dt>
                  <dd>{testdataManifest.run_command}</dd>
                </div>
                <div>
                  <dt>Limits</dt>
                  <dd>
                    {testdataManifest.timeout_seconds}s / {testdataManifest.memory_limit_mb}MB
                  </dd>
                </div>
                <div>
                  <dt>Synthetic inputs</dt>
                  <dd>{testdataManifest.synthetic_inputs.length}</dd>
                </div>
              </dl>
            </>
          )}
        </Panel>
      )}

      <Panel title="Audit Evidence">
        {auditReports.length === 0 && (
          <p className="muted">No audit reports recorded for this mission yet.</p>
        )}
        {auditReports.length > 0 && (
          <ul className="card-list">
            {auditReports.map((report) => {
              const summary =
                typeof report.report.summary === "string"
                  ? report.report.summary
                  : null;
              const findings =
                Array.isArray(report.report.findings) ? report.report.findings : [];
              const score =
                typeof report.report.score === "number" ? report.report.score : null;
              return (
                <li key={report.audit_id} className="info-card">
                  <h3>{report.audit_id}</h3>
                  <dl>
                    <div>
                      <dt>Status</dt>
                      <dd>
                        <span
                          className={`connection-chip ${
                            report.status === "PASSED"
                              ? "live"
                              : report.status === "FAILED"
                                ? "stale"
                                : "retrying"
                          }`}
                        >
                          {report.status}
                        </span>
                      </dd>
                    </div>
                    {score !== null && (
                      <div>
                        <dt>Score</dt>
                        <dd>{score}</dd>
                      </div>
                    )}
                    <div>
                      <dt>Recorded</dt>
                      <dd>{formatDateTime(report.created_at)}</dd>
                    </div>
                  </dl>
                  {summary && <p>{summary}</p>}
                  {findings.length > 0 && (
                    <>
                      <p className="muted">Findings</p>
                      <ul className="summary-list">
                        {(findings as unknown[]).slice(0, 10).map((finding, idx) => (
                          <li key={`${report.audit_id}-finding-${idx}`}>
                            <span>{typeof finding === "string" ? finding : JSON.stringify(finding)}</span>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Panel>

      <Panel title="Mission Event Log">
        {events.length === 0 && <p className="muted">No mission events recorded yet.</p>}
        {events.length > 0 && (
          <ul className="summary-list">
            {events.slice(0, 25).map((event) => {
              const eventPhaseLabel = smeltPhaseFromEventType(
                event.event_type,
                phaseDescriptor.model,
              );
              return (
                <li key={`${event.event_type}-${event.ts}`}>
                  <strong>{formatTime(event.ts)}</strong>
                  <span>
                    {eventPhaseLabel ? `${event.event_type} · ${eventPhaseLabel}` : event.event_type}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
