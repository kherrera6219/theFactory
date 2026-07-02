import { createHash } from "node:crypto";
import { Readable } from "node:stream";

import { fromBufferPromise, openPromise } from "yauzl";
import type { Entry, ZipFile } from "yauzl";

import {
  clampMaxFiles,
  estimateLines,
  languageFromPath,
  LARGE_FILE_BYTES,
  normalizeSubdirectory,
  RepoFileRecord,
} from "./shared";

export type RepoZipSource =
  | { kind: "buffer"; buffer: Buffer }
  | { kind: "file"; path: string };

export type RepoZipIndexOptions = {
  maxFiles?: number;
  subdirectory?: string;
  maxEntries?: number;
  maxTotalUncompressedBytes?: number;
  largeFileBytes?: number;
  requiredPaths?: string[];
};

export type RepoZipIndexStats = {
  archive_sha256: string;
  root_prefix: string;
  total_entries: number;
  total_files: number;
  total_uncompressed_bytes: number;
  selected_subdirectory: string;
  skipped_large_files: number;
  skipped_unsafe_entries: number;
  skipped_directory_entries: number;
  skipped_unreadable_entries: number;
  entry_limit_reached: boolean;
  byte_limit_reached: boolean;
  truncated: boolean;
};

export type RepoZipIndexResult = {
  files: RepoFileRecord[];
  stats: RepoZipIndexStats;
  logs: string[];
};

type SafeEntry = {
  rawName: string;
  fullPath: string;
  repoPath: string;
  bytes: number;
  entry: Entry;
};

const DEFAULT_MAX_ENTRIES = 10_000;
const DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES = 250_000_000;
const TEXT_DECODE_BYTE_LIMIT = LARGE_FILE_BYTES;

export function safeRepoPath(entryName: string): string | null {
  if (!entryName || entryName.includes("\0")) {
    return null;
  }
  const trimmed = entryName.trim();
  if (!trimmed) {
    return null;
  }
  const normalized = trimmed.replace(/\\/g, "/");
  if (
    normalized.startsWith("/") ||
    normalized.startsWith("//") ||
    /^[A-Za-z]:/.test(normalized)
  ) {
    return null;
  }
  const segments = normalized.split("/");
  if (
    segments.some(
      (segment) => segment.length === 0 || segment === "." || segment === "..",
    )
  ) {
    return null;
  }
  return segments.join("/");
}

export function detectCommonRootPrefix(paths: string[]): string {
  const filePaths = paths
    .map((path) => safeRepoPath(path))
    .filter((path): path is string => Boolean(path));
  if (filePaths.length === 0) {
    return "";
  }
  const firstSegments = filePaths.map((path) => path.split("/")[0]);
  const candidate = firstSegments[0];
  if (!candidate || firstSegments.some((segment) => segment !== candidate)) {
    return "";
  }
  if (filePaths.some((path) => !path.includes("/"))) {
    return "";
  }
  return `${candidate}/`;
}

export function normalizeArchivePath(entryName: string, rootPrefix = ""): string | null {
  const safePath = safeRepoPath(entryName);
  if (!safePath) {
    return null;
  }
  if (!rootPrefix) {
    return safePath;
  }
  const normalizedRoot = safeRepoPath(rootPrefix.replace(/\/$/, ""));
  if (!normalizedRoot) {
    return safePath;
  }
  const prefix = `${normalizedRoot}/`;
  return safePath.startsWith(prefix) ? safePath.slice(prefix.length) : null;
}

export async function indexZipArchive(
  source: RepoZipSource,
  options: RepoZipIndexOptions = {},
): Promise<RepoZipIndexResult> {
  const maxFiles = clampMaxFiles(options.maxFiles);
  const maxEntries = options.maxEntries ?? DEFAULT_MAX_ENTRIES;
  const maxTotalUncompressedBytes =
    options.maxTotalUncompressedBytes ?? DEFAULT_MAX_TOTAL_UNCOMPRESSED_BYTES;
  const largeFileBytes = options.largeFileBytes ?? LARGE_FILE_BYTES;
  const subdirectory = normalizeSubdirectory(options.subdirectory ?? "/");
  const archiveSha256 = await hashZipSource(source);
  const zipFile = await openZipSource(source);
  const logs: string[] = [];
  let totalEntries = 0;
  let skippedUnsafeEntries = 0;
  let skippedDirectoryEntries = 0;
  let skippedUnreadableEntries = 0;
  let skippedLargeFiles = 0;
  let totalUncompressedBytes = 0;
  let entryLimitReached = false;
  let byteLimitReached = false;

  try {
    const safeEntries: SafeEntry[] = [];
    for await (const entry of zipFile.eachEntry()) {
      totalEntries += 1;
      if (totalEntries > maxEntries) {
        entryLimitReached = true;
        logs.push(`Stopped reading archive after ${maxEntries} entries.`);
        break;
      }

      const rawName = entry.fileName;
      if (rawName.endsWith("/")) {
        skippedDirectoryEntries += 1;
        continue;
      }

      const fullPath = safeRepoPath(rawName);
      if (!fullPath) {
        skippedUnsafeEntries += 1;
        continue;
      }

      if (!entry.canDecodeFileData() || entry.isEncrypted()) {
        skippedUnreadableEntries += 1;
        continue;
      }

      const bytes = entry.uncompressedSize;
      totalUncompressedBytes += bytes;
      if (totalUncompressedBytes > maxTotalUncompressedBytes) {
        byteLimitReached = true;
        logs.push(
          `Stopped indexing after archive exceeded ${maxTotalUncompressedBytes} uncompressed bytes.`,
        );
        break;
      }

      safeEntries.push({ rawName, fullPath, repoPath: fullPath, bytes, entry });
    }

    const rootPrefix = detectCommonRootPrefix(safeEntries.map((entry) => entry.fullPath));
    const selectedPrefix = subdirectory === "/" ? "" : `${subdirectory.slice(1)}/`;
    const matches: RepoFileRecord[] = [];

    for (const safeEntry of safeEntries) {
      const repoPath = normalizeArchivePath(safeEntry.fullPath, rootPrefix);
      if (!repoPath) {
        skippedUnsafeEntries += 1;
        continue;
      }
      safeEntry.repoPath = repoPath;
      if (selectedPrefix && !repoPath.startsWith(selectedPrefix)) {
        continue;
      }
      if (safeEntry.bytes > largeFileBytes) {
        skippedLargeFiles += 1;
        continue;
      }
      matches.push({
        path: repoPath,
        language: languageFromPath(repoPath),
        bytes: safeEntry.bytes,
        estimated_lines: estimateLines(safeEntry.bytes),
      });
    }

    matches.sort((left, right) => {
      if (right.bytes !== left.bytes) {
        return right.bytes - left.bytes;
      }
      return left.path.localeCompare(right.path);
    });
    const listedFiles = matches.slice(0, maxFiles);
    const listedPaths = new Set(listedFiles.map((file) => file.path));
    const requiredPaths = new Set(
      (options.requiredPaths ?? [])
        .map((path) => safeRepoPath(path))
        .filter((path): path is string => Boolean(path)),
    );
    for (const requiredPath of requiredPaths) {
      if (listedPaths.has(requiredPath)) {
        continue;
      }
      const match = matches.find((file) => file.path === requiredPath);
      if (match) {
        listedFiles.push(match);
        listedPaths.add(requiredPath);
      }
    }

    return {
      files: listedFiles,
      logs,
      stats: {
        archive_sha256: archiveSha256,
        root_prefix: rootPrefix,
        total_entries: totalEntries,
        total_files: matches.length,
        total_uncompressed_bytes: totalUncompressedBytes,
        selected_subdirectory: subdirectory,
        skipped_large_files: skippedLargeFiles,
        skipped_unsafe_entries: skippedUnsafeEntries,
        skipped_directory_entries: skippedDirectoryEntries,
        skipped_unreadable_entries: skippedUnreadableEntries,
        entry_limit_reached: entryLimitReached,
        byte_limit_reached: byteLimitReached,
        truncated: matches.length > maxFiles || entryLimitReached || byteLimitReached,
      },
    };
  } finally {
    zipFile.close();
  }
}

export async function readZipTextFile(
  source: RepoZipSource,
  repoPath: string,
  options: { rootPrefix?: string; maxBytes?: number } = {},
): Promise<{ text: string; bytes: number; sha256: string }> {
  const results = await readZipTextFiles(source, [repoPath], options);
  const result = results.get(repoPath);
  if (!result) {
    throw new Error(`ZIP entry not found: ${repoPath}`);
  }
  if ("error" in result) {
    throw result.error;
  }
  return {
    text: result.text,
    bytes: result.bytes,
    sha256: result.sha256,
  };
}

export async function readZipTextFiles(
  source: RepoZipSource,
  repoPaths: string[],
  options: { rootPrefix?: string; maxBytes?: number } = {},
): Promise<Map<string, { text: string; bytes: number; sha256: string } | { error: Error }>> {
  const targetPaths = new Set<string>();
  for (const repoPath of repoPaths) {
    const targetPath = safeRepoPath(repoPath);
    if (!targetPath) {
      targetPaths.add(repoPath);
      continue;
    }
    targetPaths.add(targetPath);
  }
  const results = new Map<string, { text: string; bytes: number; sha256: string } | { error: Error }>();
  for (const repoPath of repoPaths) {
    if (!safeRepoPath(repoPath)) {
      results.set(repoPath, { error: new Error("Requested ZIP path is unsafe.") });
    }
  }
  const zipFile = await openZipSource(source);
  const maxBytes = options.maxBytes ?? TEXT_DECODE_BYTE_LIMIT;

  try {
    for await (const entry of zipFile.eachEntry()) {
      if (entry.fileName.endsWith("/")) {
        continue;
      }
      const entryPath = normalizeArchivePath(entry.fileName, options.rootPrefix ?? "");
      if (!entryPath || !targetPaths.has(entryPath) || results.has(entryPath)) {
        continue;
      }
      if (!entry.canDecodeFileData() || entry.isEncrypted()) {
        results.set(entryPath, { error: new Error(`ZIP entry cannot be decoded: ${entryPath}`) });
        continue;
      }
      if (entry.uncompressedSize > maxBytes) {
        results.set(entryPath, { error: new Error(`ZIP entry exceeds text read limit: ${entryPath}`) });
        continue;
      }
      try {
        const stream = await zipFile.openReadStreamPromise(entry);
        const buffer = await streamToBuffer(stream, maxBytes);
        if (looksBinary(buffer)) {
          results.set(entryPath, { error: new Error(`ZIP entry appears to be binary: ${entryPath}`) });
          continue;
        }
        results.set(entryPath, {
          text: buffer.toString("utf-8"),
          bytes: buffer.length,
          sha256: createHash("sha256").update(buffer).digest("hex"),
        });
      } catch (error) {
        results.set(entryPath, {
          error: error instanceof Error ? error : new Error("ZIP entry could not be read."),
        });
      }
    }
  } finally {
    zipFile.close();
  }

  for (const targetPath of targetPaths) {
    if (!results.has(targetPath)) {
      results.set(targetPath, { error: new Error(`ZIP entry not found: ${targetPath}`) });
    }
  }
  return results;
}

async function openZipSource(source: RepoZipSource): Promise<ZipFile> {
  const options = {
    lazyEntries: true,
    validateEntrySizes: true,
    strictFileNames: false,
  };
  if (source.kind === "buffer") {
    return fromBufferPromise(source.buffer, options);
  }
  return openPromise(source.path, options);
}

async function hashZipSource(source: RepoZipSource): Promise<string> {
  if (source.kind === "buffer") {
    return createHash("sha256").update(source.buffer).digest("hex");
  }
  const { createReadStream } = await import("node:fs");
  const hash = createHash("sha256");
  await new Promise<void>((resolve, reject) => {
    const stream = createReadStream(source.path);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("error", reject);
    stream.on("end", resolve);
  });
  return hash.digest("hex");
}

async function streamToBuffer(stream: Readable, maxBytes: number): Promise<Buffer> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of stream) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.length;
    if (total > maxBytes) {
      throw new Error("ZIP entry stream exceeded text read limit.");
    }
    chunks.push(buffer);
  }
  return Buffer.concat(chunks, total);
}

function looksBinary(buffer: Buffer): boolean {
  if (buffer.length === 0) {
    return false;
  }
  const sampleLength = Math.min(buffer.length, 4096);
  for (let index = 0; index < sampleLength; index += 1) {
    if (buffer[index] === 0) {
      return true;
    }
  }
  return false;
}
