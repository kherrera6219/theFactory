import type { BaselinePolicy, SowSlice } from "./chat-types";

export function formatFactoryTime(fc: {
  cost_estimate?: { estimated_minutes_low?: number; estimated_minutes_high?: number } | null;
  timeline?: { estimated_minutes_low?: number; estimated_minutes_high?: number } | null;
}): string {
  const low = fc.cost_estimate?.estimated_minutes_low ?? fc.timeline?.estimated_minutes_low;
  const high = fc.cost_estimate?.estimated_minutes_high ?? fc.timeline?.estimated_minutes_high;
  if (low && high) return `${low}–${high} min factory time`;
  return "Estimated after PM intake";
}

export function formatFactoryCost(estimate?: {
  likely_usd?: number | null;
  high_usd?: number | null;
  cap_usd?: number | null;
  pricing_known?: boolean;
} | null): string {
  if (!estimate || !estimate.pricing_known || estimate.likely_usd == null) return "Unpriced";
  return `Likely $${estimate.likely_usd.toFixed(2)} · Cap $${(estimate.cap_usd ?? estimate.high_usd ?? 0).toFixed(2)}`;
}

export function formatBaselinePolicy(policy?: BaselinePolicy | string | null): string {
  if (policy === "preserve_existing_behaviour") return "Preserve existing behaviour";
  if (policy === "update_behaviour") return "Update behaviour intentionally";
  if (policy === "greenfield") return "Greenfield (no baseline constraint)";
  return "Unspecified";
}

export function formatSlicesLines(slices?: SowSlice[] | null): string {
  if (!Array.isArray(slices) || slices.length === 0) return "";
  return slices
    .map((s) => {
      const filesPart = (s.files ?? []).join(", ");
      const depsPart = (s.depends_on ?? []).length > 0 ? ` | deps: ${s.depends_on!.join(", ")}` : "";
      return `${s.id} | ${s.title} | ${filesPart}${depsPart}`;
    })
    .join("\n");
}

export function parseSlicesLines(raw: string): SowSlice[] {
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const parts = line.split("|").map((p) => p.trim());
      const id = parts[0] || `slice-${index + 1}`;
      const title = parts[1] || id;
      const files = (parts[2] ?? "")
        .split(",")
        .map((f) => f.trim())
        .filter(Boolean);
      const rawDeps = parts[3]?.replace(/^deps:\s*/i, "") ?? "";
      const depends_on = rawDeps
        .split(",")
        .map((d) => d.trim())
        .filter(Boolean);
      return {
        id,
        title,
        files,
        ...(depends_on.length > 0 ? { depends_on } : {}),
      };
    });
}
