import { NextResponse } from "next/server";

import { getVaultSecret } from "../../../lib/server/vault";

export const runtime = "nodejs";

type RepoImportRequest = {
  repo_url?: string;
  branch?: string;
  subdirectory?: string;
  max_files?: number;
};

type GithubTreeItem = {
  path?: string;
  type?: string;
  size?: number;
};

type RepoFileRecord = {
  path: string;
  language: string;
  bytes: number;
  estimated_lines: number;
};

type RepoImportResponse = {
  repository: {
    owner: string;
    repo: string;
    branch: string;
    default_branch: string;
    private: boolean;
    html_url: string;
  };
  files: RepoFileRecord[];
  stats: {
    total_files: number;
    estimated_total_lines: number;
    selected_subdirectory: string;
    truncated: boolean;
    skipped_large_files: number;
  };
  logs: string[];
};

const MAX_ALLOWED_FILES = 800;
const DEFAULT_MAX_FILES = 300;
const LARGE_FILE_BYTES = 1_500_000;

const LANGUAGE_BY_EXTENSION: Array<[string, string]> = [
  [".py", "Python"],
  [".ts", "TypeScript"],
  [".tsx", "TypeScript"],
  [".js", "JavaScript"],
  [".jsx", "JavaScript"],
  [".java", "Java"],
  [".go", "Go"],
  [".rs", "Rust"],
  [".c", "C"],
  [".cpp", "C++"],
  [".cs", "C#"],
  [".rb", "Ruby"],
  [".php", "PHP"],
  [".scala", "Scala"],
  [".sql", "SQL"],
  [".sh", "Shell"],
  [".yaml", "YAML"],
  [".yml", "YAML"],
  [".json", "JSON"],
  [".md", "Markdown"],
];

function badRequest(detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: 400 });
}

export function parseGithubRepoUrl(rawUrl: string): { owner: string; repo: string } | null {
  let parsed: URL;
  try {
    parsed = new URL(rawUrl.trim());
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:" || parsed.hostname.toLowerCase() !== "github.com") {
    return null;
  }
  const parts = parsed.pathname
    .split("/")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  if (parts.length < 2) {
    return null;
  }
  const owner = parts[0];
  const repo = parts[1].replace(/\.git$/i, "");
  if (!owner || !repo) {
    return null;
  }
  return { owner, repo };
}

export function normalizeSubdirectory(value: string): string {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "/") {
    return "/";
  }
  const withoutEdges = trimmed.replace(/^\/+/, "").replace(/\/+$/, "");
  return withoutEdges.length > 0 ? `/${withoutEdges}` : "/";
}

export function languageFromPath(path: string): string {
  const normalized = path.toLowerCase();
  for (const [extension, language] of LANGUAGE_BY_EXTENSION) {
    if (normalized.endsWith(extension)) {
      return language;
    }
  }
  return "Other";
}

function estimateLines(bytes: number): number {
  return Math.max(1, Math.round(bytes / 45));
}

function clampMaxFiles(value: number | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return DEFAULT_MAX_FILES;
  }
  const integerValue = Math.floor(value);
  return Math.min(Math.max(1, integerValue), MAX_ALLOWED_FILES);
}

function branchLooksValid(value: string): boolean {
  return /^[A-Za-z0-9._\/-]{1,120}$/.test(value);
}

function buildGithubHeaders(token: string | null): HeadersInit {
  const headers: HeadersInit = {
    Accept: "application/vnd.github+json",
    "User-Agent": "theFactory-mission-control-import",
  };
  if (token && token.trim().length > 0) {
    headers.Authorization = `Bearer ${token.trim()}`;
  }
  return headers;
}

export function selectRepoFiles(
  tree: GithubTreeItem[],
  subdirectory: string,
  maxFiles: number,
): { files: RepoFileRecord[]; skippedLargeFiles: number; truncated: boolean } {
  const normalizedSubdir = subdirectory === "/" ? "/" : subdirectory.slice(1);
  const matches: RepoFileRecord[] = [];
  let skippedLargeFiles = 0;

  for (const item of tree) {
    if (item.type !== "blob" || typeof item.path !== "string") {
      continue;
    }
    const filePath = item.path.trim();
    if (!filePath) {
      continue;
    }
    if (normalizedSubdir !== "/" && !filePath.startsWith(`${normalizedSubdir}/`)) {
      continue;
    }

    const bytes = typeof item.size === "number" && item.size > 0 ? item.size : 0;
    if (bytes > LARGE_FILE_BYTES) {
      skippedLargeFiles += 1;
      continue;
    }
    matches.push({
      path: filePath,
      language: languageFromPath(filePath),
      bytes,
      estimated_lines: estimateLines(bytes),
    });
  }

  matches.sort((left, right) => {
    if (right.bytes !== left.bytes) {
      return right.bytes - left.bytes;
    }
    return left.path.localeCompare(right.path);
  });

  return {
    files: matches.slice(0, maxFiles),
    skippedLargeFiles,
    truncated: matches.length > maxFiles,
  };
}

async function fetchGithubJson(url: string, headers: HeadersInit): Promise<Response> {
  return fetch(url, {
    method: "GET",
    headers,
    cache: "no-store",
  });
}

export async function POST(request: Request) {
  let payload: RepoImportRequest;
  try {
    payload = (await request.json()) as RepoImportRequest;
  } catch {
    return badRequest("Invalid JSON payload.");
  }

  const repoUrl = String(payload.repo_url ?? "").trim();
  if (repoUrl.length < 10 || repoUrl.length > 400) {
    return badRequest("repo_url must be a valid GitHub repository URL.");
  }
  const parsedRepo = parseGithubRepoUrl(repoUrl);
  if (!parsedRepo) {
    return badRequest("Only https://github.com/<owner>/<repo> repository URLs are supported.");
  }

  const requestedBranch = String(payload.branch ?? "").trim();
  if (requestedBranch && !branchLooksValid(requestedBranch)) {
    return badRequest("branch contains unsupported characters.");
  }

  const normalizedSubdirectory = normalizeSubdirectory(String(payload.subdirectory ?? "/"));
  if (normalizedSubdirectory.length > 250) {
    return badRequest("subdirectory path is too long.");
  }

  const maxFiles = clampMaxFiles(payload.max_files);
  const githubToken = process.env.GITHUB_TOKEN ?? (await getVaultSecret("GITHUB-TOKEN"));
  const headers = buildGithubHeaders(githubToken);
  const logs: string[] = [
    "Validated repository request payload.",
    `Resolving metadata for ${parsedRepo.owner}/${parsedRepo.repo}.`,
  ];

  const repoMetadataResponse = await fetchGithubJson(
    `https://api.github.com/repos/${parsedRepo.owner}/${parsedRepo.repo}`,
    headers,
  );
  if (repoMetadataResponse.status === 404) {
    return NextResponse.json(
      { detail: "Repository not found or access denied. Configure GitHub token if private." },
      { status: 404 },
    );
  }
  if (repoMetadataResponse.status === 403) {
    return NextResponse.json(
      { detail: "GitHub API rate limited or forbidden. Retry later or configure token." },
      { status: 403 },
    );
  }
  if (!repoMetadataResponse.ok) {
    return NextResponse.json(
      { detail: `GitHub metadata request failed with status ${repoMetadataResponse.status}.` },
      { status: 502 },
    );
  }

  type GithubRepoResponse = {
    default_branch?: string;
    private?: boolean;
    html_url?: string;
  };
  const repoMetadata = (await repoMetadataResponse.json()) as GithubRepoResponse;
  const resolvedBranch = requestedBranch || String(repoMetadata.default_branch ?? "main");
  logs.push(`Resolved branch ${resolvedBranch}.`);

  const treeResponse = await fetchGithubJson(
    `https://api.github.com/repos/${parsedRepo.owner}/${parsedRepo.repo}/git/trees/${encodeURIComponent(
      resolvedBranch,
    )}?recursive=1`,
    headers,
  );
  if (treeResponse.status === 404) {
    return NextResponse.json(
      { detail: `Branch or tree not found: ${resolvedBranch}` },
      { status: 404 },
    );
  }
  if (!treeResponse.ok) {
    return NextResponse.json(
      { detail: `GitHub tree request failed with status ${treeResponse.status}.` },
      { status: 502 },
    );
  }

  type GithubTreeResponse = {
    tree?: GithubTreeItem[];
    truncated?: boolean;
  };
  const treePayload = (await treeResponse.json()) as GithubTreeResponse;
  const tree = Array.isArray(treePayload.tree) ? treePayload.tree : [];
  logs.push(`Fetched repository tree with ${tree.length} entries.`);

  const selected = selectRepoFiles(tree, normalizedSubdirectory, maxFiles);
  logs.push(`Selected ${selected.files.length} files from ${normalizedSubdirectory}.`);
  if (selected.skippedLargeFiles > 0) {
    logs.push(`Skipped ${selected.skippedLargeFiles} files larger than ${LARGE_FILE_BYTES} bytes.`);
  }
  if (selected.truncated || treePayload.truncated) {
    logs.push(`File list truncated to first ${maxFiles} files.`);
  }

  const estimatedTotalLines = selected.files.reduce((sum, item) => sum + item.estimated_lines, 0);

  const response: RepoImportResponse = {
    repository: {
      owner: parsedRepo.owner,
      repo: parsedRepo.repo,
      branch: resolvedBranch,
      default_branch: String(repoMetadata.default_branch ?? "main"),
      private: Boolean(repoMetadata.private),
      html_url: String(repoMetadata.html_url ?? repoUrl),
    },
    files: selected.files,
    stats: {
      total_files: selected.files.length,
      estimated_total_lines: estimatedTotalLines,
      selected_subdirectory: normalizedSubdirectory,
      truncated: selected.truncated || Boolean(treePayload.truncated),
      skipped_large_files: selected.skippedLargeFiles,
    },
    logs,
  };
  return NextResponse.json(response);
}
