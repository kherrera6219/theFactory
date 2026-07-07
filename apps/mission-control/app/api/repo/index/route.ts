import { createHash } from "node:crypto";

import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";

export const runtime = "nodejs";

const ORCHESTRATOR_INTERNAL_BASE_URL =
  process.env.ORCHESTRATOR_INTERNAL_BASE_URL?.trim() || "http://localhost:8101";
const INTERNAL_SERVICE_API_KEY = process.env.INTERNAL_SERVICE_API_KEY?.trim() || "";

// Repo ZIP Import Phase 6 (docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md): builds
// bounded manifest/summary/chunk knowledge records from the operator's
// already-reviewed file selection (no new archive staging cache needed --
// the review step already read every selected file into memory) and posts
// them to the orchestrator's repo-import-index endpoint.
const MAX_INDEXED_FILES = 200;
const MAX_CHUNK_TEXT_CHARS = 2_000;

type RepoIndexFile = {
  path?: string;
  language?: string;
  content_excerpt?: string;
  bytes?: number;
  estimated_lines?: number;
  sha?: string | null;
  overlay_action?: "include" | "reference";
};

type RepoIndexRequest = {
  mission_id?: string;
  import_id?: string;
  archive_sha256?: string;
  display_name?: string;
  source_ref?: string;
  files?: RepoIndexFile[];
};

function pathHash(path: string): string {
  return createHash("sha256").update(path).digest("hex").slice(0, 16);
}

export async function POST(request: Request) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }

  let payload: RepoIndexRequest;
  try {
    payload = (await request.json()) as RepoIndexRequest;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const missionId = String(payload.mission_id ?? "").trim();
  const importId = String(payload.import_id ?? "").trim();
  const archiveSha256 = String(payload.archive_sha256 ?? "").trim();
  const displayName = String(payload.display_name ?? "repository").trim() || "repository";
  const sourceRef = String(payload.source_ref ?? "").trim();
  const files = Array.isArray(payload.files) ? payload.files : [];

  if (!missionId) {
    return NextResponse.json({ detail: "mission_id is required." }, { status: 400 });
  }
  if (!importId) {
    return NextResponse.json({ detail: "import_id is required." }, { status: 400 });
  }
  if (!INTERNAL_SERVICE_API_KEY) {
    return NextResponse.json(
      { detail: "INTERNAL_SERVICE_API_KEY is not configured for the local Mission Control stack." },
      { status: 400 },
    );
  }

  const indexedFiles = files.slice(0, MAX_INDEXED_FILES);
  const languageCounts = new Map<string, number>();
  for (const file of indexedFiles) {
    const language = String(file.language ?? "Unknown");
    languageCounts.set(language, (languageCounts.get(language) ?? 0) + 1);
  }
  const topLanguages = [...languageCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([language, count]) => `${language} (${count})`)
    .join(", ");

  const importManifest = {
    knowledge_id: `repo.${importId}.manifest`,
    kind: "repo_manifest",
    source: "repo_zip_import",
    import_id: importId,
    display_name: displayName,
    archive_sha256: archiveSha256,
    combined_text:
      `Repository ${displayName} imported from ZIP` +
      (sourceRef ? ` (${sourceRef})` : "") +
      `. ${indexedFiles.length} files indexed.`,
    metadata: { file_count: indexedFiles.length, source_ref: sourceRef },
  };

  const summaryRecord = {
    knowledge_id: `repo.${importId}.summary`,
    kind: "repo_summary",
    source: "repo_zip_import",
    import_id: importId,
    combined_text: [
      `Repository: ${displayName}`,
      sourceRef ? `Source ref: ${sourceRef}` : null,
      `Files indexed: ${indexedFiles.length}`,
      topLanguages ? `Top languages: ${topLanguages}` : null,
      `Selected paths: ${indexedFiles
        .slice(0, 30)
        .map((file) => file.path)
        .filter(Boolean)
        .join(", ")}`,
    ]
      .filter(Boolean)
      .join("\n"),
    metadata: { file_count: indexedFiles.length, languages: [...languageCounts.keys()] },
  };

  const chunkRecords = indexedFiles
    .filter((file) => typeof file.path === "string" && file.path && file.content_excerpt)
    .map((file) => {
      const path = file.path as string;
      const text = String(file.content_excerpt ?? "").slice(0, MAX_CHUNK_TEXT_CHARS);
      return {
        knowledge_id: `repo.${importId}.file.${pathHash(path)}.chunk.0`,
        kind: "repo_source_chunk",
        source: "repo_zip_import",
        import_id: importId,
        path,
        language: file.language ?? "Unknown",
        chunk_index: 0,
        chunk_count: 1,
        sha256: file.sha ?? null,
        combined_text: text,
        content: text,
        metadata: {
          bytes: file.bytes ?? 0,
          estimated_lines: file.estimated_lines ?? 0,
          archive_sha256: archiveSha256,
          selected_for_review: file.overlay_action === "include",
        },
      };
    });

  try {
    const upstream = await fetch(
      `${ORCHESTRATOR_INTERNAL_BASE_URL}/internal/missions/${encodeURIComponent(missionId)}/repo-import-index`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": INTERNAL_SERVICE_API_KEY },
        body: JSON.stringify({
          import_manifest: importManifest,
          summary_record: summaryRecord,
          chunk_records: chunkRecords,
          index_status: "complete",
          index_errors: [],
        }),
        cache: "no-store",
      },
    );

    const text = await upstream.text();
    let parsed: Record<string, unknown> = {};
    try {
      parsed = text ? (JSON.parse(text) as Record<string, unknown>) : {};
    } catch {
      parsed = { detail: text || "Unexpected repo-index response." };
    }
    return NextResponse.json(parsed, { status: upstream.status });
  } catch (error) {
    return NextResponse.json(
      {
        detail: error instanceof Error ? error.message : "Unable to index repository content.",
      },
      { status: 502 },
    );
  }
}
