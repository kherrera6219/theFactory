"use client";

import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, MetricCard, SystemMessage } from "../../components/status";
import { getGatewayHealth, getGatewayReadyState, listMissions } from "../../lib/api-client";
import { humanizeState } from "../../lib/format";
import type { GatewayHealth, MissionRecord } from "../../lib/types";

export default function PerformancePage() {
  const [health, setHealth] = useState<GatewayHealth | null>(null);
  const [ready, setReady] = useState<{ ready: boolean; detail?: string } | null>(null);
  const [missions, setMissions] = useState<MissionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [healthData, readyData, missionData] = await Promise.all([
          getGatewayHealth(),
          getGatewayReadyState(),
          listMissions(40),
        ]);
        if (!cancelled) {
          setHealth(healthData);
          setReady(readyData);
          setMissions(missionData);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load performance data.");
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

  const metrics = useMemo(() => {
    const failedCount = missions.filter((mission) => mission.state.toUpperCase() === "FAILED").length;
    const runningCount = missions.filter((mission) => mission.state.toUpperCase() === "RUNNING").length;
    const verifiedCount = missions.filter((mission) => mission.state.toUpperCase() === "VERIFIED").length;

    return [
      {
        title: "Gateway Readiness",
        value: ready?.ready ? "Ready" : "Not Ready",
        trend: ready?.ready ? "All dependencies healthy" : ready?.detail ?? "Readiness details unavailable",
      },
      {
        title: "Redis Health",
        value: health?.redis_healthy ? "Healthy" : "Unavailable",
        trend: `Stream: ${health?.intake_stream ?? "unknown"}`,
      },
      {
        title: "Orchestrator Health",
        value: health?.orchestrator_healthy ? "Healthy" : "Unavailable",
        trend: `Endpoint: ${health?.orchestrator_url ?? "unknown"}`,
      },
      {
        title: "Mission States",
        value: `${runningCount} running / ${verifiedCount} verified`,
        trend: `${failedCount} failed mission(s) in current snapshot`,
      },
    ];
  }, [health, ready, missions]);

  const stateDistribution = useMemo(() => {
    const counts = new Map<string, number>();
    for (const mission of missions) {
      const state = mission.state.toUpperCase();
      counts.set(state, (counts.get(state) ?? 0) + 1);
    }
    return Array.from(counts.entries()).sort((left, right) => right[1] - left[1]);
  }, [missions]);

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Performance"
        title="Runtime Capacity and Latency"
        description="Track throughput, queue lag, and dependency health to keep refinery operations within enterprise SLO targets."
      />

      <Panel title="Key Metrics">
        {loading && <p className="muted">Collecting runtime metrics...</p>}
        {error && (
          <SystemMessage tone="critical" title="Performance metrics are unavailable">
            {error} Runtime capacity metrics will populate once the gateway can return health and mission snapshots.
          </SystemMessage>
        )}
        {!loading && !error && (
          <div className="kpi-grid" aria-label="Runtime metrics">
            {metrics.map((metric) => (
              <MetricCard
                key={metric.title}
                label={metric.title}
                value={metric.value}
                detail={metric.trend}
                tone={/Unavailable|Not Ready/i.test(metric.value) ? "critical" : "healthy"}
              />
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Mission State Distribution">
        {stateDistribution.length === 0 && (
          <EmptyState title={error ? "No performance distribution while runtime is offline" : "No mission state data yet"} compact>
            Mission throughput and state distribution will appear after mission telemetry is available.
          </EmptyState>
        )}
        {stateDistribution.length > 0 && (
          <ul className="summary-list">
            {stateDistribution.map(([state, count]) => (
              <li key={state}>
                <strong>{humanizeState(state)}</strong>
                <span>{count} mission(s)</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
