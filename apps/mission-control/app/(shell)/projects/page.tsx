"use client";

import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, StatusBadge, SystemMessage } from "../../components/status";
import { listOperationsProjects, listProjectAuditEvents } from "../../lib/api-client";
import { formatDateTime, humanizeState } from "../../lib/format";
import { TEMPLATE_CATALOG } from "../../lib/template-catalog";
import type { OperationsAuditEventRecord, OperationsProjectRecord } from "../../lib/types";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<OperationsProjectRecord[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [auditEvents, setAuditEvents] = useState<OperationsAuditEventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [auditLoading, setAuditLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const operationProjects = await listOperationsProjects(200);
        if (!cancelled) {
          setProjects(operationProjects);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load project signals.");
          setProjects([]);
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

  const sortedProjects = useMemo(
    () =>
      [...projects].sort(
        (left, right) => new Date(right.last_updated_at).getTime() - new Date(left.last_updated_at).getTime(),
      ),
    [projects],
  );

  useEffect(() => {
    if (!sortedProjects.length) {
      setSelectedProjectId(null);
      return;
    }
    setSelectedProjectId((current) =>
      current && sortedProjects.some((project) => project.project_id === current)
        ? current
        : sortedProjects[0].project_id,
    );
  }, [sortedProjects]);

  useEffect(() => {
    if (!selectedProjectId) {
      setAuditEvents([]);
      setAuditError(null);
      setAuditLoading(false);
      return;
    }
    let cancelled = false;
    const loadAudit = async () => {
      setAuditLoading(true);
      setAuditError(null);
      try {
        const events = await listProjectAuditEvents({ projectId: selectedProjectId, limit: 200 });
        if (!cancelled) {
          setAuditEvents(events);
        }
      } catch (loadError) {
        if (!cancelled) {
          setAuditError(loadError instanceof Error ? loadError.message : "Unable to load project audit events.");
          setAuditEvents([]);
        }
      } finally {
        if (!cancelled) {
          setAuditLoading(false);
        }
      }
    };
    void loadAudit();
    return () => {
      cancelled = true;
    };
  }, [selectedProjectId]);

  const selectedProject = sortedProjects.find((project) => project.project_id === selectedProjectId) ?? null;

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Projects"
        title="Projects and Templates"
        description="Manage active refinery projects, resume paused workstreams, and launch standardized template workflows."
      />

      <Panel title="Project Portfolio">
        {loading && <p className="muted">Building portfolio from mission metadata...</p>}
        {error && (
          <SystemMessage tone="critical" title="Project portfolio is unavailable">
            {error} Project signals are derived from mission metadata and will populate when the runtime is live.
          </SystemMessage>
        )}
        <div className="table-wrap" tabIndex={0} aria-label="Scrollable project audit table">
          <table className="data-table">
            <caption className="sr-only">
              Project catalog with source, status, mission counts, and last update timestamp.
            </caption>
            <thead>
              <tr>
                <th scope="col">Project ID</th>
                <th scope="col">Source</th>
                <th scope="col">Status</th>
                <th scope="col">Missions</th>
                <th scope="col">Failed</th>
                <th scope="col">Complete</th>
                <th scope="col">Last Updated</th>
              </tr>
            </thead>
            <tbody>
              {sortedProjects.map((project) => (
                <tr
                  key={project.project_id}
                  data-selected={project.project_id === selectedProjectId ? "true" : undefined}
                  onClick={() => setSelectedProjectId(project.project_id)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{project.project_id}</td>
                  <td>{project.project_name ?? project.source}</td>
                  <td>
                    <StatusBadge tone={project.status.toUpperCase().includes("FAIL") ? "critical" : "info"}>
                      {humanizeState(project.status)}
                    </StatusBadge>
                  </td>
                  <td>{project.mission_count}</td>
                  <td>{project.failed_count}</td>
                  <td>{project.complete_count}</td>
                  <td>{formatDateTime(project.last_updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && sortedProjects.length === 0 && (
          <EmptyState title="No projects available yet" compact>
            Imported repositories and mission groups will appear here after live mission metadata is available.
          </EmptyState>
        )}
      </Panel>

      <Panel
        title={selectedProject ? `Audit Timeline: ${selectedProject.project_name ?? selectedProject.project_id}` : "Audit Timeline"}
      >
        {auditLoading && <p className="muted">Loading project audit trail...</p>}
        {auditError && (
          <SystemMessage tone="critical" title="Audit timeline is unavailable">
            {auditError}
          </SystemMessage>
        )}
        {!auditLoading && !auditError && selectedProject && (
          <p className="muted">
            Showing the latest {auditEvents.length} recorded agent actions for <strong>{selectedProject.project_id}</strong>.
          </p>
        )}
        <div className="table-wrap" tabIndex={0} aria-label="Scrollable project portfolio table">
          <table className="data-table">
            <caption className="sr-only">
              Project audit log with event type, mission, agent, service, tool, and timing details.
            </caption>
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Event</th>
                <th scope="col">Mission</th>
                <th scope="col">Agent</th>
                <th scope="col">Service</th>
                <th scope="col">Tool</th>
                <th scope="col">Object</th>
                <th scope="col">Duration</th>
              </tr>
            </thead>
            <tbody>
              {auditEvents.map((event) => (
                <tr key={event.event_id}>
                  <td>{formatDateTime(event.created_at)}</td>
                  <td>
                    <strong>{event.event_type}</strong>
                    <div className="muted">{humanizeState(event.status)}</div>
                  </td>
                  <td>{event.mission_id}</td>
                  <td>{event.agent_id}</td>
                  <td>{event.service_name}</td>
                  <td>{event.tool_name ?? "—"}</td>
                  <td>{event.object_id ?? event.object_type ?? "—"}</td>
                  <td>{typeof event.duration_ms === "number" ? `${event.duration_ms} ms` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!auditLoading && !auditError && selectedProject && auditEvents.length === 0 && (
          <EmptyState title="No audit events recorded yet" compact>
            Agent actions, tool calls, and mission evidence will appear once this project has runtime activity.
          </EmptyState>
        )}
      </Panel>

      <Panel title="Template Catalog">
        <ul className="card-list">
          {TEMPLATE_CATALOG.map((template) => (
            <li key={template.id} className="info-card">
              <h3>{template.title}</h3>
              <p>{template.summary}</p>
              <p className="muted">Category: {template.category}</p>
              <p className="muted" aria-live="polite">
                Template launch is not wired in Mission Control yet.
              </p>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
