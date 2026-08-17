import { describe, expect, it } from "vitest";

import { compareQuotedActual } from "./cost-quote";

describe("quoted vs actual factory spend", () => {
  it("compares actual spend to the accepted SOW quote and cap", () => {
    const result = compareQuotedActual(
      { likely_usd: 0.4, high_usd: 0.8, cap_usd: 1.2, pricing_known: true },
      0.55,
    );
    expect(result.pricingKnown).toBe(true);
    expect(result.quotedLikely).toBe(0.4);
    expect(result.quotedCap).toBe(1.2);
    expect(result.actual).toBe(0.55);
    expect(result.varianceVsLikely).toBeCloseTo(0.15);
    expect(result.remainingToCap).toBeCloseTo(0.65);
    expect(result.overCap).toBe(false);
  });

  it("flags spend over the accepted cap", () => {
    const result = compareQuotedActual(
      { likely_usd: 0.4, high_usd: 0.8, cap_usd: 1.2, pricing_known: true },
      1.5,
    );
    expect(result.overCap).toBe(true);
    expect(result.remainingToCap).toBeLessThan(0);
  });
});
