import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import { inferRequestedTargetLanguage } from "../../../lib/language";
import type { BuilderDiffLine, BuilderPreviewFile, BuilderPreviewResponse } from "../../../lib/types";

export const runtime = "nodejs";

type BuilderReviewRequest = {
  request?: string;
  constraints?: string[];
  view_mode?: "desktop" | "tablet" | "mobile";
};

type IndexedFile = {
  path: string;
  absolutePath: string;
  content: string;
};

const INCLUDED_ROOTS = [
  "apps/mission-control/app",
  "apps/mission-control/e2e",
  "services/api-gateway/api_gateway",
  "services/orchestrator/orchestrator",
  "services/pod-worker/pod_worker",
  "tests/services",
  "docs",
];

const ALLOWED_EXTENSIONS = new Set([
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".py",
  ".md",
  ".json",
  ".yaml",
  ".yml",
  ".sql",
]);

function normalizeText(value: string | undefined): string {
  return String(value ?? "")
    .replace(/[\u0000-\u0008\u000B-\u001F\u007F]/g, "")
    .trim();
}

function workspaceRoot(): string {
  return process.env.THEFACTORY_REPO_ROOT?.trim() || path.resolve(process.cwd(), "..", "..");
}

// ---------------------------------------------------------------------------
// collectFiles cache — avoids re-reading the entire workspace on every request.
// The cache is keyed by workspace root and expires after CACHE_TTL_MS.
// ---------------------------------------------------------------------------
const CACHE_TTL_MS = 30_000; // 30 seconds

type FileCacheEntry = {
  files: IndexedFile[];
  expiresAt: number;
};

const _fileCache = new Map<string, FileCacheEntry>();

async function collectFilesCached(root: string): Promise<IndexedFile[]> {
  const now = Date.now();
  const cached = _fileCache.get(root);
  if (cached && cached.expiresAt > now) {
    return cached.files;
  }
  const files = await collectFiles(root);
  _fileCache.set(root, { files, expiresAt: now + CACHE_TTL_MS });
  return files;
}

function tokenize(value: string): string[] {
  return value
    .toLowerCase()
    .split(/[^a-z0-9_]+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 3);
}

function fileRisk(filePath: string): "low" | "medium" | "high" {
  if (filePath.startsWith("services/")) {
    return "high";
  }
  if (filePath.includes("/api/") || filePath.startsWith("tests/")) {
    return "medium";
  }
  return "low";
}

function firstMeaningfulLine(content: string): string {
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    return trimmed;
  }
  return "No non-empty source lines found.";
}

function excerptFromContent(content: string): string {
  return content
    .split(/\r?\n/)
    .slice(0, 14)
    .join("\n")
    .trim()
    .slice(0, 900);
}

async function collectFiles(root: string): Promise<IndexedFile[]> {
  const files: IndexedFile[] = [];

  async function walk(relativeRoot: string): Promise<void> {
    const absoluteRoot = path.join(root, relativeRoot);
    let entries;
    try {
      entries = await fs.readdir(absoluteRoot, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      if (entry.name.startsWith(".")) {
        continue;
      }

      const relativePath = path.join(relativeRoot, entry.name);
      const normalizedRelativePath = relativePath.replace(/\\/g, "/");
      const absolutePath = path.join(root, normalizedRelativePath);

      if (entry.isDirectory()) {
        await walk(normalizedRelativePath);
        continue;
      }

      const extension = path.extname(entry.name).toLowerCase();
      if (!ALLOWED_EXTENSIONS.has(extension)) {
        continue;
      }

      const stat = await fs.stat(absolutePath);
      if (stat.size > 250_000) {
        continue;
      }

      const content = await fs.readFile(absolutePath, "utf-8");
      files.push({
        path: normalizedRelativePath,
        absolutePath,
        content,
      });
    }
  }

  for (const includeRoot of INCLUDED_ROOTS) {
    await walk(includeRoot);
  }

  return files;
}

function scoreFile(indexedFile: IndexedFile, queryTokens: string[]): number {
  const haystack = `${indexedFile.path} ${indexedFile.content.slice(0, 4_000)}`.toLowerCase();
  let score = 0;
  for (const token of queryTokens) {
    if (indexedFile.path.toLowerCase().includes(token)) {
      score += 5;
    }
    const matches = haystack.split(token).length - 1;
    score += matches;
  }
  if (indexedFile.path.includes("/builder/")) {
    score += 2;
  }
  return score;
}

function buildSummary(filePath: string, content: string, request: string): string {
  const anchor = firstMeaningfulLine(content);
  if (filePath.endsWith(".py")) {
    return `Modify Python flow around ${anchor} to satisfy: ${request.slice(0, 80)}.`;
  }
  if (filePath.endsWith(".md")) {
    return `Update documentation context around ${anchor}.`;
  }
  return `Modify ${filePath.split("/").pop()} around ${anchor} to satisfy the staged request.`;
}

function commentLineForFile(filePath: string, request: string, constraints: string[]): string {
  const requestText = request.slice(0, 120);
  const constraintText =
    constraints.length > 0 ? ` | constraints: ${constraints.slice(0, 3).join("; ")}` : "";

  if (filePath.endsWith(".py") || filePath.endsWith(".yml") || filePath.endsWith(".yaml")) {
    return `# builder-intent: ${requestText}${constraintText}`;
  }
  if (filePath.endsWith(".md")) {
    return `<!-- builder-intent: ${requestText}${constraintText} -->`;
  }
  if (filePath.endsWith(".sql")) {
    return `-- builder-intent: ${requestText}${constraintText}`;
  }
  return `// builder-intent: ${requestText}${constraintText}`;
}

function buildPreviewLines(content: string, insertedLine: string): BuilderDiffLine[] {
  const sourceLines = content.split(/\r?\n/);
  const meaningfulIndex = Math.max(
    0,
    sourceLines.findIndex((line) => line.trim().length > 0),
  );
  const contextLine = sourceLines[meaningfulIndex] ?? "";
  const nextLine = sourceLines[meaningfulIndex + 1] ?? "";

  const lines: BuilderDiffLine[] = [
    { kind: "context", value: "@@ builder contract @@" },
    { kind: "context", value: contextLine },
    { kind: "add", value: insertedLine },
  ];
  if (nextLine) {
    lines.push({ kind: "context", value: nextLine });
  }
  return lines;
}

function buildPatchText(filePath: string, content: string, insertedLine: string): string {
  const sourceLines = content.split(/\r?\n/);
  const meaningfulIndex = Math.max(
    0,
    sourceLines.findIndex((line) => line.trim().length > 0),
  );
  const startLine = meaningfulIndex + 1;
  const contextLine = sourceLines[meaningfulIndex] ?? "";
  const nextLine = sourceLines[meaningfulIndex + 1] ?? "";
  const hunkLines = [contextLine, insertedLine, nextLine].filter((line) => line.length > 0);

  return [
    `diff --git a/${filePath} b/${filePath}`,
    `--- a/${filePath}`,
    `+++ b/${filePath}`,
    `@@ -${startLine},${Math.max(1, hunkLines.length - 1)} +${startLine},${hunkLines.length} @@`,
    ` ${contextLine}`,
    `+${insertedLine}`,
    ...(nextLine ? [` ${nextLine}`] : []),
    "",
  ].join("\n");
}

export function selectPreviewFiles(files: IndexedFile[], request: string, constraints: string[]): BuilderPreviewFile[] {
  const queryTokens = tokenize(`${request} ${constraints.join(" ")}`);
  const ranked = files
    .map((file) => ({ file, score: scoreFile(file, queryTokens) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return left.file.path.localeCompare(right.file.path);
    });

  const selected = (ranked.length > 0 ? ranked : files.map((file) => ({ file, score: 0 }))).slice(0, 4);

  return selected.map(({ file }) => {
    const insertedLine = commentLineForFile(file.path, request, constraints);
    return {
      path: file.path,
      operation: "modify",
      risk: fileRisk(file.path),
      summary: buildSummary(file.path, file.content, request),
      excerpt: excerptFromContent(file.content),
      lines: buildPreviewLines(file.content, insertedLine),
    };
  });
}

function canonicalBuilderFingerprint(params: {
  request: string;
  constraints: string[];
  files: IndexedFile[];
}): string {
  return createHash("sha256")
    .update(
      JSON.stringify({
        request: params.request,
        constraints: params.constraints,
        files: params.files.map((file) => ({
          path: file.path,
          content_hash: createHash("sha256").update(file.content).digest("hex"),
        })),
      }),
    )
    .digest("hex");
}

function buildSourceBundle(params: {
  request: string;
  constraints: string[];
  selectedFiles: IndexedFile[];
  previewFiles: BuilderPreviewFile[];
  builderFingerprint: string;
  requestedTargetLanguage: string | null;
  patchText: string;
}): string {
  const header = [
    "# Builder Workspace Source Bundle",
    `builder_fingerprint: ${params.builderFingerprint}`,
    `requested_target_language: ${params.requestedTargetLanguage ?? "auto"}`,
    `request: ${params.request}`,
    `constraints: ${params.constraints.join(" | ") || "none"}`,
    "",
    "## Selected Files",
    ...params.previewFiles.map((file) => `- ${file.path} (${file.risk} risk)`),
    "",
    "## Proposed Patch",
    params.patchText,
    "",
  ];

  const sections = params.selectedFiles.map((file) =>
    [
      `## FILE ${file.path}`,
      file.content.slice(0, 24_000),
      "",
    ].join("\n"),
  );

  return [...header, ...sections].join("\n");
}

export async function POST(request: Request) {
  let payload: BuilderReviewRequest;
  try {
    payload = (await request.json()) as BuilderReviewRequest;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const normalizedRequest = normalizeText(payload.request);
  if (normalizedRequest.length < 3) {
    return NextResponse.json({ detail: "request must be at least 3 characters" }, { status: 400 });
  }

  const constraints = Array.isArray(payload.constraints)
    ? payload.constraints.map((item) => normalizeText(String(item))).filter((item) => item.length > 0)
    : [];

  const files = await collectFilesCached(workspaceRoot());
  const previewFiles = selectPreviewFiles(files, normalizedRequest, constraints);
  const selectedFiles = previewFiles
    .map((previewFile) => files.find((file) => file.path === previewFile.path))
    .filter((file): file is IndexedFile => Boolean(file));
  const patchText = selectedFiles
    .map((file) => buildPatchText(file.path, file.content, commentLineForFile(file.path, normalizedRequest, constraints)))
    .join("\n");
  const requestedTargetLanguage = inferRequestedTargetLanguage({
    prompt: normalizedRequest,
    filePaths: selectedFiles.map((file) => file.path),
  });
  const builderFingerprint = canonicalBuilderFingerprint({
    request: normalizedRequest,
    constraints,
    files: selectedFiles,
  });
  const sourceCode = buildSourceBundle({
    request: normalizedRequest,
    constraints,
    selectedFiles,
    previewFiles,
    builderFingerprint,
    requestedTargetLanguage,
    patchText,
  });

  const response: BuilderPreviewResponse = {
    request_id: `builder-review-${builderFingerprint.slice(0, 12)}`,
    source: "workspace-review",
    generated_at: new Date().toISOString(),
    builder_fingerprint: builderFingerprint,
    requested_target_language: requestedTargetLanguage,
    source_code: sourceCode,
    patch_text: patchText,
    source_stats: {
      selected_files: previewFiles.length,
      source_characters: sourceCode.length,
      patch_characters: patchText.length,
      high_risk_files: previewFiles.filter((file) => file.risk === "high").length,
    },
    plan: [
      {
        title: "Ground Real Files",
        description: "Builder review uses local repository files rather than inferred file hints.",
      },
      {
        title: "Generate Patch Contract",
        description: `Prepared a patch contract for ${previewFiles.length} file(s) using the current workspace state.`,
      },
      {
        title: "Launch With Approved Bundle",
        description: "Use the generated source bundle and approval receipt when creating the mission.",
      },
    ],
    diff_summary: previewFiles.map((file) => `${file.path}: ${file.summary}`),
    risk_notes: [
      ...previewFiles
        .filter((file) => file.risk !== "low")
        .map((file) => `${file.path} is ${file.risk}-risk and needs focused validation.`),
      requestedTargetLanguage
        ? `Primary target language resolved to ${requestedTargetLanguage}.`
        : "No dominant target language was inferred from the staged workspace scope.",
    ],
    test_plan: [
      "Validate the grounded file selection before approval.",
      "Review the patch contract and source bundle before mission launch.",
      "Run the tests that cover the selected files before applying mission output.",
    ],
    files: previewFiles,
    notice:
      "Builder review now returns a grounded patch contract and launch bundle; approval is still required before mission execution.",
  };

  return NextResponse.json(response);
}
