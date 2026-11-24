import { describe, expect, it } from "vitest";

import { estimatedPmProgress, formatElapsed, pmStage } from "./pm-progress";

describe("PM draft progress estimate", () => {
  it("rises with time but never claims completion", () => {
    expect(estimatedPmProgress(0)).toBe(0);
    expect(estimatedPmProgress(25)).toBeGreaterThan(55);
    expect(estimatedPmProgress(45)).toBeGreaterThan(estimatedPmProgress(25));
    expect(estimatedPmProgress(600)).toBe(95);
  });

  it("names a typical stage and flags slow drafts", () => {
    expect(pmStage(2).label).toBe("Reading your request");
    expect(pmStage(30).label).toBe("Drafting the Statement of Work");
    expect(pmStage(120).label).toBe("Taking longer than usual");
  });

  it("formats elapsed time as m:ss", () => {
    expect(formatElapsed(7)).toBe("0:07");
    expect(formatElapsed(95)).toBe("1:35");
  });
});
