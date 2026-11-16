import { describe, expect, it } from "vitest";

import {
  buildSliceTimelineItems,
  extractGithubPrResult,
  extractMigrationNotes,
} from "./slice-delivery";

describe("slice-delivery helpers", () => {
  it("merges planned slices with completed commits and active paused state", () => {
    const items = buildSliceTimelineItems(
      {
        slices_completed: [
          {
            id: "slice-1",
            title: "Extract module",
            files: ["src/mod.py"],
            commit_sha: "abc123456789",
            verdict: "PRESERVED",
            verified_at: "2026-11-13T22:00:00Z",
          },
        ],
        active_slice: { id: "slice-2" },
        slice_paused: true,
      },
      [
        { id: "slice-1", title: "Extract module", files: ["src/mod.py"] },
        { id: "slice-2", title: "Wire handlers", files: ["src/api.py"] },
        { id: "slice-3", title: "Add integration tests", files: ["tests/test_api.py"] },
      ],
    );

    expect(items).toHaveLength(3);
    expect(items[0]).toMatchObject({
      id: "slice-1",
      status: "verified",
      commitSha: "abc123456789",
      verdict: "PRESERVED",
    });
    expect(items[1]).toMatchObject({
      id: "slice-2",
      status: "paused",
    });
    expect(items[2]).toMatchObject({
      id: "slice-3",
      status: "pending",
    });
  });

  it("extracts migration notes and GitHub PR delivery metadata safely", () => {
    expect(extractMigrationNotes(null)).toBeNull();
    expect(extractMigrationNotes({ migration_notes_md: "  " })).toBeNull();
    expect(extractMigrationNotes({ migration_notes_md: "# Migration Notes" })).toBe(
      "# Migration Notes",
    );

    expect(extractGithubPrResult({})).toBeNull();
    expect(
      extractGithubPrResult({
        github_pr_result: {
          exported: true,
          status: "created",
          pr_number: 42,
          pr_url: "https://github.com/org/repo/pull/42",
        },
      }),
    ).toMatchObject({ exported: true, pr_number: 42 });
  });
});
