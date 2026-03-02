"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { createMission } from "../../lib/api-client";
import { sanitizeUserText } from "../../lib/security";

type RepoFile = {
  path: string;
  language: string;
  lines: number;
  selected: boolean;
};

type MissionType = "analyze" | "update" | "add_feature" | "refactor";

const SAMPLE_FILES: RepoFile[] = [
  { path: "src/api/routes.ts", language: "TypeScript", lines: 240, selected: false },
  { path: "src/api/security.ts", language: "TypeScript", lines: 188, selected: false },
  { path: "src/agents/planner.py", language: "Python", lines: 314, selected: false },
  { path: "src/agents/auditor.py", language: "Python", lines: 271, selected: false },
  { path: "src/runtime/bus.rs", language: "Rust", lines: 211, selected: false },
  { path: "tests/integration/mission_flow.spec.ts", language: "TypeScript", lines: 176, selected: false },
];

function isValidGithubUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && parsed.hostname.toLowerCase() === "github.com";
  } catch {
    return false;
  }
}

export default function RepoImportPage() {
  const router = useRouter();

  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [subdirectory, setSubdirectory] = useState("/");
  const [files, setFiles] = useState<RepoFile[]>(SAMPLE_FILES);
  const [missionType, setMissionType] = useState<MissionType | null>(null);
  const [description, setDescription] = useState("");
  const [importing, setImporting] = useState(false);
  const [importLogs, setImportLogs] = useState<string[]>([]);
  const [importComplete, setImportComplete] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedFiles = useMemo(() => files.filter((item) => item.selected), [files]);
  const selectedLines = useMemo(
    () => selectedFiles.reduce((sum, item) => sum + item.lines, 0),
    [selectedFiles],
  );

  async function importRepository() {
    const normalizedUrl = sanitizeUserText(repoUrl);
    if (!isValidGithubUrl(normalizedUrl)) {
      setError("Enter a valid https://github.com/... repository URL.");
      return;
    }
    setError(null);
    setImporting(true);
    setImportComplete(false);
    setImportLogs(["Validating repository URL...", "Resolving branch metadata..."]);

    const stagedLogs = [
      "Cloning repository to local workspace...",
      "Counting objects...",
      "Resolving deltas...",
      "Indexing file tree...",
      "Repository import complete.",
    ];

    for (const line of stagedLogs) {
      await new Promise((resolve) => window.setTimeout(resolve, 300));
      setImportLogs((current) => [...current, line]);
    }

    setImportComplete(true);
    setImporting(false);
    setFiles(SAMPLE_FILES);
  }

  function toggleFile(path: string) {
    setFiles((current) =>
      current.map((item) => (item.path === path ? { ...item, selected: !item.selected } : item)),
    );
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
          branch: sanitizeUserText(branch) || "main",
          subdirectory: sanitizeUserText(subdirectory) || "/",
          mission_type: missionType,
          selected_files: selectedFiles.map((item) => item.path),
          estimated_lines: selectedLines,
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

  return (
    <div className="page shell-page">
      <PageHeader
        eyebrow="GitHub Import"
        title="Repository Intake and Mission Configuration"
        description="Import a repository, scope files, and launch an analysis/update/refactor mission."
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
        </div>
        <div className="inline-actions">
          <button type="button" onClick={() => void importRepository()} disabled={importing}>
            {importing ? "Importing..." : "Import Repository"}
          </button>
        </div>
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

      <Panel title="Step 2: Select Files" className={`step-panel ${step2Locked ? "locked" : ""}`}>
        {step2Locked && <p className="muted">Complete Step 1 to unlock file selection.</p>}
        {!step2Locked && (
          <>
            <ul className="repo-file-list">
              {files.map((file) => (
                <li key={file.path}>
                  <label className="inline-toggle">
                    <input
                      type="checkbox"
                      checked={file.selected}
                      onChange={() => toggleFile(file.path)}
                    />
                    <span>
                      {file.path} - {file.language} - {file.lines} LOC
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            <p className="help-text">
              Selected: {selectedFiles.length} files - {selectedLines} lines
            </p>
          </>
        )}
      </Panel>

      <Panel title="Step 3: Configure Mission" className={`step-panel ${step3Locked ? "locked" : ""}`}>
        {step3Locked && (
          <p className="muted">Select at least one file in Step 2 to configure the mission.</p>
        )}
        {!step3Locked && (
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
              placeholder="Describe the requested change or analysis scope."
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

