import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

describe("repo review route", () => {
  beforeEach(() => {
    process.env.GITHUB_TOKEN = "ghp-test-token";
  });

  afterEach(() => {
    delete process.env.GITHUB_TOKEN;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("builds a review artifact and source bundle from selected repository files", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            default_branch: "main",
            html_url: "https://github.com/octo/sample-platform",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            type: "file",
            encoding: "base64",
            size: 68,
            sha: "sha-page",
            content: Buffer.from('"use client";\nexport default function RepoPage() { return null; }\n').toString("base64"),
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            type: "file",
            encoding: "base64",
            size: 18,
            sha: "sha-readme",
            content: Buffer.from("# Sample Platform\n").toString("base64"),
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new Request("http://localhost/api/repo/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: "https://github.com/octo/sample-platform",
          branch: "main",
          subdirectory: "/",
          mission_type: "analyze",
          description: "Review repository scope before launch.",
          selected_files: [
            {
              path: "apps/mission-control/app/(shell)/repo/page.tsx",
              overlay_action: "include",
              language: "TypeScript",
              bytes: 68,
              estimated_lines: 2,
            },
            {
              path: "README.md",
              overlay_action: "reference",
              language: "Markdown",
              bytes: 18,
              estimated_lines: 1,
            },
          ],
        }),
      }),
    );

    expect(response.status).toBe(200);
    const payload = (await response.json()) as Record<string, unknown>;

    expect(payload.request_id).toBeTypeOf("string");
    expect(payload.review_fingerprint).toBeTypeOf("string");
    expect(payload.requested_target_language).toBe("typescript");
    expect(String(payload.source_code)).toContain("## FILE apps/mission-control/app/(shell)/repo/page.tsx");
    expect(String(payload.source_code)).toContain("## FILE README.md");
    expect(payload.diff_summary).toEqual(
      expect.arrayContaining([expect.stringContaining("Reviewed 2 selected files")]),
    );

    const files = payload.files as Array<Record<string, unknown>>;
    expect(files).toHaveLength(2);
    expect(files[0]).toMatchObject({
      path: "apps/mission-control/app/(shell)/repo/page.tsx",
      overlay_action: "include",
      included_in_source: true,
      requested_language: "typescript",
    });
    expect(files[1]).toMatchObject({
      path: "README.md",
      overlay_action: "reference",
      included_in_source: true,
    });
  });

  it("rejects update reviews without a description", async () => {
    const response = await POST(
      new Request("http://localhost/api/repo/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: "https://github.com/octo/sample-platform",
          branch: "main",
          subdirectory: "/",
          mission_type: "update",
          description: "",
          selected_files: [
            {
              path: "apps/mission-control/app/(shell)/repo/page.tsx",
              overlay_action: "include",
              language: "TypeScript",
              bytes: 68,
              estimated_lines: 2,
            },
          ],
        }),
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      detail: "description must be provided for update and add_feature reviews.",
    });
  });
});
