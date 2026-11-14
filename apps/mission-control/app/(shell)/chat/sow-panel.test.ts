import { describe, expect, it } from "vitest";

import {
  formatBaselinePolicy,
  formatFactoryCost,
  formatFactoryTime,
  formatSlicesLines,
  parseSlicesLines,
} from "./sow-display";

describe("SOW panel copy", () => {
  it("renders estimate range without file-count duration", () => {
    expect(
      formatFactoryTime({
        cost_estimate: { estimated_minutes_low: 8, estimated_minutes_high: 20 },
      }),
    ).toBe("8–20 min factory time");
    expect(formatFactoryTime({})).not.toMatch(/~6 minutes|~12 minutes/);
  });

  it("renders cost as likely and cap", () => {
    expect(
      formatFactoryCost({
        likely_usd: 0.4,
        high_usd: 0.8,
        cap_usd: 1.2,
        pricing_known: true,
      }),
    ).toContain("Likely $0.40");
    expect(formatFactoryCost({ pricing_known: false })).toBe("Unpriced");
  });
});

describe("repo-to-chat handoff", () => {
  it("maps ZIP+port to official PORT and keeps source in the handoff", async () => {
    const { officialMissionTypeFromIntent, officialMissionTypeFromRepoChoice } = await import(
      "../../lib/chat-repo-import"
    );
    expect(officialMissionTypeFromRepoChoice("port")).toBe("PORT");
    expect(officialMissionTypeFromIntent("port this repo to rust")).toBe("PORT");
  });

  it("formats baseline_policy and round-trips SOW execution slices", () => {
    expect(formatBaselinePolicy("preserve_existing_behaviour")).toBe("Preserve existing behaviour");
    const parsed = parseSlicesLines(
      "slice-1 | Core parser | src/parser.py, test_parser.py\n" +
        "slice-2 | API layer | src/api.py | deps: slice-1",
    );
    expect(parsed).toEqual([
      { id: "slice-1", title: "Core parser", files: ["src/parser.py", "test_parser.py"] },
      { id: "slice-2", title: "API layer", files: ["src/api.py"], depends_on: ["slice-1"] },
    ]);
    expect(formatSlicesLines(parsed)).toContain("slice-2 | API layer | src/api.py | deps: slice-1");
  });
});
