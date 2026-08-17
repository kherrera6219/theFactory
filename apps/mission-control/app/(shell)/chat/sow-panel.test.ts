import { describe, expect, it } from "vitest";

import { formatFactoryCost, formatFactoryTime } from "./sow-display";

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
