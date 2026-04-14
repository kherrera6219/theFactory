import { timingSafeEqual } from "node:crypto";

import { hasOperatorSession } from "../../lib/server/operator-session";

function safeEqual(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left, "utf-8");
  const rightBuffer = Buffer.from(right, "utf-8");
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return timingSafeEqual(leftBuffer, rightBuffer);
}

function hasValidVaultAdminHeader(request: Request): boolean {
  const adminKey = process.env.VAULT_ADMIN_KEY?.trim() ?? "";
  const headerValue = request.headers.get("x-vault-admin-key")?.trim() ?? "";
  if (!adminKey || !headerValue) {
    return false;
  }
  return safeEqual(adminKey, headerValue);
}

export function isAuthorizedVaultRequest(request: Request): boolean {
  return hasValidVaultAdminHeader(request) || hasOperatorSession(request);
}
