import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import {
  computeApprovalHmacDigest,
  getApprovalHmacSecret,
  getApprovalTtlSeconds,
} from "../../../lib/server/review-approvals";

export const runtime = "nodejs";

const ORCHESTRATOR_INTERNAL_BASE_URL =
  process.env.ORCHESTRATOR_INTERNAL_BASE_URL?.trim() || "http://localhost:8101";
const INTERNAL_SERVICE_API_KEY = process.env.INTERNAL_SERVICE_API_KEY?.trim() || "";

type ReviewApprovalRequest = {
  scope?: "builder" | "repo" | "delivery";
  fingerprint?: string;
  summary?: string;
  metadata?: Record<string, unknown>;
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
  let payload: ReviewApprovalRequest;
  try {
    payload = (await request.json()) as ReviewApprovalRequest;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const scope = payload.scope;
  if (scope !== "builder" && scope !== "repo" && scope !== "delivery") {
    return NextResponse.json({ detail: "scope must be builder, repo, or delivery." }, { status: 400 });
  }

  const fingerprint = sanitizeText(payload.fingerprint, 200);
  if (fingerprint.length < 12) {
    return NextResponse.json({ detail: "fingerprint must be at least 12 characters." }, { status: 400 });
  }

  const summary = sanitizeText(payload.summary, 400);
  if (summary.length < 3) {
    return NextResponse.json({ detail: "summary must be at least 3 characters." }, { status: 400 });
  }

  if (!INTERNAL_SERVICE_API_KEY) {
    return NextResponse.json(
      { detail: "INTERNAL_SERVICE_API_KEY is required for review approval persistence." },
      { status: 503 },
    );
  }
  if (!getApprovalHmacSecret()) {
    return NextResponse.json(
      { detail: "APPROVAL_HMAC_SECRET is required for review approval persistence." },
      { status: 503 },
    );
  }

  const approvedAt = new Date().toISOString();
  const hmacDigest = computeApprovalHmacDigest({
    scope,
    fingerprint,
    summary,
    approvedAt,
  });
  const safeMetadata =
    payload.metadata && typeof payload.metadata === "object" ? payload.metadata : {};

  try {
    const upstream = await fetch(`${ORCHESTRATOR_INTERNAL_BASE_URL}/internal/review-approvals`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": INTERNAL_SERVICE_API_KEY,
      },
      body: JSON.stringify({
        scope,
        fingerprint,
        summary,
        approved_at: approvedAt,
        expires_at: new Date(Date.now() + getApprovalTtlSeconds() * 1000).toISOString(),
        hmac_digest: hmacDigest,
        metadata: safeMetadata,
      }),
      cache: "no-store",
    });

    const text = await upstream.text();
    let parsed: Record<string, unknown> = {};
    try {
      parsed = text ? (JSON.parse(text) as Record<string, unknown>) : {};
    } catch {
      parsed = { detail: text || "Unexpected approval persistence response." };
    }

    return NextResponse.json(parsed, { status: upstream.status });
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error ? error.message : "Unable to persist review approval record.",
      },
      { status: 502 },
    );
  }
}
