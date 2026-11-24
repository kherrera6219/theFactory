/**
 * One definition of what a mission *is* for display: its readable title, short
 * id, whether it is internal, and whether a completion gate has parked it.
 *
 * Mirrors services/orchestrator/orchestrator/mission_attention.py. Before this,
 * every page decided for itself: the two Knowledge Lake bootstrap rows were
 * counted as missions, completion-blocked missions showed as green "Verified"
 * (and as "active" on other pages), and every list labelled rows "mission-…".
 */

import { humanizeState, normalizeState } from "./format";
import type { MissionRecord } from "./types";

export const SYSTEM_MISSION_IDS: ReadonlySet<string> = new Set([
  "__knowledge_lake__",
  "system-knowledge-lake",
]);

export const COMPLETION_BLOCKED_EVENT = "MISSION_COMPLETION_BLOCKED";

const TERMINAL = new Set(["COMPLETE", "FAILED", "CANCELLED"]);

type MissionLike = Pick<MissionRecord, "mission_id" | "state"> &
  Partial<Pick<MissionRecord, "prompt" | "metadata">>;

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function isSystemMission(missionId: string | null | undefined): boolean {
  return SYSTEM_MISSION_IDS.has(String(missionId ?? ""));
}

/** Drops the internal Knowledge Lake rows from a mission list. */
export function withoutSystemMissions<T extends { mission_id: string }>(missions: T[]): T[] {
  return missions.filter((mission) => !isSystemMission(mission.mission_id));
}

export function isCompletionBlocked(mission: MissionLike): boolean {
  if (TERMINAL.has(normalizeState(mission.state))) return false;
  const metadata = asRecord(mission.metadata);
  return asText(metadata?.last_chain_event_type) === COMPLETION_BLOCKED_EVENT;
}

export type BlockReason = { gate: string; reason: string };

function lastBlockedRecord(metadata: Record<string, unknown>): Record<string, unknown> | null {
  for (const key of ["chain_trace", "chain_events"]) {
    const list = metadata[key];
    if (!Array.isArray(list)) continue;
    for (let index = list.length - 1; index >= 0; index -= 1) {
      const record = asRecord(list[index]);
      if (record && asText(record.event_type) === COMPLETION_BLOCKED_EVENT) return record;
    }
  }
  return null;
}

function formatUsd(value: unknown): string | null {
  return typeof value === "number" && Number.isFinite(value) ? `$${value.toFixed(4)}` : null;
}

/**
 * Why a completion gate stopped the mission, in operator language. The spend
 * cap is checked first: missions blocked before 2026-11-23 recorded a budget
 * stop as "runtime QC did not pass".
 */
export function completionBlockReason(mission: MissionLike): BlockReason | null {
  if (!isCompletionBlocked(mission)) return null;
  const metadata = asRecord(mission.metadata) ?? {};
  const spendCap = asRecord(metadata.spend_cap);
  if (metadata.spend_cap_hit === true || asText(spendCap?.state) === "pause") {
    const actual = formatUsd(spendCap?.actual_usd);
    const cap = formatUsd(spendCap?.cap_usd);
    const amounts = actual && cap ? ` (${actual} spent of a ${cap} cap)` : "";
    return {
      gate: "Spend cap",
      reason: `LLM spend passed the approved cap${amounts}; approve more budget to finish.`,
    };
  }
  const details = asRecord(lastBlockedRecord(metadata)?.details);
  const gate = asText(details?.gate) || "completion gate";
  const reason = asText(details?.reason) || "A completion gate refused this mission.";
  return { gate: humanizeState(gate), reason };
}

/** "Blocked" for parked missions, otherwise the humanized state. */
export function missionDisplayState(mission: MissionLike): string {
  return isCompletionBlocked(mission) ? "Blocked" : humanizeState(mission.state);
}

/** CSS tone for a mission's state pill. */
export function missionStateTone(mission: MissionLike): "healthy" | "warning" | "critical" | "info" {
  if (isCompletionBlocked(mission)) return "warning";
  const state = normalizeState(mission.state);
  if (state === "FAILED" || state === "CANCELLED") return "critical";
  if (state === "COMPLETE" || state === "VERIFIED") return "healthy";
  return "info";
}

/** "mission-5b6e6a8e" — enough to tell rows apart, short enough for a list. */
export function shortMissionId(missionId: string): string {
  const match = /^(mission-[0-9a-f]{8})/i.exec(missionId);
  if (match) return match[1];
  return missionId.length > 20 ? `${missionId.slice(0, 19)}…` : missionId;
}

/** A readable mission name: contract title, operator name, or the prompt's first line. */
export function missionTitle(mission: MissionLike): string {
  const metadata = asRecord(mission.metadata) ?? {};
  const contract = asRecord(metadata.feature_contract);
  const candidates = [
    asText(contract?.title),
    asText(metadata.mission_name),
    asText(metadata.name),
    asText(mission.prompt).split(/\r?\n/)[0] ?? "",
  ];
  const title = candidates.find((value) => value.length > 0);
  if (!title) return shortMissionId(mission.mission_id);
  return title.length > 90 ? `${title.slice(0, 89)}…` : title;
}

/** Lower-cased text a mission search should match: id, title, prompt, type, language. */
export function missionSearchText(
  mission: MissionLike & Partial<Pick<MissionRecord, "mission_type" | "requested_target_language">>,
): string {
  return [
    mission.mission_id,
    missionTitle(mission),
    asText(mission.prompt),
    missionDisplayState(mission),
    asText(mission.mission_type ?? ""),
    asText(mission.requested_target_language ?? ""),
  ]
    .join(" ")
    .toLowerCase();
}
