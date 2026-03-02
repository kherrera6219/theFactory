const TERMINAL_STATES = new Set(["COMPLETE", "FAILED"]);

export const PROGRESS_BY_STATE: Record<string, number> = {
  INTAKE: 8,
  QUEUED: 25,
  RUNNING: 62,
  VERIFIED: 88,
  COMPLETE: 100,
  FAILED: 100,
};

export const ETA_BY_STATE: Record<string, string> = {
  INTAKE: "about 2-3 minutes",
  QUEUED: "about 1-2 minutes",
  RUNNING: "under 1 minute",
  VERIFIED: "under 30 seconds",
  COMPLETE: "finished",
  FAILED: "unavailable",
};

export function normalizeState(state: string | null | undefined): string {
  return (state ?? "UNKNOWN").toUpperCase();
}

export function humanizeState(state: string | null | undefined): string {
  return normalizeState(state)
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/(^\w|\s\w)/g, (match) => match.toUpperCase());
}

export function isTerminalState(state: string | null | undefined): boolean {
  return TERMINAL_STATES.has(normalizeState(state));
}

export function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown";
  }
  return parsed.toLocaleString();
}

export function formatTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown";
  }
  return parsed.toLocaleTimeString();
}

export function formatPercent(value: number): string {
  return `${Math.max(0, Math.min(100, Math.round(value)))}%`;
}
