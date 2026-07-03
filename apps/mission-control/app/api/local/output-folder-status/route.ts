import { NextRequest, NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import {
  canOpenLocalWindowsShell,
  canOpenVsCode,
  folderExists,
  resolveMissionOutputFolder,
  summarizeFolderFiles,
} from "../_lib/output-folders";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }

  const missionId = request.nextUrl.searchParams.get("missionId") ?? "";
  try {
    const folder = resolveMissionOutputFolder(missionId);
    const exists = folderExists(folder.targetPath);
    const summary = exists
      ? await summarizeFolderFiles(folder.targetPath)
      : { fileCount: 0, totalBytes: 0, files: [] };

    return NextResponse.json({
      missionId: folder.missionId,
      path: folder.targetPath,
      exists,
      fileCount: summary.fileCount,
      totalBytes: summary.totalBytes,
      files: summary.files,
      canOpenFolder: exists && canOpenLocalWindowsShell(),
      canOpenVsCode: exists && canOpenVsCode(),
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unable to read output folder status." },
      { status: 400 },
    );
  }
}
