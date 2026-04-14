import { afterEach, describe, expect, it } from "vitest";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { POST, selectPreviewFiles } from "./route";
import {
  createOperatorSessionToken,
  OPERATOR_SESSION_COOKIE_NAME,
} from "../../../lib/server/operator-session";

describe("builder review route", () => {
  let tempRoot: string | null = null;

  afterEach(async () => {
    delete process.env.THEFACTORY_REPO_ROOT;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    if (tempRoot) {
      await rm(tempRoot, { recursive: true, force: true });
      tempRoot = null;
    }
  });

  it("selects grounded files from local workspace content", () => {
    const files = [
      {
        path: "apps/mission-control/app/(shell)/builder/page.tsx",
        absolutePath: "unused",
        content: '"use client";\nexport default function BuilderPage() { return null; }\n',
      },
      {
        path: "services/api-gateway/api_gateway/main.py",
        absolutePath: "unused",
        content: "def create_builder_preview(payload):\n    return {}\n",
      },
    ];

    const selected = selectPreviewFiles(files, "Update builder workflow with safer preview output", [
      "preserve accessibility",
    ]);

    expect(selected[0]).toMatchObject({
      path: "apps/mission-control/app/(shell)/builder/page.tsx",
      operation: "modify",
    });
    expect(selected[0].lines.length).toBeGreaterThan(0);
  });

  it("returns a grounded builder preview from a fixture workspace", async () => {
    tempRoot = await mkdtemp(path.join(os.tmpdir(), "builder-review-"));
    process.env.THEFACTORY_REPO_ROOT = tempRoot;

    await mkdir(path.join(tempRoot, "apps/mission-control/app/(shell)/builder"), { recursive: true });
    await mkdir(path.join(tempRoot, "services/api-gateway/api_gateway"), { recursive: true });

    await writeFile(
      path.join(tempRoot, "apps/mission-control/app/(shell)/builder/page.tsx"),
      '"use client";\nexport default function BuilderPage() { return <p>Builder</p>; }\n',
      "utf8",
    );
    await writeFile(
      path.join(tempRoot, "services/api-gateway/api_gateway/main.py"),
      "def create_builder_preview(payload):\n    return {'ok': True}\n",
      "utf8",
    );
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";
    const cookie = `${OPERATOR_SESSION_COOKIE_NAME}=${createOperatorSessionToken()}`;

    const response = await POST(
      new Request("http://localhost/api/builder/review", {
        method: "POST",
        headers: { "Content-Type": "application/json", Cookie: cookie },
        body: JSON.stringify({
          request: "Update builder preview to show grounded repository diffs.",
          constraints: ["preserve accessibility"],
        }),
      }),
    );

    expect(response.status).toBe(200);
    const payload = (await response.json()) as Record<string, unknown>;
    expect(payload.source).toBe("workspace-review");
    expect(payload.builder_fingerprint).toBeTypeOf("string");
    expect(payload.requested_target_language).toBe("typescript");
    expect(String(payload.patch_text)).toContain(
      "diff --git a/apps/mission-control/app/(shell)/builder/page.tsx",
    );
    expect(String(payload.source_code)).toContain("# Builder Workspace Source Bundle");
    expect(payload.files).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          path: "apps/mission-control/app/(shell)/builder/page.tsx",
        }),
      ]),
    );
    expect(payload.notice).toMatch(/grounded patch contract/i);
  });
});
