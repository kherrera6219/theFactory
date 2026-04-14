import { NextResponse } from "next/server";

import {
  attachOperatorSessionCookie,
  getMissionControlAdminKey,
  getOperatorSessionTtlSeconds,
  verifyOperatorAdminKey,
} from "../../../lib/server/operator-session";

export const runtime = "nodejs";

type UnlockRequestPayload = {
  admin_key?: string;
};

export async function POST(request: Request) {
  if (!getMissionControlAdminKey()) {
    return NextResponse.json(
      {
        detail:
          "MISSION_CONTROL_ADMIN_KEY or VAULT_ADMIN_KEY must be configured before unlocking Mission Control.",
      },
      { status: 503 },
    );
  }

  let payload: UnlockRequestPayload;
  try {
    payload = (await request.json()) as UnlockRequestPayload;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  if (!verifyOperatorAdminKey(payload.admin_key)) {
    return NextResponse.json({ detail: "Invalid operator admin key." }, { status: 401 });
  }

  const response = NextResponse.json({
    authenticated: true,
    ttl_seconds: getOperatorSessionTtlSeconds(),
  });
  attachOperatorSessionCookie(response);
  return response;
}
