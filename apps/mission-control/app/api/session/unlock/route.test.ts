import { afterEach, describe, expect, it } from "vitest";

describe("session unlock route", () => {
  afterEach(() => {
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
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
});
