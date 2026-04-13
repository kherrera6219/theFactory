import { getVaultSecret } from "../../lib/server/vault";

export type GithubTreeItem = {
  path?: string;
  type?: string;
  size?: number;
};

export type RepoFileRecord = {
  path: string;
  language: string;
  bytes: number;
  estimated_lines: number;
};

type GithubFetchOptions = {
  accept?: string;
};

export class GithubApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const MAX_ALLOWED_FILES = 800;
export const DEFAULT_MAX_FILES = 300;
export const LARGE_FILE_BYTES = 1_500_000;

const LANGUAGE_BY_EXTENSION: Array<[string, string]> = [
  [".py", "Python"],
  [".tsx", "TypeScript"],
  [".ts", "TypeScript"],
  [".jsx", "JavaScript"],
  [".js", "JavaScript"],
  [".java", "Java"],
  [".kt", "Kotlin"],
  [".go", "Go"],
  [".rs", "Rust"],
  [".zig", "Zig"],
  [".c", "C"],
  [".cc", "C++"],
  [".cpp", "C++"],
  [".cxx", "C++"],
  [".cs", "C#"],
  [".rb", "Ruby"],
  [".php", "PHP"],
  [".scala", "Scala"],
  [".r", "R"],
  [".jl", "Julia"],
  [".m", "MATLAB"],
  [".sql", "SQL"],
  [".sh", "Shell"],
  [".bash", "Shell"],
  [".yaml", "YAML"],
  [".yml", "YAML"],
  [".toml", "TOML"],
  [".json", "JSON"],
  [".md", "Markdown"],
  [".txt", "Text"],
];

const REQUESTED_LANGUAGE_BY_EXTENSION: Array<[string, string]> = [
  [".py", "python"],
  [".tsx", "typescript"],
  [".ts", "typescript"],
  [".jsx", "javascript"],
  [".js", "javascript"],
  [".java", "java"],
  [".kt", "kotlin"],
  [".go", "go"],
  [".rs", "rust"],
  [".zig", "zig"],
  [".c", "c"],
  [".cc", "cpp"],
  [".cpp", "cpp"],
  [".cxx", "cpp"],
  [".cs", "csharp"],
  [".rb", "ruby"],
  [".php", "php"],
  [".scala", "scala"],
  [".r", "r"],
  [".jl", "julia"],
  [".m", "matlab"],
];

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
  // Avoid regex on uncontrolled data — strip leading/trailing slashes with index arithmetic
  let start = 0;
  while (start < trimmed.length && trimmed[start] === "/") start++;
  let end = trimmed.length;
  while (end > start && trimmed[end - 1] === "/") end--;
  const withoutEdges = trimmed.slice(start, end);
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

export function requestedLanguageFromPath(path: string): string | null {
  const normalized = path.toLowerCase();
  for (const [extension, language] of REQUESTED_LANGUAGE_BY_EXTENSION) {
    if (normalized.endsWith(extension)) {
      return language;
    }
  }
  return null;
}

export function estimateLines(bytes: number): number {
  return Math.max(1, Math.round(bytes / 45));
}

export function clampMaxFiles(value: number | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return DEFAULT_MAX_FILES;
  }
  const integerValue = Math.floor(value);
  return Math.min(Math.max(1, integerValue), MAX_ALLOWED_FILES);
}

export function branchLooksValid(value: string): boolean {
  return /^[A-Za-z0-9._/-]{1,120}$/.test(value);
}

export async function resolveGithubToken(): Promise<string | null> {
  return process.env.GITHUB_TOKEN ?? (await getVaultSecret("GITHUB-TOKEN"));
}

export function buildGithubHeaders(token: string | null, options?: GithubFetchOptions): HeadersInit {
  const headers: HeadersInit = {
    Accept: options?.accept ?? "application/vnd.github+json",
    "User-Agent": "theFactory-mission-control-import",
  };
  if (token && token.trim().length > 0) {
    headers.Authorization = `Bearer ${token.trim()}`;
  }
  return headers;
}

export function encodeGithubPath(path: string): string {
  return path
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
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

const GITHUB_API_BASE = "https://api.github.com/";

function assertGithubApiUrl(url: string): void {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new GithubApiError(400, "Request URL is not a valid URL.");
  }
  if (parsed.protocol !== "https:" || parsed.hostname !== "api.github.com") {
    throw new GithubApiError(400, `Request URL must point to the GitHub API (${GITHUB_API_BASE}).`);
  }
}

export async function fetchGithubJson(url: string, headers: HeadersInit): Promise<Response> {
  assertGithubApiUrl(url);
  return fetch(url, {
    method: "GET",
    headers,
    cache: "no-store",
  });
}

export async function fetchGithubText(url: string, headers: HeadersInit): Promise<Response> {
  assertGithubApiUrl(url);
  return fetch(url, {
    method: "GET",
    headers,
    cache: "no-store",
  });
}

export async function fetchGithubFileText(params: {
  owner: string;
  repo: string;
  branch: string;
  path: string;
  token: string | null;
}): Promise<{ text: string; bytes: number; sha: string | null }> {
  const encodedPath = encodeGithubPath(params.path);
  const url = `https://api.github.com/repos/${params.owner}/${params.repo}/contents/${encodedPath}?ref=${encodeURIComponent(
    params.branch,
  )}`;

  const metadataResponse = await fetchGithubJson(
    url,
    buildGithubHeaders(params.token, { accept: "application/vnd.github.object+json" }),
  );
  if (metadataResponse.status === 404) {
    throw new GithubApiError(404, `Selected file not found at ${params.path}.`);
  }
  if (metadataResponse.status === 403) {
    throw new GithubApiError(403, "GitHub API rate limited or forbidden. Retry later or configure token.");
  }
  if (!metadataResponse.ok) {
    throw new GithubApiError(
      502,
      `GitHub file request failed for ${params.path} with status ${metadataResponse.status}.`,
    );
  }

  type GithubContentsObject = {
    type?: string;
    content?: string;
    encoding?: string;
    size?: number;
    sha?: string;
  };

  const payload = (await metadataResponse.json()) as GithubContentsObject;
  if (payload.type !== "file") {
    throw new GithubApiError(422, `Selected path is not a file: ${params.path}.`);
  }

  if (typeof payload.content === "string" && payload.encoding === "base64") {
    const decoded = Buffer.from(payload.content.replace(/\n/g, ""), "base64").toString("utf-8");
    const bytes =
      typeof payload.size === "number" && payload.size > 0
        ? payload.size
        : Buffer.byteLength(decoded, "utf-8");
    return { text: decoded, bytes, sha: typeof payload.sha === "string" ? payload.sha : null };
  }

  const rawResponse = await fetchGithubText(
    url,
    buildGithubHeaders(params.token, { accept: "application/vnd.github.raw" }),
  );
  if (!rawResponse.ok) {
    throw new GithubApiError(
      502,
      `GitHub raw file request failed for ${params.path} with status ${rawResponse.status}.`,
    );
  }
  const text = await rawResponse.text();
  return {
    text,
    bytes:
      typeof payload.size === "number" && payload.size > 0
        ? payload.size
        : Buffer.byteLength(text, "utf-8"),
    sha: typeof payload.sha === "string" ? payload.sha : null,
  };
}
