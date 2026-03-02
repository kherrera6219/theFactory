"use client";

import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { listOperationsEvents } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import type { BusEventRecord, MissionEvent } from "../../lib/types";

function deriveProtocol(eventType: string): BusEventRecord["protocol"] {
  if (eventType.includes("QUEUED")) {
    return "RHO";
  }
  if (eventType.includes("RUNNING")) {
    return "BETA";
  }
  if (eventType.includes("VERIFIED")) {
    return "DELTA";
  }
  if (eventType.includes("FAILED")) {
    return "OMEGA";
  }
  if (eventType.includes("COMPLETE")) {
    return "SIGMA";
  }
  return "ALPHA";
}

function mapEventToBusRecord(event: MissionEvent, index: number): BusEventRecord {
  const missionId = event.mission_id ?? "unknown-mission";
  const normalizedState = event.new_state.toUpperCase();
  const protocol = deriveProtocol(event.event_type);
  const consumer =
    protocol === "ALPHA" ? "executive-tier" : protocol === "DELTA" ? "audit-ring" : "mission-workers";
  return {
    id: `${missionId}-${event.event_type}-${event.ts}-${index}`,
    ts: event.ts,
    protocol,
    producer: "orchestrator",
    consumer,
    message_type: event.event_type,
    topic: `mission.state.${event.new_state.toLowerCase()}`,
    summary: `${missionId}: ${event.event_type}`,
    priority: normalizedState === "FAILED" ? "HIGH" : "NORMAL",
    payload: {
      mission_id: missionId,
      previous_state: event.previous_state,
      new_state: event.new_state,
      event_type: event.event_type,
      timestamp: event.ts,
    },
  };
}

const REFRESH_MS = 2000;

export default function SemanticBusPage() {
  const [events, setEvents] = useState<BusEventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState(true);
  const [protocolFilter, setProtocolFilter] = useState<
    "ALL" | "ALPHA" | "BETA" | "DELTA" | "SIGMA" | "OMEGA" | "RHO"
  >(
    "ALL",
  );
  const [query, setQuery] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<BusEventRecord | null>(null);

  async function loadEvents() {
    try {
      const operationEvents = await listOperationsEvents(600);
      const mapped = operationEvents
        .map((event, index) => mapEventToBusRecord(event, index))
        .sort((left, right) => new Date(right.ts).getTime() - new Date(left.ts).getTime())
        .slice(0, 1000);
      setEvents(mapped);
      setError(null);
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : "Unable to load semantic bus events.",
      );
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadEvents();
  }, []);

  useEffect(() => {
    const toggleLive = () => setIsLive((current) => !current);
    window.addEventListener("semantic-bus-toggle-live", toggleLive);
    return () => {
      window.removeEventListener("semantic-bus-toggle-live", toggleLive);
    };
  }, []);

  useEffect(() => {
    if (!isLive) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void loadEvents();
    }, REFRESH_MS);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [isLive]);

  const filteredEvents = useMemo(() => {
    const lower = query.trim().toLowerCase();
    return events
      .filter((event) => (protocolFilter === "ALL" ? true : event.protocol === protocolFilter))
      .filter((event) => {
        if (lower.length === 0) {
          return true;
        }
        return (
          event.topic.toLowerCase().includes(lower) ||
          event.summary.toLowerCase().includes(lower) ||
          event.producer.toLowerCase().includes(lower) ||
          (event.consumer?.toLowerCase().includes(lower) ?? false) ||
          (event.message_type?.toLowerCase().includes(lower) ?? false)
        );
      });
  }, [events, protocolFilter, query]);

  const messagesPerSecond = useMemo(() => {
    if (events.length === 0) {
      return 0;
    }
    const newest = new Date(events[0].ts).getTime();
    const recent = events.filter((event) => newest - new Date(event.ts).getTime() <= 10_000).length;
    return Math.round((recent / 10) * 10) / 10;
  }, [events]);

  return (
    <div className="page shell-page">
      <PageHeader
        eyebrow="Semantic Bus"
        title="Protocol Event Monitor"
        description="Inspect envelope traffic by protocol, topic, producer, and priority to detect routing anomalies."
      />

      <Panel
        title="Stream Filters"
        actions={
          <div className="inline-actions">
            <span className={`connection-chip ${isLive ? "live" : "stale"}`}>
              {isLive ? "LIVE" : "PAUSED"}
            </span>
            <button type="button" className="secondary-button" onClick={() => setIsLive((current) => !current)}>
              {isLive ? "Pause" : "Resume"}
            </button>
            <button type="button" className="secondary-button" onClick={() => void loadEvents()}>
              Refresh
            </button>
          </div>
        }
      >
        <p className="help-text">Rate: {messagesPerSecond} msg/s</p>
        <div className="filters-grid">
          <label>
            Protocol
            <select
              value={protocolFilter}
              onChange={(event) =>
                setProtocolFilter(
                  event.target.value as
                    | "ALL"
                    | "ALPHA"
                    | "BETA"
                    | "DELTA"
                    | "SIGMA"
                    | "OMEGA"
                    | "RHO",
                )
              }
            >
              <option value="ALL">All protocols</option>
              <option value="ALPHA">Alpha</option>
              <option value="BETA">Beta</option>
              <option value="DELTA">Delta</option>
              <option value="SIGMA">Sigma</option>
              <option value="OMEGA">Omega</option>
              <option value="RHO">Rho</option>
            </select>
          </label>
          <label>
            Search
            <input
              type="search"
              placeholder="Search by topic, producer, consumer, type, or summary"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
        </div>
      </Panel>

      <Panel title="Event Stream">
        {loading && <p className="muted">Loading recent semantic bus events...</p>}
        {error && <p className="error-box">{error}</p>}
        <div className="table-wrap">
          <table className="data-table">
            <caption className="sr-only">
              Semantic bus event stream including protocol, producer, topic, priority, and summary.
            </caption>
            <thead>
              <tr>
                <th scope="col">Timestamp</th>
                <th scope="col">Protocol</th>
                <th scope="col">Producer</th>
                <th scope="col">Consumer</th>
                <th scope="col">Type</th>
                <th scope="col">Topic</th>
                <th scope="col">Priority</th>
                <th scope="col">Summary</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map((event) => (
                <tr key={event.id} className="clickable-row" onClick={() => setSelectedEvent(event)}>
                  <td>{formatDateTime(event.ts)}</td>
                  <td>{event.protocol}</td>
                  <td>{event.producer}</td>
                  <td>{event.consumer ?? "-"}</td>
                  <td>{event.message_type ?? "-"}</td>
                  <td>{event.topic}</td>
                  <td>{event.priority}</td>
                  <td>{event.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filteredEvents.length === 0 && (
          <p className="muted">No semantic bus events match the current filters.</p>
        )}
      </Panel>

      {selectedEvent && (
        <Panel
          title="Expanded Message Payload"
          actions={
            <button type="button" className="secondary-button" onClick={() => setSelectedEvent(null)}>
              Close
            </button>
          }
        >
          <div className="code-block">
            <pre>{JSON.stringify(selectedEvent.payload ?? {}, null, 2)}</pre>
          </div>
        </Panel>
      )}
    </div>
  );
}
