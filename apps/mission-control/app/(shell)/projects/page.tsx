"use client";

import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { listOperationsProjects } from "../../lib/api-client";
import { formatDateTime, humanizeState } from "../../lib/format";
import { TEMPLATE_CATALOG } from "../../lib/template-catalog";
import type { OperationsProjectRecord } from "../../lib/types";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<OperationsProjectRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        {error && <p className="error-box">{error}</p>}
        <div className="table-wrap">
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
                <tr key={project.project_id}>
                  <td>{project.project_id}</td>
                  <td>{project.source}</td>
                  <td>{humanizeState(project.status)}</td>
                  <td>{project.mission_count}</td>
                  <td>{project.failed_count}</td>
                  <td>{project.complete_count}</td>
                  <td>{formatDateTime(project.last_updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && sortedProjects.length === 0 && <p className="muted">No projects available yet.</p>}
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
