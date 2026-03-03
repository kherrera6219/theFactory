"use client";

import { useState } from "react";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { createBuilderPreview } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { sanitizeUserText } from "../../lib/security";
import type { BuilderPreviewResponse } from "../../lib/types";

type DiffLine = {
  kind: "context" | "add" | "remove";
  value: string;
};

type FileDiffPreview = {
  path: string;
  operation: "modify" | "create";
  risk: "low" | "medium" | "high";
  summary: string;
  lines: DiffLine[];
};

const FILE_HINTS: Array<{ keyword: string; path: string }> = [
  { keyword: "builder", path: "apps/mission-control/app/(shell)/builder/page.tsx" },
  { keyword: "repo", path: "apps/mission-control/app/(shell)/repo/page.tsx" },
  { keyword: "mission", path: "apps/mission-control/app/(shell)/missions/page.tsx" },
  { keyword: "agent", path: "apps/mission-control/app/(shell)/agents/page.tsx" },
  { keyword: "setting", path: "apps/mission-control/app/(shell)/settings/page.tsx" },
  { keyword: "api", path: "services/api-gateway/api_gateway/main.py" },
  { keyword: "orchestrator", path: "services/orchestrator/orchestrator/main.py" },
];

function parseConstraints(value: string): string[] {
  return value
    .split(",")
    .map((item) => sanitizeUserText(item))
    .filter((item) => item.length > 0);
}

function fileRisk(path: string): "low" | "medium" | "high" {
  if (path.startsWith("services/")) {
    return "high";
  }
  if (path.includes("/api/")) {
    return "medium";
  }
  return "low";
}

function buildDiffLines(path: string, request: string, summary: string): DiffLine[] {
  const normalizedRequest = sanitizeUserText(request).slice(0, 120) || "Apply requested change";
  const normalizedSummary = sanitizeUserText(summary).slice(0, 120) || "Update implementation plan";

  if (path.endsWith(".py")) {
    return [
      { kind: "context", value: "@@ -1,4 +1,8 @@" },
      { kind: "context", value: " def handler(payload):" },
      { kind: "remove", value: "     return existing_flow(payload)" },
      { kind: "add", value: "     # builder preview generated scope" },
      { kind: "add", value: `     apply_scope = "${normalizedRequest}"` },
      { kind: "add", value: "     return hardened_flow(payload, apply_scope)" },
      { kind: "context", value: "" },
      { kind: "add", value: ` # note: ${normalizedSummary}` },
    ];
  }
  return [
    { kind: "context", value: "@@ -1,4 +1,9 @@" },
    { kind: "context", value: " export default function Module() {" },
    { kind: "remove", value: "   return <p>Interactive preview placeholder</p>;" },
    { kind: "add", value: "   const plannedChange = {" },
    { kind: "add", value: `     request: "${normalizedRequest}",` },
    { kind: "add", value: `     summary: "${normalizedSummary}",` },
    { kind: "add", value: "   };" },
    { kind: "add", value: "   return <PreviewCard change={plannedChange} />;" },
    { kind: "context", value: " }" },
  ];
}

function inferFileDiffs(
  request: string,
  constraints: string[],
  preview: BuilderPreviewResponse,
): FileDiffPreview[] {
  const signalText = [
    request,
    ...constraints,
    ...preview.diff_summary,
    ...preview.plan.map((step) => step.description),
  ]
    .join(" ")
    .toLowerCase();

  const pickedPaths: string[] = [];
  for (const hint of FILE_HINTS) {
    if (signalText.includes(hint.keyword) && !pickedPaths.includes(hint.path)) {
      pickedPaths.push(hint.path);
    }
    if (pickedPaths.length >= 4) {
      break;
    }
  }
  if (pickedPaths.length === 0) {
    pickedPaths.push("apps/mission-control/app/(shell)/builder/page.tsx");
  }

  return pickedPaths.map((path, index) => {
    const summary =
      preview.diff_summary[index] ||
      preview.plan[index]?.description ||
      "Apply scoped implementation updates.";
    const operation: "modify" | "create" = path.includes("tests/") ? "create" : "modify";
    return {
      path,
      operation,
      risk: fileRisk(path),
      summary,
      lines: buildDiffLines(path, request, summary),
    };
  });
}

function renderDiffLine(line: DiffLine): string {
  if (line.kind === "add") {
    return `+ ${line.value}`;
  }
  if (line.kind === "remove") {
    return `- ${line.value}`;
  }
  return `  ${line.value}`;
}

export default function BuilderPage() {
  const [request, setRequest] = useState("");
  const [constraintsInput, setConstraintsInput] = useState("");
  const [viewMode, setViewMode] = useState<"desktop" | "tablet" | "mobile">("desktop");
  const [executionMessage, setExecutionMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<BuilderPreviewResponse | null>(null);
  const [fileDiffs, setFileDiffs] = useState<FileDiffPreview[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function queueRequest() {
    const sanitized = sanitizeUserText(request);
    if (sanitized.length < 3) {
      setExecutionMessage("Add more detail before sending a build request.");
      setError(null);
      return;
    }

    const parsedConstraints = parseConstraints(constraintsInput);
    setLoading(true);
    setError(null);
    setRequest(sanitized);

    try {
      const result = await createBuilderPreview({
        request: sanitized,
        constraints: parsedConstraints,
        viewMode,
      });
      setPreview(result);
      setFileDiffs(inferFileDiffs(sanitized, parsedConstraints, result));
      setExecutionMessage(
        `Preview generated from ${result.source} at ${formatDateTime(result.generated_at)}.`,
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to generate preview.");
      setExecutionMessage(null);
      setFileDiffs([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page shell-page">
      <PageHeader
        eyebrow="Builder"
        title="Builder Workspace"
        description="Compose natural-language change requests, inspect generated diff previews, and review risks before execution."
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
          placeholder="example: no schema changes, preserve accessibility AAA where possible"
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
          {!preview && <p>No preview generated yet.</p>}
          {preview && (
            <ul className="card-list">
              {fileDiffs.map((file) => (
                <li key={file.path} className={`info-card alert-${file.risk}`}>
                  <h4>{file.path}</h4>
                  <p>
                    {file.operation.toUpperCase()} - {file.summary}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="stack-gap">
          {!preview && (
            <div className="code-block">
              <p className="muted">No preview generated yet.</p>
            </div>
          )}
          {preview &&
            fileDiffs.map((file) => (
              <div key={`${file.path}-diff`} className="code-block">
                <p className="muted">{file.path}</p>
                <pre>{file.lines.map((line) => renderDiffLine(line)).join("\n")}</pre>
              </div>
            ))}
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
