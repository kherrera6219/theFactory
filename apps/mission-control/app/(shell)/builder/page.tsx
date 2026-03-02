"use client";

import { useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { createBuilderPreview } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { sanitizeUserText } from "../../lib/security";
import type { BuilderPreviewResponse } from "../../lib/types";

function parseConstraints(value: string): string[] {
  return value
    .split(",")
    .map((item) => sanitizeUserText(item))
    .filter((item) => item.length > 0);
}

export default function BuilderPage() {
  const [request, setRequest] = useState("");
  const [constraintsInput, setConstraintsInput] = useState("");
  const [viewMode, setViewMode] = useState<"desktop" | "tablet" | "mobile">("desktop");
  const [executionMessage, setExecutionMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<BuilderPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function queueRequest() {
    const sanitized = sanitizeUserText(request);
    if (sanitized.length < 3) {
      setExecutionMessage("Add more detail before sending a build request.");
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    setRequest(sanitized);

    try {
      const result = await createBuilderPreview({
        request: sanitized,
        constraints: parseConstraints(constraintsInput),
        viewMode,
      });
      setPreview(result);
      setExecutionMessage(
        `Preview generated from ${result.source} at ${formatDateTime(result.generated_at)}.`,
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to generate preview.");
      setExecutionMessage(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page shell-page">
      <PageHeader
        eyebrow="Builder"
        title="Builder Workspace"
        description="Compose natural-language change requests, inspect generated diffs, and preview results before execution."
      />

      <Panel title="Request Console">
        <label htmlFor="builder-request">Change request</label>
        <textarea
          id="builder-request"
          rows={6}
          value={request}
          onChange={(event) => setRequest(event.target.value)}
          placeholder="Describe the feature change, constraints, and acceptance criteria."
        />
        <label htmlFor="builder-constraints">Constraints (comma-separated)</label>
        <input
          id="builder-constraints"
          type="text"
          value={constraintsInput}
          onChange={(event) => setConstraintsInput(event.target.value)}
          placeholder="example: no schema changes, keep accessibility AAA where possible"
        />
        <div className="inline-actions">
          <button type="button" onClick={() => void queueRequest()} disabled={loading}>
            {loading ? "Generating..." : "Stage Request"}
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => void queueRequest()}
            disabled={loading || sanitizeUserText(request).length < 3}
          >
            Regenerate Plan
          </button>
        </div>
        {executionMessage && <p className="help-text">{executionMessage}</p>}
        {error && <p className="error-box">{error}</p>}
      </Panel>

      <Panel title="Preview and Diff">
        <div className="inline-actions">
          <button
            type="button"
            className={`secondary-button ${viewMode === "desktop" ? "active-tab" : ""}`}
            onClick={() => setViewMode("desktop")}
          >
            Desktop
          </button>
          <button
            type="button"
            className={`secondary-button ${viewMode === "tablet" ? "active-tab" : ""}`}
            onClick={() => setViewMode("tablet")}
          >
            Tablet
          </button>
          <button
            type="button"
            className={`secondary-button ${viewMode === "mobile" ? "active-tab" : ""}`}
            onClick={() => setViewMode("mobile")}
          >
            Mobile
          </button>
        </div>
        <div className={`preview-shell ${viewMode}`}>
          <p>Interactive preview placeholder for {viewMode} viewport</p>
        </div>
        <div className="code-block">
          <p className="muted">Diff Summary</p>
          {!preview && <pre>{`No preview generated yet.`}</pre>}
          {preview && (
            <pre>
              {preview.diff_summary.map((line) => `- ${line}`).join("\n")}
            </pre>
          )}
        </div>
        {preview?.notice && <p className="help-text">{preview.notice}</p>}
        {preview && (
          <div className="stack-gap">
            <h3>Execution Plan</h3>
            <ul className="card-list">
              {preview.plan.map((step) => (
                <li key={step.title} className="info-card">
                  <h4>{step.title}</h4>
                  <p>{step.description}</p>
                </li>
              ))}
            </ul>
            <h3>Risk Notes</h3>
            <ul className="summary-list">
              {preview.risk_notes.map((risk) => (
                <li key={risk}>
                  <span>{risk}</span>
                </li>
              ))}
            </ul>
            <h3>Test Plan</h3>
            <ul className="summary-list">
              {preview.test_plan.map((testStep) => (
                <li key={testStep}>
                  <span>{testStep}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Panel>
    </div>
  );
}
