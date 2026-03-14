import { NextResponse } from "next/server";

import {
  branchLooksValid,
  buildGithubHeaders,
  clampMaxFiles,
  fetchGithubJson,
  GithubTreeItem,
  normalizeSubdirectory,
  parseGithubRepoUrl,
  RepoFileRecord,
  resolveGithubToken,
  selectRepoFiles,
  LARGE_FILE_BYTES,
} from "../shared";

export const runtime = "nodejs";

type RepoImportRequest = {
  repo_url?: string;
  branch?: string;
  subdirectory?: string;
  max_files?: number;
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

function badRequest(detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: 400 });
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
  const githubToken = await resolveGithubToken();
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

export { languageFromPath, normalizeSubdirectory, parseGithubRepoUrl, selectRepoFiles } from "../shared";
