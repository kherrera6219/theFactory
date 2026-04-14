import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createOperatorSessionToken,
  OPERATOR_SESSION_COOKIE_NAME,
} from "../../../lib/server/operator-session";

const getVaultSecret = vi.fn();

vi.mock("../../../lib/server/vault", () => ({
  getVaultSecret,
}));

describe("operator mission-state route", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    getVaultSecret.mockReset();
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_API_BASE_URL;
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  it("rejects state updates without an operator session", async () => {
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://localhost/api/operator/mission-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mission_id: "mission-1",
          new_state: "FAILED",
        }),
      }),
    );

    expect(response.status).toBe(503);
  });

  it("forwards authenticated state transitions through the vault-backed operator key", async () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";
    process.env.MISSION_API_BASE_URL = "http://gateway:8100";
    getVaultSecret.mockResolvedValue("operator-key");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ mission_id: "mission-1", state: "FAILED" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./route");
    const cookie = `${OPERATOR_SESSION_COOKIE_NAME}=${createOperatorSessionToken()}`;

    const response = await POST(
      new Request("http://localhost/api/operator/mission-state", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: cookie,
        },
        body: JSON.stringify({
          mission_id: "mission-1",
          new_state: "FAILED",
          expected_state: "RUNNING",
        }),
      }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://gateway:8100/v1/missions/mission-1/state",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "x-api-key": "operator-key",
        }),
      }),
    );
  });
});
