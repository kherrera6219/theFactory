import { describe, expect, it } from "vitest";

import { inferRequestedTargetLanguage, requestedLanguageFromPath } from "./language";

describe("language helpers", () => {
  it("maps file paths to requested target languages", () => {
    expect(requestedLanguageFromPath("src/app/page.tsx")).toBe("typescript");
    expect(requestedLanguageFromPath("services/api/main.py")).toBe("python");
    expect(requestedLanguageFromPath("README.md")).toBeNull();
  });

  it("prefers attached files over weaker prompt hints", () => {
    expect(
      inferRequestedTargetLanguage({
        prompt: "Update the Java service to expose a typed API.",
        filePaths: ["apps/mission-control/app/(shell)/repo/page.tsx", "lib/router.ts"],
      }),
    ).toBe("typescript");
  });

  it("falls back to prompt hints when no supported files are attached", () => {
    expect(
      inferRequestedTargetLanguage({
        prompt: "Create a Rust CLI for audit artifact packaging.",
      }),
    ).toBe("rust");
  });

  it("maps Angular game requests to TypeScript even when a start.bat is requested", () => {
    expect(
      inferRequestedTargetLanguage({
        prompt:
          "Create a modern Snake game in Angular with a Windows start.bat file.",
      }),
    ).toBe("typescript");
  });

  it("uses feature-contract languages when launching a confirmed mission", () => {
    expect(
      inferRequestedTargetLanguage({
        prompt: "Create a modern Snake game.",
        contractLanguages: "typescript, html, css, batch",
      }),
    ).toBe("typescript");
  });

  it("never returns batch as the overall target language, even when it is the only match", () => {
    // "batch" is packaging metadata (a Windows launcher script) with no
    // backend specialist behind it; it must never win outright, regardless
    // of scoring, since nothing can route a mission to a "batch" pod.
    expect(
      inferRequestedTargetLanguage({
        prompt: "Write a start.bat launcher for the deliverable.",
      }),
    ).toBeNull();
  });

  it("does not let a start.bat mention tie with and displace the real project language", () => {
    // Regression: "typescript" and "batch" previously scored identically for
    // an Angular game that also mentions a launcher script, and only won by
    // accidental array-ordering in PROMPT_HINTS, not by design.
    expect(
      inferRequestedTargetLanguage({
        prompt: "Create a modern Snake game in Angular with a Windows start.bat file.",
        contractLanguages: ["typescript", "html", "css", "batch"],
      }),
    ).toBe("typescript");
  });
});
