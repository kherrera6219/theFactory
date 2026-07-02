import { createHash } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

type ZipFixtureEntry = {
  name: string;
  content?: string | Buffer;
};

type FormDataPart = {
  name: string;
  value?: string;
  fileName?: string;
  contentType?: string;
  content?: string | Buffer;
};

const ORIGINAL_BYPASS = process.env.MISSION_CONTROL_BYPASS_AUTH;
const ORIGINAL_SESSION_SECRET = process.env.MISSION_CONTROL_SESSION_SECRET;
const ORIGINAL_ADMIN_KEY = process.env.MISSION_CONTROL_ADMIN_KEY;

describe("repo ZIP review route", () => {
  beforeEach(() => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
  });

  afterEach(() => {
    restoreEnv("MISSION_CONTROL_BYPASS_AUTH", ORIGINAL_BYPASS);
    restoreEnv("MISSION_CONTROL_SESSION_SECRET", ORIGINAL_SESSION_SECRET);
    restoreEnv("MISSION_CONTROL_ADMIN_KEY", ORIGINAL_ADMIN_KEY);
    vi.restoreAllMocks();
  });

  it("builds a review artifact and source bundle from selected ZIP files without GitHub fetches", async () => {
    const zipBuffer = createStoredZip([
      { name: "sample-main/" },
      { name: "sample-main/README.md", content: "# Sample Platform\n" },
      { name: "sample-main/apps/mission-control/app/(shell)/repo/page.tsx", content: "\"use client\";\nexport default function RepoPage() { return null; }\n" },
    ]);
    const archiveSha256 = createHash("sha256").update(zipBuffer).digest("hex");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("unexpected fetch"));

    const response = await POST(
      createFormDataRequest([
        { name: "archive", fileName: "sample-main.zip", contentType: "application/zip", content: zipBuffer },
        { name: "display_name", value: "Sample Platform" },
        { name: "source_ref", value: "main" },
        { name: "subdirectory", value: "/" },
        { name: "archive_sha256", value: archiveSha256 },
        {
          name: "selected_files",
          value: JSON.stringify([
            {
              path: "apps/mission-control/app/(shell)/repo/page.tsx",
              overlay_action: "include",
              language: "TypeScript",
              bytes: 68,
              estimated_lines: 2,
            },
            {
              path: "README.md",
              overlay_action: "reference",
              language: "Markdown",
              bytes: 18,
              estimated_lines: 1,
            },
          ]),
        },
        { name: "mission_type", value: "analyze" },
        { name: "description", value: "Review repository scope before launch." },
      ]),
    );

    expect(response.status).toBe(200);
    const payload = (await response.json()) as Record<string, unknown>;

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(payload.request_id).toBeTypeOf("string");
    expect(payload.review_fingerprint).toBeTypeOf("string");
    expect(payload.requested_target_language).toBe("typescript");
    expect(String(payload.source_code)).toContain("## FILE apps/mission-control/app/(shell)/repo/page.tsx");
    expect(String(payload.source_code)).toContain("## FILE README.md");
    expect(payload.repository).toMatchObject({
      source: "zip",
      owner: "local",
      repo: "Sample Platform",
      branch: "main",
      archive_sha256: archiveSha256,
      root_prefix: "sample-main/",
    });
    expect(payload.diff_summary).toEqual(
      expect.arrayContaining([expect.stringContaining("uploaded ZIP Sample Platform@main")]),
    );

    const files = payload.files as Array<Record<string, unknown>>;
    expect(files).toHaveLength(2);
    expect(files[0]).toMatchObject({
      path: "apps/mission-control/app/(shell)/repo/page.tsx",
      overlay_action: "include",
      included_in_source: true,
      requested_language: "typescript",
    });
    expect(files[0].sha).toHaveLength(64);
    expect(files[1]).toMatchObject({
      path: "README.md",
      overlay_action: "reference",
      included_in_source: true,
    });
  });

  it("rejects archive SHA mismatches before building a review", async () => {
    const zipBuffer = createStoredZip([{ name: "README.md", content: "# Sample\n" }]);

    const response = await POST(
      createFormDataRequest([
        { name: "archive", fileName: "sample.zip", contentType: "application/zip", content: zipBuffer },
        { name: "archive_sha256", value: "0".repeat(64) },
        { name: "mission_type", value: "analyze" },
        {
          name: "selected_files",
          value: JSON.stringify([{ path: "README.md", overlay_action: "include" }]),
        },
      ]),
    );

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      detail: "archive_sha256 does not match the uploaded ZIP archive.",
    });
  });

  it("requires archive SHA binding for review", async () => {
    const zipBuffer = createStoredZip([{ name: "README.md", content: "# Sample\n" }]);

    const response = await POST(
      createFormDataRequest([
        { name: "archive", fileName: "sample.zip", contentType: "application/zip", content: zipBuffer },
        { name: "mission_type", value: "analyze" },
        {
          name: "selected_files",
          value: JSON.stringify([{ path: "README.md", overlay_action: "include" }]),
        },
      ]),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      detail: "archive_sha256 is required for repository ZIP review.",
    });
  });

  it("reviews a selected file outside the top display slice", async () => {
    const entries: ZipFixtureEntry[] = Array.from({ length: 121 }, (_, index) => ({
      name: `src/large-${String(index).padStart(3, "0")}.ts`,
      content: "x".repeat(500 + index),
    }));
    entries.push({ name: "README.md", content: "# Small selected file\n" });
    const zipBuffer = createStoredZip(entries);
    const archiveSha256 = createHash("sha256").update(zipBuffer).digest("hex");

    const response = await POST(
      createFormDataRequest([
        { name: "archive", fileName: "sample.zip", contentType: "application/zip", content: zipBuffer },
        { name: "archive_sha256", value: archiveSha256 },
        { name: "mission_type", value: "analyze" },
        {
          name: "selected_files",
          value: JSON.stringify([{ path: "README.md", overlay_action: "include" }]),
        },
      ]),
    );

    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload.files).toHaveLength(1);
    expect(payload.files[0]).toMatchObject({
      path: "README.md",
      bytes: Buffer.byteLength("# Small selected file\n"),
    });
  });

  it("keeps archive metadata authoritative for zero-byte files", async () => {
    const zipBuffer = createStoredZip([{ name: "empty.txt", content: "" }]);
    const archiveSha256 = createHash("sha256").update(zipBuffer).digest("hex");

    const response = await POST(
      createFormDataRequest([
        { name: "archive", fileName: "sample.zip", contentType: "application/zip", content: zipBuffer },
        { name: "archive_sha256", value: archiveSha256 },
        { name: "mission_type", value: "analyze" },
        {
          name: "selected_files",
          value: JSON.stringify([
            {
              path: "empty.txt",
              overlay_action: "include",
              bytes: 999_999,
              estimated_lines: 22_222,
            },
          ]),
        },
      ]),
    );

    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload.files[0]).toMatchObject({
      path: "empty.txt",
      bytes: 0,
      estimated_lines: 1,
    });
  });

  it("rejects update reviews without a description", async () => {
    const zipBuffer = createStoredZip([{ name: "README.md", content: "# Sample\n" }]);

    const response = await POST(
      createFormDataRequest([
        { name: "archive", fileName: "sample.zip", contentType: "application/zip", content: zipBuffer },
        { name: "mission_type", value: "update" },
        { name: "description", value: "" },
        {
          name: "selected_files",
          value: JSON.stringify([{ path: "README.md", overlay_action: "include" }]),
        },
      ]),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      detail: "description must be provided for update and add_feature reviews.",
    });
  });

  it("rejects missing archive uploads", async () => {
    const response = await POST(
      createFormDataRequest([
        { name: "mission_type", value: "analyze" },
        {
          name: "selected_files",
          value: JSON.stringify([{ path: "README.md", overlay_action: "include" }]),
        },
      ]),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      detail: expect.stringContaining("archive"),
    });
  });

  it("rejects repository review without an operator session", async () => {
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;

    const response = await POST(
      new Request("http://localhost/api/repo/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }),
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      detail: expect.stringContaining("operator session"),
    });
  });
});

function restoreEnv(key: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[key];
    return;
  }
  process.env[key] = value;
}

function createFormDataRequest(parts: FormDataPart[]): Request {
  const formData = new FormData();
  for (const part of parts) {
    if (part.fileName) {
      const fileContent = Buffer.isBuffer(part.content)
        ? new Uint8Array(part.content)
        : part.content ?? "";
      formData.set(
        part.name,
        new File([fileContent], part.fileName, {
          type: part.contentType ?? "application/octet-stream",
        }),
      );
      continue;
    }
    formData.set(part.name, part.value ?? "");
  }
  return {
    headers: new Headers(),
    formData: async () => formData,
  } as unknown as Request;
}

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
