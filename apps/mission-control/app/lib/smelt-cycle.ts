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

const EVENT_TO_PHASE_INDEX: Record<string, number> = {
  MISSION_QUEUED: 1,
  MISSION_RUNNING: 2,
  MISSION_GATING: 3,
  MISSION_FUSION: 4,
  MISSION_VERIFIED: 5,
  MISSION_COMPLETE: 6,
  MISSION_FAILED: 6,
};

const STATE_TO_PHASE_INDEX: Record<string, number> = {
  INTAKE: 0,
  QUEUED: 1,
  RUNNING: 2,
  VERIFIED: 5,
  COMPLETE: 6,
  FAILED: 6,
};

function normalizeToken(value: string | null | undefined): string {
  return String(value ?? "").trim().toUpperCase();
}

export function smeltPhaseIndexForEventType(eventType: string): number | null {
  const index = EVENT_TO_PHASE_INDEX[normalizeToken(eventType)];
  return Number.isInteger(index) ? index : null;
}

export function smeltPhaseFromEventType(eventType: string): string | null {
  const index = smeltPhaseIndexForEventType(eventType);
  if (index === null) {
    return null;
  }
  return SMELT_PHASES[index] ?? null;
}

export function smeltPhaseFromIndex(index: number): string {
  if (!Number.isFinite(index)) {
    return SMELT_PHASES[0];
  }
  const clamped = Math.min(Math.max(0, Math.floor(index)), SMELT_PHASES.length - 1);
  return SMELT_PHASES[clamped];
}

export function deriveSmeltPhaseIndex(params: {
  missionState?: string | null;
  events?: MissionEvent[];
  logicNodeCount?: number;
  verifiedLogicNodeCount?: number;
}): number {
  const missionState = normalizeToken(params.missionState);
  let phaseIndex = STATE_TO_PHASE_INDEX[missionState] ?? 0;

  for (const event of params.events ?? []) {
    const mapped = smeltPhaseIndexForEventType(event.event_type);
    if (mapped !== null) {
      phaseIndex = Math.max(phaseIndex, mapped);
    }
  }

  if (missionState === "RUNNING") {
    const logicNodeCount = Math.max(0, Number(params.logicNodeCount ?? 0));
    const verifiedLogicNodeCount = Math.max(0, Number(params.verifiedLogicNodeCount ?? 0));
    if (logicNodeCount > 0) {
      phaseIndex = Math.max(phaseIndex, 3);
    }
    if (verifiedLogicNodeCount > 0) {
      phaseIndex = Math.max(phaseIndex, 4);
    }
  }

  return Math.min(Math.max(0, phaseIndex), SMELT_PHASES.length - 1);
}
