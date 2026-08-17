import { createHash } from "node:crypto";

import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import {
  branchLooksValid,
  estimateLines,
  languageFromPath,
  normalizeSubdirectory,
  requestedLanguageFromPath,
} from "../shared";
import { indexZipArchive, readZipTextFiles } from "../archive";
import {
  archiveLooksLikeZip,
  badRequest,
  formString,
  isUploadedArchive,
  RepoZipRequestError,
  sanitizeDisplayName,
  stripZipExtension,
  uploadedArchiveBuffer,
} from "../upload";

export const runtime = "nodejs";

type RepoFileOverlayAction = "include" | "reference" | "exclude";
type MissionType = "analyze" | "update" | "add_feature" | "refactor" | "port";

type RepoReviewRequest = {
  display_name?: string;
  source_ref?: string;
  branch?: string;
  archive_sha256?: string;
  subdirectory?: string;
  mission_type?: MissionType;
  description?: string;
  selected_files?: Array<{
    path?: string;
    overlay_action?: RepoFileOverlayAction;
    language?: string;
    bytes?: number;
    estimated_lines?: number;
  }>;
};

type ReviewFileRecord = {
  path: string;
  overlay_action: Exclude<RepoFileOverlayAction, "exclude">;
  language: string;
  requested_language: string | null;
  bytes: number;
  estimated_lines: number;
  summary: string;
  content_excerpt: string;
  text_available: boolean;
  included_in_source: boolean;
  truncated_in_source: boolean;
  sha: string | null;
};

type ReviewResponse = {
  request_id: string;
  review_fingerprint: string;
  source: "repo-review";
  generated_at: string;
  repository: {
    source: "zip";
    owner: string;
    repo: string;
    branch: string;
    html_url: string | null;
    selected_subdirectory: string;
    archive_id: string;
    archive_sha256: string;
    display_name: string;
    source_ref: string;
    root_prefix: string;
  };
  mission_type: MissionType;
  requested_target_language: string | null;
  source_code: string;
  source_stats: {
    selected_files: number;
    include_files: number;
    reference_files: number;
    source_characters: number;
    bundled_files: number;
    truncated_files: number;
    unavailable_files: number;
  };
  plan: Array<{ title: string; description: string }>;
  diff_summary: string[];
  risk_notes: string[];
  test_plan: string[];
  files: ReviewFileRecord[];
  notice?: string;
};

type SanitizedSelectedFile = {
  path: string;
  overlay_action: Exclude<RepoFileOverlayAction, "exclude">;
  bytes: number;
  estimated_lines: number;
  language: string;
};

type FetchedReviewFile = SanitizedSelectedFile & {
  requested_language: string | null;
  text: string;
  text_available: boolean;
  sha: string | null;
  summary: string;
  content_excerpt: string;
};

const MAX_SELECTED_FILES = 120;
const DESCRIPTION_LIMIT = 2_000;
const SOURCE_CODE_LIMIT = 480_000;
const INCLUDE_FILE_SOFT_LIMIT = 80_000;
const REFERENCE_FILE_SOFT_LIMIT = 12_000;
const EXCERPT_LINE_LIMIT = 20;
const EXCERPT_CHAR_LIMIT = 1_500;

const MISSION_TYPES = new Set<MissionType>(["analyze", "update", "add_feature", "refactor", "port"]);

function parseSelectedFilesField(value: FormDataEntryValue | null): RepoReviewRequest["selected_files"] | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  try {
    const parsed = JSON.parse(value) as RepoReviewRequest["selected_files"];
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function sanitizeText(value: string | undefined): string {
  return String(value ?? "")
    .replace(/[\u0000-\u0008\u000B-\u001F\u007F]/g, "")
    .trim();
}

function sanitizeSelectedFiles(
  rawFiles: RepoReviewRequest["selected_files"] | null,
  normalizedSubdirectory: string,
): SanitizedSelectedFile[] | null {
  if (!Array.isArray(rawFiles) || rawFiles.length === 0) {
    return null;
  }
  const normalizedSubdir = normalizedSubdirectory === "/" ? "" : normalizedSubdirectory.slice(1);
  const accepted: SanitizedSelectedFile[] = [];
  const seenPaths = new Set<string>();

  for (const rawFile of rawFiles) {
    if (!rawFile || typeof rawFile !== "object") {
      continue;
    }
    const path = sanitizeText(typeof rawFile.path === "string" ? rawFile.path : "");
    const overlayAction = rawFile.overlay_action;
    if (!path || (overlayAction !== "include" && overlayAction !== "reference")) {
      continue;
    }
    if (
      path.startsWith("/") ||
      path.includes("\\") ||
      path.split("/").some((segment) => segment === "..")
    ) {
      return null;
    }
    if (normalizedSubdir && !path.startsWith(`${normalizedSubdir}/`)) {
      return null;
    }
    if (seenPaths.has(path)) {
      continue;
    }
    seenPaths.add(path);

    const bytes =
      typeof rawFile.bytes === "number" && Number.isFinite(rawFile.bytes) && rawFile.bytes > 0
        ? Math.floor(rawFile.bytes)
        : 0;
    const estimatedLines =
      typeof rawFile.estimated_lines === "number" &&
      Number.isFinite(rawFile.estimated_lines) &&
      rawFile.estimated_lines > 0
        ? Math.floor(rawFile.estimated_lines)
        : estimateLines(bytes);
    const language =
      sanitizeText(typeof rawFile.language === "string" ? rawFile.language : "") ||
      languageFromPath(path);
    accepted.push({
      path,
      overlay_action: overlayAction,
      bytes,
      estimated_lines: estimatedLines,
      language,
    });
  }

  if (accepted.length === 0 || accepted.length > MAX_SELECTED_FILES) {
    return null;
  }
  return accepted;
}

function isLikelyBinaryText(value: string): boolean {
  if (!value) {
    return false;
  }
  let controlChars = 0;
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code === 0) {
      return true;
    }
    if (code < 32 && code !== 9 && code !== 10 && code !== 13) {
      controlChars += 1;
    }
  }
  return controlChars / Math.max(1, value.length) > 0.03;
}

function firstMeaningfulLine(text: string): string | null {
  const lines = text.split(/\r?\n/);
  for (const line of lines) {
    const normalized = line.trim();
    if (!normalized) {
      continue;
    }
    if (
      normalized.startsWith("//") ||
      normalized.startsWith("#") ||
      normalized.startsWith("/*") ||
      normalized.startsWith("*")
    ) {
      continue;
    }
    return normalized;
  }
  return null;
}

function summarizeFileContent(path: string, language: string, text: string): string {
  const meaningfulLine = firstMeaningfulLine(text);
  const lowerPath = path.toLowerCase();
  const lowerText = text.toLowerCase();

  if (lowerPath.endsWith(".tsx") || lowerPath.endsWith(".jsx")) {
    if (lowerText.includes("\"use client\"") || lowerText.includes("'use client'")) {
      return `Client ${language} component focused on ${meaningfulLine ?? "interactive UI state"}.`;
    }
    return `${language} component or route focused on ${meaningfulLine ?? "rendered UI state"}.`;
  }
  if (lowerPath.endsWith(".ts") || lowerPath.endsWith(".js")) {
    if (lowerText.includes("export async function") || lowerPath.includes("/api/")) {
      return `${language} API or service module centered on ${meaningfulLine ?? "request handling"}.`;
    }
    return `${language} module centered on ${meaningfulLine ?? "application behavior"}.`;
  }
  if (lowerPath.endsWith(".py")) {
    if (
      lowerText.includes("fastapi") ||
      lowerText.includes("router = apirouter") ||
      lowerText.includes("@app.")
    ) {
      return `Python service module handling ${meaningfulLine ?? "API flow and orchestration"}.`;
    }
    return `Python module focused on ${meaningfulLine ?? "runtime behavior"}.`;
  }
  if (lowerPath.endsWith(".md")) {
    return `Documentation file covering ${meaningfulLine ?? "repository context and operator guidance"}.`;
  }
  if (lowerText.includes("create table") || lowerText.includes("alter table")) {
    return `Schema or SQL migration focused on ${meaningfulLine ?? "database structure changes"}.`;
  }
  return `${language} file focused on ${meaningfulLine ?? "repository implementation details"}.`;
}

function buildContentExcerpt(text: string): string {
  const lines = text.split(/\r?\n/).slice(0, EXCERPT_LINE_LIMIT);
  const excerpt = lines.join("\n").trim();
  if (excerpt.length <= EXCERPT_CHAR_LIMIT) {
    return excerpt;
  }
  return `${excerpt.slice(0, EXCERPT_CHAR_LIMIT - 3)}...`;
}

function inferRequestedTargetLanguage(files: FetchedReviewFile[]): string | null {
  const preferredScopes = [
    files.filter((file) => file.overlay_action === "include"),
    files,
  ];

  for (const scope of preferredScopes) {
    const scores = new Map<string, number>();
    for (const file of scope) {
      if (!file.requested_language) {
        continue;
      }
      const weight = Math.max(file.bytes, file.estimated_lines * 45, 1);
      scores.set(file.requested_language, (scores.get(file.requested_language) ?? 0) + weight);
    }
    if (scores.size === 0) {
      continue;
    }

    let winningLanguage: string | null = null;
    let winningScore = -1;
    for (const [language, score] of scores.entries()) {
      if (score > winningScore) {
        winningLanguage = language;
        winningScore = score;
      }
    }
    return winningLanguage;
  }

  return null;
}

function canonicalReviewFingerprint(params: {
  owner: string;
  repo: string;
  branch: string;
  subdirectory: string;
  archiveSha256: string;
  missionType: MissionType;
  description: string;
  files: FetchedReviewFile[];
}): string {
  const canonical = JSON.stringify({
    repository: `${params.owner}/${params.repo}`,
    branch: params.branch,
    subdirectory: params.subdirectory,
    archive_sha256: params.archiveSha256,
    mission_type: params.missionType,
    description: params.description,
    files: params.files.map((file) => ({
      path: file.path,
      overlay_action: file.overlay_action,
      sha: file.sha,
      bytes: file.bytes,
      requested_language: file.requested_language,
    })),
  });
  return createHash("sha256").update(canonical).digest("hex");
}

function buildSourceBundle(params: {
  owner: string;
  repo: string;
  branch: string;
  subdirectory: string;
  missionType: MissionType;
  description: string;
  reviewFingerprint: string;
  requestedTargetLanguage: string | null;
  files: FetchedReviewFile[];
}): {
  sourceCode: string;
  bundledPaths: Set<string>;
  truncatedPaths: Set<string>;
  unavailablePaths: Set<string>;
  notice: string | undefined;
} {
  const sections: string[] = [
    "# Repository Source Bundle",
    `repository: ${params.owner}/${params.repo}`,
    `branch: ${params.branch}`,
    `subdirectory: ${params.subdirectory}`,
    `mission_type: ${params.missionType}`,
    `review_fingerprint: ${params.reviewFingerprint}`,
    `requested_target_language: ${params.requestedTargetLanguage ?? "auto"}`,
    `objective: ${params.description || `Execute ${params.missionType} work against the selected repository scope.`}`,
    "",
    "## File Scope",
    ...params.files.map(
      (file) =>
        `- ${file.overlay_action}: ${file.path} (${file.language}, ${file.estimated_lines} LOC, ${file.bytes} bytes)`,
    ),
    "",
  ];

  const bundledPaths = new Set<string>();
  const truncatedPaths = new Set<string>();
  const unavailablePaths = new Set<string>();

  let current = sections.join("\n");
  for (const file of params.files) {
    if (!file.text_available) {
      unavailablePaths.add(file.path);
      continue;
    }

    const fileHeader = [
      "",
      `## FILE ${file.path}`,
      `overlay: ${file.overlay_action}`,
      `language: ${file.language}`,
      `summary: ${file.summary}`,
      "",
    ].join("\n");
    const perFileLimit =
      file.overlay_action === "include" ? INCLUDE_FILE_SOFT_LIMIT : REFERENCE_FILE_SOFT_LIMIT;
    const rawBody = file.overlay_action === "include" ? file.text : file.content_excerpt || file.text;
    const availableRoom = SOURCE_CODE_LIMIT - current.length - fileHeader.length - 64;

    if (availableRoom <= 0) {
      truncatedPaths.add(file.path);
      continue;
    }

    let body = rawBody.slice(0, Math.min(perFileLimit, availableRoom));
    const truncated = body.length < rawBody.length;
    if (truncated) {
      body = `${body}\n\n[truncated to fit source bundle budget]`;
    }
    const nextSection = `${fileHeader}${body}\n`;
    if (current.length + nextSection.length > SOURCE_CODE_LIMIT) {
      truncatedPaths.add(file.path);
      continue;
    }
    current += nextSection;
    bundledPaths.add(file.path);
    if (truncated) {
      truncatedPaths.add(file.path);
    }
  }

  let notice: string | undefined;
  if (truncatedPaths.size > 0 || unavailablePaths.size > 0) {
    const notices: string[] = [];
    if (truncatedPaths.size > 0) {
      notices.push(
        `${truncatedPaths.size} file${truncatedPaths.size === 1 ? "" : "s"} were truncated or omitted to stay within the mission source bundle limit.`,
      );
    }
    if (unavailablePaths.size > 0) {
      notices.push(
        `${unavailablePaths.size} file${unavailablePaths.size === 1 ? "" : "s"} were treated as non-text and left out of the bundle body.`,
      );
    }
    notice = notices.join(" ");
  }

  return { sourceCode: current, bundledPaths, truncatedPaths, unavailablePaths, notice };
}

function buildPlan(params: {
  files: FetchedReviewFile[];
  missionType: MissionType;
  description: string;
}): Array<{ title: string; description: string }> {
  const includePaths = params.files
    .filter((file) => file.overlay_action === "include")
    .map((file) => file.path)
    .slice(0, 4);
  const referencePaths = params.files
    .filter((file) => file.overlay_action === "reference")
    .map((file) => file.path)
    .slice(0, 4);

  const missionLineByType: Record<MissionType, string> = {
    analyze:
      "Inspect the selected repository scope and extract implementation intent before any downstream execution.",
    update:
      "Apply the requested update within the include scope while preserving the current repository contract.",
    add_feature:
      "Add the requested feature inside the selected repository scope and preserve surrounding integration points.",
    refactor:
      "Refactor the selected implementation while preserving observable behavior and existing repository contracts.",
    port:
      "Port the selected repository scope to the requested target language while preserving observable behavior.",
  };

  const plan = [
    {
      title: "Lock Approved Scope",
      description: missionLineByType[params.missionType],
    },
    {
      title: "Edit Direct Files",
      description:
        includePaths.length > 0
          ? `Direct-edit scope is ${includePaths.join(", ")}.`
          : "No direct-edit files were selected.",
    },
  ];

  if (referencePaths.length > 0) {
    plan.push({
      title: "Preserve Reference Context",
      description: `Reference-only files inform surrounding contracts: ${referencePaths.join(", ")}.`,
    });
  }
  if (params.description) {
    plan.push({
      title: "Mission Objective",
      description: params.description,
    });
  }
  return plan;
}

function buildRiskNotes(params: {
  files: FetchedReviewFile[];
  requestedTargetLanguage: string | null;
  notice: string | undefined;
}): string[] {
  const riskNotes: string[] = [];
  const languages = Array.from(
    new Set(params.files.map((file) => file.requested_language).filter(Boolean)),
  );
  if (languages.length > 1) {
    riskNotes.push(
      `Selected scope spans multiple specialist languages (${languages.join(", ")}), so cross-module contract drift is possible.`,
    );
  }
  if (params.files.some((file) => file.path.toLowerCase().includes("/api/"))) {
    riskNotes.push("API-facing files are in scope; preserve request/response contracts and error handling.");
  }
  if (params.files.some((file) => file.path.toLowerCase().endsWith(".md"))) {
    riskNotes.push("Documentation files are in scope; keep operator guidance aligned with the shipped implementation.");
  }
  if (params.files.some((file) => file.overlay_action === "reference")) {
    riskNotes.push(
      "Reference-only files will not be edited directly unless they are moved into include scope and re-reviewed.",
    );
  }
  if (!params.requestedTargetLanguage) {
    riskNotes.push(
      "No dominant implementation language was inferred from the selected files, so routing may fall back to the default specialist.",
    );
  }
  if (params.notice) {
    riskNotes.push(params.notice);
  }
  return riskNotes;
}

function buildTestPlan(params: {
  files: FetchedReviewFile[];
  requestedTargetLanguage: string | null;
}): string[] {
  const testPlan = ["Re-run repository review if the selected file scope changes before launch."];

  if (
    params.files.some(
      (file) => file.path.toLowerCase().includes("/api/") || file.path.toLowerCase().endsWith(".py"),
    )
  ) {
    testPlan.push("Run backend or service-level tests covering the edited repository surface.");
  }
  if (
    params.files.some(
      (file) =>
        file.path.toLowerCase().endsWith(".tsx") || file.path.toLowerCase().endsWith(".ts"),
    )
  ) {
    testPlan.push("Run Mission Control TypeScript and Vitest coverage for the touched UI and route logic.");
  }
  if (params.files.some((file) => file.path.toLowerCase().endsWith(".md"))) {
    testPlan.push("Verify that operator-facing documentation still reflects the updated repository behavior.");
  }
  if (
    params.requestedTargetLanguage &&
    !testPlan.some((step) => step.toLowerCase().includes(params.requestedTargetLanguage ?? ""))
  ) {
    testPlan.push(
      `Run focused verification for the ${params.requestedTargetLanguage} specialist path before marking the mission complete.`,
    );
  }
  return testPlan;
}

export async function POST(request: Request) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return badRequest("Repository ZIP review requires multipart/form-data.");
  }

  const archive = formData.get("archive");
  if (!isUploadedArchive(archive)) {
    return badRequest("archive must be a repository .zip file upload.");
  }

  const fileName = String(archive.name ?? "repository.zip").trim() || "repository.zip";
  if (!fileName.toLowerCase().endsWith(".zip")) {
    return badRequest("archive must have a .zip filename.");
  }

  const normalizedSubdirectory = normalizeSubdirectory(formString(formData, "subdirectory") || "/");
  if (normalizedSubdirectory.length > 250) {
    return badRequest("subdirectory path is too long.");
  }

  const sourceRef = formString(formData, "source_ref") || formString(formData, "branch");
  if (sourceRef && !branchLooksValid(sourceRef)) {
    return badRequest("source_ref contains unsupported characters.");
  }

  const missionType = formString(formData, "mission_type") as MissionType;
  if (!missionType || !MISSION_TYPES.has(missionType)) {
    return badRequest("mission_type must be one of analyze, update, add_feature, refactor, or port.");
  }

  const description = sanitizeText(formString(formData, "description")).slice(0, DESCRIPTION_LIMIT);
  if ((missionType === "update" || missionType === "add_feature") && description.length < 3) {
    return badRequest("description must be provided for update and add_feature reviews.");
  }

  const selectedFiles = sanitizeSelectedFiles(
    parseSelectedFilesField(formData.get("selected_files")),
    normalizedSubdirectory,
  );
  if (!selectedFiles) {
    return badRequest("selected_files must include 1-120 valid include/reference file records.");
  }

  let buffer: Buffer;
  try {
    buffer = await uploadedArchiveBuffer(archive);
  } catch (error) {
    if (error instanceof RepoZipRequestError) {
      return NextResponse.json({ detail: error.message }, { status: error.status });
    }
    throw error;
  }
  if (!archiveLooksLikeZip(buffer)) {
    return badRequest("archive must be a valid ZIP file.");
  }

  try {
    const expectedArchiveSha256 = formString(formData, "archive_sha256");
    if (!expectedArchiveSha256) {
      return badRequest("archive_sha256 is required for repository ZIP review.");
    }

    const indexed = await indexZipArchive(
      { kind: "buffer", buffer },
      {
        subdirectory: normalizedSubdirectory,
        maxFiles: MAX_SELECTED_FILES,
        requiredPaths: selectedFiles.map((file) => file.path),
      },
    );
    if (expectedArchiveSha256 !== indexed.stats.archive_sha256) {
      return NextResponse.json(
        { detail: "archive_sha256 does not match the uploaded ZIP archive." },
        { status: 409 },
      );
    }

    const metadataByPath = new Map(indexed.files.map((file) => [file.path, file]));
    const textResults = await readZipTextFiles(
      { kind: "buffer", buffer },
      selectedFiles.map((file) => file.path),
      { rootPrefix: indexed.stats.root_prefix },
    );
    const fetchedFiles = selectedFiles.map((file) => {
      const metadata = metadataByPath.get(file.path);
      if (!metadata) {
        throw new RepoZipRequestError(
          400,
          "Selected file is not available in the uploaded archive: " + file.path,
        );
      }
      const bytes = metadata.bytes;
      const estimatedLines = metadata.estimated_lines > 0 ? metadata.estimated_lines : file.estimated_lines;
      const language = metadata.language || file.language || languageFromPath(file.path);
      const fetched = textResults.get(file.path);
      if (fetched && !("error" in fetched)) {
        const textAvailable = !isLikelyBinaryText(fetched.text);
        return {
          ...file,
          bytes: fetched.bytes,
          estimated_lines: estimatedLines,
          language,
          requested_language: requestedLanguageFromPath(file.path),
          text: fetched.text,
          text_available: textAvailable,
          sha: fetched.sha256,
          summary: textAvailable
            ? summarizeFileContent(file.path, language, fetched.text)
            : "Binary or non-text " + language + " asset retained as metadata only.",
          content_excerpt: textAvailable ? buildContentExcerpt(fetched.text) : "",
        } satisfies FetchedReviewFile;
      }

      if (fetched && "error" in fetched) {
        const message = fetched.error.message;
        if (
          message.includes("appears to be binary") ||
          message.includes("exceeds text read limit") ||
          message.includes("exceeded text read limit") ||
          message.includes("cannot be decoded")
        ) {
          return {
            ...file,
            bytes,
            estimated_lines: estimatedLines,
            language,
            requested_language: requestedLanguageFromPath(file.path),
            text: "",
            text_available: false,
            sha: null,
            summary: "Binary or non-text " + language + " asset retained as metadata only.",
            content_excerpt: "",
          } satisfies FetchedReviewFile;
        }
        throw fetched.error;
      }

      throw new RepoZipRequestError(
        400,
        "Selected file is not available in the uploaded archive: " + file.path,
      );
    });

    const displayName = sanitizeDisplayName(formString(formData, "display_name") || stripZipExtension(fileName));
    const resolvedBranch = sourceRef || "zip-upload";
    const owner = "local";
    const repo = displayName;
    const requestedTargetLanguage = inferRequestedTargetLanguage(fetchedFiles);
    const reviewFingerprint = canonicalReviewFingerprint({
      owner,
      repo,
      branch: resolvedBranch,
      subdirectory: normalizedSubdirectory,
      archiveSha256: indexed.stats.archive_sha256,
      missionType,
      description,
      files: fetchedFiles,
    });
    const bundle = buildSourceBundle({
      owner,
      repo,
      branch: resolvedBranch,
      subdirectory: normalizedSubdirectory,
      missionType,
      description,
      reviewFingerprint,
      requestedTargetLanguage,
      files: fetchedFiles,
    });

    const files: ReviewFileRecord[] = fetchedFiles.map((file) => ({
      path: file.path,
      overlay_action: file.overlay_action,
      language: file.language,
      requested_language: file.requested_language,
      bytes: file.bytes,
      estimated_lines: file.estimated_lines,
      summary: file.summary,
      content_excerpt: file.content_excerpt,
      text_available: file.text_available,
      included_in_source: bundle.bundledPaths.has(file.path),
      truncated_in_source: bundle.truncatedPaths.has(file.path),
      sha: file.sha,
    }));

    const includeCount = files.filter((file) => file.overlay_action === "include").length;
    const referenceCount = files.length - includeCount;
    const archiveId = "repozip-" + indexed.stats.archive_sha256.slice(0, 12);
    const response: ReviewResponse = {
      request_id: "repo-review-" + reviewFingerprint.slice(0, 12),
      review_fingerprint: reviewFingerprint,
      source: "repo-review",
      generated_at: new Date().toISOString(),
      repository: {
        source: "zip",
        owner,
        repo,
        branch: resolvedBranch,
        html_url: null,
        selected_subdirectory: normalizedSubdirectory,
        archive_id: archiveId,
        archive_sha256: indexed.stats.archive_sha256,
        display_name: displayName,
        source_ref: sourceRef,
        root_prefix: indexed.stats.root_prefix,
      },
      mission_type: missionType,
      requested_target_language: requestedTargetLanguage,
      source_code: bundle.sourceCode,
      source_stats: {
        selected_files: files.length,
        include_files: includeCount,
        reference_files: referenceCount,
        source_characters: bundle.sourceCode.length,
        bundled_files: bundle.bundledPaths.size,
        truncated_files: bundle.truncatedPaths.size,
        unavailable_files: bundle.unavailablePaths.size,
      },
      plan: buildPlan({
        files: fetchedFiles,
        missionType,
        description,
      }),
      diff_summary: [
        "Reviewed " + files.length + " selected file" + (files.length === 1 ? "" : "s") + " from uploaded ZIP " + displayName + "@" + resolvedBranch + ".",
        "Direct-edit scope covers " + includeCount + " file" + (includeCount === 1 ? "" : "s") + "; " + referenceCount + " file" + (referenceCount === 1 ? "" : "s") + " remain reference-only.",
        "Primary target language resolved to " + (requestedTargetLanguage ?? "default specialist fallback") + ".",
        "Prepared a repository source bundle with " + bundle.bundledPaths.size + " bundled file" + (bundle.bundledPaths.size === 1 ? "" : "s") + " and " + bundle.sourceCode.length + " characters.",
      ],
      risk_notes: buildRiskNotes({
        files: fetchedFiles,
        requestedTargetLanguage,
        notice: bundle.notice,
      }),
      test_plan: buildTestPlan({
        files: fetchedFiles,
        requestedTargetLanguage,
      }),
      files,
      notice: bundle.notice,
    };

    return NextResponse.json(response);
  } catch (error) {
    if (error instanceof RepoZipRequestError) {
      return NextResponse.json({ detail: error.message }, { status: error.status });
    }
    const message = error instanceof Error ? error.message : "Unknown ZIP parse error.";
    if (message.toLowerCase().includes("zip") || message.toLowerCase().includes("invalid")) {
      return badRequest("Invalid ZIP archive: " + message);
    }
    console.error("Repository ZIP review failed unexpectedly.", error);
    return NextResponse.json(
      { detail: "Repository ZIP review failed unexpectedly." },
      { status: 500 },
    );
  }
}
