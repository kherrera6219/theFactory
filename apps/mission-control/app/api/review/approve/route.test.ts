import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { POST } from "./route";

describe("review approval route", () => {
  afterEach(() => {
    delete process.env.MISSION_CONTROL_APPROVAL_STORE_ROOT;
  });

  it("persists an approval receipt on disk", async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), "review-approval-"));
    process.env.MISSION_CONTROL_APPROVAL_STORE_ROOT = tempRoot;

    const response = await POST(
      new Request("http://localhost/api/review/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scope: "repo",
          fingerprint: "f1234567890abcdef",
          summary: "Repository review approved for mission launch.",
          metadata: { request_id: "repo-review-001" },
        }),
      }),
    );

    expect(response.status).toBe(200);
    const payload = (await response.json()) as Record<string, string>;
    expect(payload.approval_id).toContain("repo-approval-");
    expect(payload.record_path).toContain(".runtime/review-approvals/");

    const persisted = JSON.parse(
      await readFile(path.join(tempRoot, `${payload.approval_id}.json`), "utf-8"),
    ) as Record<string, unknown>;
    expect(persisted).toMatchObject({
      approval_id: payload.approval_id,
      scope: "repo",
      fingerprint: "f1234567890abcdef",
      summary: "Repository review approved for mission launch.",
      metadata: { request_id: "repo-review-001" },
      receipt_digest: payload.receipt_digest,
    });
  });
});
