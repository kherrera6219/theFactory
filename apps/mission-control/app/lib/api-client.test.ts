import {
  approveReviewArtifact,
  ApiError,
  createBuilderPreview,
  createBuilderWorkspaceReview,
  fetchJson,
  getGatewayReadyState,
  getMissionChainTrace,
  missionStateStreamUrl,
  missionApiUrl,
  parseLiveStateStreamMessage,
  toDisplayError,
  verifyReviewApproval,
} from "./api-client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("api-client", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("builds mission API URLs with default base", () => {
    expect(missionApiUrl("/health")).toBe("/api/gateway/health");
  });

  it("builds mission stream URLs with optional filters", () => {
    expect(missionStateStreamUrl()).toBe("/api/gateway/v1/stream/state");
    expect(missionStateStreamUrl({ missionId: "mission-1" })).toBe(
      "/api/gateway/v1/stream/state?mission_id=mission-1",
    );
    expect(
      missionStateStreamUrl({
        missionId: "mission-1",
        includeAgentEvents: false,
      }),
    ).toBe(
      "/api/gateway/v1/stream/state?mission_id=mission-1&include_agent_events=false",
    );
  });

  it("parses live stream message payloads", () => {
    const parsed = parseLiveStateStreamMessage(
      JSON.stringify({
        stream_id: "1-0",
        event_type: "MISSION_RUNNING",
        mission_id: "mission-1",
        state: "RUNNING",
        topic: "fusion.requested",
        producer: "orchestrator",
        created_at: "2026-03-04T00:00:00+00:00",
        payload: { mission_id: "mission-1" },
      }),
    );
    expect(parsed?.event_type).toBe("MISSION_RUNNING");
    expect(parseLiveStateStreamMessage("not json")).toBeNull();
  });

  it("parses successful JSON responses", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const payload = await fetchJson<{ ok: boolean }>("http://example.com/health", {
      method: "GET",
    });

    expect(payload).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("http://example.com/health");
    expect(call[1]?.cache).toBe("no-store");
    expect(call[1]?.headers).toMatchObject({ "Content-Type": "application/json" });
  });

  it("clears the request timeout after fetch resolves", async () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await fetchJson<{ ok: boolean }>("http://example.com/health", {
      method: "GET",
    });

    expect(clearTimeoutSpy).toHaveBeenCalledTimes(1);
  });

  it("throws an ApiError carrying the upstream status for proxied backend errors", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Mission not found." }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(fetchJson("/api/gateway/v1/missions/missing", { method: "GET" })).rejects.toEqual(
      expect.objectContaining({
        message: "Mission not found.",
        statusCode: 404,
      }),
    );
  });

  it("normalizes aborted requests into actionable timeout errors", async () => {
    fetchMock.mockRejectedValueOnce(new DOMException("signal is aborted without reason", "AbortError"));

    await expect(fetchJson("/api/gateway/v1/slow", { method: "GET" })).rejects.toEqual(
      expect.objectContaining({
        message: "The local runtime took too long to respond.",
        statusCode: 408,
        errorCode: "LOCAL_RUNTIME_REQUEST_TIMEOUT",
      }),
    );
  });

  it("gives builder preview requests a longer warmup timeout", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ plan: [], warnings: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await createBuilderPreview({ request: "Build a Windows Snake RPG", view_mode: "desktop" });

    const call = fetchMock.mock.calls[0];
    expect(call[1]?.signal).toBeDefined();
    expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 30_000);
  });

  it("maps 429 responses to friendly ApiError messages", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("{}", {
        status: 429,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(fetchJson("http://example.com/rate-limited", { method: "GET" })).rejects.toEqual(
      expect.objectContaining({
        message: "Rate limit exceeded. Retry shortly.",
        statusCode: 429,
      }),
    );
  });

  it("parses a structured FactoryError payload into ApiError fields", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: {
            user_message: "A file failed its integrity check.",
            recovery_action: "Restore a trusted backup.",
            error_code: "FACTORY-INTEGRITY-001",
          },
        }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(
      fetchJson("http://example.com/load", { method: "GET" }),
    ).rejects.toEqual(
      expect.objectContaining({
        message: "A file failed its integrity check.",
        statusCode: 400,
        errorCode: "FACTORY-INTEGRITY-001",
        recoveryAction: "Restore a trusted backup.",
      }),
    );
  });

  it("toDisplayError renders structured ApiError into the four-line shape", () => {
    const err = new ApiError("A file failed its integrity check.", 400, {
      errorCode: "FACTORY-INTEGRITY-001",
      recoveryAction: "Restore a trusted backup.",
    });
    expect(toDisplayError(err)).toEqual({
      whatHappened: "A file failed its integrity check.",
      whatYouCanDo: "Restore a trusted backup.",
      errorCode: "FACTORY-INTEGRITY-001",
    });
  });

  it("toDisplayError falls back for plain errors and strings", () => {
    expect(toDisplayError(new Error("boom")).whatHappened).toBe("boom");
    expect(toDisplayError("bad").whatHappened).toBe("bad");
    expect(toDisplayError(new Error("boom")).errorCode).toBeUndefined();
  });

  it("returns readiness details when gateway returns an API error", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "orchestrator unavailable" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const ready = await getGatewayReadyState();
    expect(ready).toEqual({
      ready: false,
      detail: "The orchestrator service is not reachable.",
    });
  });

  it("returns a fallback readiness message on non-ApiError exceptions", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network down"));

    const ready = await getGatewayReadyState();
    expect(ready).toEqual({
      ready: false,
      detail: "Readiness check failed.",
    });
  });

  it("keeps ApiError status codes attached", () => {
    const error = new ApiError("failed", 418);
    expect(error.statusCode).toBe(418);
  });

  it("fetches mission chain trace from gateway", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ mission_id: "mission-1", routing_enforced: true, events: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const payload = await getMissionChainTrace("mission-1");
    expect(payload.mission_id).toBe("mission-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/gateway/v1/missions/mission-1/chain-trace",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("posts builder workspace review requests to the local route", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ request_id: "builder-1", source: "workspace-review", generated_at: "2026-03-14T00:00:00.000Z", plan: [], diff_summary: [], risk_notes: [], test_plan: [], files: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await createBuilderWorkspaceReview({
      request: "Ground builder previews in real files.",
      constraints: ["preserve accessibility"],
      viewMode: "desktop",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/builder/review",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          request: "Ground builder previews in real files.",
          constraints: ["preserve accessibility"],
          view_mode: "desktop",
        }),
      }),
    );
  });

  it("posts review approval requests to the local approval route", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          approval_id: "builder-approval-001",
          scope: "builder",
          fingerprint: "abc123",
          approved_at: "2026-03-14T00:00:00.000Z",
          summary: "Builder review approved.",
          receipt_digest: "digest-001",
          record_path: "orchestrator://review-approvals/builder-approval-001",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await approveReviewArtifact({
      scope: "builder",
      fingerprint: "abc123",
      summary: "Builder review approved.",
      metadata: { request_id: "builder-review-001" },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/review/approve",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          scope: "builder",
          fingerprint: "abc123",
          summary: "Builder review approved.",
          metadata: { request_id: "builder-review-001" },
        }),
      }),
    );
  });

  it("posts review approval verification requests to the local route", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          valid: true,
          approval_id: "builder-approval-001",
          scope: "builder",
          fingerprint: "abc123",
          approved_at: "2026-03-14T00:00:00.000Z",
          expires_at: "2026-03-15T00:00:00.000Z",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await verifyReviewApproval({
      scope: "builder",
      approvalId: "builder-approval-001",
      fingerprint: "abc123",
      receiptDigest: "digest-001",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/review/verify",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          scope: "builder",
          approval_id: "builder-approval-001",
          fingerprint: "abc123",
          receipt_digest: "digest-001",
        }),
      }),
    );
  });
});
