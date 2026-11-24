/**
 * Mission performance computed from the mission records themselves: how long
 * missions take end to end, which pipeline steps are slow, throughput, and LLM
 * spend. The Performance page used to promise "throughput, queue lag, latency"
 * while only repeating the Home page's health badges.
 */

import { normalizeState } from "./format";
import { isCompletionBlocked, isSystemMission } from "./mission-status";
import type { MissionRecord } from "./types";

type TraceEvent = { ts: number; type: string };

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function parseTs(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function traceEvents(mission: MissionRecord): TraceEvent[] {
  const metadata = asRecord(mission.metadata) ?? {};
  const raw = Array.isArray(metadata.chain_trace)
    ? metadata.chain_trace
    : Array.isArray(metadata.chain_events)
      ? metadata.chain_events
      : [];
  const events: TraceEvent[] = [];
  for (const item of raw) {
    const record = asRecord(item);
    const ts = parseTs(record?.ts);
    const type = typeof record?.event_type === "string" ? record.event_type : "";
    // Restated records were rewritten later (completion retries); their
    // timestamps do not measure the original step.
    if (ts !== null && type && record?.restated !== true) events.push({ ts, type });
  }
  return events.sort((left, right) => left.ts - right.ts);
}

/** Seconds from creation to the last chain event, for delivered missions. */
export function missionDurationSeconds(mission: MissionRecord): number | null {
  if (normalizeState(mission.state) !== "COMPLETE") return null;
  const start = parseTs(mission.created_at);
  const metadata = asRecord(mission.metadata) ?? {};
  const end = parseTs(metadata.last_chain_event_at) ?? traceEvents(mission).at(-1)?.ts ?? null;
  if (start === null || end === null || end < start) return null;
  return (end - start) / 1000;
}

export function percentile(values: number[], fraction: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(fraction * sorted.length) - 1));
  return sorted[index];
}

export type StepTiming = { step: string; medianSeconds: number; samples: number };

/** Median time spent reaching each chain event, slowest first. */
export function slowestSteps(missions: MissionRecord[], limit = 6): StepTiming[] {
  const byStep = new Map<string, number[]>();
  for (const mission of missions) {
    const events = traceEvents(mission);
    for (let index = 1; index < events.length; index += 1) {
      const seconds = (events[index].ts - events[index - 1].ts) / 1000;
      if (seconds < 0) continue;
      const list = byStep.get(events[index].type) ?? [];
      list.push(seconds);
      byStep.set(events[index].type, list);
    }
  }
  return Array.from(byStep.entries())
    .map(([step, values]) => ({
      step,
      medianSeconds: percentile(values, 0.5) ?? 0,
      samples: values.length,
    }))
    .sort((left, right) => right.medianSeconds - left.medianSeconds)
    .slice(0, limit);
}

function missionCostUsd(mission: MissionRecord): number | null {
  const metadata = asRecord(mission.metadata) ?? {};
  const usage = asRecord(metadata.llm_usage_summary);
  if (!usage) return null;
  if (typeof usage.estimated_cost_usd === "number") return usage.estimated_cost_usd;
  if (!Array.isArray(usage.by_agent)) return null;
  let total = 0;
  for (const row of usage.by_agent) {
    const cost = asRecord(row)?.cost_usd;
    if (typeof cost === "number") total += cost;
  }
  return total;
}

export type MissionPerformance = {
  missionCount: number;
  delivered: number;
  failed: number;
  blocked: number;
  deliveryRate: number | null;
  deliveredLast24h: number;
  deliveredLast7d: number;
  medianDurationSeconds: number | null;
  p90DurationSeconds: number | null;
  totalCostUsd: number;
  costedMissions: number;
  overCap: number;
  steps: StepTiming[];
};

export function computeMissionPerformance(
  missions: MissionRecord[],
  nowMs: number = Date.now(),
): MissionPerformance {
  const real = missions.filter((mission) => !isSystemMission(mission.mission_id));
  const delivered = real.filter((mission) => normalizeState(mission.state) === "COMPLETE");
  const failed = real.filter((mission) => normalizeState(mission.state) === "FAILED").length;
  const blocked = real.filter(isCompletionBlocked).length;
  const finished = delivered.length + failed + blocked;
  const durations = delivered
    .map(missionDurationSeconds)
    .filter((value): value is number => value !== null);
  const deliveredAt = delivered
    .map((mission) => parseTs(asRecord(mission.metadata)?.last_chain_event_at))
    .filter((value): value is number => value !== null);
  let totalCostUsd = 0;
  let costedMissions = 0;
  let overCap = 0;
  for (const mission of real) {
    const cost = missionCostUsd(mission);
    if (cost !== null) {
      totalCostUsd += cost;
      costedMissions += 1;
    }
    const spendCap = asRecord(asRecord(mission.metadata)?.spend_cap);
    if (spendCap?.state === "pause") overCap += 1;
  }
  return {
    missionCount: real.length,
    delivered: delivered.length,
    failed,
    blocked,
    deliveryRate: finished > 0 ? delivered.length / finished : null,
    deliveredLast24h: deliveredAt.filter((ts) => nowMs - ts <= 86_400_000).length,
    deliveredLast7d: deliveredAt.filter((ts) => nowMs - ts <= 7 * 86_400_000).length,
    medianDurationSeconds: percentile(durations, 0.5),
    p90DurationSeconds: percentile(durations, 0.9),
    totalCostUsd,
    costedMissions,
    overCap,
    steps: slowestSteps(real),
  };
}

export function formatSeconds(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.round(seconds % 60)}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}
