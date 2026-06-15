import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import { isApprovalHmacValid } from "../../../lib/server/review-approvals";

export const runtime = "nodejs";

const ORCHESTRATOR_INTERNAL_BASE_URL =
  process.env.ORCHESTRATOR_INTERNAL_BASE_URL?.trim() || "http://localhost:8101";
const INTERNAL_SERVICE_API_KEY = process.env.INTERNAL_SERVICE_API_KEY?.trim() || "";

type ReviewApprovalVerificationRequest = {
  scope?: "builder" | "repo" | "delivery";
  approval_id?: string;
  fingerprint?: string;
  receipt_digest?: string;
};

type ReviewApprovalRecord = {
  approval_id?: string;
  scope?: "builder" | "repo" | "delivery";
  fingerprint?: string;
  summary?: string;
  receipt_digest?: string;
  approved_at?: string;
  expires_at?: string | null;
  hmac_digest?: string | null;
};

function sanitizeText(value: string | undefined, maxLength: number): string {
  return String(value ?? "")
    .replace(/[\u0000-\u0008\u000B-\u001F\u007F]/g, "")
    .trim()
    .slice(0, maxLength);
}

export async function POST(request: Request) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }
  if (!INTERNAL_SERVICE_API_KEY) {
    return NextResponse.json(
      { detail: "INTERNAL_SERVICE_API_KEY is required for review approval verification." },
      { status: 503 },
    );
  }

  let payload: ReviewApprovalVerificationRequest;
  try {
    payload = (await request.json()) as ReviewApprovalVerificationRequest;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const approvalId = sanitizeText(payload.approval_id, 120);
  const fingerprint = sanitizeText(payload.fingerprint, 200);
  const receiptDigest = sanitizeText(payload.receipt_digest, 200);
  if (!approvalId || !fingerprint || !receiptDigest) {
    return NextResponse.json(
      { detail: "approval_id, fingerprint, and receipt_digest are required." },
      { status: 400 },
    );
  }

  try {
    const upstream = await fetch(
      `${ORCHESTRATOR_INTERNAL_BASE_URL}/internal/review-approvals/${encodeURIComponent(approvalId)}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": INTERNAL_SERVICE_API_KEY,
        },
        cache: "no-store",
      },
    );

    const text = await upstream.text();
    let parsed: ReviewApprovalRecord | { detail?: string } = {};
    try {
      parsed = text ? (JSON.parse(text) as ReviewApprovalRecord) : {};
    } catch {
      parsed = { detail: text || "Unexpected review approval verification response." };
    }

    if (!upstream.ok) {
      return NextResponse.json(parsed, { status: upstream.status });
    }

    const record = parsed as ReviewApprovalRecord;
    if (
      record.approval_id !== approvalId ||
      record.fingerprint !== fingerprint ||
      record.receipt_digest !== receiptDigest ||
      (payload.scope && record.scope !== payload.scope)
    ) {
      return NextResponse.json(
        { valid: false, detail: "Review approval receipt does not match the stored record." },
        { status: 409 },
      );
    }

    if (record.expires_at) {
      const expiresAtMs = Date.parse(record.expires_at);
      if (Number.isFinite(expiresAtMs) && expiresAtMs <= Date.now()) {
        return NextResponse.json(
          { valid: false, detail: "Review approval has expired." },
          { status: 409 },
        );
      }
    }

    if (
      !record.scope ||
      !record.summary ||
      !record.approved_at ||
      !record.hmac_digest ||
      !isApprovalHmacValid(record.hmac_digest, {
        scope: record.scope,
        fingerprint,
        summary: record.summary,
        approvedAt: record.approved_at,
      })
    ) {
      return NextResponse.json(
        { valid: false, detail: "Review approval integrity validation failed." },
        { status: 409 },
      );
    }

    return NextResponse.json({
      valid: true,
      approval_id: approvalId,
      scope: record.scope,
      fingerprint,
      approved_at: record.approved_at,
      expires_at: record.expires_at ?? null,
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error ? error.message : "Unable to validate review approval record.",
      },
      { status: 502 },
    );
  }
}
