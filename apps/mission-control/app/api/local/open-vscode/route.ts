import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { NextRequest, NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import { parseJsonObject, readTrimmedString } from "../../../lib/server/request-validation";
import {
  canOpenLocalWindowsShell,
  canOpenVsCode,
  folderExists,
  resolveMissionOutputFolder,
} from "../_lib/output-folders";

export const runtime = "nodejs";

function resolveVsCodeExe(): string | null {
  try {
    const raw = execFileSync("where.exe", ["code"], {
      encoding: "utf8",
      timeout: 2000,
      windowsHide: true,
    });
    for (const line of raw.split(/\r?\n/)) {
      const candidate = line.trim();
      if (!candidate) continue;
      if (candidate.toLowerCase().endsWith(".exe") && fs.existsSync(candidate)) {
        return candidate;
      }
      const adjacentExe = path.resolve(path.dirname(candidate), "..", "Code.exe");
      if (fs.existsSync(adjacentExe)) {
        return adjacentExe;
      }
    }
  } catch {
    return null;
  }
  return null;
}

export async function POST(request: NextRequest) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }

  const payload = await parseJsonObject(request);
  if (!payload) {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  const missionId = readTrimmedString(payload, "missionId");

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

  if (/[\r\n\0"&|<>^%!$`]/.test(targetPath)) {
    return NextResponse.json(
      { error: "Unsafe characters in target output folder path.", path: targetPath },
      { status: 400 },
    );
  }

  try {
    const codeExe = resolveVsCodeExe();
    const child = codeExe
      ? spawn(/*turbopackIgnore: true*/ codeExe, [targetPath], {
          detached: true,
          stdio: "ignore",
          windowsHide: true,
          shell: false,
        })
      : spawn("cmd.exe", ["/d", "/s", "/c", "code", targetPath], {
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
