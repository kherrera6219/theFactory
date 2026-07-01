import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import {
  branchLooksValid,
  clampMaxFiles,
  languageFromPath,
  normalizeSubdirectory,
  parseGithubRepoUrl,
  selectRepoFiles,
} from "../shared";
import type { RepoFileRecord } from "../shared";
import { indexZipArchive } from "../archive";

export const runtime = "nodejs";

type UploadedArchive = {
  name?: string;
  type?: string;
  size?: number;
  arrayBuffer: () => Promise<ArrayBuffer>;
};

type RepoImportResponse = {
  repository: {
    source: "zip";
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
    total_entries: number;
    total_uncompressed_bytes: number;
  };
  logs: string[];
};

function badRequest(detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: 400 });
}

function formString(formData: FormData, key: string): string {
  const value = formData.get(key);
  return typeof value === "string" ? value.trim() : "";
}

function formNumber(formData: FormData, key: string): number | undefined {
  const value = formData.get(key);
  if (typeof value !== "string" || !value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function isUploadedArchive(value: unknown): value is UploadedArchive {
  return (
    typeof value === "object" &&
    value !== null &&
    "arrayBuffer" in value &&
    typeof (value as UploadedArchive).arrayBuffer === "function"
  );
}

function stripZipExtension(fileName: string): string {
  return fileName.replace(/\.zip$/i, "");
}

function sanitizeDisplayName(value: string): string {
  const cleaned = value
    .trim()
    .replace(/\.zip$/i, "")
    .replace(/[^A-Za-z0-9._ -]+/g, "-")
    .replace(/[-_ .]+$/g, "")
    .slice(0, 120);
  return cleaned || "repository-archive";
}

function archiveLooksLikeZip(buffer: Buffer): boolean {
  if (buffer.length < 4) {
    return false;
  }
  const signature = buffer.readUInt32LE(0);
  return signature === 0x04034b50 || signature === 0x06054b50 || signature === 0x08074b50;
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
    return badRequest("Repository ZIP import requires multipart/form-data.");
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

  const maxFiles = clampMaxFiles(formNumber(formData, "max_files"));
  const displayName = sanitizeDisplayName(formString(formData, "display_name") || stripZipExtension(fileName));
  const logs: string[] = ["Validated repository ZIP upload payload."];
  const buffer = Buffer.from(await archive.arrayBuffer());
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
      total_entries: indexed.stats.total_entries,
      total_uncompressed_bytes: indexed.stats.total_uncompressed_bytes,
    },
    logs,
  };
  return NextResponse.json(response);
}

export { languageFromPath, normalizeSubdirectory, parseGithubRepoUrl, selectRepoFiles } from "../shared";
