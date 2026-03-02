import {
  ApiError,
  fetchJson,
  getGatewayReadyState,
  getOperatorApiKey,
  missionApiUrl,
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
});
