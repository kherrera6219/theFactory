import { describe, expect, it } from "vitest";

import { isOperatorAuthError, operatorRecoveryMessage } from "./operator-auth-error";

describe("operator-auth-error", () => {
  it("detects known operator-auth failure phrasings case-insensitively", () => {
    expect(isOperatorAuthError("Operator authentication required")).toBe(true);
    expect(isOperatorAuthError("missing operator session")).toBe(true);
    expect(isOperatorAuthError("Operator API key not found in vault")).toBe(true);
  });

  it("does not treat unrelated errors as operator-auth failures", () => {
    expect(isOperatorAuthError("orchestrator unavailable")).toBe(false);
    expect(isOperatorAuthError("mission not found")).toBe(false);
  });

  it("rewrites operator-auth errors into an actionable recovery message", () => {
    const message = operatorRecoveryMessage("Operator authentication required");
    expect(message).toContain("Mission Control is unlocked for local operation");
    expect(message).toContain("Restart the app stack");
  });

  it("passes through unrelated error messages unchanged", () => {
    expect(operatorRecoveryMessage("mission not found")).toBe("mission not found");
  });
});
