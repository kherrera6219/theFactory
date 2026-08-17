import { describe, expect, it } from "vitest";

import {
  buildRepoPmHandoff,
  isProjectZipFile,
  officialMissionTypeFromIntent,
  officialMissionTypeFromRepoChoice,
  parseRepoPmHandoff,
} from "./chat-repo-import";
import type { RepoReviewResponse } from "./types";

function sampleReview(): RepoReviewResponse {
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
    files: [],
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
});
