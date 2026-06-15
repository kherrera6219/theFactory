import { afterEach, describe, expect, it } from "vitest";

describe("session unlock route", () => {
  afterEach(() => {
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.OPERATOR_SESSION_BYPASS;
  });

  it("issues an operator session cookie when the admin key matches", async () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://localhost/api/session/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_key: "mission-control-admin-secret" }),
      }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toContain("mission-control-operator-session=");
  });

  it("rejects invalid admin keys", async () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://localhost/api/session/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_key: "wrong-secret" }),
      }),
    );

    expect(response.status).toBe(401);
  });

  it("reports authenticated when local operator session bypass is enabled without secrets", async () => {
    process.env.OPERATOR_SESSION_BYPASS = "true";
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://localhost/api/session/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }),
    );
    const payload = (await response.json()) as { authenticated?: boolean; bypass?: boolean };

    expect(response.status).toBe(200);
    expect(payload.authenticated).toBe(true);
    expect(payload.bypass).toBe(true);
  });
});
