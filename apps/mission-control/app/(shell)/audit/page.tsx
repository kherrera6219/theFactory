"use client";

import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, SystemMessage } from "../../components/status";
import { useLastRefreshed } from "../../lib/use-last-refreshed";
import { listMissions, listOperationsAlerts, listOperationsEvents } from "../../lib/api-client";
import { downloadCsv, downloadJson } from "../../lib/export";
import { formatDateTime, humanizeState } from "../../lib/format";
import type { MissionRecord, OperationsAlertRecord, MissionEvent } from "../../lib/types";

type AuditEntry = {
  id: string;
  ts: string;
  category: "mission" | "alert" | "event";
  severity: "info" | "warning" | "critical";
  title: string;
  detail: string;
  source: string;
};

function missionToEntry(m: MissionRecord): AuditEntry {
  const state = m.state.toUpperCase();
  const sev: AuditEntry["severity"] =
    state === "FAILED" || state === "CANCELLED" ? "critical"
    : state === "RUNNING" || state === "QUEUED" ? "warning"
    : "info";
  const name = String((m.metadata as Record<string, unknown> | undefined)?.name ?? "");
  return {
    id: `mission-${m.mission_id}`,
    ts: m.created_at,
    category: "mission",
    severity: sev,
    title: name ? `Mission: ${name}` : `Mission ${m.mission_id.slice(0, 8)}…`,
    detail: humanizeState(m.state),
    source: "mission-service",
  };
}

function alertToEntry(a: OperationsAlertRecord): AuditEntry {
  const sev: AuditEntry["severity"] =
    a.severity === "critical" || a.severity === "high" ? "critical"
    : a.severity === "medium" ? "warning"
    : "info";
  return {
    id: `alert-${a.alert_id}`,
    ts: a.created_at,
    category: "alert",
    severity: sev,
    title: a.title,
    detail: `${a.state} · ${a.source}`,
    source: a.source,
  };
}

function eventToEntry(ev: MissionEvent, index: number): AuditEntry {
  const sev: AuditEntry["severity"] =
    ev.new_state.toUpperCase() === "FAILED" ? "critical"
    : ev.new_state.toUpperCase() === "RUNNING" ? "warning"
    : "info";
  return {
    id: `event-${ev.mission_id ?? "sys"}-${ev.ts}-${index}`,
    ts: ev.ts,
    category: "event",
    severity: sev,
    title: ev.event_type,
    detail: `${humanizeState(ev.previous_state ?? "—")} → ${humanizeState(ev.new_state)}`,
    source: ev.mission_id ?? "system",
  };
}

const CATEGORY_LABELS = [
  { value: "ALL", label: "All" },
  { value: "mission", label: "Missions" },
  { value: "alert", label: "Alerts" },
  { value: "event", label: "Events" },
] as const;

type CategoryFilter = (typeof CATEGORY_LABELS)[number]["value"];

const PAGE_SIZE = 30;

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchAt, setLastFetchAt] = useState<string | null>(null);
  const [category, setCategory] = useState<CategoryFilter>("ALL");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const lastRefreshedLabel = useLastRefreshed(lastFetchAt);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [missions, alerts, events] = await Promise.allSettled([
        listMissions(50),
        listOperationsAlerts(50),
        listOperationsEvents(100),
      ]);

      const missionEntries =
        missions.status === "fulfilled" ? missions.value.map(missionToEntry) : [];
      const alertEntries =
        alerts.status === "fulfilled" ? alerts.value.map(alertToEntry) : [];
      const eventEntries =
        events.status === "fulfilled"
          ? events.value.map((ev, i) => eventToEntry(ev, i))
          : [];

      const all = [...missionEntries, ...alertEntries, ...eventEntries].sort(
        (a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime(),
      );

      if (all.length === 0) {
        setError(
          missions.status === "rejected" &&
          alerts.status === "rejected" &&
          events.status === "rejected"
            ? "All audit data sources are unavailable. Start the local runtime to populate this log."
            : null,
        );
      }

      setEntries(all);
      setLastFetchAt(new Date().toISOString());
      setPage(0);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load audit log.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return entries.filter((e) => {
      if (category !== "ALL" && e.category !== category) return false;
      if (!q) return true;
      return (
        e.title.toLowerCase().includes(q) ||
        e.detail.toLowerCase().includes(q) ||
        e.source.toLowerCase().includes(q)
      );
    });
  }, [entries, category, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const visible = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  function handleCategory(cat: CategoryFilter) {
    setCategory(cat);
    setPage(0);
  }

  function handleSearch(q: string) {
    setSearch(q);
    setPage(0);
  }

  function exportAsCsv() {
    downloadCsv(
      filtered.map((e) => ({
        timestamp: e.ts,
        category: e.category,
        severity: e.severity,
        title: e.title,
        detail: e.detail,
        source: e.source,
      })),
      `audit-log-${new Date().toISOString().slice(0, 10)}`,
    );
  }

  function exportAsJson() {
    downloadJson(filtered, `audit-log-${new Date().toISOString().slice(0, 10)}`);
  }

  const severityIcon: Record<AuditEntry["severity"], string> = {
    critical: "✕",
    warning: "!",
    info: "·",
  };

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Configuration"
        title="Audit &amp; Activity Log"
        description="Chronological activity log aggregating mission state changes, system alerts, and protocol bus events."
      />

      <Panel
        title="Activity Log"
        actions={
          <>
            {lastRefreshedLabel && (
              <span className="last-refreshed">{lastRefreshedLabel}</span>
            )}
            <button
              type="button"
              className="secondary-button"
              onClick={() => void load()}
              disabled={loading}
            >
              {loading ? "Loading…" : "Refresh"}
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={filtered.length === 0}
              onClick={exportAsCsv}
            >
              CSV
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={filtered.length === 0}
              onClick={exportAsJson}
            >
              JSON
            </button>
          </>
        }
      >
        {/* Filters */}
        <div className="history-filters">
          <div className="inline-actions">
            {CATEGORY_LABELS.map((cat) => (
              <button
                key={cat.value}
                type="button"
                className={`secondary-button${category === cat.value ? " active-tab" : ""}`}
                onClick={() => handleCategory(cat.value)}
              >
                {cat.label}
              </button>
            ))}
          </div>
          <input
            type="search"
            className="table-search"
            placeholder="Search by title, detail, or source…"
            value={search}
            aria-label="Search audit log"
            onChange={(e) => handleSearch(e.target.value)}
          />
        </div>

        {error && (
          <SystemMessage tone="critical" title="Audit data unavailable">
            {error}
          </SystemMessage>
        )}

        {/* Loading skeletons */}
        {loading && (
          <ul aria-label="Loading audit entries">
            {Array.from({ length: 5 }, (_, i) => (
              <li key={`skel-${i}`} className="audit-entry-skeleton">
                <span className="skeleton-line" style={{ width: "60%" }} />
                <span className="skeleton-line" style={{ width: "40%", marginTop: "6px" }} />
              </li>
            ))}
          </ul>
        )}

        {!loading && filtered.length === 0 && (
          <EmptyState
            title={entries.length === 0 ? "No audit entries yet" : "No entries match these filters"}
            compact
          >
            {entries.length === 0
              ? "Start the local runtime to begin collecting mission events, alerts, and system activity."
              : "Adjust the category filter or clear the search field."}
          </EmptyState>
        )}

        {!loading && visible.length > 0 && (
          <>
            <p className="muted history-count">
              Showing {safePage * PAGE_SIZE + 1}–
              {Math.min(safePage * PAGE_SIZE + PAGE_SIZE, filtered.length)} of {filtered.length} entries
            </p>
            <ol className="audit-log-list" aria-label="Audit entries">
              {visible.map((entry) => (
                <li key={entry.id} className={`audit-entry audit-${entry.severity}`}>
                  <div className="audit-entry-header">
                    <span
                      className={`audit-sev-marker sev-${entry.severity}`}
                      aria-label={entry.severity}
                    >
                      {severityIcon[entry.severity]}
                    </span>
                    <span className="audit-entry-title">{entry.title}</span>
                    <span className="audit-entry-category muted">{entry.category}</span>
                    <time className="audit-entry-ts muted" dateTime={entry.ts}>
                      {formatDateTime(entry.ts)}
                    </time>
                  </div>
                  <p className="audit-entry-detail muted">{entry.detail}</p>
                </li>
              ))}
            </ol>

            {totalPages > 1 && (
              <div className="pagination-bar">
                <button
                  type="button"
                  className="secondary-button"
                  disabled={safePage === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  ← Prev
                </button>
                <span className="muted">
                  Page {safePage + 1} of {totalPages}
                </span>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={safePage >= totalPages - 1}
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </Panel>
    </div>
  );
}
