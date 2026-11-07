import { describe, expect, it } from "vitest";
import {
  buildClarificationPrompt,
  buildSelectedClarificationAnswersText,
  emptySowFields,
} from "./chat-helpers";
import type { DisplayFeatureContract } from "./chat-types";

describe("PM Studio clarification helpers (Phase 5)", () => {
  const baseContract: DisplayFeatureContract = {
    title: "Modern Snake Game",
    languages: "TypeScript",
    scope: "Build a responsive Snake game.",
    estimatedDuration: "10–15 min factory time",
    ...emptySowFields(),
    launchPrompt: "Build Snake game",
  };

  it("populates structured clarification items with recommended default and options", () => {
    const prompt = buildClarificationPrompt(
      ["What visual style should we use? (Recommended default: Modern neon arcade)"],
      baseContract,
      [
        {
          id: "q1",
          question: "What visual style should we use?",
          recommended_default: "Modern neon arcade",
          options: ["Modern neon arcade", "Retro pixel art", "Minimalist flat"],
          impact: "Defines UI styling and assets.",
        },
      ],
    );
    expect(prompt.structured).toBeDefined();
    expect(prompt.structured?.[0]?.id).toBe("q1");
    expect(prompt.structured?.[0]?.recommended_default).toBe("Modern neon arcade");
    expect(prompt.structured?.[0]?.options).toContain("Retro pixel art");
  });

  it("builds formatted decision text from operator-selected answers", () => {
    const prompt = buildClarificationPrompt(
      [
        "What visual style should we use?",
        "Where should high scores be saved?",
      ],
      baseContract,
    );
    const text = buildSelectedClarificationAnswersText(prompt, {
      0: "Retro pixel art",
      1: "LocalStorage only",
    });
    expect(text).toContain("1. What visual style should we use?\nAnswer: Retro pixel art");
    expect(text).toContain("2. Where should high scores be saved?\nAnswer: LocalStorage only");
    expect(text).toContain("Finalize the feature contract with these decisions");
  });
});
