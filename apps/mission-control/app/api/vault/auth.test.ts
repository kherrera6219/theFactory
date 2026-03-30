import { afterEach, describe, expect, it } from "vitest";

import { isAuthorizedVaultRequest } from "./auth";

describe("vault request authorization", () => {
  afterEach(() => {
    delete process.env.VAULT_ADMIN_KEY;
  });

  it("allows trusted local browser requests across localhost aliases on the same port", () => {
    const request = new Request("http://127.0.0.1:3000/api/vault", {
      method: "POST",
      headers: {
        Origin: "http://localhost:3000",
        Referer: "http://localhost:3000/settings",
        "Sec-Fetch-Site": "same-origin",
      },
    });

    expect(isAuthorizedVaultRequest(request)).toBe(true);
  });

  it("rejects cross-origin requests without an admin header", () => {
    const request = new Request("http://127.0.0.1:3000/api/vault", {
      method: "POST",
      headers: {
        Origin: "https://attacker.example",
        Referer: "https://attacker.example/steal",
        "Sec-Fetch-Site": "cross-site",
      },
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
