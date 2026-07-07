/**
 * Saved chat sessions (full message text) were persisted in localStorage
 * indefinitely, bounded only by a 30-session count cap — a session from
 * months ago would never expire on its own as long as that cap was never
 * hit. This adds a time-based expiry alongside the existing count cap.
 */
const MAX_SESSION_AGE_DAYS = 30;

export function isSessionExpired(savedAt: string, now: number = Date.now()): boolean {
  const savedAtMs = new Date(savedAt).getTime();
  if (Number.isNaN(savedAtMs)) {
    // Unparseable timestamp — treat as expired rather than keep it forever.
    return true;
  }
  const ageMs = now - savedAtMs;
  return ageMs > MAX_SESSION_AGE_DAYS * 24 * 60 * 60 * 1000;
}

export function pruneExpiredSessions<T extends { savedAt: string }>(sessions: T[]): T[] {
  const now = Date.now();
  return sessions.filter((session) => !isSessionExpired(session.savedAt, now));
}
