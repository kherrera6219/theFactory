"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { PageHeader } from "../components/page-header";
import { Panel } from "../components/panel";
import { EmptyState, MetricCard, StatusBadge, SystemMessage } from "../components/status";
import { humanizeState, normalizeState } from "../lib/format";
import {
  completionBlockReason,
  isCompletionBlocked,
  missionTitle,
  shortMissionId,
  withoutSystemMissions,
} from "../lib/mission-status";
import { useLastRefreshed } from "../lib/use-last-refreshed";
import {
  getGatewayHealth,
  getGatewayReadyState,
  getOperationsSummary,
  listMissions,
} from "../lib/api-client";
import type { GatewayHealth, MissionRecord, OperationsSummary } from "../lib/types";

const POLL_INTERVAL_MS = 5000;

type MissionCounts = {
  total: number;
  inProgress: number;
  complete: number;
  blocked: number;
  failed: number;
  byState: Array<[string, number]>;
};

/**
 * Counts from the orchestrator summary when available (it already excludes the
 * internal Knowledge Lake missions and lists completion-blocked ones), else from
 * the mission list. "Blocked" is pulled out of VERIFIED: those missions are
 * parked by a completion gate, not passing validation.
 */
function countMissions(summary: OperationsSummary | null, missions: MissionRecord[]): MissionCounts {
  let byStateMap: Map<string, number>;
  let blocked: number;
  if (summary?.mission_state_counts && Object.keys(summary.mission_state_counts).length > 0) {
    byStateMap = new Map(
      Object.entries(summary.mission_state_counts).map(([state, count]) => [normalizeState(state), count]),
    );
    blocked = summary.blocked_mission_ids?.length ?? missions.filter(isCompletionBlocked).length;
  } else {
    byStateMap = new Map();
    for (const mission of missions) {
      const state = normalizeState(mission.state);
      byStateMap.set(state, (byStateMap.get(state) ?? 0) + 1);
    }
    blocked = missions.filter(isCompletionBlocked).length;
  }
  const total = Array.from(byStateMap.values()).reduce((acc, count) => acc + count, 0);
  const complete = byStateMap.get("COMPLETE") ?? 0;
  const failed = byStateMap.get("FAILED") ?? 0;
  if (blocked > 0) {
    const verified = (byStateMap.get("VERIFIED") ?? 0) - blocked;
    if (verified > 0) byStateMap.set("VERIFIED", verified);
    else byStateMap.delete("VERIFIED");
    byStateMap.set("BLOCKED", blocked);
  }
  const byState = Array.from(byStateMap.entries()).sort((left, right) => right[1] - left[1]);
  return {
    total,
    inProgress: Math.max(0, total - complete - failed - blocked),
    complete,
    blocked,
    failed,
    byState,
  };
}

export default function LaunchPad() {
  const [missions, setMissions] = useState<MissionRecord[]>([]);
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [health, setHealth] = useState<GatewayHealth | null>(null);
  const [readyState, setReadyState] = useState<{ ready: boolean; detail?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchAt, setLastFetchAt] = useState<string | null>(null);

  const lastRefreshedLabel = useLastRefreshed(lastFetchAt);

  const counts = useMemo(() => countMissions(summary, missions), [summary, missions]);
  const stateSummary = counts.byState;
  const attentionMissions = useMemo(
    () =>
      missions.filter(
        (mission) => isCompletionBlocked(mission) || normalizeState(mission.state) === "FAILED",
      ),
    [missions],
  );

  const loadData = useCallback(async (isInitial = false) => {
    if (isInitial) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError(null);
    try {
      const [data, summaryData, healthData, ready] = await Promise.all([
        listMissions(50),
        getOperationsSummary().catch(() => null),
        getGatewayHealth().catch(() => null),
        getGatewayReadyState().catch(() => null),
      ]);
      setMissions(withoutSystemMissions(data));
      if (summaryData) {
        setSummary(summaryData);
      }
      setHealth(healthData);
      setReadyState(ready);
      setLastFetchAt(new Date().toISOString());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load mission overview.");
    } finally {
      if (isInitial) {
        setLoading(false);
      } else {
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void loadData(true);

    const interval = window.setInterval(() => {
      if (!cancelled) {
        void loadData(false);
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [loadData]);

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Home"
        title="Launch Pad"
        description="Open mission control and assess system health before launching the next mission."
      />

      <Panel
        title="System Health Snapshot"
        actions={
          <div className="flex items-center gap-2">
            {lastRefreshedLabel ? <span className="last-refreshed">{lastRefreshedLabel}</span> : null}
            <button
              type="button"
              className="ghost-button text-xs"
              onClick={() => void loadData(false)}
              disabled={loading || refreshing}
              aria-label="Refresh dashboard metrics"
            >
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        }
      >
        {error && (
          <SystemMessage
            tone="critical"
            title="Mission metrics are unavailable"
            action={
              <Link href="/settings" className="secondary-button shell-link-button">
                Configure API Keys
              </Link>
            }
          >
            The UI is running, but the local gateway did not return dashboard data. Configure runtime access, then refresh this view.
          </SystemMessage>
        )}
        <div className="kpi-grid" aria-label="Mission metrics">
          <MetricCard
            label="Total Missions"
            value={error ? "—" : counts.total}
            loading={loading}
            tone={error ? "neutral" : "info"}
            detail={error ? "Waiting for runtime" : "Excludes internal Knowledge Lake records"}
          />
          <MetricCard
            label="In Progress"
            value={error ? "—" : counts.inProgress}
            loading={loading}
            tone="warning"
            detail="Moving through the pipeline now"
          />
          <MetricCard
            label="Complete"
            value={error ? "—" : counts.complete}
            loading={loading}
            tone="healthy"
            detail="Delivered"
          />
          <MetricCard
            label="Needs Attention"
            value={error ? "—" : counts.blocked + counts.failed}
            loading={loading}
            tone={counts.blocked + counts.failed > 0 ? "critical" : "neutral"}
            detail={`${counts.blocked} blocked · ${counts.failed} failed`}
          />
        </div>
      </Panel>

      {attentionMissions.length > 0 ? (
        <Panel
          title="Needs Attention"
          description="Missions a completion gate has parked, or that failed. Open one to see its chain trace."
        >
          <ul className="attention-list">
            {attentionMissions.slice(0, 8).map((mission) => {
              const reason = completionBlockReason(mission);
              const failed = normalizeState(mission.state) === "FAILED";
              return (
                <li key={mission.mission_id}>
                  <div className="attention-list-main">
                    <Link href={`/missions/detail?id=${encodeURIComponent(mission.mission_id)}`}>
                      {missionTitle(mission)}
                    </Link>
                    <span className="muted mono-id">{shortMissionId(mission.mission_id)}</span>
                  </div>
                  <p className="attention-list-reason">
                    <StatusBadge tone={failed ? "critical" : "warning"}>
                      {failed ? "Failed" : reason?.gate ?? "Blocked"}
                    </StatusBadge>
                    <span>{failed ? "The mission failed." : reason?.reason}</span>
                  </p>
                </li>
              );
            })}
          </ul>
          {attentionMissions.length > 8 ? (
            <Link href="/missions/history" className="ghost-button shell-link-button">
              View all {attentionMissions.length} in Mission History
            </Link>
          ) : null}
        </Panel>
      ) : null}

      <Panel title="Runtime Health">
        <ul className="summary-list">
          <li>
            <strong>Gateway readiness</strong>
            <StatusBadge
              tone={readyState?.ready ? "healthy" : "critical"}
              label={`Gateway readiness: ${readyState?.ready ? "Ready" : readyState?.detail ?? "Unavailable"}`}
            >
              {readyState?.ready ? "Ready" : readyState?.detail ?? "Unavailable"}
            </StatusBadge>
          </li>
          <li>
            <strong>Redis</strong>
            <StatusBadge tone={health?.redis_healthy ? "healthy" : "critical"} label={`Redis: ${health?.redis_healthy ? "Healthy" : "Unavailable"}`}>
              {health?.redis_healthy ? "Healthy" : "Unavailable"}
            </StatusBadge>
          </li>
          <li>
            <strong>Orchestrator</strong>
            <StatusBadge tone={health?.orchestrator_healthy ? "healthy" : "critical"} label={`Orchestrator: ${health?.orchestrator_healthy ? "Healthy" : "Unavailable"}`}>
              {health?.orchestrator_healthy ? "Healthy" : "Unavailable"}
            </StatusBadge>
          </li>
        </ul>
      </Panel>

      <Panel title="Top Mission States">
        {stateSummary.length === 0 && (
          <EmptyState
            title={error ? "Mission state data is offline" : "No mission state data yet"}
            action={
              error ? (
                <Link href="/settings" className="secondary-button shell-link-button">
                  Start Runtime First
                </Link>
              ) : (
                <Link href="/chat" className="secondary-button shell-link-button">
                  Launch Mission
                </Link>
              )
            }
            variant={error ? "offline" : "empty"}
          >
            {error
              ? "State charts will populate when the local runtime can return mission telemetry."
              : "Launch a mission to populate state distribution, progress, and operational history."}
          </EmptyState>
        )}
        {stateSummary.length > 0 && (
          <ul className="summary-list">
            {stateSummary.map(([state, count]) => (
              <li key={state}>
                <strong>{humanizeState(state)}</strong>
                <span>{count} mission(s)</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Operational Shortcuts">
        <div className="shortcut-grid">
          <Link href="/chat" className="shortcut-card">
            <h3>PM Agent Chat</h3>
            <p>Describe mission goals in natural language and launch directly.</p>
          </Link>
          <Link href="/agents" className="shortcut-card">
            <h3>Agent Grid</h3>
            <p>Inspect pod health, workload distribution, and stalled workers.</p>
          </Link>
          <Link href="/protocol-bus" className="shortcut-card">
            <h3>Protocol Bus</h3>
            <p>Trace live protocol messages and identify delivery bottlenecks.</p>
          </Link>
          <Link href="/repo" className="shortcut-card">
            <h3>Repo Import</h3>
            <p>Import a repository, scope files, and launch a targeted mission.</p>
          </Link>
        </div>
      </Panel>
    </div>
  );
}
