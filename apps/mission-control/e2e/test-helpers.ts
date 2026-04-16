import { createHmac, randomUUID } from "node:crypto";

import type { Page } from "@playwright/test";

const SESSION_TTL_SECONDS = 28_800;
const SESSION_COOKIE_NAME = "mission-control-operator-session";
const SESSION_SECRET =
  process.env.MISSION_CONTROL_SESSION_SECRET ??
  "mission-control-session-secret-for-tests";

function createOperatorSessionToken(nowMs = Date.now()): string {
  const issuedAt = Math.floor(nowMs / 1000);
  const payload = {
    v: 1 as const,
    sid: randomUUID(),
    iat: issuedAt,
    exp: issuedAt + SESSION_TTL_SECONDS,
  };
  const encodedPayload = Buffer.from(JSON.stringify(payload), "utf-8").toString("base64url");
  const signature = createHmac("sha256", SESSION_SECRET)
    .update(encodedPayload)
    .digest("base64url");
  return `${encodedPayload}.${signature}`;
}

export async function attachOperatorSession(page: Page): Promise<void> {
  const nowMs = Date.now();
  await page.context().addCookies([
    {
      name: SESSION_COOKIE_NAME,
      value: createOperatorSessionToken(nowMs),
      url: "http://127.0.0.1:3000",
      httpOnly: true,
      sameSite: "Strict",
      secure: false,
      expires: Math.floor(nowMs / 1000) + SESSION_TTL_SECONDS,
    },
  ]);
}
