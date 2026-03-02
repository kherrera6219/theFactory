"use client";

import { useEffect, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { getGatewayHealth, getOperationsSummary } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
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

function buildCards(summary: OperationsSummary | null, health: GatewayHealth | null): DatabaseCard[] {
  const redisHealthy = Boolean(health?.redis_healthy);
  const dbHealthy = Boolean(summary?.runtime.db_ready);
  const generatedAt = summary?.generated_at ?? new Date().toISOString();
  const lastWrite = formatDateTime(generatedAt);

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
    {
      id: "qdrant",
      name: "Knowledge Vectors",
      engine: "Qdrant",
      status: "planned",
      details: "Reserved in architecture plan. Runtime integration pending.",
      lastWrite: "Pending activation",
    },
    {
      id: "neo4j",
      name: "Traceability Graph",
      engine: "Neo4j",
      status: "planned",
      details: "Planned optional datastore for compliance and provenance mapping.",
      lastWrite: "Pending activation",
    },
    {
      id: "object-storage",
      name: "Artifact Store",
      engine: "Object Storage",
      status: "planned",
      details: "Planned for binary bundles and audit evidence retention.",
      lastWrite: "Pending activation",
    },
  ];
}

export default function DatabasesPage() {
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [health, setHealth] = useState<GatewayHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [summaryData, healthData] = await Promise.all([getOperationsSummary(), getGatewayHealth()]);
        if (!cancelled) {
          setSummary(summaryData);
          setHealth(healthData);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load database health.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
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
        eyebrow="Database Health"
        title="Data Plane Status"
        description="Track all five shared database systems used by the refinery control plane."
      />

      <Panel title="Health Overview">
        {loading && <p className="muted">Collecting database diagnostics...</p>}
        {error && <p className="error-box">{error}</p>}
        {!loading && !error && (
          <ul className="summary-list">
            <li>
              <strong>Runtime database ready</strong>
              <span>{summary?.runtime.db_ready ? "Yes" : "No"}</span>
            </li>
            <li>
              <strong>Redis ready</strong>
              <span>{health?.redis_healthy ? "Yes" : "No"}</span>
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
                <span className={`pill ${card.status}`}>
                  {card.status === "healthy" ? "Healthy" : card.status === "degraded" ? "Degraded" : "Planned"}
                </span>
              </div>
              <p className="muted">{card.engine}</p>
              <p>{card.details}</p>
              <p className="muted">Last write: {card.lastWrite}</p>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

