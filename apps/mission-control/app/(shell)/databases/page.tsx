"use client";

import { useEffect, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { StatusBadge, SystemMessage } from "../../components/status";
import { getGatewayHealth, getOperationsSummary } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { useLastRefreshed } from "../../lib/use-last-refreshed";
import type { GatewayHealth, OperationsSummary } from "../../lib/types";

const REFRESH_MS = 10_000;

type DatabaseCard = {
  id: string;
  name: string;
  engine: string;
  status: "healthy" | "degraded" | "planned";
  details: string;
  lastWrite: string;
};

function runtimeFlag(
  summary: OperationsSummary | null,
  key: "qdrant_ready" | "milvus_ready" | "neo4j_ready" | "object_storage_ready" | "jaeger_ready",
): boolean | null {
  const value = summary?.runtime[key];
  return typeof value === "boolean" ? value : null;
}

function adapterCard(params: {
  id: string;
  name: string;
  engine: string;
  ready: boolean | null;
  healthyDetails: string;
  degradedDetails: string;
  disabledDetails: string;
  lastWrite: string;
}): DatabaseCard {
  return {
    id: params.id,
    name: params.name,
    engine: params.engine,
    status: params.ready === null ? "planned" : params.ready ? "healthy" : "degraded",
    details:
      params.ready === null
        ? params.disabledDetails
        : params.ready
          ? params.healthyDetails
          : params.degradedDetails,
    lastWrite: params.ready === null ? "Optional adapter disabled" : params.lastWrite,
  };
}

function buildCards(summary: OperationsSummary | null, health: GatewayHealth | null): DatabaseCard[] {
  const redisHealthy = Boolean(health?.redis_healthy);
  const dbHealthy = Boolean(summary?.runtime.db_ready);
  const lastWrite = summary?.generated_at
    ? formatDateTime(summary.generated_at)
    : "Awaiting runtime sample";

  return [
    {
      id: "redis",
      name: "Semantic Bus",
      engine: "Redis",
      status: redisHealthy ? "healthy" : "degraded",
      details: redisHealthy ? "Pub/Sub and stream transport operational." : "Redis connection unavailable.",
      lastWrite,
    },
    {
      id: "postgresql",
      name: "State Graph",
      engine: "PostgreSQL",
      status: dbHealthy ? "healthy" : "degraded",
      details: dbHealthy ? "Mission and telemetry persistence ready." : "Database dependency unavailable.",
      lastWrite,
    },
    adapterCard({
      id: "qdrant",
      name: "Knowledge Vectors (Primary)",
      engine: "Qdrant",
      ready: runtimeFlag(summary, "qdrant_ready"),
      healthyDetails: "Qdrant mirror and retrieval path are active.",
      degradedDetails: "Qdrant is enabled but not ready.",
      disabledDetails: "Optional vector adapter is disabled.",
      lastWrite,
    }),
    adapterCard({
      id: "milvus",
      name: "Knowledge Vectors (Secondary)",
      engine: "Milvus",
      ready: runtimeFlag(summary, "milvus_ready"),
      healthyDetails: "Milvus vector mirror is active.",
      degradedDetails: "Milvus is enabled but not ready.",
      disabledDetails: "Optional Milvus adapter is disabled.",
      lastWrite,
    }),
    adapterCard({
      id: "neo4j",
      name: "Traceability Graph",
      engine: "Neo4j",
      ready: runtimeFlag(summary, "neo4j_ready"),
      healthyDetails: "Neo4j graph mirror is active for traceability views.",
      degradedDetails: "Neo4j is enabled but not ready.",
      disabledDetails: "Optional graph adapter is disabled.",
      lastWrite,
    }),
    adapterCard({
      id: "object-storage",
      name: "Artifact Store",
      engine: "Object Storage",
      ready: runtimeFlag(summary, "object_storage_ready"),
      healthyDetails: "Audit artifact retention mirror is active.",
      degradedDetails: "Object storage is enabled but not ready.",
      disabledDetails: "Optional object-storage adapter is disabled.",
      lastWrite,
    }),
    adapterCard({
      id: "jaeger",
      name: "Observability Pipeline",
      engine: "Jaeger",
      ready: runtimeFlag(summary, "jaeger_ready"),
      healthyDetails: "Distributed tracing is active and collecting spans.",
      degradedDetails: "Jaeger OTLP endpoint is unreachable.",
      disabledDetails: "Tracing is disabled in environment.",
      lastWrite,
    }),
  ];
}

export default function DatabasesPage() {
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [health, setHealth] = useState<GatewayHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [orchestratorOffline, setOrchestratorOffline] = useState(false);
  const [lastFetchAt, setLastFetchAt] = useState<string | null>(null);
  const lastRefreshed = useLastRefreshed(lastFetchAt);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      const [summaryResult, healthResult] = await Promise.allSettled([
        getOperationsSummary(),
        getGatewayHealth(),
      ]);

      if (cancelled) return;

      const isNetworkError = (r: PromiseSettledResult<unknown>) =>
        r.status === "rejected" &&
        r.reason instanceof Error &&
        (r.reason.message === "Failed to fetch" || r.reason.message.includes("NetworkError"));

      if (isNetworkError(summaryResult) || isNetworkError(healthResult)) {
        setOrchestratorOffline(true);
        setError(null);
        setLoading(false);
        return;
      }

      setOrchestratorOffline(false);

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      }
      if (healthResult.status === "fulfilled") {
        setHealth(healthResult.value);
      }

      const firstError =
        summaryResult.status === "rejected" ? summaryResult.reason :
        healthResult.status === "rejected" ? healthResult.reason : null;

      setError(firstError instanceof Error ? firstError.message : firstError ? "Unable to load database health." : null);
      setLastFetchAt(new Date().toISOString());
      setLoading(false);
    };

    void load();
    const intervalId = window.setInterval(() => void load(), REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  const cards = buildCards(summary, health);

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Database Health"
        title="Data Plane Status"
        description="Track the live readiness of the shared data systems used by the refinery control plane."
      />

      <Panel
        title="Health Overview"
        actions={lastRefreshed ? <span className="last-refreshed">Updated {lastRefreshed}</span> : undefined}
      >
        {loading && <p className="muted">Collecting database diagnostics...</p>}
        {orchestratorOffline && (
          <SystemMessage tone="warning" title="Database diagnostics are running in offline mode">
            Orchestrator unreachable at port 8100. Start the Docker stack to see live database health.
          </SystemMessage>
        )}
        {error && (
          <SystemMessage tone="critical" title="Database health could not be loaded">
            {error}
          </SystemMessage>
        )}
        {!loading && !orchestratorOffline && !error && (
          <ul className="summary-list">
            <li>
              <strong>Runtime database ready</strong>
              <StatusBadge tone={summary?.runtime.db_ready ? "healthy" : "critical"}>
                {summary?.runtime.db_ready ? "Ready" : "Unavailable"}
              </StatusBadge>
            </li>
            <li>
              <strong>Redis ready</strong>
              <StatusBadge tone={health?.redis_healthy ? "healthy" : "critical"}>
                {health?.redis_healthy ? "Ready" : "Unavailable"}
              </StatusBadge>
            </li>
            <li>
              <strong>Protocol consumer running</strong>
              <StatusBadge tone={summary?.runtime.consumer_running ? "healthy" : "warning"}>
                {summary?.runtime.consumer_running ? "Running" : "Stopped"}
              </StatusBadge>
            </li>
            <li>
              <strong>Generated at</strong>
              <span>{summary ? formatDateTime(summary.generated_at) : "n/a"}</span>
            </li>
          </ul>
        )}
      </Panel>

      <Panel title="Database Cards">
        <ul className="card-list">
          {cards.map((card) => (
            <li key={card.id} className={`info-card db-${card.status}`}>
              <div className="panel-title-row">
                <h3>{card.name}</h3>
                <StatusBadge
                  tone={
                    card.status === "healthy" ? "healthy" :
                    card.status === "degraded" ? "critical" : "neutral"
                  }
                >
                  {card.status === "healthy" ? "Healthy" : card.status === "degraded" ? "Degraded" : "Disabled"}
                </StatusBadge>
              </div>
              <p className="muted">{card.engine}</p>
              <p>{card.details}</p>
              <p className="muted">Last write: {card.lastWrite}</p>
              {/* Phase 2G — actionable buttons for non-healthy states */}
              {card.status === "degraded" && (
                <div className="db-card-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => void (async () => { setLoading(true); await new Promise((r) => setTimeout(r, 400)); setLoading(false); })()}
                  >
                    Retry Connection
                  </button>
                </div>
              )}
              {card.status === "planned" && (
                <div className="db-card-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    title="Enable this adapter in your compose environment variables"
                    onClick={() => {
                      const target = document.querySelector<HTMLElement>("[href='/settings']");
                      target?.click();
                    }}
                  >
                    Configure Adapter →
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
