"use client";

import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, MetricCard, StatusBadge, SystemMessage } from "../../components/status";
import { getGatewayHealth, getGatewayReadyState, listMissions } from "../../lib/api-client";
import { computeMissionPerformance, formatSeconds } from "../../lib/mission-performance";
import type { GatewayHealth, MissionRecord } from "../../lib/types";

const MISSION_SAMPLE = 200;

function stepLabel(eventType: string): string {
  return eventType
    .replace(/^MISSION_/, "")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/(^\w|\s\w)/g, (match) => match.toUpperCase());
}

function formatUsd(value: number): string {
  return `$${value.toFixed(value < 1 ? 4 : 2)}`;
}

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
          listMissions(MISSION_SAMPLE),
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

  const perf = useMemo(() => computeMissionPerformance(missions), [missions]);

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Performance"
        title="Mission Throughput and Timing"
        description={`How fast missions are delivered, which pipeline steps take longest, and what they cost — computed from the latest ${MISSION_SAMPLE} mission records.`}
      />

      {error && (
        <SystemMessage tone="critical" title="Performance data is unavailable">
          {error} These figures populate once the gateway can return mission records.
        </SystemMessage>
      )}

      <Panel title="Throughput">
        <div className="kpi-grid" aria-label="Throughput metrics">
          <MetricCard
            label="Delivered (24h)"
            value={error ? "—" : perf.deliveredLast24h}
            loading={loading}
            tone="info"
            detail={`${perf.deliveredLast7d} in the last 7 days`}
          />
          <MetricCard
            label="Delivery Rate"
            value={error || perf.deliveryRate === null ? "—" : `${Math.round(perf.deliveryRate * 100)}%`}
            loading={loading}
            tone={perf.deliveryRate !== null && perf.deliveryRate < 0.7 ? "warning" : "healthy"}
            detail={`${perf.delivered} delivered · ${perf.blocked} blocked · ${perf.failed} failed`}
          />
          <MetricCard
            label="Median Duration"
            value={error ? "—" : formatSeconds(perf.medianDurationSeconds)}
            loading={loading}
            tone="info"
            detail={`p90 ${formatSeconds(perf.p90DurationSeconds)} · intake to delivery`}
          />
          <MetricCard
            label="LLM Spend"
            value={error ? "—" : formatUsd(perf.totalCostUsd)}
            loading={loading}
            tone={perf.overCap > 0 ? "warning" : "info"}
            detail={
              perf.costedMissions > 0
                ? `${formatUsd(perf.totalCostUsd / perf.costedMissions)} per mission · ${perf.overCap} over cap`
                : "No usage recorded yet"
            }
          />
        </div>
      </Panel>

      <Panel
        title="Slowest Pipeline Steps"
        description="Median time from the previous chain event to this one, across missions."
      >
        {!loading && perf.steps.length === 0 ? (
          <EmptyState title="No step timings yet" compact>
            Step timings appear once missions record chain-trace events.
          </EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <caption className="sr-only">Median duration of each pipeline step</caption>
              <thead>
                <tr>
                  <th scope="col">Step</th>
                  <th scope="col">Median time</th>
                  <th scope="col">Samples</th>
                </tr>
              </thead>
              <tbody>
                {perf.steps.map((step) => (
                  <tr key={step.step}>
                    <td>{stepLabel(step.step)}</td>
                    <td className="mono-id">{formatSeconds(step.medianSeconds)}</td>
                    <td className="muted">{step.samples}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Service Health">
        <ul className="summary-list">
          <li>
            <strong>Gateway readiness</strong>
            <StatusBadge tone={ready?.ready ? "healthy" : "critical"}>
              {ready?.ready ? "Ready" : ready?.detail ?? "Not ready"}
            </StatusBadge>
          </li>
          <li>
            <strong>Redis (intake stream)</strong>
            <StatusBadge tone={health?.redis_healthy ? "healthy" : "critical"}>
              {health?.redis_healthy ? "Healthy" : "Unavailable"}
            </StatusBadge>
          </li>
          <li>
            <strong>Orchestrator</strong>
            <StatusBadge tone={health?.orchestrator_healthy ? "healthy" : "critical"}>
              {health?.orchestrator_healthy ? "Healthy" : "Unavailable"}
            </StatusBadge>
          </li>
        </ul>
      </Panel>
    </div>
  );
}
