import maturityMatrix from "./language-maturity.generated.json";

const EXTENSION_TO_LANGUAGE: Array<[string, string]> = [
  [".py", "python"],
  [".ts", "typescript"],
  [".tsx", "typescript"],
  [".js", "javascript"],
  [".jsx", "javascript"],
  [".bat", "batch"],
  [".java", "java"],
  [".go", "go"],
  [".rs", "rust"],
  [".rb", "ruby"],
  [".php", "php"],
  [".cs", "csharp"],
  [".scala", "scala"],
  [".kt", "kotlin"],
  [".c", "c"],
  [".cpp", "cpp"],
  [".cc", "cpp"],
  [".cxx", "cpp"],
  [".zig", "zig"],
  [".m", "matlab"],
  [".r", "r"],
  [".jl", "julia"],
  [".wl", "mathematica"],
  [".nb", "mathematica"],
  [".hs", "haskell"],
  [".ml", "ocaml"],
  [".mli", "ocaml"],
];

const PROMPT_HINTS: Array<[RegExp, string]> = [
  [/\bangular\b/i, "typescript"],
  [/\btsx\b|\bts\b/i, "typescript"],
  [/\btypescript\b/i, "typescript"],
  [/\bjavascript\b/i, "javascript"],
  [/\bpython\b/i, "python"],
  [/\bjava\b/i, "java"],
  [/\brust\b/i, "rust"],
  [/\bgo(lang)?\b/i, "go"],
  [/\bruby\b/i, "ruby"],
  [/\bphp\b/i, "php"],
  [/\bc#|csharp\b/i, "csharp"],
  [/\bscala\b/i, "scala"],
  [/\bkotlin\b/i, "kotlin"],
  [/\bmatlab\b/i, "matlab"],
  [/\bmathematica\b/i, "mathematica"],
  [/\bjulia\b/i, "julia"],
  [/\bhaskell\b/i, "haskell"],
  [/\bocaml\b/i, "ocaml"],
  [/\bzig\b/i, "zig"],
  [/\bbatch\b|\bstart\.bat\b|\b\.bat\b/i, "batch"],
  [/\bc\+\+\b/i, "cpp"],
  [/\bansi c\b|\bc language\b/i, "c"],
];

export function requestedLanguageFromPath(filePath: string): string | null {
  const lowerPath = filePath.toLowerCase();
  for (const [extension, language] of EXTENSION_TO_LANGUAGE) {
    if (lowerPath.endsWith(extension)) {
      return language;
    }
  }
  return null;
}

export function inferRequestedTargetLanguage(params: {
  prompt?: string;
  filePaths?: string[];
  contractLanguages?: string | string[];
}): string | null {
  const scores = new Map<string, number>();
  const addScore = (language: string, score: number) => {
    scores.set(language, (scores.get(language) ?? 0) + score);
  };

  for (const filePath of params.filePaths ?? []) {
    const language = requestedLanguageFromPath(filePath);
    if (!language) {
      continue;
    }
    addScore(language, 5);
  }

  const prompt = String(params.prompt ?? "").trim();
  for (const [pattern, language] of PROMPT_HINTS) {
    if (pattern.test(prompt)) {
      addScore(language, 2);
    }
  }

  const contractLanguageText = Array.isArray(params.contractLanguages)
    ? params.contractLanguages.join(", ")
    : String(params.contractLanguages ?? "");
  for (const [pattern, language] of PROMPT_HINTS) {
    if (pattern.test(contractLanguageText)) {
      addScore(language, 3);
    }
  }

  // "batch" is packaging metadata (a Windows launcher script), never a real
  // specialist implementation language — no backend pod handles it. It must
  // never win the overall pick, even if a start.bat mention ties or outscores
  // the project's actual language (e.g. an Angular app that also asks for a
  // start.bat: both "typescript" and "batch" can score equally, and letting
  // "batch" win would route the mission to a nonexistent specialist).
  scores.delete("batch");

  let winningLanguage: string | null = null;
  let winningScore = -1;
  for (const [language, score] of scores.entries()) {
    if (score > winningScore) {
      winningLanguage = language;
      winningScore = score;
    }
  }

  return winningLanguage;
}

export type LanguageMaturityInfo = {
  tier: string;
  label: string;
};

type GeneratedMaturityRow = {
  tier: string;
  tier_label: string;
  extraction: string;
  test_runner: string;
  dependency_cache: string;
  behavioural_equivalence: string;
};

// Generated from the orchestrator's live runtime tables by
// scripts/generate_language_maturity.py (CI runs it with --check), so the badge
// shows the same extraction / test / dependency facts as docs/LANGUAGE_MATURITY.md
// instead of a hand-maintained summary that can overstate capability.
const GENERATED_MATURITY = (maturityMatrix as { languages: Record<string, GeneratedMaturityRow> })
  .languages;

export function languageMaturityTier(language: string | null | undefined): LanguageMaturityInfo | null {
  const normalized = String(language ?? "").trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  const row = GENERATED_MATURITY[normalized];
  if (!row) {
    return null;
  }
  const deps = row.dependency_cache && row.dependency_cache !== "none" ? row.dependency_cache : "no dep cache";
  return {
    tier: row.tier,
    label: `${row.extraction} · tests: ${row.test_runner} · deps: ${deps}`,
  };
}

/** Every routed target language, in the matrix's order (Python first). */
export const SUPPORTED_TARGET_LANGUAGES: readonly string[] = Object.keys(GENERATED_MATURITY);
