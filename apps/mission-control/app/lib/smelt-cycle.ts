import type { MissionEvent } from "./types";

export const SMELT_PHASES = [
  "INTAKE",
  "FETCH",
  "SMELT",
  "GATING",
  "FUSION",
  "SQUEEZE",
  "DELIVERY",
] as const;

export const MISSION_FLOW_V2_PHASES = [
  "INTAKE",
  "QUEUED",
  "PM INTAKE",
  "FETCH",
  "CEO DELEGATED",
  "POD ASSIGNED",
  "SPECIALIST ASSIGNED",
  "RUNNING",
  "GATING",
  "FUSION",
  "VERIFIED",
  "COMPLETE",
] as const;

export type MissionPhaseModel = "v1" | "v2";

const V1_EVENT_TO_PHASE_INDEX: Record<string, number> = {
  MISSION_QUEUED: 1,
  MISSION_RUNNING: 2,
  MISSION_GATING: 3,
  MISSION_FUSION: 4,
  MISSION_VERIFIED: 5,
  MISSION_COMPLETE: 6,
  MISSION_FAILED: 6,
};

const V1_STATE_TO_PHASE_INDEX: Record<string, number> = {
  INTAKE: 0,
  QUEUED: 1,
  RUNNING: 2,
  VERIFIED: 5,
  COMPLETE: 6,
  FAILED: 6,
};

const V2_EVENT_TO_PHASE_INDEX: Record<string, number> = {
  MISSION_INTAKE: 0,
  MISSION_QUEUED: 1,
  MISSION_PM_INTAKE: 2,
  MISSION_FETCH: 3,
  MISSION_FETCH_COMPLETE: 3,
  MISSION_CEO_DELEGATED: 4,
  MISSION_POD_MANAGER_ASSIGNED: 5,
  MISSION_POD_ASSIGNED: 5,
  MISSION_SPECIALIST_ASSIGNED: 6,
  MISSION_SPECIALIST_PLANNED: 6,
  MISSION_RUNNING: 7,
  MISSION_GATING: 8,
  MISSION_FUSION: 9,
  MISSION_LOGIC_FOLDED: 9,
  MISSION_VERIFIED: 10,
  MISSION_COMPLETE: 11,
  MISSION_FAILED: 11,
};

const V2_STATE_TO_PHASE_INDEX: Record<string, number> = {
  INTAKE: 0,
  QUEUED: 1,
  PM_INTAKE: 2,
  FETCH: 3,
  CEO_DELEGATED: 4,
  POD_ASSIGNED: 5,
  SPECIALIST_ASSIGNED: 6,
  RUNNING: 7,
  GATING: 8,
  FUSION: 9,
  VERIFIED: 10,
  COMPLETE: 11,
  FAILED: 11,
};

const V2_STATE_SET = new Set(Object.keys(V2_STATE_TO_PHASE_INDEX));
const V2_EVENT_SET = new Set(Object.keys(V2_EVENT_TO_PHASE_INDEX));

function normalizeToken(value: string | null | undefined): string {
  return String(value ?? "").trim().toUpperCase();
}

function phaseMapsForModel(model: MissionPhaseModel): {
  eventToIndex: Record<string, number>;
  stateToIndex: Record<string, number>;
  phases: readonly string[];
} {
  if (model === "v2") {
    return {
      eventToIndex: V2_EVENT_TO_PHASE_INDEX,
      stateToIndex: V2_STATE_TO_PHASE_INDEX,
      phases: MISSION_FLOW_V2_PHASES,
    };
  }
  return {
    eventToIndex: V1_EVENT_TO_PHASE_INDEX,
    stateToIndex: V1_STATE_TO_PHASE_INDEX,
    phases: SMELT_PHASES,
  };
}

export function detectMissionPhaseModel(params: {
  missionState?: string | null;
  events?: MissionEvent[];
  routingVersion?: string | null;
}): MissionPhaseModel {
  if (normalizeToken(params.routingVersion) === "V2") {
    return "v2";
  }

  const missionState = normalizeToken(params.missionState);
  if (
    V2_STATE_SET.has(missionState) &&
    !Object.prototype.hasOwnProperty.call(V1_STATE_TO_PHASE_INDEX, missionState)
  ) {
    return "v2";
  }
  if (
    missionState === "PM_INTAKE" || missionState === "FETCH" ||
    missionState === "CEO_DELEGATED" || missionState === "POD_ASSIGNED" ||
    missionState === "SPECIALIST_ASSIGNED"
  ) {
    return "v2";
  }

  for (const event of params.events ?? []) {
    const eventType = normalizeToken(event.event_type);
    if (V2_EVENT_SET.has(eventType) && !(eventType in V1_EVENT_TO_PHASE_INDEX)) {
      return "v2";
    }
    if (
      eventType === "MISSION_PM_INTAKE" ||
      eventType === "MISSION_CEO_DELEGATED" ||
      eventType === "MISSION_POD_MANAGER_ASSIGNED" ||
      eventType === "MISSION_SPECIALIST_ASSIGNED" ||
      eventType === "MISSION_SPECIALIST_PLANNED"
    ) {
      return "v2";
    }
  }
  return "v1";
}

export function smeltPhaseIndexForEventType(
  eventType: string,
  model: MissionPhaseModel = "v1",
): number | null {
  const { eventToIndex } = phaseMapsForModel(model);
  const index = eventToIndex[normalizeToken(eventType)];
  return Number.isInteger(index) ? index : null;
}

export function smeltPhaseFromEventType(
  eventType: string,
  model: MissionPhaseModel = "v1",
): string | null {
  const index = smeltPhaseIndexForEventType(eventType, model);
  if (index === null) {
    return null;
  }
  return phaseMapsForModel(model).phases[index] ?? null;
}

export function smeltPhaseFromIndex(index: number, model: MissionPhaseModel = "v1"): string {
  const { phases } = phaseMapsForModel(model);
  if (!Number.isFinite(index)) {
    return phases[0];
  }
  const clamped = Math.min(Math.max(0, Math.floor(index)), phases.length - 1);
  return phases[clamped];
}

export function deriveMissionPhaseDescriptor(params: {
  missionState?: string | null;
  events?: MissionEvent[];
  logicNodeCount?: number;
  verifiedLogicNodeCount?: number;
  routingVersion?: string | null;
}): {
  model: MissionPhaseModel;
  phaseIndex: number;
  phaseName: string;
  phases: readonly string[];
} {
  const model = detectMissionPhaseModel(params);
  const { eventToIndex, stateToIndex, phases } = phaseMapsForModel(model);
  const missionState = normalizeToken(params.missionState);
  let phaseIndex = stateToIndex[missionState] ?? 0;

  for (const event of params.events ?? []) {
    const mapped = eventToIndex[normalizeToken(event.event_type)];
    if (Number.isInteger(mapped)) {
      phaseIndex = Math.max(phaseIndex, mapped);
    }
  }

  if (model === "v1" && missionState === "RUNNING") {
    const logicNodeCount = Math.max(0, Number(params.logicNodeCount ?? 0));
    const verifiedLogicNodeCount = Math.max(0, Number(params.verifiedLogicNodeCount ?? 0));
    if (logicNodeCount > 0) {
      phaseIndex = Math.max(phaseIndex, 3);
    }
    if (verifiedLogicNodeCount > 0) {
      phaseIndex = Math.max(phaseIndex, 4);
    }
  }

  phaseIndex = Math.min(Math.max(0, phaseIndex), phases.length - 1);
  return {
    model,
    phaseIndex,
    phaseName: phases[phaseIndex] ?? phases[0],
    phases,
  };
}

export function deriveSmeltPhaseIndex(params: {
  missionState?: string | null;
  events?: MissionEvent[];
  logicNodeCount?: number;
  verifiedLogicNodeCount?: number;
  routingVersion?: string | null;
}): number {
  return deriveMissionPhaseDescriptor(params).phaseIndex;
}
