import { NextResponse } from "next/server";

import { clearOperatorSessionCookie } from "../../../lib/server/operator-session";

export const runtime = "nodejs";

export async function POST() {
  const response = NextResponse.json({ logged_out: true });
  clearOperatorSessionCookie(response);
  return response;
}
