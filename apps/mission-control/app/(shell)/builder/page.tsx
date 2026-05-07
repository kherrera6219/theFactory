"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, SystemMessage } from "../../components/status";
import {
  approveReviewArtifact,
  createBuilderWorkspaceReview,
  createMission,
  verifyReviewApproval,
} from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { sanitizeUserText } from "../../lib/security";
import type { BuilderPreviewResponse, ReviewApprovalReceipt } from "../../lib/types";

function parseConstraints(value: string): string[] {
  return value
    .split(",")
    .map((item) => sanitizeUserText(item))
    .filter((item) => item.length > 0);
}

function renderDiffLine(line: { kind: "context" | "add" | "remove"; value: string }): string {
  if (line.kind === "add") {
    return `+ ${line.value}`;
  }
  if (line.kind === "remove") {
    return `- ${line.value}`;
  }
  return `  ${line.value}`;
}

export default function BuilderPage() {
  const router = useRouter();
  const [request, setRequest] = useState("");
  const [constraintsInput, setConstraintsInput] = useState("");
  const [viewMode, setViewMode] = useState<"desktop" | "tablet" | "mobile">("desktop");
  const [executionMessage, setExecutionMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<BuilderPreviewResponse | null>(null);
  const [approval, setApproval] = useState<ReviewApprovalReceipt | null>(null);
  const [loading, setLoading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function resetApproval() {
    setApproval(null);
  }

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
    resetApproval();
    setRequest(sanitized);

    try {
      const result = await createBuilderWorkspaceReview({
        request: sanitized,
        constraints: parsedConstraints,
        viewMode,
      });
      setPreview(result);
      setExecutionMessage(
        `Preview generated from ${result.source} at ${formatDateTime(result.generated_at)}.`,
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to generate preview.");
      setExecutionMessage(null);
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }

  async function applyReviewGate() {
    if (!preview?.builder_fingerprint) {
      setError("Generate a Builder review before applying the gate.");
      return;
    }

    setApproving(true);
    setError(null);
    try {
      const receipt = await approveReviewArtifact({
        scope: "builder",
        fingerprint: preview.builder_fingerprint,
        summary: `Builder review approved for ${preview.files?.length ?? 0} workspace file(s).`,
        metadata: {
          request_id: preview.request_id,
          requested_target_language: preview.requested_target_language ?? null,
          selected_files: preview.files?.map((file) => file.path) ?? [],
          source_characters: preview.source_stats?.source_characters ?? 0,
        },
      });
      setApproval(receipt);
    } catch (approvalError) {
      setError(
        approvalError instanceof Error ? approvalError.message : "Unable to persist Builder approval.",
      );
      setApproval(null);
    } finally {
      setApproving(false);
    }
  }

  async function launchBuilderMission() {
    const sanitized = sanitizeUserText(request);
    if (!preview || !preview.builder_fingerprint || !preview.source_code) {
      setError("Generate a Builder review before launch.");
      return;
    }
    if (!approval || approval.fingerprint !== preview.builder_fingerprint) {
      setError("Apply the Builder review gate before launching the mission.");
      return;
    }
    if (sanitized.length < 3) {
      setError("Add more detail before launching the mission.");
      return;
    }

    setLaunching(true);
    setError(null);
    try {
      await verifyReviewApproval({
        scope: "builder",
        approvalId: approval.approval_id,
        fingerprint: approval.fingerprint,
        receiptDigest: approval.receipt_digest,
      });
      const mission = await createMission({
        prompt: sanitized,
        requested_target_language: preview.requested_target_language ?? null,
        source_code: preview.source_code,
        metadata: {
          source: "mission-control-builder",
          builder_request_id: preview.request_id,
          builder_fingerprint: preview.builder_fingerprint,
          builder_generated_at: preview.generated_at,
          builder_view_mode: viewMode,
          builder_constraints: parseConstraints(constraintsInput),
          builder_patch_characters: preview.source_stats?.patch_characters ?? 0,
          builder_selected_files: preview.files?.map((file) => file.path) ?? [],
          review_approval_id: approval.approval_id,
          review_approved_at: approval.approved_at,
          review_receipt_digest: approval.receipt_digest,
          requested_target_language: preview.requested_target_language ?? null,
          diff_summary: preview.diff_summary.slice(0, 12),
          test_plan: preview.test_plan,
        },
      });
      router.push(`/missions/${mission.mission_id}`);
    } catch (launchError) {
      if (launchError instanceof Error && /approval/i.test(launchError.message)) {
        setApproval(null);
      }
      setError(launchError instanceof Error ? launchError.message : "Unable to launch Builder mission.");
    } finally {
      setLaunching(false);
    }
  }

  const reviewLocked = !preview;
  const launchLocked =
    !preview ||
    !preview.builder_fingerprint ||
    !preview.source_code ||
    !approval ||
    approval.fingerprint !== preview.builder_fingerprint;

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Builder"
        title="Builder Workspace"
        description="Compose natural-language change requests, inspect grounded patch contracts, apply review approval, and launch an execution-ready mission bundle."
      />

      <Panel title="Step 1: Request Console">
        <label htmlFor="builder-request">Change request</label>
        <textarea
          id="builder-request"
          rows={6}
          value={request}
          onChange={(event) => {
            setRequest(event.target.value);
            if (approval) {
              resetApproval();
            }
          }}
          placeholder="Describe the feature change, constraints, and acceptance criteria."
        />
        <label htmlFor="builder-constraints">Constraints (comma-separated)</label>
        <input
          id="builder-constraints"
          type="text"
          value={constraintsInput}
          onChange={(event) => {
            setConstraintsInput(event.target.value);
            if (approval) {
              resetApproval();
            }
          }}
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
        {error && (
          <SystemMessage tone="critical" title="Builder request could not continue">
            {error}
          </SystemMessage>
        )}
      </Panel>

      <Panel title={`Step 2: Review Patch Contract${reviewLocked ? " (locked)" : ""}`}>
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
              {(preview.files ?? []).map((file) => (
                <li key={file.path} className={`info-card alert-${file.risk}`}>
                  <h4>{file.path}</h4>
                  <p>
                    {file.operation.toUpperCase()} - {file.summary}
                  </p>
                  {file.excerpt && <p className="muted">{file.excerpt.slice(0, 180)}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="stack-gap">
          {!preview && (
            <EmptyState title="No patch contract generated yet" compact>
              Stage a request to inspect affected files, proposed changes, risk notes, and test plan before launch.
            </EmptyState>
          )}
          {preview &&
            (preview.files ?? []).map((file) => (
              <div key={`${file.path}-diff`} className="code-block">
                <p className="muted">{file.path}</p>
                <pre>{file.lines.map((line) => renderDiffLine(line)).join("\n")}</pre>
              </div>
            ))}
          {preview?.patch_text && (
            <div className="code-block">
              <p className="muted">Patch Contract</p>
              <pre>{preview.patch_text}</pre>
            </div>
          )}
        </div>
        {preview?.notice && <p className="help-text">{preview.notice}</p>}
        {preview && (
          <div className="stack-gap">
            <ul className="summary-list">
              <li>
                <strong>Requested target language</strong>
                <span>{preview.requested_target_language ?? "auto"}</span>
              </li>
              <li>
                <strong>Selected files</strong>
                <span>{preview.source_stats?.selected_files ?? 0}</span>
              </li>
              <li>
                <strong>Source bundle size</strong>
                <span>{preview.source_stats?.source_characters ?? 0} chars</span>
              </li>
              <li>
                <strong>Patch size</strong>
                <span>{preview.source_stats?.patch_characters ?? 0} chars</span>
              </li>
            </ul>
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
            <div className="inline-actions">
              <button type="button" onClick={() => void applyReviewGate()} disabled={approving}>
                {approving ? "Applying Gate..." : approval ? "Reapply Review Gate" : "Apply Review Gate"}
              </button>
            </div>
            {approval && (
              <p className="success-box">
                Review gate persisted at {formatDateTime(approval.approved_at)}.
              </p>
            )}
          </div>
        )}
      </Panel>

      <Panel title={`Step 3: Launch Mission${launchLocked ? " (locked)" : ""}`}>
        {launchLocked && (
          <EmptyState title="Launch is locked by review approval" compact>
            Apply the Step 2 review gate to persist the patch contract before launching a mission.
          </EmptyState>
        )}
        {!launchLocked && preview && approval && (
          <div className="stack-gap">
            <ul className="summary-list">
              <li>
                <strong>Approval receipt</strong>
                <span>{approval.approval_id}</span>
              </li>
              <li>
                <strong>Receipt digest</strong>
                <span>{approval.receipt_digest.slice(0, 16)}...</span>
              </li>
              <li>
                <strong>Requested target language</strong>
                <span>{preview.requested_target_language ?? "auto"}</span>
              </li>
              <li>
                <strong>Source bundle size</strong>
                <span>{preview.source_stats?.source_characters ?? 0} chars</span>
              </li>
            </ul>
            <div className="inline-actions">
              <button type="button" onClick={() => void launchBuilderMission()} disabled={launching}>
                {launching ? "Launching..." : "Launch Mission"}
              </button>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}
