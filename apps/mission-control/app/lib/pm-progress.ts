/**
 * Time-based progress for the PM Agent's Statement of Work draft.
 *
 * The PM call is one request with no server-side progress events, so this is an
 * honest estimate from how long drafts usually take (30–60 s), not a measured
 * percentage. It approaches but never reaches 100% until the reply arrives, so
 * a slow draft never looks finished, and it says when a draft is running long.
 */

export const PM_TYPICAL_SECONDS = 45;
export const PM_SLOW_AFTER_SECONDS = 90;
export const PM_TIMEOUT_SECONDS = 240;

/** Estimated percent (0–95) after `elapsedSeconds`. */
export function estimatedPmProgress(elapsedSeconds: number): number {
  const t = Math.max(0, elapsedSeconds);
  // ~63% at 25 s, ~84% at 45 s, ~95% cap by ~90 s.
  return Math.min(95, Math.round(100 * (1 - Math.exp(-t / 25))));
}

export type PmStage = { label: string; detail: string };

/** What the PM is typically doing at this point (estimated from time, not reported). */
export function pmStage(elapsedSeconds: number): PmStage {
  if (elapsedSeconds < 8) return { label: "Reading your request", detail: "Checking scope and intent" };
  if (elapsedSeconds < 25) return { label: "Researching", detail: "Looking up anything it needs to know" };
  if (elapsedSeconds < 50) return { label: "Drafting the Statement of Work", detail: "Scope, deliverables, acceptance criteria" };
  if (elapsedSeconds < PM_SLOW_AFTER_SECONDS)
    return { label: "Finishing up", detail: "Clarifying questions and cost estimate" };
  return {
    label: "Taking longer than usual",
    detail: `Still working — the request stays open for up to ${Math.round(PM_TIMEOUT_SECONDS / 60)} minutes`,
  };
}

export function formatElapsed(elapsedSeconds: number): string {
  const s = Math.max(0, Math.floor(elapsedSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
