import { describe, expect, it } from "vitest";

import {
  computeMissionPerformance,
  formatSeconds,
  missionDurationSeconds,
  percentile,
  slowestSteps,
} from "./mission-performance";
import type { MissionRecord } from "./types";

const NOW = Date.parse("2026-11-24T12:00:00Z");

function mission(partial: Partial<MissionRecord> & { mission_id: string }): MissionRecord {
  return {
    state: "COMPLETE",
    requested_target_language: "python",
    created_at: "2026-11-24T10:00:00Z",
    ...partial,
  };
}

const delivered = mission({
  mission_id: "mission-a",
  metadata: {
    last_chain_event_at: "2026-11-24T10:05:00Z",
    chain_trace: [
      { ts: "2026-11-24T10:00:00Z", event_type: "MISSION_PM_INTAKE" },
      { ts: "2026-11-24T10:01:00Z", event_type: "MISSION_FETCH_COMPLETE" },
      { ts: "2026-11-24T10:04:00Z", event_type: "GENERATED_OUTPUT_CREATED" },
      { ts: "2026-11-24T11:30:00Z", event_type: "MISSION_DELIVERED", restated: true },
    ],
    llm_usage_summary: { by_agent: [{ cost_usd: 0.01 }, { cost_usd: 0.02 }] },
  },
});

describe("mission performance", () => {
  it("measures delivered missions from creation to their last chain event", () => {
    expect(missionDurationSeconds(delivered)).toBe(300);
    expect(missionDurationSeconds({ ...delivered, state: "VERIFIED" })).toBeNull();
  });

  it("ranks the slowest steps and ignores restated timestamps", () => {
    const steps = slowestSteps([delivered]);
    expect(steps[0]).toEqual({ step: "GENERATED_OUTPUT_CREATED", medianSeconds: 180, samples: 1 });
    expect(steps.map((s) => s.step)).not.toContain("MISSION_DELIVERED");
  });

  it("summarises throughput, delivery rate, spend, and excludes system missions", () => {
    const perf = computeMissionPerformance(
      [
        delivered,
        mission({ mission_id: "mission-f", state: "FAILED" }),
        mission({
          mission_id: "mission-b",
          state: "VERIFIED",
          metadata: { last_chain_event_type: "MISSION_COMPLETION_BLOCKED", spend_cap: { state: "pause" } },
        }),
        mission({ mission_id: "__knowledge_lake__" }),
      ],
      NOW,
    );
    expect(perf.missionCount).toBe(3);
    expect(perf.delivered).toBe(1);
    expect(perf.deliveryRate).toBeCloseTo(1 / 3);
    expect(perf.deliveredLast24h).toBe(1);
    expect(perf.totalCostUsd).toBeCloseTo(0.03);
    expect(perf.overCap).toBe(1);
  });

  it("formats durations and percentiles", () => {
    expect(percentile([5, 1, 3], 0.5)).toBe(3);
    expect(percentile([], 0.5)).toBeNull();
    expect(formatSeconds(45)).toBe("45s");
    expect(formatSeconds(300)).toBe("5m 0s");
    expect(formatSeconds(7260)).toBe("2h 1m");
  });
});
