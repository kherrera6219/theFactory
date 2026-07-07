import { describe, expect, it } from "vitest";

import { isSessionExpired, pruneExpiredSessions } from "./chat-session-retention";

const DAY_MS = 24 * 60 * 60 * 1000;

describe("chat-session-retention", () => {
  it("treats a recently-saved session as not expired", () => {
    const now = Date.now();
    expect(isSessionExpired(new Date(now - DAY_MS).toISOString(), now)).toBe(false);
  });

  it("treats a session older than 30 days as expired", () => {
    const now = Date.now();
    expect(isSessionExpired(new Date(now - 31 * DAY_MS).toISOString(), now)).toBe(true);
  });

  it("treats an unparseable timestamp as expired rather than kept forever", () => {
    expect(isSessionExpired("not-a-real-date")).toBe(true);
  });

  it("filters only expired sessions out of a list, regardless of count", () => {
    const now = Date.now();
    const sessions = [
      { id: "fresh", savedAt: new Date(now - DAY_MS).toISOString() },
      { id: "stale", savedAt: new Date(now - 90 * DAY_MS).toISOString() },
    ];
    const result = pruneExpiredSessions(sessions);
    expect(result.map((s) => s.id)).toEqual(["fresh"]);
  });
});
