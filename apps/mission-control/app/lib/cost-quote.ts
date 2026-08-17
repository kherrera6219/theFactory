export type QuotedFactoryCost = {
  likely_usd?: number | null;
  high_usd?: number | null;
  cap_usd?: number | null;
  pricing_known?: boolean;
};

export type QuotedVsActual = {
  quotedLikely: number | null;
  quotedHigh: number | null;
  quotedCap: number | null;
  actual: number | null;
  remainingToCap: number | null;
  varianceVsLikely: number | null;
  overCap: boolean;
  pricingKnown: boolean;
};

export function compareQuotedActual(
  quoted: QuotedFactoryCost | null | undefined,
  actualUsd: number | null | undefined,
): QuotedVsActual {
  const pricingKnown = quoted?.pricing_known !== false && quoted?.likely_usd != null;
  const quotedLikely = typeof quoted?.likely_usd === "number" ? quoted.likely_usd : null;
  const quotedHigh = typeof quoted?.high_usd === "number" ? quoted.high_usd : null;
  const quotedCap = typeof quoted?.cap_usd === "number" ? quoted.cap_usd : null;
  const actual = typeof actualUsd === "number" ? actualUsd : null;
  const remainingToCap =
    quotedCap != null && actual != null ? Number((quotedCap - actual).toFixed(6)) : null;
  const varianceVsLikely =
    quotedLikely != null && actual != null ? Number((actual - quotedLikely).toFixed(6)) : null;
  return {
    quotedLikely,
    quotedHigh,
    quotedCap,
    actual,
    remainingToCap,
    varianceVsLikely,
    overCap: remainingToCap != null && remainingToCap < 0,
    pricingKnown,
  };
}
