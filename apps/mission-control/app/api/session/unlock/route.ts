import { NextResponse } from "next/server";

import {
  attachOperatorSessionCookie,
  getMissionControlAdminKey,
  getOperatorSessionTtlSeconds,
  isOperatorSessionConfigured,
  isOperatorSessionBypassed,
  verifyOperatorAdminKey,
} from "../../../lib/server/operator-session";
import { parseJsonObject } from "../../../lib/server/request-validation";

export const runtime = "nodejs";

export async function POST(request: Request) {
  // Dev bypass — auto-issue a session without requiring an admin key.
  if (isOperatorSessionBypassed()) {
    const response = NextResponse.json({
      authenticated: true,
      ttl_seconds: getOperatorSessionTtlSeconds(),
      bypass: true,
    });
    if (isOperatorSessionConfigured()) {
      attachOperatorSessionCookie(response);
    }
    return response;
  }

  if (!getMissionControlAdminKey()) {
    return NextResponse.json(
      {
        detail:
          "MISSION_CONTROL_ADMIN_KEY or VAULT_ADMIN_KEY must be configured before unlocking Mission Control.",
      },
      { status: 503 },
    );
  }

  const payload = await parseJsonObject(request);
  if (!payload) {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const adminKey = typeof payload.admin_key === "string" ? payload.admin_key : undefined;
  if (!verifyOperatorAdminKey(adminKey)) {
    return NextResponse.json({ detail: "Invalid operator admin key." }, { status: 401 });
  }

  const response = NextResponse.json({
    authenticated: true,
    ttl_seconds: getOperatorSessionTtlSeconds(),
  });
  attachOperatorSessionCookie(response);
  return response;
}
