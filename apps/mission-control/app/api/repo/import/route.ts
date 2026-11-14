import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import {
  branchLooksValid,
  clampMaxFiles,
  normalizeSubdirectory,
} from "../shared";
import type { RepoFileRecord } from "../shared";
import { indexZipArchive } from "../archive";
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

function orchestratorInternalBaseUrl(): string {
  return process.env.ORCHESTRATOR_INTERNAL_BASE_URL?.trim() || "http://localhost:8101";
}

function internalServiceApiKey(): string {
  return process.env.INTERNAL_SERVICE_API_KEY?.trim() || "";
}

type RepoImportResponse = {
  repository: {
    source: "zip" | "local" | "git";
    owner: string;
    repo: string;
    branch: string;
    default_branch: string;
    private: boolean;
    html_url: string | null;
    display_name: string;
    archive_id: string;
    archive_sha256: string;
    source_ref: string;
    root_prefix: string;
    workspace_id?: string | null;
    base_commit?: string | null;
  };
  files: RepoFileRecord[];
  stats: {
    total_files: number;
    estimated_total_lines: number;
    selected_subdirectory: string;
    truncated: boolean;
    skipped_large_files: number;
    skipped_unsafe_entries: number;
    skipped_directory_entries: number;
    skipped_unreadable_entries: number;
    entry_limit_reached: boolean;
    byte_limit_reached: boolean;
    total_entries: number;
    total_uncompressed_bytes: number;
  };
  logs: string[];
};

function formNumber(formData: FormData, key: string): number | undefined {
  const value = formData.get(key);
  if (typeof value !== "string" || !value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function optionalString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function optionalNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

async function createBackendWorkspace(
  payload: Record<string, unknown>,
): Promise<{ status: number; data: Record<string, unknown> }> {
  const apiKey = internalServiceApiKey();
  if (!apiKey) {
    return {
      status: 503,
      data: {
        detail:
          "INTERNAL_SERVICE_API_KEY is not configured; cannot reach orchestrator workspace service.",
      },
    };
  }
  const upstream = await fetch(`${orchestratorInternalBaseUrl()}/internal/workspaces`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-internal-api-key": apiKey,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  let parsed: Record<string, unknown> = {};
  try {
    parsed = (await upstream.json()) as Record<string, unknown>;
  } catch {
    parsed = { detail: `Orchestrator returned HTTP ${upstream.status}` };
  }
  return { status: upstream.status, data: parsed };
}

export async function POST(request: Request) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }

  const contentType = request.headers.get("content-type")?.toLowerCase() || "";
  if (contentType.includes("application/json")) {
    let body: Record<string, unknown>;
    try {
      body = (await request.json()) as Record<string, unknown>;
    } catch {
      return badRequest("Invalid JSON payload for repository workspace import.");
    }
    const localPath = optionalString(body.local_path);
    const gitUrl = optionalString(body.git_url);
    if (!localPath && !gitUrl) {
      return badRequest("local_path or git_url is required for JSON workspace import.");
    }
    const normalizedSubdirectory = normalizeSubdirectory(optionalString(body.subdirectory) || "/");
    if (normalizedSubdirectory.length > 250) {
      return badRequest("subdirectory path is too long.");
    }
    const sourceRef = optionalString(body.ref) || optionalString(body.source_ref) || optionalString(body.branch);
    if (sourceRef && !branchLooksValid(sourceRef)) {
      return badRequest("source_ref contains unsupported characters.");
    }
    const maxFiles = clampMaxFiles(optionalNumber(body.max_files));
    const displayName = optionalString(body.display_name)
      ? sanitizeDisplayName(optionalString(body.display_name))
      : undefined;

    try {
      const upstream = await createBackendWorkspace({
        source_type: gitUrl ? "git" : "local",
        ...(localPath ? { local_path: localPath } : {}),
        ...(gitUrl ? { git_url: gitUrl } : {}),
        ...(sourceRef ? { ref: sourceRef, source_ref: sourceRef } : {}),
        ...(displayName ? { display_name: displayName } : {}),
        subdirectory: normalizedSubdirectory,
        max_files: maxFiles,
      });
      return NextResponse.json(upstream.data, { status: upstream.status });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to reach orchestrator";
      return NextResponse.json({ detail: message }, { status: 502 });
    }
  }

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return badRequest("Repository ZIP import requires multipart/form-data.");
  }

  const archive = formData.get("archive");
  const localPath = formString(formData, "local_path");
  const gitUrl = formString(formData, "git_url");
  if (!isUploadedArchive(archive)) {
    if (localPath || gitUrl) {
      const normalizedSubdirectory = normalizeSubdirectory(formString(formData, "subdirectory") || "/");
      if (normalizedSubdirectory.length > 250) {
        return badRequest("subdirectory path is too long.");
      }
      const sourceRef =
        formString(formData, "ref") || formString(formData, "source_ref") || formString(formData, "branch");
      if (sourceRef && !branchLooksValid(sourceRef)) {
        return badRequest("source_ref contains unsupported characters.");
      }
      const maxFiles = clampMaxFiles(formNumber(formData, "max_files"));
      const rawDisplay = formString(formData, "display_name");
      try {
        const upstream = await createBackendWorkspace({
          source_type: gitUrl ? "git" : "local",
          ...(localPath ? { local_path: localPath } : {}),
          ...(gitUrl ? { git_url: gitUrl } : {}),
          ...(sourceRef ? { ref: sourceRef, source_ref: sourceRef } : {}),
          ...(rawDisplay ? { display_name: sanitizeDisplayName(rawDisplay) } : {}),
          subdirectory: normalizedSubdirectory,
          max_files: maxFiles,
        });
        return NextResponse.json(upstream.data, { status: upstream.status });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to reach orchestrator";
        return NextResponse.json({ detail: message }, { status: 502 });
      }
    }
    return badRequest("archive must be a repository .zip file upload, or provide local_path / git_url.");
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

  const maxFiles = clampMaxFiles(formNumber(formData, "max_files"));
  const displayName = sanitizeDisplayName(formString(formData, "display_name") || stripZipExtension(fileName));
  const logs: string[] = ["Validated repository ZIP upload payload."];
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

  let indexed;
  try {
    indexed = await indexZipArchive(
      { kind: "buffer", buffer },
      { maxFiles, subdirectory: normalizedSubdirectory },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown ZIP parse error.";
    return badRequest("Invalid ZIP archive: " + message);
  }

  logs.push(...indexed.logs);
  logs.push("Indexed " + indexed.files.length + " files from " + normalizedSubdirectory + ".");
  if (indexed.stats.skipped_large_files > 0) {
    logs.push("Skipped " + indexed.stats.skipped_large_files + " files larger than the import limit.");
  }
  if (indexed.stats.skipped_unsafe_entries > 0) {
    logs.push("Skipped " + indexed.stats.skipped_unsafe_entries + " unsafe archive entries.");
  }
  if (indexed.stats.truncated) {
    logs.push("File list truncated to first " + maxFiles + " files.");
  }

  const estimatedTotalLines = indexed.files.reduce((sum, item) => sum + item.estimated_lines, 0);
  const archiveId = "repozip-" + indexed.stats.archive_sha256.slice(0, 12);

  let workspaceId: string | null = null;
  let baseCommit: string | null = null;
  if (internalServiceApiKey()) {
    try {
      const synced = await createBackendWorkspace({
        source_type: "zip",
        archive_base64: buffer.toString("base64"),
        display_name: displayName,
        source_ref: sourceRef || "zip-upload",
        subdirectory: normalizedSubdirectory,
        max_files: maxFiles,
      });
      if (synced.status >= 200 && synced.status < 300) {
        const syncedRepo = synced.data.repository as Record<string, unknown> | undefined;
        if (syncedRepo && typeof syncedRepo.workspace_id === "string") {
          workspaceId = syncedRepo.workspace_id;
          baseCommit =
            typeof syncedRepo.base_commit === "string" ? syncedRepo.base_commit : null;
          logs.push(`Initialized Git-backed workspace ${workspaceId}.`);
        }
      }
    } catch {
      logs.push("Backend workspace initialization unavailable; using local ZIP index.");
    }
  }

  const response: RepoImportResponse = {
    repository: {
      source: "zip",
      owner: "local",
      repo: displayName,
      branch: sourceRef || "zip-upload",
      default_branch: sourceRef || "zip-upload",
      private: true,
      html_url: null,
      display_name: displayName,
      archive_id: archiveId,
      archive_sha256: indexed.stats.archive_sha256,
      source_ref: sourceRef,
      root_prefix: indexed.stats.root_prefix,
      ...(workspaceId ? { workspace_id: workspaceId, base_commit: baseCommit } : {}),
    },
    files: indexed.files,
    stats: {
      total_files: indexed.stats.total_files,
      estimated_total_lines: estimatedTotalLines,
      selected_subdirectory: indexed.stats.selected_subdirectory,
      truncated: indexed.stats.truncated,
      skipped_large_files: indexed.stats.skipped_large_files,
      skipped_unsafe_entries: indexed.stats.skipped_unsafe_entries,
      skipped_directory_entries: indexed.stats.skipped_directory_entries,
      skipped_unreadable_entries: indexed.stats.skipped_unreadable_entries,
      entry_limit_reached: indexed.stats.entry_limit_reached,
      byte_limit_reached: indexed.stats.byte_limit_reached,
      total_entries: indexed.stats.total_entries,
      total_uncompressed_bytes: indexed.stats.total_uncompressed_bytes,
    },
    logs,
  };
  return NextResponse.json(response);
}
