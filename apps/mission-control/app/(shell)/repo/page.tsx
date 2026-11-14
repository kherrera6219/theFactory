"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, SystemMessage } from "../../components/status";
import {
  approveReviewArtifact,
  createRepoZipReview,
  createWorkspaceReview,
  importRepoSource,
  importRepoZip,
  verifyReviewApproval,
} from "../../lib/api-client";
import {
  REPO_HANDOFF_STORAGE_KEY,
  buildRepoPmHandoff,
  officialMissionTypeFromRepoChoice,
} from "../../lib/chat-repo-import";
import { formatDateTime } from "../../lib/format";
import { sanitizeUserText } from "../../lib/security";
import type { RepoImportResponse, RepoReviewResponse, ReviewApprovalReceipt } from "../../lib/types";

type RepoFileOverlayAction = "include" | "reference" | "exclude";

type RepoFile = {
  path: string;
  language: string;
  bytes: number;
  estimatedLines: number;
  selected: boolean;
  overlayAction: RepoFileOverlayAction;
};

type MissionType = "analyze" | "update" | "add_feature" | "refactor" | "port";

function formatBytes(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)} MB`;
  }
  if (value >= 1_000) {
    return `${Math.round(value / 1_000)} KB`;
  }
  return `${value} B`;
}

function overlayLabel(action: RepoFileOverlayAction): string {
  if (action === "include") {
    return "Include";
  }
  if (action === "reference") {
    return "Reference";
  }
  return "Exclude";
}

export default function RepoImportPage() {
  const router = useRouter();

  const [sourceMode, setSourceMode] = useState<"zip" | "local" | "git">("zip");
  const [archiveFile, setArchiveFile] = useState<File | null>(null);
  const [localPath, setLocalPath] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [sourceRef, setSourceRef] = useState("main");
  const [subdirectory, setSubdirectory] = useState("/");
  const [maxFiles, setMaxFiles] = useState(300);
  const [fileFilter, setFileFilter] = useState("");
  const [files, setFiles] = useState<RepoFile[]>([]);
  const [importSnapshot, setImportSnapshot] = useState<RepoImportResponse | null>(null);
  const [missionType, setMissionType] = useState<MissionType | null>(null);
  const [description, setDescription] = useState("");
  const [reviewPreview, setReviewPreview] = useState<RepoReviewResponse | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [approvalReceipt, setApprovalReceipt] = useState<ReviewApprovalReceipt | null>(null);
  const [approving, setApproving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importLogs, setImportLogs] = useState<string[]>([]);
  const [importComplete, setImportComplete] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedFiles = useMemo(() => files.filter((item) => item.selected), [files]);
  const selectedLines = useMemo(
    () => selectedFiles.reduce((sum, item) => sum + item.estimatedLines, 0),
    [selectedFiles],
  );
  const overlayCounts = useMemo(
    () =>
      selectedFiles.reduce(
        (summary, file) => {
          summary[file.overlayAction] += 1;
          return summary;
        },
        { include: 0, reference: 0, exclude: 0 } as Record<RepoFileOverlayAction, number>,
      ),
    [selectedFiles],
  );
  const normalizedFilter = sanitizeUserText(fileFilter).toLowerCase();
  const visibleFiles = useMemo(() => {
    if (!normalizedFilter) {
      return files;
    }
    return files.filter((item) => item.path.toLowerCase().includes(normalizedFilter));
  }, [files, normalizedFilter]);

  function resetReviewGate() {
    setApprovalReceipt(null);
    setReviewPreview(null);
  }

  function resetImportResults() {
    setImportSnapshot(null);
    setFiles([]);
    setImportLogs([]);
    setImportComplete(false);
    setMissionType(null);
    setDescription("");
    resetReviewGate();
  }

  function selectMissionType(nextMissionType: MissionType) {
    if (missionType !== nextMissionType) {
      resetReviewGate();
    }
    setMissionType(nextMissionType);
    setError(null);
  }

  function updateMissionDescription(nextDescription: string) {
    if (description !== nextDescription) {
      resetReviewGate();
    }
    setDescription(nextDescription);
    setError(null);
  }

  async function importRepository() {
    if (sourceMode === "zip") {
      if (!archiveFile) {
        setError("Select a repository .zip archive before import.");
        return;
      }
      if (!archiveFile.name.toLowerCase().endsWith(".zip")) {
        setError("Repository archive must be a .zip file.");
        return;
      }
    } else if (sourceMode === "local") {
      if (!localPath.trim()) {
        setError("Enter a local folder path before import.");
        return;
      }
    } else if (!gitUrl.trim()) {
      setError("Enter a Git repository URL before import.");
      return;
    }

    setError(null);
    setImporting(true);
    setImportComplete(false);
    setImportLogs([
      sourceMode === "zip"
        ? "Validating repository ZIP upload..."
        : sourceMode === "local"
          ? "Validating local directory path..."
          : "Cloning Git repository into baseline workspace...",
      "Indexing repository entries...",
    ]);
    setImportSnapshot(null);
    setFiles([]);
    setMissionType(null);
    setDescription("");
    resetReviewGate();

    try {
      let payload: RepoImportResponse;
      if (sourceMode === "zip" && archiveFile) {
        const formData = new FormData();
        formData.set("archive", archiveFile);
        formData.set("display_name", sanitizeUserText(displayName));
        formData.set("source_ref", sanitizeUserText(sourceRef));
        formData.set("subdirectory", sanitizeUserText(subdirectory) || "/");
        formData.set("max_files", String(maxFiles));
        payload = await importRepoZip(formData);
      } else {
        payload = await importRepoSource({
          ...(sourceMode === "local"
            ? { localPath: sanitizeUserText(localPath) }
            : { gitUrl: sanitizeUserText(gitUrl) }),
          displayName: sanitizeUserText(displayName) || undefined,
          ref: sanitizeUserText(sourceRef) || undefined,
          subdirectory: sanitizeUserText(subdirectory) || "/",
          maxFiles,
        });
      }
      setImportSnapshot(payload);
      setImportLogs(payload.logs);
      setFiles(
        payload.files.map((file) => ({
          path: file.path,
          language: file.language,
          bytes: file.bytes,
          estimatedLines: file.estimated_lines,
          selected: false,
          overlayAction: "include",
        })),
      );
      setImportComplete(true);
    } catch (importError) {
      setError(
        importError instanceof Error ? importError.message : "Repository import failed unexpectedly.",
      );
      setImportLogs((current) => [...current, "Import failed."]);
    } finally {
      setImporting(false);
    }
  }

  function toggleFile(path: string) {
    setFiles((current) =>
      current.map((item) => {
        if (item.path !== path) {
          return item;
        }
        const nextSelected = !item.selected;
        return {
          ...item,
          selected: nextSelected,
          overlayAction: nextSelected ? item.overlayAction : "exclude",
        };
      }),
    );
    setError(null);
    resetReviewGate();
  }

  function updateOverlay(path: string, overlayAction: RepoFileOverlayAction) {
    setFiles((current) =>
      current.map((item) => {
        if (item.path !== path) {
          return item;
        }
        return {
          ...item,
          overlayAction,
          selected: overlayAction !== "exclude",
        };
      }),
    );
    setError(null);
    resetReviewGate();
  }

  function selectTopFiles(count: number) {
    setFiles((current) =>
      current.map((item, index) => ({
        ...item,
        selected: index < count,
        overlayAction: index < count ? "include" : "exclude",
      })),
    );
    setError(null);
    resetReviewGate();
  }

  function clearSelection() {
    setFiles((current) =>
      current.map((item) => ({ ...item, selected: false, overlayAction: "exclude" })),
    );
    setError(null);
    resetReviewGate();
  }

  async function generateReview() {
    if (!importSnapshot || (!archiveFile && !importSnapshot.repository.workspace_id)) {
      setError("Import a repository before generating repository review.");
      return;
    }
    if (selectedFiles.length === 0) {
      setError("Select at least one file before generating repository review.");
      return;
    }
    if (!missionType) {
      setError("Select a mission type before generating repository review.");
      return;
    }
    if (
      (missionType === "add_feature" || missionType === "update") &&
      sanitizeUserText(description).length < 3
    ) {
      setError("Provide a mission description for Add Feature or Update before review.");
      return;
    }

    setError(null);
    setReviewing(true);
    setApprovalReceipt(null);

    try {
      const reviewSelection = selectedFiles
        .filter((file) => file.overlayAction !== "exclude")
        .map((file) => ({
          path: file.path,
          overlay_action: (file.overlayAction === "reference" ? "reference" : "include") as
            | "include"
            | "reference",
          language: file.language,
          bytes: file.bytes,
          estimated_lines: file.estimatedLines,
        }));
      let preview: RepoReviewResponse;
      if (archiveFile && sourceMode === "zip") {
        const formData = new FormData();
        formData.set("archive", archiveFile);
        formData.set("display_name", importSnapshot.repository.display_name || sanitizeUserText(displayName));
        formData.set("source_ref", importSnapshot.repository.source_ref || sanitizeUserText(sourceRef));
        formData.set("subdirectory", importSnapshot.stats.selected_subdirectory || sanitizeUserText(subdirectory) || "/");
        formData.set("archive_sha256", importSnapshot.repository.archive_sha256);
        formData.set("mission_type", missionType);
        formData.set("description", sanitizeUserText(description));
        formData.set("selected_files", JSON.stringify(reviewSelection));
        if (importSnapshot.repository.workspace_id) {
          formData.set("workspace_id", importSnapshot.repository.workspace_id);
        }
        if (importSnapshot.repository.base_commit) {
          formData.set("base_commit", importSnapshot.repository.base_commit);
        }
        preview = await createRepoZipReview(formData);
      } else if (importSnapshot.repository.workspace_id) {
        preview = await createWorkspaceReview({
          workspaceId: importSnapshot.repository.workspace_id,
          subdirectory:
            importSnapshot.stats.selected_subdirectory || sanitizeUserText(subdirectory) || "/",
          missionType,
          description: sanitizeUserText(description),
          selectedFiles: reviewSelection.map((file) => ({
            path: file.path,
            overlay_action: file.overlay_action,
          })),
          sourceRef: importSnapshot.repository.source_ref || sanitizeUserText(sourceRef),
          displayName: importSnapshot.repository.display_name || sanitizeUserText(displayName),
        });
      } else {
        throw new Error("Missing workspace_id or archive for review.");
      }
      setReviewPreview(preview);
    } catch (reviewError) {
      setError(
        reviewError instanceof Error ? reviewError.message : "Unable to generate repository review.",
      );
      setReviewPreview(null);
    } finally {
      setReviewing(false);
    }
  }

  async function applyReviewGate() {
    if (!reviewPreview) {
      setError("Generate and inspect the review output before applying the gate.");
      return;
    }
    setError(null);
    setApproving(true);
    try {
      const receipt = await approveReviewArtifact({
        scope: "repo",
        fingerprint: reviewPreview.review_fingerprint,
        summary: `Repository review approved for ${reviewPreview.files.length} selected file(s).`,
        metadata: {
          request_id: reviewPreview.request_id,
          repository: reviewPreview.repository,
          requested_target_language: reviewPreview.requested_target_language,
          selected_files: reviewPreview.files.map((file) => ({
            path: file.path,
            overlay_action: file.overlay_action,
          })),
        },
      });
      setApprovalReceipt(receipt);
    } catch (approvalError) {
      setError(
        approvalError instanceof Error ? approvalError.message : "Unable to persist repository approval.",
      );
      setApprovalReceipt(null);
    } finally {
      setApproving(false);
    }
  }

  async function launchRepoMission() {
    if (!missionType) {
      setError("Select a mission type before launch.");
      return;
    }
    if (selectedFiles.length === 0) {
      setError("Select at least one file to include in the mission.");
      return;
    }
    if (!approvalReceipt) {
      setError("Apply Step 3 review gate before launching the mission.");
      return;
    }
    if (!reviewPreview || reviewPreview.review_fingerprint !== approvalReceipt.fingerprint) {
      setError("Repository review changed after gate approval. Reapply the review gate before launch.");
      return;
    }
    if (
      (missionType === "add_feature" || missionType === "update") &&
      sanitizeUserText(description).length < 3
    ) {
      setError("Provide a mission description for Add Feature or Update.");
      return;
    }

    setError(null);
    setLaunching(true);
    try {
      await verifyReviewApproval({
        scope: "repo",
        approvalId: approvalReceipt.approval_id,
        fingerprint: approvalReceipt.fingerprint,
        receiptDigest: approvalReceipt.receipt_digest,
      });
      const missionPrompt =
        sanitizeUserText(description) ||
        `Run ${missionType} mission for ${selectedFiles.length} files from ${reviewPreview.repository.display_name}.`;
      const officialType = officialMissionTypeFromRepoChoice(missionType);
      const handoff = buildRepoPmHandoff({
        officialMissionType: officialType,
        description: missionPrompt,
        review: reviewPreview,
        approval: {
          approval_id: approvalReceipt.approval_id,
          fingerprint: approvalReceipt.fingerprint,
          receipt_digest: approvalReceipt.receipt_digest,
        },
      });
      window.sessionStorage.setItem(REPO_HANDOFF_STORAGE_KEY, JSON.stringify(handoff));
      router.push("/chat?fromRepo=1");
    } catch (launchError) {
      if (launchError instanceof Error && /approval/i.test(launchError.message)) {
        setApprovalReceipt(null);
      }
      setError(launchError instanceof Error ? launchError.message : "Unable to launch repo mission.");
    } finally {
      setLaunching(false);
    }
  }

  const step2Locked = !importComplete;
  const step3Locked = !importComplete || selectedFiles.length === 0;
  const step4Locked =
    step3Locked ||
    !approvalReceipt ||
    !reviewPreview ||
    reviewPreview.review_fingerprint !== approvalReceipt.fingerprint;

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="Repository Import & Workspace"
        title="Repository Intake and Mission Configuration"
        description="Import a repository ZIP archive, local directory, or Git URL into a Git-backed baseline workspace, review scope, then launch with the PM Agent."
      />

      <Panel title="Step 1: Import Repository Source" className="step-panel">
        <div className="inline-actions" style={{ marginBottom: "12px" }} role="tablist" aria-label="Repository source mode">
          <button
            type="button"
            className={sourceMode === "zip" ? "active" : "secondary"}
            onClick={() => {
              setSourceMode("zip");
              resetImportResults();
              setError(null);
            }}
          >
            ZIP Archive
          </button>
          <button
            type="button"
            className={sourceMode === "local" ? "active" : "secondary"}
            onClick={() => {
              setSourceMode("local");
              resetImportResults();
              setError(null);
            }}
          >
            Local Folder
          </button>
          <button
            type="button"
            className={sourceMode === "git" ? "active" : "secondary"}
            onClick={() => {
              setSourceMode("git");
              resetImportResults();
              setError(null);
            }}
          >
            Git URL
          </button>
        </div>

        {sourceMode === "zip" && (
          <>
            <label htmlFor="repo-archive">Repository ZIP archive</label>
            <div className="repo-url-row">
              <input
                id="repo-archive"
                type="file"
                accept=".zip,application/zip"
                onChange={(event) => {
                  setArchiveFile(event.target.files?.[0] ?? null);
                  resetImportResults();
                  setError(null);
                }}
                style={{ flex: 1 }}
              />
              {archiveFile && (
                <span className="repo-local-hint muted">
                  {archiveFile.name} - {formatBytes(archiveFile.size)}
                </span>
              )}
            </div>
          </>
        )}

        {sourceMode === "local" && (
          <div style={{ marginBottom: "12px" }}>
            <label htmlFor="repo-local-path">Local repository directory path</label>
            <input
              id="repo-local-path"
              type="text"
              value={localPath}
              onChange={(event) => {
                setLocalPath(event.target.value);
                resetImportResults();
                setError(null);
              }}
              placeholder="C:/projects/my-app or /workspace/my-app"
              style={{ width: "100%" }}
            />
          </div>
        )}

        {sourceMode === "git" && (
          <div style={{ marginBottom: "12px" }}>
            <label htmlFor="repo-git-url">Git repository URL</label>
            <input
              id="repo-git-url"
              type="text"
              value={gitUrl}
              onChange={(event) => {
                setGitUrl(event.target.value);
                resetImportResults();
                setError(null);
              }}
              placeholder="https://github.com/org/repo.git"
              style={{ width: "100%" }}
            />
          </div>
        )}
        <div className="filters-grid">
          <label>
            Display name
            <input
              type="text"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="sample-platform"
            />
          </label>
          <label>
            Source ref
            <input
              type="text"
              value={sourceRef}
              onChange={(event) => setSourceRef(event.target.value)}
              placeholder="main or commit SHA"
            />
          </label>
          <label>
            Subdirectory
            <input
              type="text"
              value={subdirectory}
              onChange={(event) => setSubdirectory(event.target.value)}
              placeholder="/"
            />
          </label>
          <label>
            Max files
            <input
              type="number"
              min={50}
              max={800}
              value={maxFiles}
              onChange={(event) =>
                setMaxFiles(Math.max(50, Math.min(800, Number(event.target.value) || 300)))
              }
            />
          </label>
        </div>
        <div className="inline-actions">
          <button
            type="button"
            onClick={() => void importRepository()}
            disabled={
              importing ||
              (sourceMode === "zip"
                ? !archiveFile
                : sourceMode === "local"
                  ? !localPath.trim()
                  : !gitUrl.trim())
            }
          >
            {importing
              ? "Importing..."
              : sourceMode === "zip"
                ? "Import ZIP"
                : sourceMode === "local"
                  ? "Import Local Workspace"
                  : "Clone Git Workspace"}
          </button>
        </div>
        {importSnapshot && (
          <ul className="summary-list">
            <li>
              <strong>Source</strong>
              <span>{importSnapshot.repository.display_name} ({importSnapshot.repository.source})</span>
            </li>
            {importSnapshot.repository.workspace_id && (
              <li>
                <strong>Workspace ID</strong>
                <span>{importSnapshot.repository.workspace_id}</span>
              </li>
            )}
            {importSnapshot.repository.base_commit && (
              <li>
                <strong>Base commit</strong>
                <span>{importSnapshot.repository.base_commit.slice(0, 12)}</span>
              </li>
            )}
            <li>
              <strong>Source ref</strong>
              <span>{importSnapshot.repository.source_ref || "zip-upload"}</span>
            </li>
            <li>
              <strong>Archive SHA-256</strong>
              <span>{importSnapshot.repository.archive_sha256.slice(0, 12)}</span>
            </li>
            <li>
              <strong>Root prefix</strong>
              <span>{importSnapshot.repository.root_prefix || "/"}</span>
            </li>
            <li>
              <strong>Files</strong>
              <span>{importSnapshot.stats.total_files}</span>
            </li>
            <li>
              <strong>Estimated lines</strong>
              <span>{importSnapshot.stats.estimated_total_lines}</span>
            </li>
          </ul>
        )}
        {importLogs.length > 0 && (
          <ul className="summary-list">
            {importLogs.map((line) => (
              <li key={line}>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Step 2: Select Files and Overlay Actions" className={`step-panel ${step2Locked ? "locked" : ""}`}>
        {step2Locked && (
          <EmptyState title="File selection unlocks after import" compact>
            Import a ZIP archive to preview files, choose inclusion scope, and assign overlay actions.
          </EmptyState>
        )}
        {!step2Locked && (
          <>
            <div className="inline-actions">
              <input
                type="text"
                value={fileFilter}
                onChange={(event) => setFileFilter(event.target.value)}
                placeholder="Filter files by path..."
              />
              <button type="button" className="secondary-button" onClick={() => selectTopFiles(25)}>
                Select Top 25
              </button>
              <button type="button" className="secondary-button" onClick={() => selectTopFiles(100)}>
                Select Top 100
              </button>
              <button type="button" className="secondary-button" onClick={clearSelection}>
                Clear Selection
              </button>
            </div>
            <ul className="repo-file-list">
              {visibleFiles.map((file) => (
                <li key={file.path} className="repo-file-item">
                  <label className="inline-toggle">
                    <input type="checkbox" checked={file.selected} onChange={() => toggleFile(file.path)} />
                    <span>
                      {file.path} - {file.language} - {formatBytes(file.bytes)} - {file.estimatedLines} LOC
                    </span>
                  </label>
                  <label>
                    Overlay
                    <select
                      value={file.overlayAction}
                      onChange={(event) =>
                        updateOverlay(file.path, event.target.value as RepoFileOverlayAction)
                      }
                    >
                      <option value="include">Include (direct edits)</option>
                      <option value="reference">Reference (context only)</option>
                      <option value="exclude">Exclude</option>
                    </select>
                  </label>
                </li>
              ))}
            </ul>
            <p className="help-text">
              Selected: {selectedFiles.length} files - {selectedLines} estimated lines - Overlays: include{" "}
              {overlayCounts.include}, reference {overlayCounts.reference}, exclude {overlayCounts.exclude}
            </p>
          </>
        )}
      </Panel>

      <Panel title="Step 3: Review Scope and Apply Gate" className={`step-panel ${step3Locked ? "locked" : ""}`}>
        {step3Locked && (
          <EmptyState title="Review gate requires selected files" compact>
            Select at least one file in Step 2, then generate a review artifact before launch.
          </EmptyState>
        )}
        {!step3Locked && (
          <div className="stack-gap">
            <div className="mission-type-grid">
              <button
                type="button"
                className={`secondary-button ${missionType === "analyze" ? "active-tab" : ""}`}
                onClick={() => selectMissionType("analyze")}
              >
                Analyze
              </button>
              <button
                type="button"
                className={`secondary-button ${missionType === "update" ? "active-tab" : ""}`}
                onClick={() => selectMissionType("update")}
              >
                Update
              </button>
              <button
                type="button"
                className={`secondary-button ${missionType === "add_feature" ? "active-tab" : ""}`}
                onClick={() => selectMissionType("add_feature")}
              >
                Add Feature
              </button>
              <button
                type="button"
                className={`secondary-button ${missionType === "port" ? "active-tab" : ""}`}
                onClick={() => selectMissionType("port")}
              >
                Port
              </button>
              <button
                type="button"
                className={`secondary-button ${missionType === "refactor" ? "active-tab" : ""}`}
                onClick={() => selectMissionType("refactor")}
              >
                Refactor
              </button>
            </div>
            <label htmlFor="repo-mission-description">Mission description</label>
            <textarea
              id="repo-mission-description"
              rows={4}
              value={description}
              onChange={(event) => updateMissionDescription(event.target.value)}
              placeholder="Describe requested changes, business constraints, and expected outputs."
            />
            <ul className="summary-list">
              {selectedFiles.map((file) => (
                <li key={`${file.path}-overlay`}>
                  <strong>{file.path}</strong>
                  <span>
                    {overlayLabel(file.overlayAction)} - {file.estimatedLines} LOC
                  </span>
                </li>
              ))}
            </ul>
            <div className="inline-actions">
              <button type="button" onClick={() => void generateReview()} disabled={reviewing}>
                {reviewing ? "Generating Review..." : "Generate Repository Review"}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void applyReviewGate()}
                disabled={!reviewPreview || approving}
              >
                {approving
                  ? "Applying Review Gate..."
                  : approvalReceipt
                    ? "Reapply Review Gate"
                    : "Apply Review Gate"}
              </button>
            </div>
            {approvalReceipt && (
              <p className="success-box">
                Review gate persisted at {formatDateTime(approvalReceipt.approved_at)}.
              </p>
            )}
            {!approvalReceipt && reviewPreview && (
              <p className="warning-box">
                Review generated at {formatDateTime(reviewPreview.generated_at)}. Apply gate to unlock mission launch.
              </p>
            )}
            {reviewPreview && (
              <div className="stack-gap">
                {reviewPreview.notice && <p className="warning-box">{reviewPreview.notice}</p>}
                <h3 className="section-title">Review Summary</h3>
                <ul className="summary-list">
                  {reviewPreview.diff_summary.map((item) => (
                    <li key={item}>
                      <span>{item}</span>
                    </li>
                  ))}
                  {reviewPreview.diff_summary.length === 0 && (
                    <li>
                      <span>No review summary lines returned by the review service.</span>
                    </li>
                  )}
                </ul>
                <h3 className="section-title">Repository Scope</h3>
                <ul className="summary-list">
                  {reviewPreview.files.map((file) => (
                    <li key={`${file.overlay_action}-${file.path}`}>
                      <strong>{file.path}</strong>
                      <span>
                        {overlayLabel(file.overlay_action)} - {file.language} - {file.summary}
                      </span>
                    </li>
                  ))}
                </ul>
                <h3 className="section-title">Execution Plan</h3>
                <ul className="summary-list">
                  {reviewPreview.plan.map((step) => (
                    <li key={step.title}>
                      <strong>{step.title}</strong>
                      <span>{step.description}</span>
                    </li>
                  ))}
                </ul>
                <h3 className="section-title">Risk Notes</h3>
                <ul className="summary-list">
                  {reviewPreview.risk_notes.map((risk) => (
                    <li key={risk}>
                      <span>{risk}</span>
                    </li>
                  ))}
                  {reviewPreview.risk_notes.length === 0 && (
                    <li>
                      <span>No additional risk notes returned.</span>
                    </li>
                  )}
                </ul>
                <h3 className="section-title">Test Plan</h3>
                <ul className="summary-list">
                  {reviewPreview.test_plan.map((step) => (
                    <li key={step}>
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Panel>

      <Panel title="Step 4: Continue with PM" className={`step-panel ${step4Locked ? "locked" : ""}`}>
        {step4Locked && (
          <EmptyState title="PM handoff is locked by review approval" compact>
            Apply the Step 3 review gate to persist scope approval and unlock the PM Statement of Work.
          </EmptyState>
        )}
        {!step4Locked && (
          <>
            <ul className="summary-list">
              <li>
                <strong>Mission type</strong>
                <span>{missionType}</span>
              </li>
              <li>
                <strong>Requested target language</strong>
                <span>{reviewPreview?.requested_target_language ?? "default specialist fallback"}</span>
              </li>
              <li>
                <strong>Approval receipt</strong>
                <span>{approvalReceipt?.approval_id ?? "n/a"}</span>
              </li>
              <li>
                <strong>Bundled files</strong>
                <span>
                  {reviewPreview?.source_stats.bundled_files} / {reviewPreview?.source_stats.selected_files}
                </span>
              </li>
              <li>
                <strong>Source bundle size</strong>
                <span>{reviewPreview ? `${reviewPreview.source_stats.source_characters} chars` : "n/a"}</span>
              </li>
            </ul>
            <div className="inline-actions">
              <button type="button" onClick={() => void launchRepoMission()} disabled={launching}>
                {launching ? "Opening PM..." : "Draft SOW with PM"}
              </button>
            </div>
          </>
        )}
      </Panel>

      {error && (
        <SystemMessage tone="critical" title="Repository workflow needs attention">
          {error}
        </SystemMessage>
      )}
    </div>
  );
}
