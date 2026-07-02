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
