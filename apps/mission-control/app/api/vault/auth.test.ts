import { afterEach, describe, expect, it } from "vitest";

import { isAuthorizedVaultRequest } from "./auth";
import {
  createOperatorSessionToken,
  OPERATOR_SESSION_COOKIE_NAME,
} from "../../lib/server/operator-session";

describe("vault request authorization", () => {
  afterEach(() => {
    delete process.env.VAULT_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
  });

  it("accepts a valid operator session cookie", () => {
    process.env.MISSION_CONTROL_ADMIN_KEY = "mission-control-admin-secret";
    process.env.MISSION_CONTROL_SESSION_SECRET = "mission-control-session-secret";
    const cookie = `${OPERATOR_SESSION_COOKIE_NAME}=${createOperatorSessionToken()}`;
    const request = new Request("http://127.0.0.1:3000/api/vault", {
      method: "POST",
      headers: {
        Cookie: cookie,
      },
    });

    expect(isAuthorizedVaultRequest(request)).toBe(true);
  });

  it("rejects requests without a valid session or admin header", () => {
    const request = new Request("http://127.0.0.1:3000/api/vault", {
      method: "POST",
    });

    expect(isAuthorizedVaultRequest(request)).toBe(false);
  });

  it("allows scripted admin access when the configured key matches", () => {
    process.env.VAULT_ADMIN_KEY = "vault-admin-secret";
    const request = new Request("http://localhost:3000/api/vault", {
      method: "GET",
      headers: {
        "x-vault-admin-key": "vault-admin-secret",
      },
    });

    expect(isAuthorizedVaultRequest(request)).toBe(true);
  });
});
