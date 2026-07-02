import { describe, expect, it } from "vitest";

import {
  deriveMissionPhaseDescriptor,
  deriveSmeltPhaseIndex,
  detectMissionPhaseModel,
  smeltPhaseFromEventType,
  smeltPhaseFromIndex,
  smeltPhaseIndexForEventType,
} from "./smelt-cycle";
import type { MissionEvent } from "./types";

function event(eventType: string): MissionEvent {
  return {
    mission_id: "mission-1",
    previous_state: "RUNNING",
    new_state: "RUNNING",
    event_type: eventType,
    ts: "2026-03-04T00:00:00+00:00",
  };
}

describe("smelt-cycle mapping", () => {
  it("maps lifecycle event types to deterministic phase indexes", () => {
    expect(smeltPhaseIndexForEventType("MISSION_QUEUED")).toBe(1);
    expect(smeltPhaseIndexForEventType("MISSION_GATING")).toBe(3);
    expect(smeltPhaseIndexForEventType("MISSION_COMPLETE")).toBe(6);
    expect(smeltPhaseIndexForEventType("MISSION_PM_INTAKE", "v2")).toBe(2);
    expect(smeltPhaseIndexForEventType("UNKNOWN")).toBeNull();
  });

  it("maps event types and indexes to phase names", () => {
    expect(smeltPhaseFromEventType("MISSION_FUSION")).toBe("FUSION");
    expect(smeltPhaseFromEventType("MISSION_SPECIALIST_ASSIGNED", "v2")).toBe(
      "SPECIALIST ASSIGNED",
    );
    expect(smeltPhaseFromEventType("OTHER_EVENT")).toBeNull();
    expect(smeltPhaseFromIndex(5)).toBe("SQUEEZE");
    expect(smeltPhaseFromIndex(3, "v2")).toBe("FETCH");
    expect(smeltPhaseFromIndex(4, "v2")).toBe("CEO DELEGATED");
    expect(smeltPhaseFromIndex(999)).toBe("DELIVERY");
    expect(smeltPhaseFromIndex(-1)).toBe("INTAKE");
  });

  it("derives phase from mission state fallback", () => {
    expect(deriveSmeltPhaseIndex({ missionState: "QUEUED" })).toBe(1);
    expect(deriveSmeltPhaseIndex({ missionState: "VERIFIED" })).toBe(5);
    expect(deriveSmeltPhaseIndex({ missionState: "COMPLETE" })).toBe(6);
  });

  it("advances phase deterministically from event history", () => {
    const events: MissionEvent[] = [
      event("MISSION_QUEUED"),
      event("MISSION_RUNNING"),
      event("MISSION_GATING"),
      event("MISSION_FUSION"),
      event("MISSION_VERIFIED"),
    ];
    expect(
      deriveSmeltPhaseIndex({
        missionState: "RUNNING",
        events,
      }),
    ).toBe(5);
  });

  it("ignores non-phase audit events when deriving the current phase", () => {
    const descriptor = deriveMissionPhaseDescriptor({
      missionState: "COMPLETE",
      events: [
        event("MISSION_DELIVERED"),
        event("MISSION_COMPLIANCE_ASSESSMENT_COMPLETE"),
      ],
      routingVersion: "v2",
    });

    expect(descriptor.phaseIndex).toBe(11);
    expect(descriptor.phaseName).toBe("COMPLETE");
  });

  it("uses logicnode signals to bridge older missions without checkpoint events", () => {
    expect(
      deriveSmeltPhaseIndex({
        missionState: "RUNNING",
        events: [event("MISSION_RUNNING")],
        logicNodeCount: 2,
        verifiedLogicNodeCount: 0,
      }),
    ).toBe(3);

    expect(
      deriveSmeltPhaseIndex({
        missionState: "RUNNING",
        events: [event("MISSION_RUNNING")],
        logicNodeCount: 4,
        verifiedLogicNodeCount: 2,
      }),
    ).toBe(4);
  });

  it("detects and renders the v2 mission flow", () => {
    const descriptor = deriveMissionPhaseDescriptor({
      missionState: "CEO_DELEGATED",
      events: [event("MISSION_PM_INTAKE"), event("MISSION_CEO_DELEGATED")],
      routingVersion: "v2",
    });

    expect(detectMissionPhaseModel({ missionState: "CEO_DELEGATED" })).toBe("v2");
    expect(descriptor.model).toBe("v2");
    expect(descriptor.phaseIndex).toBe(4);
    expect(descriptor.phaseName).toBe("CEO DELEGATED");
    expect(descriptor.phases).toHaveLength(12);
  });
});
