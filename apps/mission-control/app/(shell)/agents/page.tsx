"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, StatusBadge, SystemMessage } from "../../components/status";
import {
  getOperationsAgents,
  missionStateStreamUrl,
  parseLiveStateStreamMessage,
} from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { useLastRefreshed } from "../../lib/use-last-refreshed";
import type { AgentRuntimeClass, OperationsAgentRecord, OperationsAgentsSnapshot } from "../../lib/types";

const POLL_INTERVAL_MS = 2000;
const STREAM_REFRESH_DEBOUNCE_MS = 500;
const AGENT_TABLE_HEIGHT_PX = 440;
const AGENT_TABLE_ROW_HEIGHT_PX = 46;
const AGENT_TABLE_OVERSCAN_ROWS = 8;
const AGENT_LOG_HEIGHT_PX = 280;
const AGENT_LOG_ROW_HEIGHT_PX = 54;
const AGENT_LOG_OVERSCAN_ROWS = 8;
const MAX_AGENT_LOG_ENTRIES = 2500;

type AgentLogLevel = "INFO" | "WARNING" | "ERROR";

type AgentLogEntry = {
  id: string;
  ts: string;
  agentId: string;
  level: AgentLogLevel;
  eventType: string;
  message: string;
};

function mapAgentStateToLevel(agent: OperationsAgentRecord): AgentLogLevel {
  if (agent.state === "ERROR") {
    return "ERROR";
  }
  if (agent.queue_depth >= 5 || agent.workload_pct >= 85) {
    return "WARNING";
  }
  return "INFO";
}

function inferEventLevel(eventType: string): AgentLogLevel {
  const normalized = eventType.toUpperCase();
  if (normalized.includes("ERROR") || normalized.includes("FAILED")) {
    return "ERROR";
  }
  if (normalized.includes("WARN") || normalized.includes("PAUSED")) {
    return "WARNING";
  }
  return "INFO";
}

export default function AgentsPage() {
  const [viewMode, setViewMode] = useState<"runtime" | "conceptual">("runtime");
  const [tierFilter, setTierFilter] = useState<string>("ALL");
  const [podFilter, setPodFilter] = useState<string>("ALL");
  const [stateFilter, setStateFilter] = useState<string>("ALL");
  const [snapshot, setSnapshot] = useState<OperationsAgentsSnapshot | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<OperationsAgentRecord | null>(null);
  const [logLevel, setLogLevel] = useState<"ALL" | "INFO" | "WARNING" | "ERROR">("ALL");
  const [agentLogs, setAgentLogs] = useState<AgentLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastSnapshotAt, setLastSnapshotAt] = useState<string | null>(null);
  const [transportMode, setTransportMode] = useState<"stream" | "poll">("poll");
  const [streamEventsSeen, setStreamEventsSeen] = useState(0);
  const [streamErrors, setStreamErrors] = useState(0);
  const [pollFallbackTicks, setPollFallbackTicks] = useState(0);
  const [agentTableScrollTop, setAgentTableScrollTop] = useState(0);
  const [agentLogScrollTop, setAgentLogScrollTop] = useState(0);
  const lastStreamRefreshRef = useRef(0);
  const lastSnapshotLabel = useLastRefreshed(lastSnapshotAt);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await getOperationsAgents({
        missionLimit: 2000,
        assignmentLimit: 2000,
        eventLimit: 500,
      });
      setSnapshot(data);
      setLastSnapshotAt(new Date().toISOString());
      const generatedAt = data.generated_at;
      const heartbeatLogs: AgentLogEntry[] = data.agents.map((agent) => ({
        id: `heartbeat-${generatedAt}-${agent.agent_id}`,
        ts: generatedAt,
        agentId: agent.agent_id,
        level: mapAgentStateToLevel(agent),
        eventType: "AGENT_HEARTBEAT",
        message: `state=${agent.state} queue=${agent.queue_depth} workload=${agent.workload_pct}%`,
      }));
      setAgentLogs((current) => [...heartbeatLogs, ...current].slice(0, MAX_AGENT_LOG_ENTRIES));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load agent telemetry.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const startPollingFallback = () => {
      setTransportMode("poll");
      void load();
      const intervalId = window.setInterval(() => {
        setPollFallbackTicks((count) => count + 1);
        void load();
      }, POLL_INTERVAL_MS);
      return () => window.clearInterval(intervalId);
    };

    if (typeof window === "undefined" || typeof window.EventSource === "undefined") {
      return startPollingFallback();
    }

    const eventSource = new EventSource(
      missionStateStreamUrl({
        includeAgentEvents: true,
      }),
    );
    let closeFallback: (() => void) | null = null;
    let streamOpen = false;

    eventSource.onopen = () => {
      streamOpen = true;
      setTransportMode("stream");
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
      const eventType = parsed.event_type.toUpperCase();
      if (!eventType.startsWith("AGENT_") && !eventType.startsWith("MISSION_")) {
        return;
      }
      setStreamEventsSeen((count) => count + 1);
      const payload = parsed.payload;
      const payloadAgentId =
        typeof payload.agent_id === "string"
          ? payload.agent_id
          : typeof payload.assigned_agent_id === "string"
            ? payload.assigned_agent_id
            : "system";
      const payloadMessage =
        typeof payload.message === "string"
          ? payload.message
          : `${eventType.toLowerCase()} observed via live state stream.`;
      setAgentLogs((current) =>
        [
          {
            id: `stream-${parsed.stream_id}`,
            ts: parsed.created_at ?? new Date().toISOString(),
            agentId: payloadAgentId,
            level: inferEventLevel(eventType),
            eventType,
            message: payloadMessage,
          },
          ...current,
        ].slice(0, MAX_AGENT_LOG_ENTRIES),
      );
      const now = Date.now();
      if ((now - lastStreamRefreshRef.current) < STREAM_REFRESH_DEBOUNCE_MS) {
        return;
      }
      lastStreamRefreshRef.current = now;
      void load();
    });

    return () => {
      eventSource.close();
      if (closeFallback) {
        closeFallback();
      }
    };
  }, [load]);

  useEffect(() => {
    setAgentLogScrollTop(0);
  }, [selectedAgent?.agent_id, logLevel]);

  const agents = snapshot?.agents ?? [];

  const tiers = useMemo(() => {
    const discovered = new Set<string>();
    agents.forEach((item) => discovered.add(item.tier));
    return ["ALL", ...Array.from(discovered).sort()];
  }, [agents]);

  const pods = useMemo(() => {
    const discovered = new Set<string>();
    agents.forEach((item) => discovered.add(item.pod));
    return ["ALL", ...Array.from(discovered).sort()];
  }, [agents]);

  const states = useMemo(() => {
    const discovered = new Set<string>();
    agents.forEach((item) => discovered.add(item.state));
    return ["ALL", ...Array.from(discovered).sort()];
  }, [agents]);

  const filteredAgents = useMemo(
    () =>
      agents.filter((agent) => {
        if (viewMode === "runtime") {
          // Active Runtime: show only agents with confirmed live heartbeats.
          // Use heartbeat_source when available; fall back to runtime_class.
          const src = agent.heartbeat_source;
          if (src != null) {
            if (src !== "live") return false;
          } else if (agent.runtime_class !== "shared_worker") {
            return false;
          }
        }
        if (tierFilter !== "ALL" && agent.tier !== tierFilter) {
          return false;
        }
        if (podFilter !== "ALL" && agent.pod !== podFilter) {
          return false;
        }
        if (stateFilter !== "ALL" && agent.state !== stateFilter) {
          return false;
        }
        return true;
      }),
    [agents, viewMode, tierFilter, podFilter, stateFilter],
  );

  const virtualizedAgents = useMemo(() => {
    const totalRows = filteredAgents.length;
    if (totalRows === 0) {
      return {
        rows: [] as OperationsAgentRecord[],
        topSpacerHeight: 0,
        bottomSpacerHeight: 0,
      };
    }

    const visibleRows = Math.ceil(AGENT_TABLE_HEIGHT_PX / AGENT_TABLE_ROW_HEIGHT_PX);
    const startIndexRaw = Math.max(
      0,
      Math.floor(agentTableScrollTop / AGENT_TABLE_ROW_HEIGHT_PX) - AGENT_TABLE_OVERSCAN_ROWS,
    );
    const startIndex = Math.min(totalRows - 1, startIndexRaw);
    const endExclusive = Math.min(totalRows, startIndex + visibleRows + AGENT_TABLE_OVERSCAN_ROWS * 2);
    return {
      rows: filteredAgents.slice(startIndex, endExclusive),
      topSpacerHeight: startIndex * AGENT_TABLE_ROW_HEIGHT_PX,
      bottomSpacerHeight: Math.max(0, (totalRows - endExclusive) * AGENT_TABLE_ROW_HEIGHT_PX),
    };
  }, [filteredAgents, agentTableScrollTop]);

  const selectedAgentLogs = useMemo(() => {
    if (!selectedAgent) {
      return [] as AgentLogEntry[];
    }
    const scoped = agentLogs.filter((entry) => entry.agentId === selectedAgent.agent_id);
    return scoped.filter((entry) => (logLevel === "ALL" ? true : entry.level === logLevel));
  }, [agentLogs, selectedAgent, logLevel]);

  const visibleAgentLogs = useMemo(() => {
    if (!selectedAgent) {
      return [] as AgentLogEntry[];
    }
    if (selectedAgentLogs.length > 0) {
      return selectedAgentLogs;
    }
    return [
      {
        id: `fallback-selected-${selectedAgent.agent_id}`,
        ts: new Date().toISOString(),
        agentId: selectedAgent.agent_id,
        level: "INFO" as AgentLogLevel,
        eventType: "AGENT_SELECTED",
        message: "Agent selected for inspection.",
      },
      {
        id: `fallback-assignments-${selectedAgent.agent_id}`,
        ts: new Date().toISOString(),
        agentId: selectedAgent.agent_id,
        level: "INFO" as AgentLogLevel,
        eventType: "AGENT_ASSIGNMENTS",
        message: `Mission assignments: ${selectedAgent.active_mission_ids.join(", ") || "none"}`,
      },
      {
        id: `fallback-specialties-${selectedAgent.agent_id}`,
        ts: new Date().toISOString(),
        agentId: selectedAgent.agent_id,
        level: "INFO" as AgentLogLevel,
        eventType: "AGENT_SPECIALTIES",
        message: `Specialty scope: ${selectedAgent.specialties.join(", ")}`,
      },
    ];
  }, [selectedAgent, selectedAgentLogs]);

  const virtualizedAgentLogs = useMemo(() => {
    const totalRows = visibleAgentLogs.length;
    if (totalRows === 0) {
      return {
        rows: [] as AgentLogEntry[],
        topSpacerHeight: 0,
        bottomSpacerHeight: 0,
      };
    }
    const visibleRows = Math.ceil(AGENT_LOG_HEIGHT_PX / AGENT_LOG_ROW_HEIGHT_PX);
    const startIndexRaw = Math.max(
      0,
      Math.floor(agentLogScrollTop / AGENT_LOG_ROW_HEIGHT_PX) - AGENT_LOG_OVERSCAN_ROWS,
    );
    const startIndex = Math.min(totalRows - 1, startIndexRaw);
    const endExclusive = Math.min(totalRows, startIndex + visibleRows + AGENT_LOG_OVERSCAN_ROWS * 2);
    return {
      rows: visibleAgentLogs.slice(startIndex, endExclusive),
      topSpacerHeight: startIndex * AGENT_LOG_ROW_HEIGHT_PX,
      bottomSpacerHeight: Math.max(0, (totalRows - endExclusive) * AGENT_LOG_ROW_HEIGHT_PX),
    };
  }, [visibleAgentLogs, agentLogScrollTop]);

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Agents"
        title="Agent Runtime Control Grid"
        description="Track the active agent topology, runtime health, and mission workload distribution."
      />

      <Panel title="Filters">
        <div className="inline-actions" style={{ marginBottom: "0.75rem" }}>
          <span className="muted">View mode</span>
          <button
            type="button"
            className={`secondary-button ${viewMode === "runtime" ? "active-tab" : ""}`}
            onClick={() => setViewMode("runtime")}
            title="Show only agents with confirmed live heartbeats"
          >
            Active Runtime
          </button>
          <button
            type="button"
            className={`secondary-button ${viewMode === "conceptual" ? "active-tab" : ""}`}
            onClick={() => setViewMode("conceptual")}
            title="Show full agent registry including synthesized and stale entries"
          >
            Conceptual Architecture
          </button>
        </div>
        <div className="filters-grid">
          <label>
            Tier
            <select value={tierFilter} onChange={(event) => setTierFilter(event.target.value)}>
              {tiers.map((tier) => (
                <option key={tier} value={tier}>
                  {tier === "ALL" ? "All tiers" : tier}
                </option>
              ))}
            </select>
          </label>
          <label>
            Pod
            <select value={podFilter} onChange={(event) => setPodFilter(event.target.value)}>
              {pods.map((pod) => (
                <option key={pod} value={pod}>
                  {pod === "ALL" ? "All pods" : pod}
                </option>
              ))}
            </select>
          </label>
          <label>
            State
            <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
              {states.map((state) => (
                <option key={state} value={state}>
                  {state === "ALL" ? "All states" : state}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Panel>

      <Panel title="Runtime Dependencies">
        {error && (
          <SystemMessage
            tone="critical"
            title="Agent telemetry is unavailable"
            action={
              <Link href="/settings" className="secondary-button shell-link-button">
                Configure in Settings →
              </Link>
            }
          >
            {error} Ensure the backend gateway is running and API keys are configured.
          </SystemMessage>
        )}
        {!error && snapshot && (
          <div role="alert" aria-live="polite">
            {!snapshot.runtime.consumer_running && (
              <p className="warning-box">
                Consumer task is not running — mission intake is paused. New missions will not be processed until the consumer restarts.
              </p>
            )}
            {!snapshot.runtime.protocol_ready && (
              <p className="warning-box">
                Protocol validation is unavailable — mission envelope validation is disabled.
              </p>
            )}
            {!snapshot.runtime.redis_ready && (
              <p className="warning-box">
                Redis is unavailable — event streaming and state bus features are degraded.
              </p>
            )}
            {!snapshot.runtime.db_ready && (
              <p className="error-box">
                Database is unavailable — all mission operations are blocked.
              </p>
            )}
            {snapshot.runtime.langgraph_enabled === false && (
              <p className="warning-box">
                LangGraph is disabled (LANGGRAPH_ENABLED=false) — Mission Flow V2 remains the default runtime path while legacy stays available only as a compatibility fallback.
              </p>
            )}
          </div>
        )}
        {!error && (
          <ul className="summary-list">
            <li>
              <strong>Redis</strong>
              <StatusBadge tone={snapshot?.runtime.redis_ready ? "healthy" : "critical"}>
                {snapshot?.runtime.redis_ready ? "Healthy" : "Unavailable"}
              </StatusBadge>
            </li>
            <li>
              <strong>Database</strong>
              <StatusBadge tone={snapshot?.runtime.db_ready ? "healthy" : "critical"}>
                {snapshot?.runtime.db_ready ? "Ready" : "Unavailable"}
              </StatusBadge>
            </li>
            <li>
              <strong>Protocol validation</strong>
              <StatusBadge tone={snapshot?.runtime.protocol_ready ? "healthy" : "warning"}>
                {snapshot?.runtime.protocol_ready ? "Ready" : "Unavailable"}
              </StatusBadge>
            </li>
            <li>
              <strong>Consumer task</strong>
              <StatusBadge tone={snapshot?.runtime.consumer_running ? "healthy" : "warning"}>
                {snapshot?.runtime.consumer_running ? "Running" : "Not running"}
              </StatusBadge>
            </li>
            <li>
              <strong>Topology mode</strong>
              <StatusBadge tone={snapshot?.topology_mode === "full-dedicated" ? "healthy" : snapshot?.topology_mode === "dedicated" ? "warning" : "neutral"}>
                {snapshot?.topology_mode ?? "condensed"}
              </StatusBadge>
            </li>
            <li>
              <strong>Transport mode</strong>
              <StatusBadge tone={transportMode === "stream" ? "healthy" : "warning"}>
                {transportMode}
              </StatusBadge>
            </li>
            <li>
              <strong>Stream events</strong>
              <span>{streamEventsSeen}</span>
            </li>
            <li>
              <strong>Stream errors</strong>
              <span>{streamErrors > 0 ? streamErrors : "—"}</span>
            </li>
            <li>
              <strong>Poll fallback ticks</strong>
              <span>{pollFallbackTicks > 0 ? pollFallbackTicks : "—"}</span>
            </li>
          </ul>
        )}
      </Panel>

      {/* Suppress snapshot + distribution panels entirely when telemetry is unavailable */}
      {!error && <Panel title="Agent and Mission Snapshot">
        {loading && <p className="muted">Loading pod workload summary...</p>}
        {!loading && snapshot && (
          <ul className="summary-list">
            <li>
              <strong>Total agents</strong>
              <span>{snapshot.total_agents}</span>
            </li>
            <li>
              <strong>Active missions</strong>
              <span>{snapshot.mission_backlog.active}</span>
            </li>
            <li>
              <strong>Verified missions</strong>
              <span>{snapshot.mission_backlog.verified}</span>
            </li>
            <li>
              <strong>Completed missions</strong>
              <span>{snapshot.mission_backlog.complete}</span>
            </li>
          </ul>
        )}
      </Panel>}

      {!error && <Panel title="State Distribution">
        {!loading && snapshot && (
          <ul className="summary-list">
            {Object.entries(snapshot.state_counts).map(([state, count]) => (
              <li key={state}>
                <strong>{state}</strong>
                <span>{count} agent(s)</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>}

      <Panel
        title="Agent Grid"
        actions={lastSnapshotLabel ? <span className="last-refreshed">{lastSnapshotLabel}</span> : undefined}
      >
        <p className="muted">
          Showing {filteredAgents.length} of {agents.length} agents. Windowed rows: {virtualizedAgents.rows.length}.
          Last snapshot: {snapshot ? formatDateTime(snapshot.generated_at) : "n/a"}.
        </p>
        <div
          className="table-wrap virtualized-table-wrap"
          tabIndex={0}
          aria-label="Scrollable agent roster"
          style={{ maxHeight: `${AGENT_TABLE_HEIGHT_PX}px` }}
          onScroll={(event) => setAgentTableScrollTop(event.currentTarget.scrollTop)}
        >
          <table className="data-table">
            <caption className="sr-only">
              Full agent roster with state, queue depth, workload, and specialization.
            </caption>
            <thead>
              <tr>
                <th scope="col">Agent</th>
                <th scope="col">Tier</th>
                <th scope="col">Pod</th>
                <th scope="col">State</th>
                <th scope="col">Queue</th>
                <th scope="col">Workload</th>
                <th scope="col">Specialties</th>
                <th scope="col">Runtime</th>
                <th scope="col">Last heartbeat</th>
              </tr>
            </thead>
            <tbody>
              {virtualizedAgents.topSpacerHeight > 0 && (
                <tr className="virtual-spacer" aria-hidden="true">
                  <td colSpan={9} style={{ height: `${virtualizedAgents.topSpacerHeight}px` }} />
                </tr>
              )}
              {virtualizedAgents.rows.map((agent) => (
                <AgentRow
                  key={agent.agent_id}
                  agent={agent}
                  onSelect={() => setSelectedAgent(agent)}
                  rowClassName="virtualized-row"
                />
              ))}
              {virtualizedAgents.bottomSpacerHeight > 0 && (
                <tr className="virtual-spacer" aria-hidden="true">
                  <td colSpan={9} style={{ height: `${virtualizedAgents.bottomSpacerHeight}px` }} />
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {filteredAgents.length === 0 && !loading && agents.length === 0 && (
          <EmptyState
            title="No runtime agents available"
            action={
              <Link href="/settings" className="secondary-button shell-link-button">
                Check Settings
              </Link>
            }
          >
            Ensure the backend gateway is running and reachable, then verify the API base URL.
          </EmptyState>
        )}
        {filteredAgents.length === 0 && !loading && agents.length > 0 && (
          <EmptyState title="No agents match these filters" compact>
            Try switching to Conceptual Architecture or clearing tier, pod, and state filters.
          </EmptyState>
        )}
      </Panel>

      <Panel title="Pod Topology">
        {!loading && snapshot && (
          <ul className="summary-list">
            {Object.entries(snapshot.pod_counts).map(([pod, count]) => (
              <li key={pod}>
                <strong>{pod}</strong>
                <span>{count} agent(s)</span>
              </li>
            ))}
            {Object.keys(snapshot.pod_counts).length === 0 && (
              <li>
                <strong>No pod topology</strong>
                <span>Agent topology data is currently unavailable.</span>
              </li>
            )}
          </ul>
        )}
      </Panel>

      {selectedAgent && (
        <Panel
          title={`Agent Detail - ${selectedAgent.agent_id}`}
          actions={
            <button type="button" className="secondary-button" onClick={() => setSelectedAgent(null)}>
              Close
            </button>
          }
        >
          <dl>
            <div>
              <dt>Name</dt>
              <dd>{selectedAgent.name}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>{selectedAgent.role}</dd>
            </div>
            <div>
              <dt>Pod</dt>
              <dd>{selectedAgent.pod}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{selectedAgent.state}</dd>
            </div>
            <div>
              <dt>Queue Depth</dt>
              <dd>{selectedAgent.queue_depth}</dd>
            </div>
            <div>
              <dt>Workload</dt>
              <dd>{selectedAgent.workload_pct}%</dd>
            </div>
            <div>
              <dt>Last Heartbeat</dt>
              <dd>{formatDateTime(selectedAgent.last_heartbeat_iso)}</dd>
            </div>
          </dl>
          <div className="inline-actions">
            <span className="muted">Log Level</span>
            <button
              type="button"
              className={`secondary-button ${logLevel === "ALL" ? "active-tab" : ""}`}
              onClick={() => setLogLevel("ALL")}
            >
              All
            </button>
            <button
              type="button"
              className={`secondary-button ${logLevel === "INFO" ? "active-tab" : ""}`}
              onClick={() => setLogLevel("INFO")}
            >
              Info
            </button>
            <button
              type="button"
              className={`secondary-button ${logLevel === "WARNING" ? "active-tab" : ""}`}
              onClick={() => setLogLevel("WARNING")}
            >
              Warning
            </button>
            <button
              type="button"
              className={`secondary-button ${logLevel === "ERROR" ? "active-tab" : ""}`}
              onClick={() => setLogLevel("ERROR")}
            >
              Error
            </button>
          </div>
          <p className="muted">
            Rendering {virtualizedAgentLogs.rows.length} of {visibleAgentLogs.length} log entries (windowed).
          </p>
          <div
            className="virtual-log-shell"
            style={{ maxHeight: `${AGENT_LOG_HEIGHT_PX}px` }}
            onScroll={(event) => setAgentLogScrollTop(event.currentTarget.scrollTop)}
          >
            <ul className="virtual-log-list">
              {virtualizedAgentLogs.topSpacerHeight > 0 && (
                <li
                  className="virtual-log-spacer"
                  aria-hidden="true"
                  style={{ height: `${virtualizedAgentLogs.topSpacerHeight}px` }}
                />
              )}
              {virtualizedAgentLogs.rows.map((entry) => (
                <li key={entry.id} className={`virtual-log-item level-${entry.level.toLowerCase()}`}>
                  <div className="virtual-log-meta">
                    <strong>{formatDateTime(entry.ts)}</strong>
                    <span>{entry.level}</span>
                    <span>{entry.eventType}</span>
                  </div>
                  <p>{entry.message}</p>
                </li>
              ))}
              {virtualizedAgentLogs.bottomSpacerHeight > 0 && (
                <li
                  className="virtual-log-spacer"
                  aria-hidden="true"
                  style={{ height: `${virtualizedAgentLogs.bottomSpacerHeight}px` }}
                />
              )}
            </ul>
          </div>
          <h3 className="section-title">8-Part Persona Profile</h3>
          <dl>
            <div>
              <dt>Job Title</dt>
              <dd>{selectedAgent.persona_profile.job_role.title}</dd>
            </div>
            <div>
              <dt>Scope</dt>
              <dd>{selectedAgent.persona_profile.job_role.scope}</dd>
            </div>
            <div>
              <dt>Primary Protocol</dt>
              <dd>
                {selectedAgent.persona_profile.protocol.primary_code} (
                {selectedAgent.persona_profile.protocol.primary_name})
              </dd>
            </div>
            <div>
              <dt>Model Routing</dt>
              <dd>
                {String(selectedAgent.persona_profile.api_configuration.model_routing.provider)}/
                {String(selectedAgent.persona_profile.api_configuration.model_routing.model)}
              </dd>
            </div>
          </dl>
          <h4 className="section-title">Education & Certifications</h4>
          <ul className="summary-list">
            {selectedAgent.persona_profile.education_certifications.map((item) => (
              <li key={item}>
                <strong>Item</strong>
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <h4 className="section-title">Traits & Skills</h4>
          <ul className="summary-list">
            {selectedAgent.persona_profile.traits_skills.map((item) => (
              <li key={item}>
                <strong>Item</strong>
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <h4 className="section-title">Methods & Procedures</h4>
          <ul className="summary-list">
            {selectedAgent.persona_profile.methods_procedures.map((item) => (
              <li key={item}>
                <strong>Method</strong>
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <h4 className="section-title">Tools</h4>
          <ul className="summary-list">
            {selectedAgent.persona_profile.tools.map((item) => (
              <li key={item}>
                <strong>Tool</strong>
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <h4 className="section-title">Master Instruction</h4>
          <p className="muted">{selectedAgent.persona_profile.master_instruction}</p>
          <h4 className="section-title">Standards Alignment</h4>
          <ul className="summary-list">
            {selectedAgent.persona_profile.standards_alignment.map((item) => (
              <li key={item.standard_id}>
                <strong>
                  {item.framework} ({item.version})
                </strong>
                <span>{item.role_mapping}</span>
              </li>
            ))}
          </ul>
          <h4 className="section-title">Evidence Sources</h4>
          <ul className="summary-list">
            {selectedAgent.persona_profile.evidence_sources.map((source) => (
              <li key={source.source_id}>
                <strong>{source.organization}</strong>
                <span>
                  <a href={source.url} target="_blank" rel="noreferrer noopener">
                    {source.title}
                  </a>{" "}
                  ({source.version}) - verified {formatDateTime(source.last_verified)}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

const RUNTIME_CLASS_LABELS: Record<AgentRuntimeClass, string> = {
  shared_worker: "Worker",
  synthesized_heartbeat: "Managed",
};

const RUNTIME_CLASS_CHIP_CLASS: Record<AgentRuntimeClass, string> = {
  shared_worker: "live",
  synthesized_heartbeat: "idle",
};

function AgentRow({
  agent,
  onSelect,
  rowClassName,
}: {
  agent: OperationsAgentRecord;
  onSelect: () => void;
  rowClassName?: string;
}) {
  const stateClass = agent.state.toLowerCase();
  const specialties = agent.specialties.length > 0 ? agent.specialties.join(", ") : "n/a";
  const runtimeClass = agent.runtime_class ?? "synthesized_heartbeat";
  return (
    <tr className={rowClassName}>
      <td>
        <button type="button" className="link-button" onClick={onSelect}>
          <strong>{agent.name}</strong>
          <div className="muted">{agent.agent_id}</div>
        </button>
      </td>
      <td>{agent.tier}</td>
      <td>{agent.pod}</td>
      <td>
        <span className={`status-dot ${stateClass}`} aria-hidden="true" />
        {agent.state}
      </td>
      <td>{agent.queue_depth}</td>
      <td>{agent.workload_pct}%</td>
      <td title={specialties}>{specialties}</td>
      <td>
        <span
          className={`connection-chip ${RUNTIME_CLASS_CHIP_CLASS[runtimeClass as AgentRuntimeClass] ?? "stale"}`}
          title={`runtime_class=${runtimeClass}${agent.heartbeat_source ? ` heartbeat_source=${agent.heartbeat_source}` : ""}`}
        >
          {RUNTIME_CLASS_LABELS[runtimeClass as AgentRuntimeClass] ?? runtimeClass}
          {agent.heartbeat_source && agent.heartbeat_source !== "live" && (
            <span style={{ marginLeft: "0.25em", opacity: 0.75 }}>({agent.heartbeat_source})</span>
          )}
        </span>
      </td>
      <td>{formatDateTime(agent.last_heartbeat_iso)}</td>
    </tr>
  );
}
