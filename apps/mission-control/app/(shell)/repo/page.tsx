"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { createBuilderPreview, createMission } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { sanitizeUserText } from "../../lib/security";
import type { BuilderPreviewResponse } from "../../lib/types";

type RepoFileOverlayAction = "include" | "reference" | "exclude";

type RepoFile = {
  path: string;
  language: string;
  bytes: number;
  estimatedLines: number;
  selected: boolean;
  overlayAction: RepoFileOverlayAction;
};

type MissionType = "analyze" | "update" | "add_feature" | "refactor";

type RepoImportResponse = {
  repository: {
    owner: string;
    repo: string;
    branch: string;
    default_branch: string;
    private: boolean;
    html_url: string;
  };
  files: Array<{
    path: string;
    language: string;
    bytes: number;
    estimated_lines: number;
  }>;
  stats: {
    total_files: number;
    estimated_total_lines: number;
    selected_subdirectory: string;
    truncated: boolean;
    skipped_large_files: number;
  };
  logs: string[];
};

function isValidGithubUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && parsed.hostname.toLowerCase() === "github.com";
  } catch {
    return false;
  }
}

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

function reviewConstraints(params: {
  snapshot: RepoImportResponse | null;
  branch: string;
  subdirectory: string;
  selectedFiles: RepoFile[];
  selectedLines: number;
}): string[] {
  const base = [
    `branch=${params.snapshot?.repository.branch || sanitizeUserText(params.branch) || "main"}`,
    `subdirectory=${params.snapshot?.stats.selected_subdirectory || sanitizeUserText(params.subdirectory) || "/"}`,
    `estimated_lines=${params.selectedLines}`,
  ];
  const fileScope = params.selectedFiles.slice(0, 40).map(
    (file) =>
      `file=${file.path};overlay=${file.overlayAction};language=${file.language};lines=${file.estimatedLines}`,
  );
  return [...base, ...fileScope];
}

export default function RepoImportPage() {
  const router = useRouter();

  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [subdirectory, setSubdirectory] = useState("/");
  const [maxFiles, setMaxFiles] = useState(300);
  const [fileFilter, setFileFilter] = useState("");
  const [files, setFiles] = useState<RepoFile[]>([]);
  const [importSnapshot, setImportSnapshot] = useState<RepoImportResponse | null>(null);
  const [missionType, setMissionType] = useState<MissionType | null>(null);
  const [description, setDescription] = useState("");
  const [reviewPreview, setReviewPreview] = useState<BuilderPreviewResponse | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [reviewAppliedAt, setReviewAppliedAt] = useState<string | null>(null);
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
    setReviewAppliedAt(null);
    setReviewPreview(null);
  }

  async function importRepository() {
    const normalizedUrl = sanitizeUserText(repoUrl);
    if (!isValidGithubUrl(normalizedUrl)) {
      setError("Enter a valid https://github.com/<owner>/<repo> repository URL.");
      return;
    }

    setError(null);
    setImporting(true);
    setImportComplete(false);
    setImportLogs(["Validating repository request...", "Fetching repository metadata..."]);
    setImportSnapshot(null);
    setFiles([]);
    setMissionType(null);
    setDescription("");
    resetReviewGate();

    try {
      const response = await fetch("/api/repo/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: normalizedUrl,
          branch: sanitizeUserText(branch),
          subdirectory: sanitizeUserText(subdirectory) || "/",
          max_files: maxFiles,
        }),
      });
      const payload = (await response.json()) as RepoImportResponse & { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Repository import request failed.");
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
    if (selectedFiles.length === 0) {
      setError("Select at least one file before generating diff review.");
      return;
    }

    setError(null);
    setReviewing(true);
    setReviewAppliedAt(null);

    const missionSummary = sanitizeUserText(description);
    const request = [
      `Generate a repository mission review for ${sanitizeUserText(repoUrl)}.`,
      `Selected files: ${selectedFiles.length}.`,
      `Estimated lines: ${selectedLines}.`,
      missionType ? `Requested mission type: ${missionType}.` : "Mission type: pending selection.",
      missionSummary.length > 0
        ? `Mission objective: ${missionSummary}.`
        : "Mission objective: validate selected file overlays and scope.",
    ].join(" ");

    try {
      const preview = await createBuilderPreview({
        request,
        constraints: reviewConstraints({
          snapshot: importSnapshot,
          branch,
          subdirectory,
          selectedFiles,
          selectedLines,
        }),
      });
      setReviewPreview(preview);
    } catch (reviewError) {
      setError(
        reviewError instanceof Error ? reviewError.message : "Unable to generate repository diff review.",
      );
      setReviewPreview(null);
    } finally {
      setReviewing(false);
    }
  }

  function applyReviewGate() {
    if (!reviewPreview) {
      setError("Generate and inspect the review output before applying the gate.");
      return;
    }
    setError(null);
    setReviewAppliedAt(new Date().toISOString());
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
    if (!reviewAppliedAt) {
      setError("Apply Step 3 review gate before launching the mission.");
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
      const missionPrompt =
        sanitizeUserText(description) ||
        `Run ${missionType} mission for ${selectedFiles.length} files from ${repoUrl}`;
      const mission = await createMission({
        prompt: missionPrompt,
        requested_target_language: "python",
        metadata: {
          source: "repo-import-ui",
          repo_url: sanitizeUserText(repoUrl),
          branch: importSnapshot?.repository.branch || sanitizeUserText(branch) || "main",
          subdirectory:
            importSnapshot?.stats.selected_subdirectory || sanitizeUserText(subdirectory) || "/",
          mission_type: missionType,
          selected_files: selectedFiles.map((item) => item.path),
          selected_file_overlays: selectedFiles.map((item) => ({
            path: item.path,
            overlay_action: item.overlayAction,
            estimated_lines: item.estimatedLines,
            language: item.language,
          })),
          estimated_lines: selectedLines,
          repository_owner: importSnapshot?.repository.owner,
          repository_name: importSnapshot?.repository.repo,
          review_gate_applied_at: reviewAppliedAt,
          review_request_id: reviewPreview?.request_id,
        },
      });
      router.push(`/missions/${mission.mission_id}`);
    } catch (launchError) {
      setError(launchError instanceof Error ? launchError.message : "Unable to launch repo mission.");
    } finally {
      setLaunching(false);
    }
  }

  const step2Locked = !importComplete;
  const step3Locked = !importComplete || selectedFiles.length === 0;
  const step4Locked = step3Locked || !reviewAppliedAt;

  return (
    <div className="page shell-page">
      <PageHeader
        eyebrow="GitHub Import"
        title="Repository Intake and Mission Configuration"
        description="Import repository metadata, layer file-level mission overlays, review generated diff scope, then launch."
      />

      <Panel title="Step 1: Import Repository" className="step-panel">
        <label htmlFor="repo-url">GitHub repository URL</label>
        <input
          id="repo-url"
          type="url"
          value={repoUrl}
          onChange={(event) => setRepoUrl(event.target.value)}
          placeholder="https://github.com/org/project"
        />
        <div className="filters-grid">
          <label>
            Branch
            <input
              type="text"
              value={branch}
              onChange={(event) => setBranch(event.target.value)}
              placeholder="main"
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
              onChange={(event) => setMaxFiles(Math.max(50, Math.min(800, Number(event.target.value) || 300)))}
            />
          </label>
        </div>
        <div className="inline-actions">
          <button type="button" onClick={() => void importRepository()} disabled={importing}>
            {importing ? "Importing..." : "Import Repository"}
          </button>
        </div>
        {importSnapshot && (
          <ul className="summary-list">
            <li>
              <strong>Repository</strong>
              <span>
                {importSnapshot.repository.owner}/{importSnapshot.repository.repo}
              </span>
            </li>
            <li>
              <strong>Branch</strong>
              <span>{importSnapshot.repository.branch}</span>
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
        {step2Locked && <p className="muted">Complete Step 1 to unlock file selection.</p>}
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

      <Panel title="Step 3: Diff Review and Apply Gate" className={`step-panel ${step3Locked ? "locked" : ""}`}>
        {step3Locked && <p className="muted">Select at least one file in Step 2 to run diff review.</p>}
        {!step3Locked && (
          <div className="stack-gap">
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
                {reviewing ? "Generating Review..." : "Generate Diff Review"}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={applyReviewGate}
                disabled={!reviewPreview}
              >
                {reviewAppliedAt ? "Reapply Review Gate" : "Apply Review Gate"}
              </button>
            </div>
            {reviewAppliedAt && (
              <p className="success-box">Review gate applied at {formatDateTime(reviewAppliedAt)}.</p>
            )}
            {!reviewAppliedAt && reviewPreview && (
              <p className="warning-box">
                Review generated at {formatDateTime(reviewPreview.generated_at)}. Apply gate to unlock mission launch.
              </p>
            )}
            {reviewPreview && (
              <div className="stack-gap">
                <h3 className="section-title">Diff Summary</h3>
                <ul className="summary-list">
                  {reviewPreview.diff_summary.map((item) => (
                    <li key={item}>
                      <span>{item}</span>
                    </li>
                  ))}
                  {reviewPreview.diff_summary.length === 0 && (
                    <li>
                      <span>No diff summary lines returned by preview service.</span>
                    </li>
                  )}
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

      <Panel title="Step 4: Configure Mission" className={`step-panel ${step4Locked ? "locked" : ""}`}>
        {step4Locked && <p className="muted">Apply Step 3 review gate to unlock mission configuration and launch.</p>}
        {!step4Locked && (
          <>
            <div className="mission-type-grid">
              <button
                type="button"
                className={`secondary-button ${missionType === "analyze" ? "active-tab" : ""}`}
                onClick={() => setMissionType("analyze")}
              >
                Analyze
              </button>
              <button
                type="button"
                className={`secondary-button ${missionType === "update" ? "active-tab" : ""}`}
                onClick={() => setMissionType("update")}
              >
                Update
              </button>
              <button
                type="button"
                className={`secondary-button ${missionType === "add_feature" ? "active-tab" : ""}`}
                onClick={() => setMissionType("add_feature")}
              >
                Add Feature
              </button>
              <button
                type="button"
                className={`secondary-button ${missionType === "refactor" ? "active-tab" : ""}`}
                onClick={() => setMissionType("refactor")}
              >
                Refactor
              </button>
            </div>
            <label htmlFor="repo-mission-description">Mission description</label>
            <textarea
              id="repo-mission-description"
              rows={4}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Describe requested changes, business constraints, and expected outputs."
            />
            <div className="inline-actions">
              <button type="button" onClick={() => void launchRepoMission()} disabled={launching}>
                {launching ? "Launching..." : "Launch Mission"}
              </button>
            </div>
          </>
        )}
      </Panel>

      {error && <p className="error-box">{error}</p>}
    </div>
  );
}
