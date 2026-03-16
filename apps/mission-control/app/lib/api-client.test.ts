import {
  approveReviewArtifact,
  ApiError,
  createBuilderWorkspaceReview,
  fetchJson,
  getGatewayReadyState,
  getMissionChainTrace,
  getOperatorApiKey,
  missionStateStreamUrl,
  missionApiUrl,
  parseLiveStateStreamMessage,
  updateMissionState,
} from "./api-client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("api-client", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("builds mission API URLs with default base", () => {
    expect(missionApiUrl("/health")).toBe("http://localhost:8100/health");
  });

  it("builds mission stream URLs with optional filters", () => {
    expect(missionStateStreamUrl()).toBe("http://localhost:8100/v1/stream/state");
    expect(missionStateStreamUrl({ missionId: "mission-1" })).toBe(
      "http://localhost:8100/v1/stream/state?mission_id=mission-1",
    );
    expect(
      missionStateStreamUrl({
        missionId: "mission-1",
        includeAgentEvents: false,
      }),
    ).toBe(
      "http://localhost:8100/v1/stream/state?mission_id=mission-1&include_agent_events=false",
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

  it("prefers session operator key over local storage and trims values", () => {
    window.localStorage.setItem("mission-control:operator-api-key", " local-key ");
    window.sessionStorage.setItem("mission-control:operator-api-key", " session-key ");

    expect(getOperatorApiKey()).toBe("session-key");
  });

  it("attaches operator key and expected_state when updating mission state", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await updateMissionState({
      missionId: "mission-123",
      newState: "COMPLETE",
      expectedState: "VERIFIED",
      operatorApiKey: "operator-key",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8100/v1/missions/mission-123/state");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({
      "Content-Type": "application/json",
      "x-api-key": "operator-key",
    });
    expect(init?.body).toBe(
      JSON.stringify({
        new_state: "COMPLETE",
        expected_state: "VERIFIED",
      }),
    );
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
      detail: "orchestrator unavailable",
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
      "http://localhost:8100/v1/missions/mission-1/chain-trace",
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
          record_path: ".runtime/review-approvals/builder-approval-001.json",
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
});
