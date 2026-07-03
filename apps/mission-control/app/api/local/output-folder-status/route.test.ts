import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as outputFolders from "../_lib/output-folders";
import { GET } from "./route";

const ORIGINAL_BYPASS = process.env.MISSION_CONTROL_BYPASS_AUTH;
const ORIGINAL_SESSION_SECRET = process.env.MISSION_CONTROL_SESSION_SECRET;
const ORIGINAL_ADMIN_KEY = process.env.MISSION_CONTROL_ADMIN_KEY;

describe("output folder status route", () => {
  beforeEach(() => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
  });

  afterEach(() => {
    restoreEnv("MISSION_CONTROL_BYPASS_AUTH", ORIGINAL_BYPASS);
    restoreEnv("MISSION_CONTROL_SESSION_SECRET", ORIGINAL_SESSION_SECRET);
    restoreEnv("MISSION_CONTROL_ADMIN_KEY", ORIGINAL_ADMIN_KEY);
    vi.restoreAllMocks();
  });

  it("rejects requests without an operator session", async () => {
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;

    const response = await GET(
      new NextRequest("http://localhost/api/local/output-folder-status?missionId=mission-abc123"),
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      detail: expect.stringContaining("operator session"),
    });
  });

  it("returns folder status for a valid mission id when authorized", async () => {
    vi.spyOn(outputFolders, "folderExists").mockReturnValue(false);

    const response = await GET(
      new NextRequest("http://localhost/api/local/output-folder-status?missionId=mission-abc123"),
    );

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.missionId).toBe("mission-abc123");
    expect(body.exists).toBe(false);
    expect(body.canOpenFolder).toBe(false);
  });

  it("rejects an invalid mission id", async () => {
    const response = await GET(
      new NextRequest("http://localhost/api/local/output-folder-status?missionId=../etc/passwd"),
    );

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
