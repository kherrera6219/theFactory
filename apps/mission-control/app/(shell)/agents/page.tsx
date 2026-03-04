"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import {
  getOperationsAgents,
  missionStateStreamUrl,
  parseLiveStateStreamMessage,
} from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import type { OperationsAgentRecord, OperationsAgentsSnapshot } from "../../lib/types";

const POLL_INTERVAL_MS = 2000;
const STREAM_REFRESH_DEBOUNCE_MS = 500;

export default function AgentsPage() {
  const [tierFilter, setTierFilter] = useState<string>("ALL");
  const [podFilter, setPodFilter] = useState<string>("ALL");
  const [stateFilter, setStateFilter] = useState<string>("ALL");
  const [snapshot, setSnapshot] = useState<OperationsAgentsSnapshot | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<OperationsAgentRecord | null>(null);
  const [logLevel, setLogLevel] = useState<"ALL" | "INFO" | "WARNING" | "ERROR">("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transportMode, setTransportMode] = useState<"stream" | "poll">("poll");
  const [streamEventsSeen, setStreamEventsSeen] = useState(0);
  const [streamErrors, setStreamErrors] = useState(0);
  const [pollFallbackTicks, setPollFallbackTicks] = useState(0);
  const lastStreamRefreshRef = useRef(0);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await getOperationsAgents({
        missionLimit: 2000,
        assignmentLimit: 2000,
        eventLimit: 500,
      });
      setSnapshot(data);
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
    [agents, tierFilter, podFilter, stateFilter],
  );

  return (
    <div className="page shell-page">
      <PageHeader
        eyebrow="Agents"
        title="35-Agent Runtime Control Grid"
        description="Track the full multi-agent topology, runtime health, and mission workload distribution."
      />

      <Panel title="Filters">
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
        {error && <p className="error-box">{error}</p>}
        {!error && (
          <ul className="summary-list">
            <li>
              <strong>Redis</strong>
              <span>{snapshot?.runtime.redis_ready ? "Healthy" : "Unavailable"}</span>
            </li>
            <li>
              <strong>Database</strong>
              <span>{snapshot?.runtime.db_ready ? "Ready" : "Unavailable"}</span>
            </li>
            <li>
              <strong>Protocol validation</strong>
              <span>{snapshot?.runtime.protocol_ready ? "Ready" : "Unavailable"}</span>
            </li>
            <li>
              <strong>Consumer task</strong>
              <span>{snapshot?.runtime.consumer_running ? "Running" : "Not running"}</span>
            </li>
            <li>
              <strong>Transport mode</strong>
              <span>{transportMode}</span>
            </li>
            <li>
              <strong>Stream events</strong>
              <span>{streamEventsSeen}</span>
            </li>
            <li>
              <strong>Stream errors</strong>
              <span>{streamErrors}</span>
            </li>
            <li>
              <strong>Poll fallback ticks</strong>
              <span>{pollFallbackTicks}</span>
            </li>
          </ul>
        )}
      </Panel>

      <Panel title="Agent and Mission Snapshot">
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
      </Panel>

      <Panel title="State Distribution">
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
      </Panel>

      <Panel title="Agent Grid">
        <p className="muted">
          Showing {filteredAgents.length} of {agents.length} agents. Last refresh:{" "}
          {snapshot ? formatDateTime(snapshot.generated_at) : "n/a"}.
        </p>
        <div className="table-wrap">
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
                <th scope="col">Last heartbeat</th>
              </tr>
            </thead>
            <tbody>
              {filteredAgents.map((agent) => (
                <AgentRow key={agent.agent_id} agent={agent} onSelect={() => setSelectedAgent(agent)} />
              ))}
            </tbody>
          </table>
        </div>
        {filteredAgents.length === 0 && !loading && (
          <p className="muted">No agents match the selected filters.</p>
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
          <div className="code-block">
            <pre>
              {[
                `${formatDateTime(new Date().toISOString())} [INFO] Agent selected for inspection`,
                `${formatDateTime(new Date().toISOString())} [INFO] Mission assignments: ${
                  selectedAgent.active_mission_ids.join(", ") || "none"
                }`,
                `${formatDateTime(new Date().toISOString())} [INFO] Specialty scope: ${selectedAgent.specialties.join(", ")}`,
              ].join("\n")}
            </pre>
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

function AgentRow({
  agent,
  onSelect,
}: {
  agent: OperationsAgentRecord;
  onSelect: () => void;
}) {
  const stateClass = agent.state.toLowerCase();
  const specialties = agent.specialties.length > 0 ? agent.specialties.join(", ") : "n/a";
  return (
    <tr>
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
      <td>{formatDateTime(agent.last_heartbeat_iso)}</td>
    </tr>
  );
}
