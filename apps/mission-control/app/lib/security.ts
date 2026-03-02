const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);

export function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function safeJsonParse<T>(raw: string, fallback: T): T {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function isAllowedLocalApiBase(urlText: string): boolean {
  try {
    const parsed = new URL(urlText);
    return (
      (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      LOCAL_HOSTS.has(parsed.hostname)
    );
  } catch {
    return false;
  }
}

export function sanitizeUserText(raw: string): string {
  return raw
    .replace(/[\u0000-\u0008\u000B-\u001F\u007F]/g, "")
    .trim();
}
