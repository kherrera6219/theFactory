"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../../components/page-header";
import { Panel } from "../../../components/panel";
import {
  getMission,
  getMissionEvents,
  getOperationsAgents,
  listOperationsLogicNodes,
  updateMissionState,
  updateMissionStateWithVault,
} from "../../../lib/api-client";
import { formatDateTime, formatTime, humanizeState, normalizeState } from "../../../lib/format";
import type {
  MissionEvent,
  MissionRecord,
  OperationsAgentRecord,
  OperationsLogicNodeRecord,
} from "../../../lib/types";

const POLL_INTERVAL_MS = 2500;
const SMELT_PHASES = ["INTAKE", "FETCH", "SMELT", "GATING", "FUSION", "SQUEEZE", "DELIVERY"] as const;

function phaseIndexFromState(state: string): number {
  const normalized = normalizeState(state);
  if (normalized === "QUEUED") return 0;
  if (normalized === "RUNNING") return 2;
  if (normalized === "VERIFIED") return 3;
  if (normalized === "COMPLETE" || normalized === "FAILED") return 6;
  return 0;
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

export default function MissionDetailPage() {
  const params = useParams<{ id: string }>();
  const missionId = String(params.id ?? "").trim();

  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [logicNodes, setLogicNodes] = useState<OperationsLogicNodeRecord[]>([]);
  const [activeAgents, setActiveAgents] = useState<OperationsAgentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [pausedMonitor, setPausedMonitor] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  async function loadDetails() {
    if (!missionId) {
      return;
    }
    try {
      const [missionData, missionEvents, nodes, agentSnapshot] = await Promise.all([
        getMission(missionId),
        getMissionEvents(missionId, 60),
        listOperationsLogicNodes({ limit: 400, missionId }),
        getOperationsAgents({ missionLimit: 300, assignmentLimit: 300, eventLimit: 200 }),
      ]);
      setMission(missionData);
      setEvents(missionEvents);
      setLogicNodes(nodes);
      setActiveAgents(agentSnapshot.agents.filter((agent) => isAgentActive(agent, missionId)));
      setError(null);
      setLastUpdatedAt(new Date().toISOString());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load mission details.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setLoading(true);
    void loadDetails();
  }, [missionId]);

  useEffect(() => {
    if (!missionId || pausedMonitor) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void loadDetails();
    }, POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [missionId, pausedMonitor]);

  const phaseIndex = phaseIndexFromState(mission?.state ?? "QUEUED");

  const verifiedCount = useMemo(
    () =>
      logicNodes.filter((node) => {
        const status = node.node.status;
        return typeof status === "string" && normalizeState(status) === "VERIFIED";
      }).length,
    [logicNodes],
  );

  const avgConfidence = useMemo(() => {
    const values = logicNodes.map((node) => nodeConfidence(node)).filter((value): value is number => value !== null);
    if (values.length === 0) {
      return "N/A";
    }
    const average = values.reduce((sum, value) => sum + value, 0) / values.length;
    return `${Math.round(average * 1000) / 10}%`;
  }, [logicNodes]);

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
      try {
        await updateMissionStateWithVault({
          missionId: mission.mission_id,
          newState: "FAILED",
          expectedState: mission.state,
        });
      } catch {
        await updateMissionState({
          missionId: mission.mission_id,
          newState: "FAILED",
          expectedState: mission.state,
        });
      }
      await loadDetails();
    } catch (requestError) {
      setActionError(
        requestError instanceof Error
          ? requestError.message
          : "Mission state update failed. Confirm operator API key in Settings.",
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

      <Panel title="Smelt-Cycle Phase Stepper">
        <ol className="phase-stepper" aria-label="Smelt cycle phases">
          {SMELT_PHASES.map((phase, index) => {
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
                <dt>Created</dt>
                <dd>{formatDateTime(mission.created_at)}</dd>
              </div>
              <div>
                <dt>Target language</dt>
                <dd>{mission.requested_target_language ?? "n/a"}</dd>
              </div>
              <div>
                <dt>Last refresh</dt>
                <dd>{lastUpdatedAt ? formatTime(lastUpdatedAt) : "n/a"}</dd>
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

      <Panel title="Mission Event Log">
        {events.length === 0 && <p className="muted">No mission events recorded yet.</p>}
        {events.length > 0 && (
          <ul className="summary-list">
            {events.slice(0, 25).map((event) => (
              <li key={`${event.event_type}-${event.ts}`}>
                <strong>{formatTime(event.ts)}</strong>
                <span>{event.event_type}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
