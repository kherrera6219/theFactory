import { describe, expect, it } from "vitest";

import {
  buildRepoImportLaunchMetadata,
  buildRepoIndexRequest,
  buildRepoPmHandoff,
  isProjectZipFile,
  officialMissionTypeFromIntent,
  officialMissionTypeFromRepoChoice,
  parseRepoPmHandoff,
} from "./chat-repo-import";
import type { RepoReviewResponse } from "./types";

function sampleReview(overrides?: Partial<RepoReviewResponse>): RepoReviewResponse {
  return {
    request_id: "req-1",
    review_fingerprint: "fp-1",
    source: "repo-review",
    generated_at: "2026-08-17T00:00:00Z",
    repository: {
      source: "zip",
      owner: "op",
      repo: "sample",
      branch: "main",
      html_url: null,
      selected_subdirectory: "/",
      archive_id: "repozip-abc",
      archive_sha256: "a".repeat(64),
      display_name: "sample",
      source_ref: "main",
      root_prefix: "",
    },
    mission_type: "update",
    requested_target_language: "python",
    source_code: "## FILE app.py\nprint('hi')\n",
    source_stats: {
      selected_files: 1,
      include_files: 1,
      reference_files: 0,
      source_characters: 20,
      bundled_files: 1,
      truncated_files: 0,
      unavailable_files: 0,
    },
    plan: [],
    diff_summary: [],
    risk_notes: [],
    test_plan: [],
    files: [
      {
        path: "app.py",
        overlay_action: "include",
        language: "Python",
        requested_language: "python",
        bytes: 20,
        estimated_lines: 2,
        summary: "entry",
        content_excerpt: "print('hi')\n",
        text_available: true,
        included_in_source: true,
        truncated_in_source: false,
        sha: "file-sha-1",
      },
      {
        path: "binary.bin",
        overlay_action: "reference",
        language: "Unknown",
        requested_language: null,
        bytes: 4,
        estimated_lines: 0,
        summary: "binary",
        content_excerpt: "",
        text_available: false,
        included_in_source: false,
        truncated_in_source: false,
        sha: null,
      },
    ],
    ...overrides,
  };
}

describe("chat repo import helpers", () => {
  it("detects project ZIP attachments", () => {
    expect(isProjectZipFile({ name: "app.zip", type: "" })).toBe(true);
    expect(isProjectZipFile({ name: "app.py", type: "text/x-python" })).toBe(false);
    expect(isProjectZipFile({ name: "blob", type: "application/zip" })).toBe(true);
  });

  it("maps unofficial repo choices and ZIP+port intent to official types", () => {
    expect(officialMissionTypeFromRepoChoice("analyze")).toBe("ANALYZE_ONLY");
    expect(officialMissionTypeFromRepoChoice("update")).toBe("IMPORT_MODERNIZE");
    expect(officialMissionTypeFromRepoChoice("add_feature")).toBe("IMPORT_MODERNIZE");
    expect(officialMissionTypeFromRepoChoice("port")).toBe("PORT");
    expect(officialMissionTypeFromIntent("port this python app to go")).toBe("PORT");
    expect(officialMissionTypeFromIntent("analyze reliability risks")).toBe("ANALYZE_ONLY");
  });

  it("round-trips a repo-to-chat handoff without dropping source", () => {
    const handoff = buildRepoPmHandoff({
      officialMissionType: officialMissionTypeFromRepoChoice("port"),
      description: "Port this CLI to Go",
      review: sampleReview(),
    });
    const parsed = parseRepoPmHandoff(JSON.stringify(handoff));
    expect(parsed?.officialMissionType).toBe("PORT");
    expect(parsed?.review.source_code).toContain("## FILE app.py");
    expect(parseRepoPmHandoff("not-json")).toBeNull();
  });

  it("builds Phase 5 arming metadata with index_required pending", () => {
    const meta = buildRepoImportLaunchMetadata(sampleReview());
    expect(meta).toEqual({
      source: "repo_zip_import",
      import_id: "repozip-abc",
      archive_sha256: "a".repeat(64),
      display_name: "sample",
      source_ref: "main",
      index_required: true,
      index_status: "pending",
    });
  });

  it("returns null launch metadata without a review or archive ids", () => {
    expect(buildRepoImportLaunchMetadata(null)).toBeNull();
    expect(
      buildRepoImportLaunchMetadata(
        sampleReview({
          repository: {
            ...sampleReview().repository,
            archive_id: "",
            archive_sha256: "",
          },
        }),
      ),
    ).toBeNull();
  });

  it("builds index request from review text-available files only", () => {
    const request = buildRepoIndexRequest("mission-1", sampleReview());
    expect(request.mission_id).toBe("mission-1");
    expect(request.import_id).toBe("repozip-abc");
    expect(request.archive_sha256).toBe("a".repeat(64));
    expect(request.files).toHaveLength(1);
    expect(request.files[0]).toMatchObject({
      path: "app.py",
      language: "Python",
      content_excerpt: "print('hi')\n",
      overlay_action: "include",
    });
  });
});
