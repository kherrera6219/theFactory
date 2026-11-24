/**
 * Cross-site request guard for Mission Control (applied by `proxy.ts`).
 *
 * Mission Control is usually served on localhost with OPERATOR_SESSION_BYPASS
 * on (desktop embedded server, compose container on 127.0.0.1:3100), so every
 * request is treated as the operator and the server injects gateway / vault
 * credentials on the caller's behalf. "Only reachable on localhost" does not
 * stop a browser: any web page the operator visits can
 *
 *  - send requests to it (CSRF) -- a `text/plain` POST needs no CORS preflight;
 *  - read responses via DNS rebinding -- the attacker's own hostname is
 *    re-pointed at 127.0.0.1, so the browser treats it as same-origin and only
 *    the Host header still names the foreign site.
 *
 * The guard therefore (1) pins Host to loopback names (plus an explicit
 * allow-list) whenever the session bypass is on, and (2) refuses requests a
 * browser marks as coming from another site, for every route.
 */

const LOOPBACK_HOSTNAMES = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export type GuardRequest = {
  method: string;
  /** Path portion of the URL, e.g. `/api/vault`. */
  pathname: string;
  headers: { get(name: string): string | null };
};

export type GuardEnv = {
  bypassActive: boolean;
  /** Extra Host names (no port) accepted in addition to loopback. */
  allowedHosts: ReadonlySet<string>;
};

export type GuardDecision = { ok: true } | { ok: false; status: number; reason: string };

export function parseAllowedHosts(raw: string | undefined): Set<string> {
  const hosts = new Set<string>();
  for (const entry of (raw ?? "").split(",")) {
    const host = entry.trim().toLowerCase();
    if (host) hosts.add(host);
  }
  return hosts;
}

/** Strips the port from a Host header value; keeps IPv6 brackets. */
export function hostnameOf(hostHeader: string): string {
  const value = hostHeader.trim().toLowerCase();
  if (value.startsWith("[")) {
    const end = value.indexOf("]");
    return end === -1 ? value : value.slice(0, end + 1);
  }
  const colon = value.indexOf(":");
  return colon === -1 ? value : value.slice(0, colon);
}

function isAllowedHost(hostHeader: string | null, env: GuardEnv): boolean {
  if (!hostHeader) return false;
  const hostname = hostnameOf(hostHeader);
  return LOOPBACK_HOSTNAMES.has(hostname) || env.allowedHosts.has(hostname);
}

function originHost(origin: string): string | null {
  try {
    return new URL(origin).host.toLowerCase();
  } catch {
    return null;
  }
}

export function evaluateRequest(request: GuardRequest, env: GuardEnv): GuardDecision {
  const host = request.headers.get("host");
  const enforceHost = env.bypassActive || env.allowedHosts.size > 0;
  if (enforceHost && !isAllowedHost(host, env)) {
    return { ok: false, status: 421, reason: "Host not allowed." };
  }

  // Sec-Fetch-Site is set by every current browser and cannot be forged by
  // page script. "none" = typed URL / bookmark, "same-origin" = this app.
  // "same-site" is refused too: other localhost ports are other apps.
  const fetchSite = request.headers.get("sec-fetch-site")?.toLowerCase();
  if (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none") {
    // Top-level navigations to pages (a link from elsewhere) stay allowed;
    // they cannot read the response, and pages hold no credentials.
    const isPageNavigation =
      !request.pathname.startsWith("/api/") &&
      SAFE_METHODS.has(request.method.toUpperCase()) &&
      request.headers.get("sec-fetch-mode")?.toLowerCase() === "navigate";
    if (!isPageNavigation) {
      return { ok: false, status: 403, reason: "Cross-site request refused." };
    }
  }

  // Fallback for clients without Fetch Metadata: a browser always sends Origin
  // on a cross-origin state-changing request, so it must name this host.
  if (!SAFE_METHODS.has(request.method.toUpperCase())) {
    const origin = request.headers.get("origin");
    if (origin !== null) {
      const fromHost = origin === "null" ? null : originHost(origin);
      if (!fromHost || !host || fromHost !== host.trim().toLowerCase()) {
        return { ok: false, status: 403, reason: "Cross-origin request refused." };
      }
    }
  }

  return { ok: true };
}
