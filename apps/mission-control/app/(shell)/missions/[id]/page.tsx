"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "../../../components/page-header";
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
  getMissionTokenUsage,
} from "../../../lib/api-client";
import { humanizeState, normalizeState } from "../../../lib/format";
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
  LlmUsageSummary,
} from "../../../lib/types";

// Import all 22 panels from the structured subfolders
import {
  MissionSignalsPanel,
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

export default function MissionDetailPage() {
  const params = useParams<{ id: string }>();
  const missionId = String(params.id ?? "").trim();
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
  const lastStreamRefreshRef = useRef(0);

  const loadDetails = useCallback(async () => {
    if (!missionId) {
      return;
    }
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
      message: "Cancel mission? This operation marks the mission as FAILED in the current backend workflow.",
      confirmText: "Cancel Mission",
      cancelText: "Dismiss",
    });
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
        <ErrorBoundary>
          <MissionSignalsPanel
            loading={loading}
            mission={mission}
            chainTrace={chainTrace}
            lifecycleEngine={lifecycleEngine}
            phaseLabel={phaseLabel}
            phaseName={phaseName}
            lastUpdatedAt={lastUpdatedAt}
            transportMode={transportMode}
            streamEventsSeen={streamEventsSeen}
            streamErrors={streamErrors}
            pollFallbackTicks={pollFallbackTicks}
          />
        </ErrorBoundary>

        <ErrorBoundary>
          <LogicNodeProgressPanel
            missionId={missionId}
            logicNodes={logicNodes}
            verifiedCount={verifiedCount}
            avgConfidence={avgConfidence}
          />
        </ErrorBoundary>

        <ErrorBoundary>
          <CostPanel tokenUsage={tokenUsage} />
        </ErrorBoundary>

        <ErrorBoundary>
          <ChainOfCommandTracePanel chainTrace={chainTrace} />
        </ErrorBoundary>

        <ErrorBoundary>
          <RouteProvenancePanel chainTrace={chainTrace} />
        </ErrorBoundary>

        <ErrorBoundary>
          <PmFeatureContractPanel featureContract={featureContract} />
        </ErrorBoundary>

        <ErrorBoundary>
          <MissionCharterPanel missionCharter={missionCharter as any} />
        </ErrorBoundary>

        <ErrorBoundary>
          <AimPanel applicationIntelligenceMap={applicationIntelligenceMap as any} />
        </ErrorBoundary>

        <ErrorBoundary>
          <MissionContractPanel missionContract={missionContract} />
        </ErrorBoundary>

        <ErrorBoundary>
          <LogicClustersPanel logicClusters={logicClusters} />
        </ErrorBoundary>

        <ErrorBoundary>
          <PodGroupStandardsPanel podGroupStandards={podGroupStandards} />
        </ErrorBoundary>

        <ErrorBoundary>
          <KnowledgeLakePanel fetchResult={fetchResult} />
        </ErrorBoundary>

        <ErrorBoundary>
          <FusionPanel masterLogicStream={masterLogicStream} />
        </ErrorBoundary>

        <ErrorBoundary>
          <ActiveAgentsPanel activeAgents={activeAgents} />
        </ErrorBoundary>

        <ErrorBoundary>
          <GeneratedOutputPanel missionId={missionId} generatedCodeArtifact={generatedCodeArtifact} />
        </ErrorBoundary>

        <ErrorBoundary>
          <DeliveryPanel buildArtifacts={buildArtifacts} />
        </ErrorBoundary>

        <ErrorBoundary>
          <EquivalenceReportPanel equivalenceReport={equivalenceReport} />
        </ErrorBoundary>

        <ErrorBoundary>
          <SecurityCompliancePanel securityComplianceReport={securityComplianceReport as any} />
        </ErrorBoundary>

        <ErrorBoundary>
          <DependencyAbsorptionPanel
            dependencyInventory={dependencyInventory}
            dependencyClassificationReport={dependencyClassificationReport}
            dependencyAbsorptionReport={dependencyAbsorptionReport}
            depabsExecution={depabsExecution}
            sbomDelta={sbomDelta}
            dependencySurvivalJustifications={dependencySurvivalJustifications}
          />
        </ErrorBoundary>

        <ErrorBoundary>
          <RuntimeQcPanel runtimeQcReport={runtimeQcReport} testdataManifest={testdataManifest} />
        </ErrorBoundary>

        <ErrorBoundary>
          <AuditEvidencePanel auditReports={auditReports} />
        </ErrorBoundary>

        <ErrorBoundary>
          <MissionEventLogPanel events={events} model={phaseDescriptor.model} />
        </ErrorBoundary>
      </div>
    </div>
  );
}
