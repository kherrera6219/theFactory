import { afterEach, describe, expect, it } from "vitest";

import {
  createOperatorSessionToken,
  getOperatorSessionFromCookieValue,
  hasOperatorSession,
  isOperatorSessionBypassed,
  verifyOperatorAdminKey,
} from "./operator-session";

describe("operator session helpers", () => {
  afterEach(() => {
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_CONTROL_SESSION_TTL_SECONDS;
    delete process.env.OPERATOR_SESSION_BYPASS;
  });

  it("creates and validates signed operator sessions", () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";
    process.env.MISSION_CONTROL_SESSION_TTL_SECONDS = "3600";

    const token = createOperatorSessionToken();
    const session = getOperatorSessionFromCookieValue(token);

    expect(session?.sid).toBeTypeOf("string");
    expect(session?.exp).toBeGreaterThan(session?.iat ?? 0);
  });

  it("rejects tampered operator sessions", () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";

    const token = createOperatorSessionToken();
    const tampered = `${token}x`;

    expect(getOperatorSessionFromCookieValue(tampered)).toBeNull();
  });

  it("verifies the configured admin key with constant-time comparison", () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";

    expect(verifyOperatorAdminKey("mission-control-admin-secret")).toBe(true);
    expect(verifyOperatorAdminKey("wrong-secret")).toBe(false);
  });

  it("treats OPERATOR_SESSION_BYPASS=true as an unlocked local operator session", () => {
    process.env.OPERATOR_SESSION_BYPASS = "true";

    expect(isOperatorSessionBypassed()).toBe(true);
    expect(hasOperatorSession(new Request("http://localhost/settings"))).toBe(true);
  });

  it("keeps the legacy MISSION_CONTROL_BYPASS_AUTH=true alias working", () => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";

    expect(isOperatorSessionBypassed()).toBe(true);
    expect(hasOperatorSession(new Request("http://localhost/settings"))).toBe(true);
  });
});
