import { NextResponse, type NextRequest } from "next/server";

import { isOperatorSessionBypassed } from "./app/lib/server/operator-session";
import { evaluateRequest, parseAllowedHosts } from "./app/lib/server/request-origin-guard";

/**
 * Refuses DNS-rebinding and cross-site requests before any route runs; see
 * app/lib/server/request-origin-guard.ts. MISSION_CONTROL_ALLOWED_HOSTS
 * (comma-separated hostnames) admits non-loopback names, e.g. a LAN or
 * reverse-proxy hostname.
 */
export function proxy(request: NextRequest) {
  const decision = evaluateRequest(
    {
      method: request.method,
      pathname: request.nextUrl.pathname,
      headers: request.headers,
    },
    {
      bypassActive: isOperatorSessionBypassed(),
      allowedHosts: parseAllowedHosts(process.env.MISSION_CONTROL_ALLOWED_HOSTS),
    },
  );
  if (!decision.ok) {
    return NextResponse.json({ detail: decision.reason }, { status: decision.status });
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
