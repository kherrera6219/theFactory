export function formatFactoryTime(contract: {
  cost_estimate?: { estimated_minutes_low?: number; estimated_minutes_high?: number };
  timeline?: { estimated_minutes_low?: number; estimated_minutes_high?: number };
}): string {
  const low = contract.cost_estimate?.estimated_minutes_low ?? contract.timeline?.estimated_minutes_low;
  const high = contract.cost_estimate?.estimated_minutes_high ?? contract.timeline?.estimated_minutes_high;
  if (low && high) {
    return `${low}–${high} min factory time`;
  }
  return "Factory time after estimate";
}

export function formatFactoryCost(estimate?: {
  likely_usd?: number | null;
  high_usd?: number | null;
  cap_usd?: number | null;
  pricing_known?: boolean;
}): string {
  if (!estimate?.pricing_known || estimate.likely_usd == null) {
    return "Unpriced";
  }
  return `Likely $${estimate.likely_usd.toFixed(2)} · Cap $${(estimate.cap_usd ?? 0).toFixed(2)}`;
}
