import { spawn } from "node:child_process";

import { NextRequest, NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import {
  canOpenLocalWindowsShell,
  canOpenVsCode,
  folderExists,
  resolveMissionOutputFolder,
} from "../_lib/output-folders";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }

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
      { error: "Output folder has not been written yet.", path: targetPath },
      { status: 404 },
    );
  }

  if (!canOpenLocalWindowsShell()) {
    return NextResponse.json(
      {
        error: "Opening VS Code is only supported from the local Windows UI process.",
        path: targetPath,
      },
      { status: 409 },
    );
  }

  if (!canOpenVsCode()) {
    return NextResponse.json(
      {
        error: "VS Code CLI 'code' is not available on PATH.",
        path: targetPath,
      },
      { status: 409 },
    );
  }

  try {
    const quotedPath = targetPath.replaceAll('"', '""');
    const child = spawn("cmd.exe", ["/d", "/s", "/c", `code "${quotedPath}"`], {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    });
    child.unref();
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Unable to open VS Code.",
        path: targetPath,
      },
      { status: 500 },
    );
  }

  return NextResponse.json({ opened: true, path: targetPath });
}
