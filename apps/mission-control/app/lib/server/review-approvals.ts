import { createHmac, timingSafeEqual } from "node:crypto";

type ApprovalHmacPayload = {
  scope: string;
  fingerprint: string;
  summary: string;
  approvedAt: string;
};

function safeEqual(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left, "utf-8");
  const rightBuffer = Buffer.from(right, "utf-8");
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return timingSafeEqual(leftBuffer, rightBuffer);
}

export function getApprovalHmacSecret(): string {
  return process.env.APPROVAL_HMAC_SECRET?.trim() ?? "";
}

export function getApprovalTtlSeconds(): number {
  const raw = process.env.APPROVAL_TTL_SECONDS?.trim() ?? "86400";
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 86_400;
  }
  return Math.min(parsed, 2_592_000);
}

export function computeApprovalHmacDigest(payload: ApprovalHmacPayload): string | null {
  const secret = getApprovalHmacSecret();
  if (!secret) {
    return null;
  }
  const canonical = `${payload.scope}:${payload.fingerprint}:${payload.summary}:${payload.approvedAt}`;
  return createHmac("sha256", secret).update(canonical).digest("hex");
}

export function isApprovalHmacValid(
  expectedDigest: string | null | undefined,
  payload: ApprovalHmacPayload,
): boolean {
  const computedDigest = computeApprovalHmacDigest(payload);
  if (!expectedDigest || !computedDigest) {
    return false;
  }
  return safeEqual(expectedDigest, computedDigest);
}
