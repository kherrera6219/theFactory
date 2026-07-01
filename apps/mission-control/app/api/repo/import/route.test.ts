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

describe("repo ZIP import route", () => {
  beforeEach(() => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
  });

  afterEach(() => {
    restoreEnv("MISSION_CONTROL_BYPASS_AUTH", ORIGINAL_BYPASS);
    restoreEnv("MISSION_CONTROL_SESSION_SECRET", ORIGINAL_SESSION_SECRET);
    restoreEnv("MISSION_CONTROL_ADMIN_KEY", ORIGINAL_ADMIN_KEY);
    vi.restoreAllMocks();
  });

  it("accepts multipart ZIP uploads and indexes files without GitHub fetches", async () => {
    const zipBuffer = createStoredZip([
      { name: "sample-main/" },
      { name: "sample-main/README.md", content: "# Sample\n" },
      { name: "sample-main/src/app.py", content: "print(\"hi\")\n" },
      { name: "sample-main/src/util.py", content: "def util():\n    return 1\n" },
      { name: "sample-main/src/large.py", content: "x".repeat(1_500_001) },
    ]);
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("unexpected fetch"));

    const response = await POST(
      createFormDataRequest([
        { name: "archive", fileName: "sample-main.zip", contentType: "application/zip", content: zipBuffer },
        { name: "display_name", value: "Sample Platform" },
        { name: "source_ref", value: "main" },
        { name: "subdirectory", value: "/src" },
        { name: "max_files", value: "1" },
      ]),
    );

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(body.repository).toMatchObject({
      source: "zip",
      owner: "local",
      repo: "Sample Platform",
      branch: "main",
      source_ref: "main",
      root_prefix: "sample-main/",
    });
    expect(body.repository.archive_id).toMatch(/^repozip-[a-f0-9]{12}$/);
    expect(body.repository.archive_sha256).toHaveLength(64);
    expect(body.stats).toMatchObject({
      selected_subdirectory: "/src",
      skipped_directory_entries: 1,
      skipped_large_files: 1,
      truncated: true,
    });
    expect(body.files).toHaveLength(1);
    expect(body.files[0]).toMatchObject({ path: "src/util.py", language: "Python" });
  });

  it("rejects missing archive uploads", async () => {
    const response = await POST(createFormDataRequest([{ name: "display_name", value: "Missing" }]));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      detail: expect.stringContaining("archive"),
    });
  });

  it("rejects non-ZIP uploads before indexing", async () => {
    const response = await POST(
      createFormDataRequest([
        { name: "archive", fileName: "repo.zip", contentType: "application/zip", content: "not a zip" },
      ]),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      detail: "archive must be a valid ZIP file.",
    });
  });

  it("rejects unsupported source refs", async () => {
    const zipBuffer = createStoredZip([{ name: "README.md", content: "# Sample\n" }]);

    const response = await POST(
      createFormDataRequest([
        { name: "archive", fileName: "repo.zip", contentType: "application/zip", content: zipBuffer },
        { name: "source_ref", value: "main;bad" },
      ]),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      detail: "source_ref contains unsupported characters.",
    });
  });

  it("rejects repository intake without an operator session", async () => {
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;

    const response = await POST(
      new Request("http://localhost/api/repo/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: "https://github.com/octo/sample-platform" }),
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