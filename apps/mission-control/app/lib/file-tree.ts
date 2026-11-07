import { requestedLanguageFromPath } from "./language";

export interface VirtualFileEntry {
  path: string;
  name: string;
  directory: string;
  content: string;
  sizeBytes: number;
  lineCount: number;
  language: string;
}

export interface DiffLine {
  type: "same" | "add" | "del";
  line: string;
  oldLine?: number;
  newLine?: number;
}

const FILE_MARKER_RE = /^## FILE:?\s+(.+)$/gm;

export function sanitizeVirtualPath(rawPath: string): string {
  const normalized = String(rawPath || "")
    .trim()
    .replace(/\\/g, "/")
    .replace(/^[A-Za-z]:/, "")
    .replace(/^\/+/, "");
  const parts = normalized
    .split("/")
    .filter((part) => part && part !== "." && part !== "..");
  return parts.join("/") || "output.txt";
}

function countLines(text: string): number {
  if (!text) return 0;
  return text.split("\n").length;
}

export function parseMultiFileBundle(
  artifactText: string | null | undefined,
  fallbackFilename = "output.txt",
  fallbackLanguage = "text",
): VirtualFileEntry[] {
  const source = String(artifactText ?? "");
  if (!source.trim()) {
    return [];
  }

  const matches = Array.from(source.matchAll(FILE_MARKER_RE));
  if (matches.length === 0) {
    const cleanPath = sanitizeVirtualPath(fallbackFilename);
    const slashIdx = cleanPath.lastIndexOf("/");
    const name = slashIdx >= 0 ? cleanPath.slice(slashIdx + 1) : cleanPath;
    const directory = slashIdx >= 0 ? cleanPath.slice(0, slashIdx) : "";
    const lang = requestedLanguageFromPath(cleanPath) ?? fallbackLanguage ?? "text";
    return [
      {
        path: cleanPath,
        name,
        directory,
        content: source,
        sizeBytes: new TextEncoder().encode(source).length,
        lineCount: countLines(source),
        language: lang,
      },
    ];
  }

  const entries: VirtualFileEntry[] = [];
  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    const cleanPath = sanitizeVirtualPath(match[1] ?? `file-${i + 1}.txt`);
    const start = (match.index ?? 0) + match[0].length;
    const end = i + 1 < matches.length ? (matches[i + 1].index ?? source.length) : source.length;
    const content = source.slice(start, end).replace(/^\r?\n/, "").replace(/\s+$/, "") + "\n";
    const slashIdx = cleanPath.lastIndexOf("/");
    const name = slashIdx >= 0 ? cleanPath.slice(slashIdx + 1) : cleanPath;
    const directory = slashIdx >= 0 ? cleanPath.slice(0, slashIdx) : "";
    const lang = requestedLanguageFromPath(cleanPath) ?? fallbackLanguage ?? "text";
    entries.push({
      path: cleanPath,
      name,
      directory,
      content,
      sizeBytes: new TextEncoder().encode(content).length,
      lineCount: countLines(content.trimEnd()),
      language: lang,
    });
  }
  return entries;
}

export function computeLineDiff(beforeText: string, afterText: string): DiffLine[] {
  const oldLines = beforeText.replace(/\r\n/g, "\n").split("\n");
  const newLines = afterText.replace(/\r\n/g, "\n").split("\n");

  const m = oldLines.length;
  const n = newLines.length;
  if (m + n > 1200) {
    // Fast fallback for very large files
    const result: DiffLine[] = [];
    const maxLen = Math.max(m, n);
    for (let i = 0; i < maxLen; i++) {
      const a = oldLines[i];
      const b = newLines[i];
      if (a === b && a !== undefined) {
        result.push({ type: "same", line: a, oldLine: i + 1, newLine: i + 1 });
      } else {
        if (a !== undefined) result.push({ type: "del", line: a, oldLine: i + 1 });
        if (b !== undefined) result.push({ type: "add", line: b, newLine: i + 1 });
      }
    }
    return result;
  }

  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (oldLines[i] === newLines[j]) {
        dp[i][j] = 1 + dp[i + 1][j + 1];
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  const diff: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (oldLines[i] === newLines[j]) {
      diff.push({ type: "same", line: oldLines[i], oldLine: i + 1, newLine: j + 1 });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      diff.push({ type: "del", line: oldLines[i], oldLine: i + 1 });
      i++;
    } else {
      diff.push({ type: "add", line: newLines[j], newLine: j + 1 });
      j++;
    }
  }
  while (i < m) {
    diff.push({ type: "del", line: oldLines[i], oldLine: i + 1 });
    i++;
  }
  while (j < n) {
    diff.push({ type: "add", line: newLines[j], newLine: j + 1 });
    j++;
  }
  return diff;
}
