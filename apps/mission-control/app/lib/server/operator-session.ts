import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";

import { NextResponse } from "next/server";

export const OPERATOR_SESSION_COOKIE_NAME = "mission-control-operator-session";

type OperatorSessionPayload = {
  v: 1;
  sid: string;
  iat: number;
  exp: number;
};

function getConfiguredSessionTtlSeconds(): number {
  const raw = process.env.MISSION_CONTROL_SESSION_TTL_SECONDS?.trim() ?? "28800";
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 28_800;
  }
  return Math.min(parsed, 604_800);
}

function getExplicitSecureCookieFlag(): boolean | null {
  const raw = process.env.MISSION_CONTROL_SESSION_SECURE?.trim().toLowerCase();
  if (!raw) {
    return null;
  }
  if (["1", "true", "yes", "on"].includes(raw)) {
    return true;
  }
  if (["0", "false", "no", "off"].includes(raw)) {
    return false;
  }
  return null;
}

function shouldUseSecureCookies(): boolean {
  const explicit = getExplicitSecureCookieFlag();
  if (explicit !== null) {
    return explicit;
  }
  const environment = process.env.ENVIRONMENT?.trim().toLowerCase() ?? "";
  return process.env.NODE_ENV === "production" || environment === "production";
}

function base64UrlEncode(value: string): string {
  return Buffer.from(value, "utf-8").toString("base64url");
}

function base64UrlDecode(value: string): string | null {
  try {
    return Buffer.from(value, "base64url").toString("utf-8");
  } catch {
    return null;
  }
}

function hmacDigest(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

function safeEqual(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left, "utf-8");
  const rightBuffer = Buffer.from(right, "utf-8");
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return timingSafeEqual(leftBuffer, rightBuffer);
}

function parseCookieHeader(cookieHeader: string | null): Record<string, string> {
  if (!cookieHeader) {
    return {};
  }
  const pairs = cookieHeader.split(";");
  const parsed: Record<string, string> = {};
  for (const pair of pairs) {
    const separator = pair.indexOf("=");
    if (separator <= 0) {
      continue;
    }
    const name = pair.slice(0, separator).trim();
    const value = pair.slice(separator + 1).trim();
    if (!name || !value) {
      continue;
    }
    parsed[name] = value;
  }
  return parsed;
}

function parsePayload(token: string): OperatorSessionPayload | null {
  const [encodedPayload, providedSignature] = token.split(".");
  if (!encodedPayload || !providedSignature) {
    return null;
  }
  const decoded = base64UrlDecode(encodedPayload);
  if (!decoded) {
    return null;
  }
  let payload: OperatorSessionPayload;
  try {
    payload = JSON.parse(decoded) as OperatorSessionPayload;
  } catch {
    return null;
  }
  if (
    payload.v !== 1 ||
    typeof payload.sid !== "string" ||
    typeof payload.iat !== "number" ||
    typeof payload.exp !== "number"
  ) {
    return null;
  }
  const secret = getOperatorSessionSecret();
  if (!secret) {
    return null;
  }
  const expectedSignature = hmacDigest(encodedPayload, secret);
  if (!safeEqual(expectedSignature, providedSignature)) {
    return null;
  }
  if (payload.exp * 1000 <= Date.now()) {
    return null;
  }
  return payload;
}

export function getMissionControlAdminKey(): string {
  return (
    process.env.MISSION_CONTROL_ADMIN_KEY?.trim() ??
    process.env.VAULT_ADMIN_KEY?.trim() ??
    ""
  );
}

/**
 * Returns true when local Mission Control session bypass is enabled.
 * Intended for local development where no admin key setup has been completed.
 * Never set this in production.
 */
export function isOperatorSessionBypassed(): boolean {
  return (
    process.env.MISSION_CONTROL_BYPASS_AUTH === "true" ||
    process.env.OPERATOR_SESSION_BYPASS === "true"
  );
}

export function getOperatorSessionSecret(): string {
  return process.env.MISSION_CONTROL_SESSION_SECRET?.trim() ?? getMissionControlAdminKey();
}

export function isOperatorSessionConfigured(): boolean {
  return getOperatorSessionSecret().length > 0;
}

export function verifyOperatorAdminKey(candidate: string | undefined): boolean {
  const configuredKey = getMissionControlAdminKey();
  const providedKey = candidate?.trim() ?? "";
  if (!configuredKey || !providedKey) {
    return false;
  }
  return safeEqual(configuredKey, providedKey);
}

export function createOperatorSessionToken(nowMs = Date.now()): string {
  const secret = getOperatorSessionSecret();
  if (!secret) {
    throw new Error(
      "MISSION_CONTROL_SESSION_SECRET or MISSION_CONTROL_ADMIN_KEY must be configured.",
    );
  }
  const issuedAt = Math.floor(nowMs / 1000);
  const payload: OperatorSessionPayload = {
    v: 1,
    sid: randomUUID(),
    iat: issuedAt,
    exp: issuedAt + getConfiguredSessionTtlSeconds(),
  };
  const encodedPayload = base64UrlEncode(JSON.stringify(payload));
  const signature = hmacDigest(encodedPayload, secret);
  return `${encodedPayload}.${signature}`;
}

export function getOperatorSessionFromCookieValue(
  cookieValue: string | undefined,
): OperatorSessionPayload | null {
  if (!cookieValue) {
    return null;
  }
  return parsePayload(cookieValue);
}

export function getOperatorSessionFromRequest(request: Request): OperatorSessionPayload | null {
  const cookies = parseCookieHeader(request.headers.get("cookie"));
  return getOperatorSessionFromCookieValue(cookies[OPERATOR_SESSION_COOKIE_NAME]);
}

export function hasOperatorSession(request: Request): boolean {
  if (isOperatorSessionBypassed()) return true;
  return getOperatorSessionFromRequest(request) !== null;
}

export function operatorSessionUnauthorizedResponse(): NextResponse {
  if (!isOperatorSessionConfigured()) {
    return NextResponse.json(
      {
        detail:
          "Mission Control operator session is not configured. Set MISSION_CONTROL_SESSION_SECRET and MISSION_CONTROL_ADMIN_KEY.",
      },
      { status: 503 },
    );
  }
  return NextResponse.json({ detail: "Operator authentication required." }, { status: 401 });
}

export function requireOperatorRequestSession(request: Request): NextResponse | null {
  if (hasOperatorSession(request)) {
    return null;
  }
  return operatorSessionUnauthorizedResponse();
}

export function attachOperatorSessionCookie(response: NextResponse, nowMs = Date.now()): void {
  response.cookies.set({
    name: OPERATOR_SESSION_COOKIE_NAME,
    value: createOperatorSessionToken(nowMs),
    httpOnly: true,
    sameSite: "strict",
    secure: shouldUseSecureCookies(),
    maxAge: getConfiguredSessionTtlSeconds(),
    path: "/",
  });
}

export function clearOperatorSessionCookie(response: NextResponse): void {
  response.cookies.set({
    name: OPERATOR_SESSION_COOKIE_NAME,
    value: "",
    httpOnly: true,
    sameSite: "strict",
    secure: shouldUseSecureCookies(),
    maxAge: 0,
    expires: new Date(0),
    path: "/",
  });
}

export function getOperatorSessionTtlSeconds(): number {
  return getConfiguredSessionTtlSeconds();
}
