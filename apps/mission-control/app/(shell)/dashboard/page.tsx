"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, MetricCard, StatusBadge, SystemMessage } from "../../components/status";
import { humanizeState } from "../../lib/format";
import { useLastRefreshed } from "../../lib/use-last-refreshed";
import { getGatewayHealth, getGatewayReadyState, listMissions } from "../../lib/api-client";
import type { GatewayHealth, MissionRecord } from "../../lib/types";

function summarizeStates(missions: MissionRecord[]) {
  const summary = new Map<string, number>();
  for (const mission of missions) {
    const state = mission.state.toUpperCase();
    summary.set(state, (summary.get(state) ?? 0) + 1);
  }
  return Array.from(summary.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, 4);
}

export default function DashboardPage() {
  const [missions, setMissions] = useState<MissionRecord[]>([]);
  const [health, setHealth] = useState<GatewayHealth | null>(null);
  const [readyState, setReadyState] = useState<{ ready: boolean; detail?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchAt, setLastFetchAt] = useState<string | null>(null);

  const lastRefreshedLabel = useLastRefreshed(lastFetchAt);
  const stateSummary = useMemo(() => summarizeStates(missions), [missions]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [data, healthData, ready] = await Promise.all([
          listMissions(30),
          getGatewayHealth(),
          getGatewayReadyState(),
        ]);
        if (!cancelled) {
          setMissions(data);
          setHealth(healthData);
          setReadyState(ready);
          setLastFetchAt(new Date().toISOString());
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load mission overview.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

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
        actions={lastRefreshedLabel ? <span className="last-refreshed">{lastRefreshedLabel}</span> : undefined}
      >
        {error && (
          <SystemMessage tone="critical" title="Mission metrics are unavailable">
            The UI is running, but the local gateway did not return dashboard data. Add API keys and start the runtime before the live-data review.
          </SystemMessage>
        )}
        <div className="kpi-grid" aria-label="Mission metrics">
          <MetricCard
            label="Total Missions"
            value={error ? "—" : missions.length}
            loading={loading}
            tone={error ? "neutral" : "info"}
            detail={error ? "Waiting for runtime" : "Loaded from mission service"}
          />
          <MetricCard
            label="Running"
            value={error ? "—" : missions.filter((item) => item.state.toUpperCase() === "RUNNING").length}
            loading={loading}
            tone="warning"
            detail="Active execution"
          />
          <MetricCard
            label="Verified"
            value={error ? "—" : missions.filter((item) => item.state.toUpperCase() === "VERIFIED").length}
            loading={loading}
            tone="healthy"
            detail="Passed validation"
          />
          <MetricCard
            label="Failed"
            value={error ? "—" : missions.filter((item) => item.state.toUpperCase() === "FAILED").length}
            loading={loading}
            tone="critical"
            detail="Needs operator attention"
          />
        </div>
      </Panel>

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
              <Link href="/chat" className="secondary-button shell-link-button">
                Launch mission
              </Link>
            }
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
