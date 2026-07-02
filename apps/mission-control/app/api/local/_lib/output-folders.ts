import { existsSync } from "node:fs";
import { readdir, stat } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

export const MISSION_ID_PATTERN = /^mission-[a-zA-Z0-9-]+$/;

export type OutputFolderFile = {
  path: string;
  sizeBytes: number;
};

export type MissionOutputFolder = {
  missionId: string;
  outputRoot: string;
  targetPath: string;
};

export function repoRoot(): string {
  return path.resolve(process.cwd(), "..", "..");
}

export function resolveMissionOutputFolder(missionId: string): MissionOutputFolder {
  const normalizedMissionId = missionId.trim();
  if (!MISSION_ID_PATTERN.test(normalizedMissionId)) {
    throw new Error("Invalid mission id.");
  }

  const outputRoot = path.resolve(repoRoot(), "output");
  const targetPath = path.resolve(outputRoot, normalizedMissionId);
  const relative = path.relative(outputRoot, targetPath);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("Output folder is outside the allowed root.");
  }

  return {
    missionId: normalizedMissionId,
    outputRoot,
    targetPath,
  };
}

export function folderExists(targetPath: string): boolean {
  return existsSync(targetPath);
}

export function canOpenLocalWindowsShell(): boolean {
  return process.platform === "win32";
}

export function canOpenVsCode(): boolean {
  if (!canOpenLocalWindowsShell()) {
    return false;
  }
  const result = spawnSync("where.exe", ["code"], {
    stdio: "ignore",
    windowsHide: true,
  });
  return result.status === 0;
}

export async function summarizeFolderFiles(
  targetPath: string,
  params?: { maxFiles?: number },
): Promise<{ fileCount: number; totalBytes: number; files: OutputFolderFile[] }> {
  const maxFiles = params?.maxFiles ?? 50;
  const files: OutputFolderFile[] = [];
  let fileCount = 0;
  let totalBytes = 0;

  async function walk(currentPath: string) {
    const entries = await readdir(currentPath, { withFileTypes: true });
    for (const entry of entries) {
      const entryPath = path.join(currentPath, entry.name);
      if (entry.isDirectory()) {
        await walk(entryPath);
        continue;
      }
      if (!entry.isFile()) {
        continue;
      }
      const entryStat = await stat(entryPath);
      fileCount += 1;
      totalBytes += entryStat.size;
      if (files.length < maxFiles) {
        files.push({
          path: path.relative(targetPath, entryPath).replaceAll(path.sep, "/"),
          sizeBytes: entryStat.size,
        });
      }
    }
  }

  await walk(targetPath);
  return { fileCount, totalBytes, files };
}
