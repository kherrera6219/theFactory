import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

export const runtime = "nodejs";

type ReviewApprovalRequest = {
  scope?: "builder" | "repo";
  fingerprint?: string;
  summary?: string;
  metadata?: Record<string, unknown>;
};

type StoredApprovalRecord = {
  approval_id: string;
  scope: "builder" | "repo";
  fingerprint: string;
  approved_at: string;
  summary: string;
  receipt_digest: string;
  metadata: Record<string, unknown>;
};

function sanitizeText(value: string | undefined, maxLength: number): string {
  return String(value ?? "")
    .replace(/[\u0000-\u0008\u000B-\u001F\u007F]/g, "")
    .trim()
    .slice(0, maxLength);
}

function approvalsRoot(): string {
  return (
    process.env.MISSION_CONTROL_APPROVAL_STORE_ROOT?.trim() ||
    path.resolve(process.cwd(), ".runtime", "review-approvals")
  );
}

function relativeRecordPath(approvalId: string): string {
  return path.join(".runtime", "review-approvals", `${approvalId}.json`).replace(/\\/g, "/");
}

function canonicalDigest(record: Omit<StoredApprovalRecord, "receipt_digest">): string {
  return createHash("sha256").update(JSON.stringify(record)).digest("hex");
}

export async function POST(request: Request) {
  let payload: ReviewApprovalRequest;
  try {
    payload = (await request.json()) as ReviewApprovalRequest;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const scope = payload.scope;
  if (scope !== "builder" && scope !== "repo") {
    return NextResponse.json({ detail: "scope must be builder or repo." }, { status: 400 });
  }

  const fingerprint = sanitizeText(payload.fingerprint, 200);
  if (fingerprint.length < 12) {
    return NextResponse.json({ detail: "fingerprint must be at least 12 characters." }, { status: 400 });
  }

  const summary = sanitizeText(payload.summary, 400);
  if (summary.length < 3) {
    return NextResponse.json({ detail: "summary must be at least 3 characters." }, { status: 400 });
  }

  const metadata = payload.metadata && typeof payload.metadata === "object" ? payload.metadata : {};
  const approvedAt = new Date().toISOString();
  const approvalId = `${scope}-approval-${fingerprint.slice(0, 12)}-${Date.now()}`;
  const recordWithoutDigest = {
    approval_id: approvalId,
    scope,
    fingerprint,
    approved_at: approvedAt,
    summary,
    metadata,
  } satisfies Omit<StoredApprovalRecord, "receipt_digest">;
  const receiptDigest = canonicalDigest(recordWithoutDigest);
  const record: StoredApprovalRecord = {
    ...recordWithoutDigest,
    receipt_digest: receiptDigest,
  };

  const recordPath = path.join(approvalsRoot(), `${approvalId}.json`);
  await fs.mkdir(path.dirname(recordPath), { recursive: true });
  await fs.writeFile(recordPath, JSON.stringify(record, null, 2), "utf-8");

  return NextResponse.json({
    approval_id: approvalId,
    scope,
    fingerprint,
    approved_at: approvedAt,
    summary,
    receipt_digest: receiptDigest,
    record_path: relativeRecordPath(approvalId),
  });
}
