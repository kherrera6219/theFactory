import { describe, expect, it } from "vitest";

import {
  completionBlockReason,
  isCompletionBlocked,
  isSystemMission,
  missionDisplayState,
  missionSearchText,
  missionTitle,
  shortMissionId,
  withoutSystemMissions,
} from "./mission-status";

const blockedMeta = { last_chain_event_type: "MISSION_COMPLETION_BLOCKED" };

describe("mission status helpers", () => {
  it("recognises the internal Knowledge Lake missions", () => {
    expect(isSystemMission("__knowledge_lake__")).toBe(true);
    expect(isSystemMission("system-knowledge-lake")).toBe(true);
    expect(isSystemMission("mission-1")).toBe(false);
    const list = [{ mission_id: "mission-1" }, { mission_id: "__knowledge_lake__" }];
    expect(withoutSystemMissions(list)).toEqual([{ mission_id: "mission-1" }]);
  });

  it("treats a VERIFIED mission parked by a completion gate as blocked", () => {
    const blocked = { mission_id: "m", state: "VERIFIED", metadata: blockedMeta };
    expect(isCompletionBlocked(blocked)).toBe(true);
    expect(missionDisplayState(blocked)).toBe("Blocked");
    expect(isCompletionBlocked({ ...blocked, state: "COMPLETE" })).toBe(false);
    expect(missionDisplayState({ mission_id: "m", state: "VERIFIED" })).toBe("Verified");
  });

  it("reports a spend-cap stop even when the recorded reason says runtime QC", () => {
    const reason = completionBlockReason({
      mission_id: "m",
      state: "VERIFIED",
      metadata: {
        ...blockedMeta,
        spend_cap_hit: true,
        spend_cap: { state: "pause", actual_usd: 0.23921, cap_usd: 0.0693 },
        chain_trace: [
          {
            event_type: "MISSION_COMPLETION_BLOCKED",
            details: { gate: "runtime_qc", reason: "runtime QC did not pass" },
          },
        ],
      },
    });
    expect(reason?.gate).toBe("Spend cap");
    expect(reason?.reason).toContain("$0.2392 spent of a $0.0693 cap");
  });

  it("uses the gate recorded in the chain trace otherwise", () => {
    const reason = completionBlockReason({
      mission_id: "m",
      state: "VERIFIED",
      metadata: {
        ...blockedMeta,
        chain_events: [
          {
            event_type: "MISSION_COMPLETION_BLOCKED",
            details: { gate: "runtime_qc", reason: "runtime QC did not pass" },
          },
        ],
      },
    });
    expect(reason).toEqual({ gate: "Runtime Qc", reason: "runtime QC did not pass" });
  });

  it("builds a readable title and a distinguishing short id", () => {
    expect(
      missionTitle({
        mission_id: "mission-5b6e6a8e-7de9",
        state: "COMPLETE",
        metadata: { feature_contract: { title: "Word Frequency CLI" } },
      }),
    ).toBe("Word Frequency CLI");
    expect(
      missionTitle({ mission_id: "mission-1", state: "QUEUED", prompt: "Build a tool\nmore" }),
    ).toBe("Build a tool");
    expect(shortMissionId("mission-5b6e6a8e-7de9-4bc5-874e-cc72bf4720d2")).toBe("mission-5b6e6a8e");
  });

  it("searches by what the mission built, not just its id", () => {
    const text = missionSearchText({
      mission_id: "mission-5b6e6a8e",
      state: "COMPLETE",
      prompt: "Write a Python command-line tool named wordcount",
      metadata: { feature_contract: { title: "Word Frequency Counter" } },
    });
    expect(text).toContain("word frequency");
    expect(text).toContain("wordcount");
  });
});
