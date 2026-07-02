import { createHash } from "node:crypto";

import { describe, expect, it } from "vitest";

import {
  detectCommonRootPrefix,
  indexZipArchive,
  normalizeArchivePath,
  readZipTextFile,
  safeRepoPath,
} from "./archive";

type ZipFixtureEntry = {
  name: string;
  content?: string | Buffer;
};

describe("repo ZIP archive helpers", () => {
  it("normalizes safe repository paths and rejects dangerous entries", () => {
    expect(safeRepoPath("src\\main.ts")).toBe("src/main.ts");
    expect(safeRepoPath("repo-main/src/index.ts")).toBe("repo-main/src/index.ts");
    expect(safeRepoPath("../secrets.txt")).toBeNull();
    expect(safeRepoPath("src/../secrets.txt")).toBeNull();
    expect(safeRepoPath("/absolute/path.ts")).toBeNull();
    expect(safeRepoPath("C:/absolute/path.ts")).toBeNull();
    expect(safeRepoPath("\\\\server\\share\\path.ts")).toBeNull();
    expect(safeRepoPath("src//path.ts")).toBeNull();
    expect(safeRepoPath("src/\0/path.ts")).toBeNull();
  });

  it("detects and strips a common archive root", () => {
    expect(
      detectCommonRootPrefix([
        "sample-main/README.md",
        "sample-main/src/index.ts",
        "sample-main/package.json",
      ]),
    ).toBe("sample-main/");
    expect(normalizeArchivePath("sample-main/src/index.ts", "sample-main/")).toBe(
      "src/index.ts",
    );
    expect(normalizeArchivePath("src/index.ts", "sample-main/")).toBeNull();
    expect(detectCommonRootPrefix(["README.md", "src/index.ts"])).toBe("");
  });

  it("indexes ZIP files with common root stripping, subdirectory filtering, and limits", async () => {
    const zipBuffer = createStoredZip([
      { name: "sample-main/" },
      { name: "sample-main/README.md", content: "# Sample\n" },
      { name: "sample-main/src/index.ts", content: "export const value = 1;\n" },
      { name: "sample-main/src/util.ts", content: "export function util() {}\n" },
      { name: "sample-main/src/large.ts", content: "x".repeat(80) },
    ]);

    const result = await indexZipArchive(
      { kind: "buffer", buffer: zipBuffer },
      { subdirectory: "/src", maxFiles: 1, largeFileBytes: 50 },
    );

    expect(result.stats.archive_sha256).toBe(
      createHash("sha256").update(zipBuffer).digest("hex"),
    );
    expect(result.stats.root_prefix).toBe("sample-main/");
    expect(result.stats.selected_subdirectory).toBe("/src");
    expect(result.stats.skipped_directory_entries).toBe(1);
    expect(result.stats.skipped_unsafe_entries).toBe(0);
    expect(result.stats.skipped_large_files).toBe(1);
    expect(result.stats.total_files).toBe(2);
    expect(result.stats.truncated).toBe(true);
    expect(result.files).toHaveLength(1);
    expect(result.files[0]).toMatchObject({
      path: "src/util.ts",
      language: "TypeScript",
    });
  });

  it("rejects ZIP archives with traversal entries before indexing", async function () {
    const zipBuffer = createStoredZip([
      { name: "../escape.ts", content: "export const bad = true;\n" },
    ]);

    await expect(
      indexZipArchive({ kind: "buffer", buffer: zipBuffer }),
    ).rejects.toThrow("invalid relative path");
  });

  it("supports root-level ZIP files without forcing a synthetic root", async () => {
    const zipBuffer = createStoredZip([
      { name: "README.md", content: "# Root\n" },
      { name: "src/app.py", content: "print('hi')\n" },
    ]);

    const result = await indexZipArchive({ kind: "buffer", buffer: zipBuffer });

    expect(result.stats.root_prefix).toBe("");
    expect(result.files.map((file) => file.path)).toEqual(["src/app.py", "README.md"]);
  });

  it("includes required paths even when they fall outside the display slice", async () => {
    const zipBuffer = createStoredZip([
      { name: "README.md", content: "# Root\n" },
      { name: "src/app.py", content: "x".repeat(300) },
      { name: "src/util.py", content: "x".repeat(200) },
    ]);

    const result = await indexZipArchive(
      { kind: "buffer", buffer: zipBuffer },
      { maxFiles: 1, requiredPaths: ["README.md"] },
    );

    expect(result.stats.truncated).toBe(true);
    expect(result.files.map((file) => file.path)).toEqual(["src/app.py", "README.md"]);
  });

  it("marks entry and byte cap stops as truncated", async () => {
    const entryLimited = await indexZipArchive(
      {
        kind: "buffer",
        buffer: createStoredZip([
          { name: "a.txt", content: "a" },
          { name: "b.txt", content: "b" },
        ]),
      },
      { maxEntries: 1 },
    );
    expect(entryLimited.stats.entry_limit_reached).toBe(true);
    expect(entryLimited.stats.truncated).toBe(true);

    const byteLimited = await indexZipArchive(
      {
        kind: "buffer",
        buffer: createStoredZip([
          { name: "a.txt", content: "aaaa" },
          { name: "b.txt", content: "bbbb" },
        ]),
      },
      { maxTotalUncompressedBytes: 4 },
    );
    expect(byteLimited.stats.byte_limit_reached).toBe(true);
    expect(byteLimited.stats.truncated).toBe(true);
  });

  it("reads selected text entries by normalized repository path", async () => {
    const zipBuffer = createStoredZip([
      { name: "sample-main/README.md", content: "# Sample\n" },
      { name: "sample-main/src/index.ts", content: "export const value = 1;\n" },
    ]);

    const result = await readZipTextFile(
      { kind: "buffer", buffer: zipBuffer },
      "src/index.ts",
      { rootPrefix: "sample-main/" },
    );

    expect(result.text).toBe("export const value = 1;\n");
    expect(result.bytes).toBe(Buffer.byteLength(result.text));
    expect(result.sha256).toBe(
      createHash("sha256").update(result.text).digest("hex"),
    );
  });

  it("rejects binary-looking entries during text reads", async () => {
    const zipBuffer = createStoredZip([
      { name: "sample-main/assets/data.bin", content: Buffer.from([0, 1, 2, 3]) },
    ]);

    await expect(
      readZipTextFile(
        { kind: "buffer", buffer: zipBuffer },
        "assets/data.bin",
        { rootPrefix: "sample-main/" },
      ),
    ).rejects.toThrow("appears to be binary");
  });
});

function createStoredZip(entries: ZipFixtureEntry[]): Buffer {
  const localParts: Buffer[] = [];
  const centralParts: Buffer[] = [];
  let offset = 0;

  for (const entry of entries) {
    const fileName = Buffer.from(entry.name, "utf-8");
    const data = Buffer.isBuffer(entry.content)
      ? entry.content
      : Buffer.from(entry.content ?? "", "utf-8");
    const crc = crc32(data);
    const localHeader = Buffer.alloc(30);
    localHeader.writeUInt32LE(0x04034b50, 0);
    localHeader.writeUInt16LE(20, 4);
    localHeader.writeUInt16LE(0, 6);
    localHeader.writeUInt16LE(0, 8);
    localHeader.writeUInt16LE(0, 10);
    localHeader.writeUInt16LE(0, 12);
    localHeader.writeUInt32LE(crc, 14);
    localHeader.writeUInt32LE(data.length, 18);
    localHeader.writeUInt32LE(data.length, 22);
    localHeader.writeUInt16LE(fileName.length, 26);
    localHeader.writeUInt16LE(0, 28);
    localParts.push(localHeader, fileName, data);

    const centralHeader = Buffer.alloc(46);
    centralHeader.writeUInt32LE(0x02014b50, 0);
    centralHeader.writeUInt16LE(20, 4);
    centralHeader.writeUInt16LE(20, 6);
    centralHeader.writeUInt16LE(0, 8);
    centralHeader.writeUInt16LE(0, 10);
    centralHeader.writeUInt16LE(0, 12);
    centralHeader.writeUInt16LE(0, 14);
    centralHeader.writeUInt32LE(crc, 16);
    centralHeader.writeUInt32LE(data.length, 20);
    centralHeader.writeUInt32LE(data.length, 24);
    centralHeader.writeUInt16LE(fileName.length, 28);
    centralHeader.writeUInt16LE(0, 30);
    centralHeader.writeUInt16LE(0, 32);
    centralHeader.writeUInt16LE(0, 34);
    centralHeader.writeUInt16LE(0, 36);
    centralHeader.writeUInt32LE(entry.name.endsWith("/") ? 0x10 : 0, 38);
    centralHeader.writeUInt32LE(offset, 42);
    centralParts.push(centralHeader, fileName);

    offset += localHeader.length + fileName.length + data.length;
  }

  const centralDirectory = Buffer.concat(centralParts);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(0, 4);
  end.writeUInt16LE(0, 6);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(centralDirectory.length, 12);
  end.writeUInt32LE(offset, 16);
  end.writeUInt16LE(0, 20);

  return Buffer.concat([...localParts, centralDirectory, end]);
}

function crc32(buffer: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc = (crc >>> 8) ^ CRC_TABLE[(crc ^ byte) & 0xff];
  }
  return (crc ^ 0xffffffff) >>> 0;
}

const CRC_TABLE = Array.from({ length: 256 }, (_, tableIndex) => {
  let value = tableIndex;
  for (let bit = 0; bit < 8; bit += 1) {
    value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  }
  return value >>> 0;
});
