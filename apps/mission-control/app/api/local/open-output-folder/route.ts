import { spawn } from "node:child_process";

import { NextRequest, NextResponse } from "next/server";

import {
  canOpenLocalWindowsShell,
  folderExists,
  resolveMissionOutputFolder,
} from "../_lib/output-folders";

export const runtime = "nodejs";
export async function POST(request: NextRequest) {
  let missionId = "";
  try {
    const payload = (await request.json()) as { missionId?: unknown };
    missionId = String(payload.missionId ?? "").trim();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  let targetPath = "";
  try {
    targetPath = resolveMissionOutputFolder(missionId).targetPath;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Invalid mission id." },
      { status: 400 },
    );
  }

  if (!folderExists(targetPath)) {
    return NextResponse.json(
      {
        error: "Output folder has not been written yet.",
        path: targetPath,
      },
      { status: 404 },
    );
  }

  if (!canOpenLocalWindowsShell()) {
    return NextResponse.json(
      {
        error: "Opening folders is only supported from the local Windows UI process.",
        path: targetPath,
      },
      { status: 409 },
    );
  }

  try {
    const child = spawn("explorer.exe", [targetPath], {
      detached: true,
      stdio: "ignore",
      windowsHide: false,
    });
    child.unref();
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Unable to open output folder.",
        path: targetPath,
      },
      { status: 500 },
    );
  }

  return NextResponse.json({ opened: true, path: targetPath });
}
