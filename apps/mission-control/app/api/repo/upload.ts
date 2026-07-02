import { NextResponse } from "next/server";

export type UploadedArchive = {
  name?: string;
  type?: string;
  size?: number;
  arrayBuffer: () => Promise<ArrayBuffer>;
};

export const MAX_ARCHIVE_UPLOAD_BYTES = 250_000_000;

export class RepoZipRequestError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function badRequest(detail: string): NextResponse {
  return NextResponse.json({ detail }, { status: 400 });
}

export function formString(formData: FormData, key: string): string {
  const value = formData.get(key);
  return typeof value === "string" ? value.trim() : "";
}

export function isUploadedArchive(value: unknown): value is UploadedArchive {
  return (
    typeof value === "object" &&
    value !== null &&
    "arrayBuffer" in value &&
    typeof (value as UploadedArchive).arrayBuffer === "function"
  );
}

export function stripZipExtension(fileName: string): string {
  return fileName.replace(/\.zip$/i, "");
}

export function sanitizeDisplayName(value: string): string {
  const cleaned = value
    .trim()
    .replace(/\.zip$/i, "")
    .replace(/[^A-Za-z0-9._ -]+/g, "-")
    .replace(/[-_ .]+$/g, "")
    .slice(0, 120);
  return cleaned || "repository-archive";
}

export function archiveLooksLikeZip(buffer: Buffer): boolean {
  if (buffer.length < 4) {
    return false;
  }
  const signature = buffer.readUInt32LE(0);
  return signature === 0x04034b50 || signature === 0x06054b50 || signature === 0x08074b50;
}

export async function uploadedArchiveBuffer(archive: UploadedArchive): Promise<Buffer> {
  if (typeof archive.size === "number" && archive.size > MAX_ARCHIVE_UPLOAD_BYTES) {
    throw new RepoZipRequestError(413, "archive exceeds the maximum upload size.");
  }
  const buffer = Buffer.from(await archive.arrayBuffer());
  if (buffer.length > MAX_ARCHIVE_UPLOAD_BYTES) {
    throw new RepoZipRequestError(413, "archive exceeds the maximum upload size.");
  }
  return buffer;
}
