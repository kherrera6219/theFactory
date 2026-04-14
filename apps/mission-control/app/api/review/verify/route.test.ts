import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createOperatorSessionToken,
  OPERATOR_SESSION_COOKIE_NAME,
} from "../../../lib/server/operator-session";
import { computeApprovalHmacDigest } from "../../../lib/server/review-approvals";

describe("review approval verification route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.INTERNAL_SERVICE_API_KEY;
    delete process.env.ORCHESTRATOR_INTERNAL_BASE_URL;
    delete process.env.APPROVAL_HMAC_SECRET;
  });

  it("rejects expired review approvals before mission launch", async () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";
    process.env.INTERNAL_SERVICE_API_KEY = "internal-test-key";
    process.env.ORCHESTRATOR_INTERNAL_BASE_URL = "http://orchestrator:8001";
    process.env.APPROVAL_HMAC_SECRET = "approval-hmac-secret";

    const approvedAt = "2026-04-10T00:00:00.000Z";
    const expiredAt = "2026-04-11T00:00:00.000Z";
    const hmacDigest = computeApprovalHmacDigest({
      scope: "repo",
      fingerprint: "f1234567890abcdef",
      summary: "Repository review approved for mission launch.",
      approvedAt,
    });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          approval_id: "repo-approval-f1234567890abcde",
          scope: "repo",
          fingerprint: "f1234567890abcdef",
          summary: "Repository review approved for mission launch.",
          receipt_digest: "digest-001",
          approved_at: approvedAt,
          expires_at: expiredAt,
          hmac_digest: hmacDigest,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-14T00:00:00.000Z"));
    const { POST } = await import("./route");

    const cookie = `${OPERATOR_SESSION_COOKIE_NAME}=${createOperatorSessionToken(
      new Date("2026-04-14T00:00:00.000Z").getTime(),
    )}`;
    const response = await POST(
      new Request("http://localhost/api/review/verify", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: cookie,
        },
        body: JSON.stringify({
          scope: "repo",
          approval_id: "repo-approval-f1234567890abcde",
          fingerprint: "f1234567890abcdef",
          receipt_digest: "digest-001",
        }),
      }),
    );

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      valid: false,
      detail: "Review approval has expired.",
    });
    vi.useRealTimers();
  });
});
