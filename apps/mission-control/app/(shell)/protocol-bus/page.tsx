"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { OperatorAuthErrorAction } from "../../components/operator-auth-error-action";
import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, StatusBadge, SystemMessage } from "../../components/status";
import {
  listOperationsEvents,
  missionStateStreamUrl,
  parseLiveStateStreamMessage,
} from "../../lib/api-client";
import { downloadJson } from "../../lib/export";
import { formatDateTime } from "../../lib/format";
import { operatorRecoveryMessage } from "../../lib/operator-auth-error";
import type { BusEventRecord, LiveStateStreamEvent, MissionEvent } from "../../lib/types";

const SPARKLINE_BUCKETS = 60; // 60 one-second buckets = 60s rolling window
const SPARKLINE_W = 200;
const SPARKLINE_H = 40;

/** 5E — SVG sparkline showing events/sec over the last 60 seconds. */
function BusSparkline({ events }: { events: BusEventRecord[] }) {
  const buckets = useMemo(() => {
    const now = Date.now();
    const counts = new Array<number>(SPARKLINE_BUCKETS).fill(0);
    for (const ev of events) {
      const age = Math.floor((now - new Date(ev.ts).getTime()) / 1000);
      if (age >= 0 && age < SPARKLINE_BUCKETS) {
        counts[SPARKLINE_BUCKETS - 1 - age]++;
      }
    }
    return counts;
  }, [events]);

  const max = Math.max(...buckets, 1);
  const points = buckets
    .map((count, i) => {
      const x = (i / (SPARKLINE_BUCKETS - 1)) * SPARKLINE_W;
      const y = SPARKLINE_H - (count / max) * SPARKLINE_H;
      return `${x},${y}`;
    })
    .join(" ");

  const messagesPerSecond = useMemo(() => {
    if (events.length === 0) return 0;
    const now = Date.now();
    const recent = events.filter(
      (ev) => now - new Date(ev.ts).getTime() <= 10_000,
    ).length;
    return Math.round((recent / 10) * 10) / 10;
  }, [events]);

  return (
    <div className="bus-sparkline-wrap">
      <div className="bus-rate-label" aria-label={`${messagesPerSecond} messages per second`}>
        {messagesPerSecond}
        <span className="bus-rate-unit"> msg/s</span>
      </div>
      <svg
        className="bus-sparkline-svg"
        width={SPARKLINE_W}
        height={SPARKLINE_H}
        viewBox={`0 0 ${SPARKLINE_W} ${SPARKLINE_H}`}
        aria-hidden="true"
        role="presentation"
      >
        <polyline
          points={points}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          opacity="0.85"
        />
        {/* Fill area under line */}
        <polyline
          points={`0,${SPARKLINE_H} ${points} ${SPARKLINE_W},${SPARKLINE_H}`}
          fill="var(--accent)"
          fillOpacity="0.12"
          stroke="none"
        />
      </svg>
      <p className="bus-sparkline-label muted">60s window</p>
    </div>
  );
}

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

function mapLiveStreamToBusRecord(event: LiveStateStreamEvent): BusEventRecord | null {
  const eventType = event.event_type.trim();
  if (!eventType) {
    return null;
  }
  const missionId = event.mission_id ?? "unknown-mission";
  const state = (event.state ?? "").toUpperCase();
  return {
    id: `${event.stream_id}-${eventType}`,
    ts: event.created_at ?? new Date().toISOString(),
    protocol: deriveProtocol(eventType),
    producer: event.producer ?? "orchestrator",
    consumer: eventType.startsWith("AGENT_") ? "operations-grid" : "mission-workers",
    message_type: eventType,
    topic: event.topic ?? `mission.state.${state.toLowerCase()}`,
    summary: `${missionId}: ${eventType}`,
    priority: state === "FAILED" ? "HIGH" : "NORMAL",
    payload: event.payload,
  };
}

const REFRESH_MS = 2000;
const STREAM_REFRESH_DEBOUNCE_MS = 500;
const EVENT_TABLE_HEIGHT_PX = 440;
const EVENT_ROW_HEIGHT_PX = 44;
const EVENT_OVERSCAN_ROWS = 8;

export default function ProtocolBusPage() {
  const [events, setEvents] = useState<BusEventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState(true);
  const [transportMode, setTransportMode] = useState<"stream" | "poll" | "paused">("poll");
  const [streamEventsSeen, setStreamEventsSeen] = useState(0);
  const [streamErrors, setStreamErrors] = useState(0);
  const [pollFallbackTicks, setPollFallbackTicks] = useState(0);
  const [protocolFilter, setProtocolFilter] = useState<
    "ALL" | "ALPHA" | "BETA" | "DELTA" | "SIGMA" | "OMEGA" | "RHO"
  >(
    "ALL",
  );
  const [query, setQuery] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<BusEventRecord | null>(null);
  const [eventTableScrollTop, setEventTableScrollTop] = useState(0);
  const lastPollRefreshRef = useRef(0);

  const loadEvents = useCallback(async () => {
    try {
      const operationEvents = await listOperationsEvents(600);
      const mapped = operationEvents
        .map((event, index) => mapEventToBusRecord(event, index))
        .sort((left, right) => new Date(right.ts).getTime() - new Date(left.ts).getTime())
        .slice(0, 1000);
      setEvents(mapped);
      setError(null);
    } catch (loadError) {
      const rawMessage =
        loadError instanceof Error ? loadError.message : "Unable to load protocol bus events.";
      setError(operatorRecoveryMessage(rawMessage));
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    const toggleLive = () => setIsLive((current) => !current);
    window.addEventListener("protocol-bus-toggle-live", toggleLive);
    return () => {
      window.removeEventListener("protocol-bus-toggle-live", toggleLive);
    };
  }, []);

  useEffect(() => {
    if (!isLive) {
      setTransportMode("paused");
      return;
    }

    const startPollingFallback = () => {
      setTransportMode("poll");
      void loadEvents();
      const intervalId = window.setInterval(() => {
        setPollFallbackTicks((count) => count + 1);
        void loadEvents();
      }, REFRESH_MS);
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
      const mapped = mapLiveStreamToBusRecord(parsed);
      if (!mapped) {
        return;
      }
      setStreamEventsSeen((count) => count + 1);
      setEvents((current) => [mapped, ...current].slice(0, 1000));
      const now = Date.now();
      if ((now - lastPollRefreshRef.current) < STREAM_REFRESH_DEBOUNCE_MS) {
        return;
      }
      lastPollRefreshRef.current = now;
      // Keep metadata consistent with server truth while stream is active.
      void loadEvents();
    });

    return () => {
      eventSource.close();
      if (closeFallback) {
        closeFallback();
      }
    };
  }, [isLive, loadEvents]);

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

  const virtualizedEvents = useMemo(() => {
    const totalRows = filteredEvents.length;
    if (totalRows === 0) {
      return {
        rows: [] as BusEventRecord[],
        startIndex: 0,
        topSpacerHeight: 0,
        bottomSpacerHeight: 0,
      };
    }

    const visibleRows = Math.ceil(EVENT_TABLE_HEIGHT_PX / EVENT_ROW_HEIGHT_PX);
    const startIndexRaw = Math.max(
      0,
      Math.floor(eventTableScrollTop / EVENT_ROW_HEIGHT_PX) - EVENT_OVERSCAN_ROWS,
    );
    const startIndex = Math.min(totalRows - 1, startIndexRaw);
    const endExclusive = Math.min(totalRows, startIndex + visibleRows + EVENT_OVERSCAN_ROWS * 2);
    return {
      rows: filteredEvents.slice(startIndex, endExclusive),
      startIndex,
      topSpacerHeight: startIndex * EVENT_ROW_HEIGHT_PX,
      bottomSpacerHeight: Math.max(0, (totalRows - endExclusive) * EVENT_ROW_HEIGHT_PX),
    };
  }, [filteredEvents, eventTableScrollTop]);

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Protocol Bus"
        title="Protocol Event Monitor"
        description="Inspect envelope traffic by protocol, topic, producer, and priority to detect routing anomalies."
      />

      <Panel
        title="Stream Filters"
        actions={
          <div className="inline-actions">
            <StatusBadge tone={isLive ? (transportMode === "stream" ? "healthy" : "warning") : "neutral"}>
              {isLive ? `LIVE (${transportMode})` : "PAUSED"}
            </StatusBadge>
            <button type="button" className="secondary-button" onClick={() => setIsLive((current) => !current)}>
              {isLive ? "Pause" : "Resume"}
            </button>
            <button type="button" className="secondary-button" onClick={() => void loadEvents()}>
              Refresh
            </button>
          </div>
        }
      >
        {/* 5E — Sparkline replaces the buried msg/s plain text */}
        <BusSparkline events={events} />
        <p className="help-text">
          Stream events: {streamEventsSeen} • Errors: {streamErrors} • Poll ticks:{" "}
          {pollFallbackTicks}
        </p>
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

      <Panel
        title="Event Stream"
        actions={
          <button
            type="button"
            className="secondary-button"
            disabled={filteredEvents.length === 0}
            onClick={() =>
              downloadJson(
                filteredEvents,
                `protocol-bus-${new Date().toISOString().slice(0, 10)}.json`,
              )
            }
          >
            Export JSON
          </button>
        }
      >
        {loading && <p className="muted">Loading recent protocol bus events...</p>}
        {error && (
          <SystemMessage tone="critical" title="Protocol bus events are unavailable">
            {error} Live events will appear once the runtime stream or polling endpoint is available.
            <OperatorAuthErrorAction error={error} />
          </SystemMessage>
        )}
        <p className="muted">
          Rendering {virtualizedEvents.rows.length} of {filteredEvents.length} rows (windowed).
        </p>
        <div
          className="table-wrap virtualized-table-wrap"
          tabIndex={0}
          aria-label="Scrollable protocol bus event table"
          style={{ maxHeight: `${EVENT_TABLE_HEIGHT_PX}px` }}
          onScroll={(event) => setEventTableScrollTop(event.currentTarget.scrollTop)}
        >
          <table className="data-table">
            <caption className="sr-only">
              Protocol bus event stream including protocol, producer, topic, priority, and summary.
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
              {virtualizedEvents.topSpacerHeight > 0 && (
                <tr className="virtual-spacer" aria-hidden="true">
                  <td colSpan={8} style={{ height: `${virtualizedEvents.topSpacerHeight}px` }} />
                </tr>
              )}
              {virtualizedEvents.rows.map((event) => (
                <tr
                  key={event.id}
                  className="clickable-row virtualized-row"
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedEvent(event)}
                  onKeyDown={(keyEvent) => {
                    if (keyEvent.key === "Enter" || keyEvent.key === " ") {
                      keyEvent.preventDefault();
                      setSelectedEvent(event);
                    }
                  }}
                >
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
              {virtualizedEvents.bottomSpacerHeight > 0 && (
                <tr className="virtual-spacer" aria-hidden="true">
                  <td colSpan={8} style={{ height: `${virtualizedEvents.bottomSpacerHeight}px` }} />
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {filteredEvents.length === 0 && (
          <EmptyState title={error ? "No stream data while runtime is offline" : "No events match the current filters"} compact>
            {error
              ? "The monitor is ready, but the event source has not returned data."
              : "Clear the search or protocol filter to broaden the visible event stream."}
          </EmptyState>
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
