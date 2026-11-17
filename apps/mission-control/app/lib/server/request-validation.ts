export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Parse a JSON request body and verify it is a non-null plain object.
 * Returns null if JSON parsing fails or the top-level value is not an object.
 */
export async function parseJsonObject(request: Request): Promise<Record<string, unknown> | null> {
  try {
    const parsed: unknown = await request.json();
    return isPlainObject(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function readTrimmedString(obj: Record<string, unknown>, key: string): string {
  const value = obj[key];
  return typeof value === "string" ? value.trim() : "";
}
