export type RepoFileRecord = {
  path: string;
  language: string;
  bytes: number;
  estimated_lines: number;
};

export const MAX_ALLOWED_FILES = 800;
export const DEFAULT_MAX_FILES = 300;
export const LARGE_FILE_BYTES = 1_500_000;

const LANGUAGE_BY_EXTENSION: Array<[string, string]> = [
  [".py", "Python"],
  [".tsx", "TypeScript"],
  [".ts", "TypeScript"],
  [".jsx", "JavaScript"],
  [".js", "JavaScript"],
  [".java", "Java"],
  [".kt", "Kotlin"],
  [".go", "Go"],
  [".rs", "Rust"],
  [".zig", "Zig"],
  [".c", "C"],
  [".cc", "C++"],
  [".cpp", "C++"],
  [".cxx", "C++"],
  [".cs", "C#"],
  [".rb", "Ruby"],
  [".php", "PHP"],
  [".scala", "Scala"],
  [".r", "R"],
  [".jl", "Julia"],
  [".m", "MATLAB"],
  [".sql", "SQL"],
  [".sh", "Shell"],
  [".bash", "Shell"],
  [".yaml", "YAML"],
  [".yml", "YAML"],
  [".toml", "TOML"],
  [".json", "JSON"],
  [".md", "Markdown"],
  [".txt", "Text"],
];

const REQUESTED_LANGUAGE_BY_EXTENSION: Array<[string, string]> = [
  [".py", "python"],
  [".tsx", "typescript"],
  [".ts", "typescript"],
  [".jsx", "javascript"],
  [".js", "javascript"],
  [".java", "java"],
  [".kt", "kotlin"],
  [".go", "go"],
  [".rs", "rust"],
  [".zig", "zig"],
  [".c", "c"],
  [".cc", "cpp"],
  [".cpp", "cpp"],
  [".cxx", "cpp"],
  [".cs", "csharp"],
  [".rb", "ruby"],
  [".php", "php"],
  [".scala", "scala"],
  [".r", "r"],
  [".jl", "julia"],
  [".m", "matlab"],
];

export function normalizeSubdirectory(value: string): string {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "/") {
    return "/";
  }
  // Avoid regex on uncontrolled data — strip leading/trailing slashes with index arithmetic
  let start = 0;
  while (start < trimmed.length && trimmed[start] === "/") start++;
  let end = trimmed.length;
  while (end > start && trimmed[end - 1] === "/") end--;
  const withoutEdges = trimmed.slice(start, end);
  return withoutEdges.length > 0 ? `/${withoutEdges}` : "/";
}

export function languageFromPath(path: string): string {
  const normalized = path.toLowerCase();
  for (const [extension, language] of LANGUAGE_BY_EXTENSION) {
    if (normalized.endsWith(extension)) {
      return language;
    }
  }
  return "Other";
}

export function requestedLanguageFromPath(path: string): string | null {
  const normalized = path.toLowerCase();
  for (const [extension, language] of REQUESTED_LANGUAGE_BY_EXTENSION) {
    if (normalized.endsWith(extension)) {
      return language;
    }
  }
  return null;
}

export function estimateLines(bytes: number): number {
  return Math.max(1, Math.round(bytes / 45));
}

export function clampMaxFiles(value: number | undefined): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return DEFAULT_MAX_FILES;
  }
  const integerValue = Math.floor(value);
  return Math.min(Math.max(1, integerValue), MAX_ALLOWED_FILES);
}

export function branchLooksValid(value: string): boolean {
  return /^[A-Za-z0-9._/-]{1,120}$/.test(value);
}
