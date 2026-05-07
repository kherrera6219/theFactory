"use client";

import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, StatusBadge, SystemMessage } from "../../components/status";
import { listOperationsAlerts } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import type { AlertRecord, OperationsAlertRecord } from "../../lib/types";

function mapAlertRecord(record: OperationsAlertRecord): AlertRecord {
  return {
    id: record.alert_id,
    title: record.title,
    severity: record.severity,
    state: record.state,
    source: record.source,
    createdAt: record.created_at,
    recommendation: record.recommendation,
  };
}

function nextAlertState(current: AlertRecord["state"]): AlertRecord["state"] {
  if (current === "open") {
    return "acknowledged";
  }
  if (current === "acknowledged") {
    return "resolved";
  }
  return "resolved";
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const operationAlerts = await listOperationsAlerts(100);
        if (!cancelled) {
          setAlerts(operationAlerts.map(mapAlertRecord));
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load live alert signals.",
          );
          setAlerts([]);
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

  const openCount = useMemo(() => alerts.filter((item) => item.state === "open").length, [alerts]);

  function advanceAlert(alertId: string) {
    setAlerts((current) =>
      current.map((item) =>
        item.id === alertId
          ? {
              ...item,
              state: nextAlertState(item.state),
            }
          : item,
      ),
    );
  }

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Alerts"
        title="Incident and Alert Center"
        description="Review current operational alerts, acknowledge ownership, and guide remediation actions."
      />

      <Panel title="Alert Summary">
        {loading && <p className="muted">Collecting live alert signals...</p>}
        {error && (
          <SystemMessage tone="critical" title="Alert signals are unavailable">
            {error} Incident data will appear when the operations API is reachable.
          </SystemMessage>
        )}
        {!loading && !error && <p className="muted">Open alerts: {openCount}</p>}
      </Panel>

      <Panel title="Active and Recent Alerts">
        {!loading && !error && alerts.length === 0 && (
          <EmptyState title="No active alerts" compact>
            Alert history and remediation recommendations will appear here when the operations service reports incidents.
          </EmptyState>
        )}
        <ul className="card-list">
          {alerts.map((alert) => (
            <li key={alert.id} className={`info-card alert-${alert.severity}`}>
              <div className="panel-title-row">
                <h3>{alert.title}</h3>
                <StatusBadge tone={alert.state === "resolved" ? "healthy" : alert.state === "acknowledged" ? "warning" : "critical"}>
                  {alert.state}
                </StatusBadge>
              </div>
              <p>{alert.recommendation}</p>
              <dl className="card-meta">
                <div>
                  <dt>Severity</dt>
                  <dd>{alert.severity}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>{alert.source}</dd>
                </div>
                <div>
                  <dt>Created</dt>
                  <dd>{formatDateTime(alert.createdAt)}</dd>
                </div>
              </dl>
              {alert.state !== "resolved" && (
                <button type="button" className="secondary-button" onClick={() => advanceAlert(alert.id)}>
                  {alert.state === "open" ? "Acknowledge" : "Mark Resolved"}
                </button>
              )}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
