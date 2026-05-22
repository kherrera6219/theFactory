"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { CopyId } from "../../../components/copy-id";
import { PageHeader } from "../../../components/page-header";
import { Panel } from "../../../components/panel";
import { EmptyState, SystemMessage } from "../../../components/status";
import { useLastRefreshed } from "../../../lib/use-last-refreshed";
import { listMissions } from "../../../lib/api-client";
import { formatDateTime, humanizeState, isTerminalState } from "../../../lib/format";
import type { MissionRecord } from "../../../lib/types";

const HISTORY_LIMIT = 200;
const PAGE_SIZE = 25;

const STATE_GROUPS = [
  { label: "All", value: "ALL" },
  { label: "Active", value: "ACTIVE" },
  { label: "Completed", value: "VERIFIED" },
  { label: "Failed", value: "FAILED" },
  { label: "Cancelled", value: "CANCELLED" },
] as const;

type StateGroupValue = (typeof STATE_GROUPS)[number]["value"];

function matchesGroup(mission: MissionRecord, group: StateGroupValue): boolean {
  if (group === "ALL") return true;
  const state = mission.state.toUpperCase();
  if (group === "ACTIVE") return !isTerminalState(state);
  return state === group || state.startsWith(group);
}

export default function MissionHistoryPage() {
  const [missions, setMissions] = useState<MissionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchAt, setLastFetchAt] = useState<string | null>(null);
  const [stateGroup, setStateGroup] = useState<StateGroupValue>("ALL");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const lastRefreshedLabel = useLastRefreshed(lastFetchAt);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await listMissions(HISTORY_LIMIT);
      setMissions(data);
      setLastFetchAt(new Date().toISOString());
      setPage(0);
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : "Unable to load mission history.",
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
    return missions.filter((m) => {
      if (!matchesGroup(m, stateGroup)) return false;
      if (!q) return true;
      const name = String((m.metadata as Record<string, unknown> | undefined)?.name ?? "").toLowerCase();
      return m.mission_id.toLowerCase().includes(q) || name.includes(q) || m.state.toLowerCase().includes(q);
    });
  }, [missions, stateGroup, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const visibleMissions = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  function handleGroupChange(group: StateGroupValue) {
    setStateGroup(group);
    setPage(0);
  }

  function handleSearchChange(value: string) {
    setSearch(value);
    setPage(0);
  }

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Missions"
        title="Mission History"
        description="Browse the full mission archive with state filtering, text search, and direct links to live mission detail."
        actions={
          <Link href="/missions" className="secondary-button shell-link-button">
            ← Back to Intake
          </Link>
        }
      />

      <Panel
        title="Mission Archive"
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
          </>
        }
      >
        {/* Filters */}
        <div className="history-filters">
          <div className="inline-actions">
            {STATE_GROUPS.map((g) => (
              <button
                key={g.value}
                type="button"
                className={`secondary-button${stateGroup === g.value ? " active-tab" : ""}`}
                onClick={() => handleGroupChange(g.value)}
              >
                {g.label}
              </button>
            ))}
          </div>
          <input
            type="search"
            className="table-search"
            placeholder="Search by ID, name, or state…"
            value={search}
            aria-label="Search missions"
            onChange={(e) => handleSearchChange(e.target.value)}
          />
        </div>

        {/* Error */}
        {error && (
          <SystemMessage tone="critical" title="Mission history unavailable">
            {error} Start the local runtime and refresh, or check API key configuration in Settings.
          </SystemMessage>
        )}

        {/* Loading skeletons */}
        {loading && (
          <ul className="mission-list" aria-label="Loading mission history">
            {Array.from({ length: 6 }, (_, i) => (
              <li key={`skeleton-${i}`}>
                <div className="mission-item">
                  <div className="mission-item-skeleton-main" aria-hidden="true">
                    <span className="skeleton-line skeleton-mission-id" />
                    <span className="skeleton-line skeleton-mission-meta" />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}

        {/* Empty */}
        {!loading && !error && filtered.length === 0 && missions.length === 0 && (
          <EmptyState title="No missions in the archive yet">
            Launch a mission from the Intake page or the PM Agent Chat to populate mission history.
          </EmptyState>
        )}
        {!loading && !error && filtered.length === 0 && missions.length > 0 && (
          <EmptyState title="No missions match these filters" compact>
            Try a different state group or clear the search field.
          </EmptyState>
        )}

        {/* Mission list */}
        {!loading && visibleMissions.length > 0 && (
          <>
            <p className="muted history-count">
              Showing {safePage * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE + PAGE_SIZE, filtered.length)} of {filtered.length}{" "}
              {stateGroup === "ALL" ? "" : `${stateGroup.toLowerCase()} `}mission{filtered.length !== 1 ? "s" : ""}
            </p>
            <div className="table-wrap">
              <table className="data-table">
                <caption className="sr-only">Mission archive with state, type, depth, and creation date</caption>
                <thead>
                  <tr>
                    <th scope="col">Mission ID</th>
                    <th scope="col">Name</th>
                    <th scope="col">State</th>
                    <th scope="col">Type</th>
                    <th scope="col">Depth</th>
                    <th scope="col">Created</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleMissions.map((m) => {
                    const name = String(
                      (m.metadata as Record<string, unknown> | undefined)?.name ?? "",
                    );
                    const stateClass = m.state.toLowerCase().replace(/_/g, "-");
                    return (
                      <tr key={m.mission_id}>
                        <td>
                          <CopyId
                            id={m.mission_id}
                            display={m.mission_id.slice(0, 8) + "…"}
                          />
                        </td>
                        <td className="muted">{name || "—"}</td>
                        <td>
                          <span className={`status-dot ${stateClass}`} aria-hidden="true" />
                          {humanizeState(m.state)}
                        </td>
                        <td className="muted">{m.mission_type ?? "—"}</td>
                        <td className="muted">{m.depth_mode ?? "—"}</td>
                        <td className="muted">{formatDateTime(m.created_at)}</td>
                        <td>
                          <Link
                            href={`/missions/${m.mission_id}`}
                            className="secondary-button shell-link-button"
                          >
                            View Live
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
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
