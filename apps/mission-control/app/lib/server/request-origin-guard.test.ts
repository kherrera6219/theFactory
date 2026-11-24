import { describe, expect, it } from "vitest";

import {
  evaluateRequest,
  hostnameOf,
  parseAllowedHosts,
  type GuardEnv,
} from "./request-origin-guard";

const bypass: GuardEnv = { bypassActive: true, allowedHosts: new Set() };
const sessionMode: GuardEnv = { bypassActive: false, allowedHosts: new Set() };

function req(method: string, pathname: string, headers: Record<string, string>) {
  const lower = Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  return { method, pathname, headers: { get: (name: string) => lower[name.toLowerCase()] ?? null } };
}

describe("request origin guard", () => {
  it("parses hostnames with ports and IPv6 brackets", () => {
    expect(hostnameOf("localhost:3100")).toBe("localhost");
    expect(hostnameOf("[::1]:64471")).toBe("[::1]");
    expect(hostnameOf("Example.COM")).toBe("example.com");
    expect([...parseAllowedHosts(" a.lan, ,B.lan ")]).toEqual(["a.lan", "b.lan"]);
  });

  it.each(["localhost:3100", "127.0.0.1:3100", "[::1]:64471", "localhost"])(
    "accepts loopback Host %s under bypass",
    (host) => {
      expect(evaluateRequest(req("GET", "/api/gateway/missions", { host }), bypass).ok).toBe(true);
    },
  );

  it("refuses a DNS-rebound Host under bypass", () => {
    const decision = evaluateRequest(req("GET", "/api/gateway/missions", { host: "evil.example" }), bypass);
    expect(decision).toEqual({ ok: false, status: 421, reason: "Host not allowed." });
  });

  it("refuses a missing Host under bypass", () => {
    expect(evaluateRequest(req("GET", "/", {}), bypass).ok).toBe(false);
  });

  it("admits explicitly allow-listed hosts and enforces the list without bypass", () => {
    const env: GuardEnv = { bypassActive: false, allowedHosts: new Set(["factory.lan"]) };
    expect(evaluateRequest(req("GET", "/", { host: "factory.lan:443" }), env).ok).toBe(true);
    expect(evaluateRequest(req("GET", "/", { host: "evil.example" }), env).ok).toBe(false);
  });

  it("does not pin Host in session mode without an allow-list", () => {
    expect(evaluateRequest(req("GET", "/", { host: "factory.example.com" }), sessionMode).ok).toBe(true);
  });

  it("refuses a cross-site text/plain POST to the vault (CSRF)", () => {
    const decision = evaluateRequest(
      req("POST", "/api/vault", {
        host: "localhost:3100",
        origin: "https://evil.example",
        "sec-fetch-site": "cross-site",
        "sec-fetch-mode": "no-cors",
      }),
      bypass,
    );
    expect(decision.ok).toBe(false);
  });

  it("refuses a cross-origin POST from a browser without Fetch Metadata", () => {
    const headers = { host: "localhost:3100", origin: "https://evil.example" };
    expect(evaluateRequest(req("POST", "/api/vault", headers), bypass).ok).toBe(false);
    const opaque = { host: "localhost:3100", origin: "null" };
    expect(evaluateRequest(req("POST", "/api/vault", opaque), bypass).ok).toBe(false);
  });

  it("refuses requests from another localhost port (same-site)", () => {
    const decision = evaluateRequest(
      req("GET", "/api/vault", { host: "localhost:3100", "sec-fetch-site": "same-site" }),
      bypass,
    );
    expect(decision.ok).toBe(false);
  });

  it("refuses cross-site API reads even as GET", () => {
    const decision = evaluateRequest(
      req("GET", "/api/gateway/missions", { host: "localhost:3100", "sec-fetch-site": "cross-site", "sec-fetch-mode": "navigate" }),
      bypass,
    );
    expect(decision.ok).toBe(false);
  });

  it("allows a top-level navigation to a page from another site", () => {
    const decision = evaluateRequest(
      req("GET", "/missions", { host: "localhost:3100", "sec-fetch-site": "cross-site", "sec-fetch-mode": "navigate" }),
      bypass,
    );
    expect(decision.ok).toBe(true);
  });

  it("allows the app's own same-origin POST", () => {
    const decision = evaluateRequest(
      req("POST", "/api/vault", {
        host: "localhost:64471",
        origin: "http://localhost:64471",
        "sec-fetch-site": "same-origin",
      }),
      bypass,
    );
    expect(decision.ok).toBe(true);
  });

  it("allows non-browser clients that send no Origin or Fetch Metadata", () => {
    expect(evaluateRequest(req("POST", "/api/vault", { host: "localhost:3100" }), bypass).ok).toBe(true);
  });
});
