import type { RepoIndexRequest } from "./types/api";
import type { RepoReviewResponse } from "./types";

export const REPO_HANDOFF_STORAGE_KEY = "mission-control:repo-pm-handoff";

export type OfficialFactoryMissionType =
  | "BUILD_NEW"
  | "IMPORT_MODERNIZE"
  | "PORT"
  | "ANALYZE_ONLY"
  | "DEBUG_REPAIR";

export type RepoPmHandoff = {
  version: 1;
  officialMissionType: OfficialFactoryMissionType;
  description: string;
  review: RepoReviewResponse;
  approval?: {
    approval_id: string;
    fingerprint: string;
    receipt_digest: string;
  };
};

/** Compact mission.metadata.repo_import block that arms Phase 5 intake guard. */
export type RepoImportLaunchMetadata = {
  source: "repo_zip_import";
  import_id: string;
  archive_sha256: string;
  display_name?: string;
  source_ref?: string;
  index_required: true;
  index_status: "pending";
};

const OFFICIAL: ReadonlySet<string> = new Set([
  "BUILD_NEW",
  "IMPORT_MODERNIZE",
  "PORT",
  "ANALYZE_ONLY",
  "DEBUG_REPAIR",
]);

export function isProjectZipFile(file: { name?: string; type?: string }): boolean {
  const name = String(file.name ?? "").toLowerCase();
  const type = String(file.type ?? "").toLowerCase();
  return (
    name.endsWith(".zip") ||
    type === "application/zip" ||
    type === "application/x-zip-compressed"
  );
}

export function officialMissionTypeFromRepoChoice(
  missionType: string | null | undefined,
): OfficialFactoryMissionType {
  const raw = String(missionType ?? "").trim();
  const upper = raw.toUpperCase();
  if (OFFICIAL.has(upper)) {
    return upper as OfficialFactoryMissionType;
  }
  const normalized = raw.toLowerCase();
  if (normalized === "analyze") return "ANALYZE_ONLY";
  if (normalized === "port") return "PORT";
  if (normalized === "debug" || normalized === "debug_repair") return "DEBUG_REPAIR";
  if (normalized === "build_new" || normalized === "build-new") return "BUILD_NEW";
  return "IMPORT_MODERNIZE";
}

export function officialMissionTypeFromIntent(
  text: string,
  fallback: OfficialFactoryMissionType = "IMPORT_MODERNIZE",
): OfficialFactoryMissionType {
  const t = text.toLowerCase();
  if (/\bport(ing)?\b/.test(t)) return "PORT";
  if (/\banaly[sz]e\b|\banalysis\b/.test(t)) return "ANALYZE_ONLY";
  if (/\bdebug\b|\brepair\b/.test(t)) return "DEBUG_REPAIR";
  return fallback;
}

export function parseRepoPmHandoff(raw: string | null | undefined): RepoPmHandoff | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<RepoPmHandoff>;
    if (parsed.version !== 1 || !parsed.review || typeof parsed.review !== "object") {
      return null;
    }
    if (typeof parsed.review.source_code !== "string" || !parsed.review.source_code.trim()) {
      return null;
    }
    return {
      version: 1,
      officialMissionType: officialMissionTypeFromRepoChoice(parsed.officialMissionType),
      description: typeof parsed.description === "string" ? parsed.description : "",
      review: parsed.review,
      approval: parsed.approval,
    };
  } catch {
    return null;
  }
}

export function buildRepoPmHandoff(input: Omit<RepoPmHandoff, "version">): RepoPmHandoff {
  return {
    version: 1,
    officialMissionType: officialMissionTypeFromRepoChoice(input.officialMissionType),
    description: input.description,
    review: input.review,
    approval: input.approval,
  };
}

/**
 * Build the compact `metadata.repo_import` block that Phase 5's
 * `_prepare_pm_intake` guard keys on. Callers must pass a completed review
 * (archive_id + archive_sha256). Returns null when review is absent so
 * BUILD_NEW launches stay clean.
 */
export function buildRepoImportLaunchMetadata(
  review: RepoReviewResponse | null | undefined,
): RepoImportLaunchMetadata | null {
  if (!review?.repository) {
    return null;
  }
  const importId = String(review.repository.archive_id ?? "").trim();
  const archiveSha256 = String(review.repository.archive_sha256 ?? "").trim();
  if (!importId || !archiveSha256) {
    return null;
  }
  return {
    source: "repo_zip_import",
    import_id: importId,
    archive_sha256: archiveSha256,
    display_name: String(review.repository.display_name ?? "").trim() || undefined,
    source_ref: String(review.repository.source_ref ?? "").trim() || undefined,
    index_required: true,
    index_status: "pending",
  };
}

/**
 * Build the POST /api/repo/index payload from a mission id + review artifact.
 * Only files with text_available are indexed (matches Chat launch behavior).
 */
export function buildRepoIndexRequest(
  missionId: string,
  review: RepoReviewResponse,
): RepoIndexRequest {
  return {
    mission_id: missionId,
    import_id: review.repository.archive_id,
    archive_sha256: review.repository.archive_sha256,
    display_name: review.repository.display_name,
    source_ref: review.repository.source_ref,
    files: review.files
      .filter((file) => file.text_available)
      .map((file) => ({
        path: file.path,
        language: file.language,
        content_excerpt: file.content_excerpt,
        bytes: file.bytes,
        estimated_lines: file.estimated_lines,
        sha: file.sha,
        overlay_action: file.overlay_action,
      })),
  };
}
