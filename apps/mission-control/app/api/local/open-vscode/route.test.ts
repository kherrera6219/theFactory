import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as outputFolders from "../_lib/output-folders";
import { POST } from "./route";

const ORIGINAL_BYPASS = process.env.MISSION_CONTROL_BYPASS_AUTH;
const ORIGINAL_SESSION_SECRET = process.env.MISSION_CONTROL_SESSION_SECRET;
const ORIGINAL_ADMIN_KEY = process.env.MISSION_CONTROL_ADMIN_KEY;

function jsonRequest(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/local/open-vscode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("open VS Code route", () => {
  beforeEach(() => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
  });

  afterEach(() => {
    restoreEnv("MISSION_CONTROL_BYPASS_AUTH", ORIGINAL_BYPASS);
    restoreEnv("MISSION_CONTROL_SESSION_SECRET", ORIGINAL_SESSION_SECRET);
    restoreEnv("MISSION_CONTROL_ADMIN_KEY", ORIGINAL_ADMIN_KEY);
    vi.restoreAllMocks();
  });

  it("rejects requests without an operator session, before spawning any process", async () => {
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;

    const canOpenSpy = vi.spyOn(outputFolders, "canOpenVsCode");

    const response = await POST(jsonRequest({ missionId: "mission-abc123" }));

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      detail: expect.stringContaining("operator session"),
    });
    // The session gate must run before any local-machine side effect is attempted.
    expect(canOpenSpy).not.toHaveBeenCalled();
  });

  it("returns 404 for a mission whose output folder has not been written yet", async () => {
    vi.spyOn(outputFolders, "folderExists").mockReturnValue(false);

    const response = await POST(jsonRequest({ missionId: "mission-abc123" }));

    expect(response.status).toBe(404);
  });

  it("rejects an invalid mission id", async () => {
    const response = await POST(jsonRequest({ missionId: "../etc/passwd" }));

    expect(response.status).toBe(400);
  });
});

function restoreEnv(key: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[key];
  } else {
    process.env[key] = value;
  }
}
