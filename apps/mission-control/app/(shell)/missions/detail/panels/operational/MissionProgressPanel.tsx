'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import {
  ETA_BY_STATE,
  PROGRESS_BY_STATE,
  formatTime,
  humanizeState,
  isTerminalState,
  normalizeState,
} from '../../../../../lib/format';
import type { MissionChainEvent, MissionChainTrace, MissionEvent, MissionRecord } from '../../../../../lib/types';

type MissionProgressPanelProps = {
  mission: MissionRecord | null;
  chainTrace: MissionChainTrace | null;
  events: MissionEvent[];
  phaseLabel: string;
  phaseName: string;
  lastUpdatedAt: string | null;
  transportMode: "stream" | "poll" | "paused";
  streamEventsSeen: number;
  pollFallbackTicks: number;
  activeAgentCount: number;
  buildArtifactCount: number;
};

function latestChainEvent(chainTrace: MissionChainTrace | null): MissionChainEvent | null {
  const events = chainTrace?.events ?? [];
  return events.length > 0 ? events[events.length - 1] : null;
}

function latestMissionEvent(events: MissionEvent[]): MissionEvent | null {
  return events.length > 0 ? events[0] : null;
}

function secondsSince(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) {
    return null;
  }
  return Math.max(0, Math.floor((Date.now() - parsed) / 1000));
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) {
    return "unknown";
  }
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

function eventLabel(eventType: string | null | undefined): string {
  return String(eventType ?? "No event yet")
    .replace(/^MISSION_/, "")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/(^\w|\s\w)/g, (match) => match.toUpperCase());
}

function eventDetail(details: Record<string, unknown> | undefined): string | null {
  if (!details) return null;
  for (const key of ["user_message", "message", "reason", "error", "detail"]) {
    const value = details[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim().slice(0, 180);
    }
  }
  return null;
}

function activityState(params: {
  missionState: string;
  transportMode: "stream" | "poll" | "paused";
  secondsSinceRefresh: number | null;
  secondsSinceEvent: number | null;
  lastEventType: string | null;
  lastEventDetail: string | null;
  buildArtifactCount: number;
}): { tone: "live" | "retrying" | "stale"; label: string; detail: string; nextAction: string } {
  const eventType = String(params.lastEventType ?? "").toUpperCase();
  if (params.missionState === "CLARIFYING" || eventType.includes("CLARIF")) {
    return {
      tone: "retrying",
      label: "Waiting for PM answers",
      detail: params.lastEventDetail ?? "The mission is paused until clarification is provided.",
      nextAction: "Answer the PM questions or continue with recommended defaults.",
    };
  }
  if (eventType.includes("BLOCKED") || eventType.includes("GATED")) {
    return {
      tone: "stale",
      label: "Blocked",
      detail: params.lastEventDetail ?? "The backend reported a blocking condition.",
      nextAction: "Review the latest event and rerun after the blocking issue is resolved.",
    };
  }
  if (eventType.includes("WAIT") || eventType.includes("RETRY")) {
    return {
      tone: "retrying",
      label: "Waiting",
      detail: params.lastEventDetail ?? "The backend is retrying or waiting on a dependency.",
      nextAction: "Keep monitoring unless the quiet time continues to climb.",
    };
  }
  if (isTerminalState(params.missionState)) {
    return {
      tone: params.missionState === "FAILED" ? "stale" : "live",
      label: params.missionState === "FAILED" ? "Stopped" : "Finished",
      detail: params.missionState === "FAILED" ? "Mission ended in failure." : "Mission completed.",
      nextAction:
        params.missionState === "FAILED"
          ? "Open the event log and fix the reported failure."
          : params.buildArtifactCount > 0
            ? "Open the output folder or continue with PM for follow-up work."
            : "Review generated output and delivery notes.",
    };
  }
  if (params.transportMode === "paused") {
    return {
      tone: "stale",
      label: "Monitor paused",
      detail: "Resume monitoring to refresh the live view.",
      nextAction: "Resume live monitoring.",
    };
  }
  if (params.secondsSinceRefresh !== null && params.secondsSinceRefresh > 45) {
    return {
      tone: "stale",
      label: "Refresh stale",
      detail: "The browser has not received a recent mission update.",
      nextAction: "Refresh the page or check runtime health if the timestamp does not move.",
    };
  }
  if (params.secondsSinceEvent !== null && params.secondsSinceEvent > 180) {
    return {
      tone: "retrying",
      label: "Long-running phase",
      detail: "The backend is still being polled; this phase may take longer on larger builds.",
      nextAction: "Keep monitoring; inspect logs if quiet time continues beyond this phase estimate.",
    };
  }
  return {
    tone: "live",
    label: "Working",
    detail: "Recent mission activity is visible.",
    nextAction: "No user action needed.",
  };
}

export function MissionProgressPanel({
  mission,
  chainTrace,
  events,
  phaseLabel,
  phaseName,
  lastUpdatedAt,
  transportMode,
  streamEventsSeen,
  pollFallbackTicks,
  activeAgentCount,
  buildArtifactCount,
}: MissionProgressPanelProps) {
  const missionState = normalizeState(mission?.state);
  const progress = PROGRESS_BY_STATE[missionState] ?? 10;
  const eta = ETA_BY_STATE[missionState] ?? "varies by mission size";
  const chainEvent = latestChainEvent(chainTrace);
  const missionEvent = latestMissionEvent(events);
  const lastEventType = chainEvent?.event_type ?? missionEvent?.event_type ?? null;
  const lastEventAt = chainEvent?.ts ?? missionEvent?.ts ?? null;
  const lastEventDetail = eventDetail(chainEvent?.details);
  const secondsSinceEvent = secondsSince(lastEventAt);
  const secondsSinceRefresh = secondsSince(lastUpdatedAt);
  const activity = activityState({
    missionState,
    transportMode,
    secondsSinceRefresh,
    secondsSinceEvent,
    lastEventType,
    lastEventDetail,
    buildArtifactCount,
  });
  const transportLabel =
    transportMode === "stream"
      ? `${streamEventsSeen} stream event${streamEventsSeen === 1 ? "" : "s"}`
      : transportMode === "poll"
        ? `${pollFallbackTicks} poll refresh${pollFallbackTicks === 1 ? "" : "es"}`
        : "paused";

  return (
    <Panel title="Live Progress" className="mission-progress-panel">
      {!mission && <p className="muted">Loading mission progress...</p>}
      {mission && (
        <>
          <div className="mission-progress-header">
            <div>
              <span className={`connection-chip ${activity.tone}`}>{activity.label}</span>
              <h2>{humanizeState(mission.state)}</h2>
              <p className="muted">{activity.detail}</p>
            </div>
            <div className="mission-progress-percent" aria-label={`Progress ${progress}%`}>
              {progress}%
            </div>
          </div>

          <div
            className="mission-progress-meter"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            aria-label="Mission progress"
          >
            <span style={{ width: `${progress}%` }} />
          </div>

          <dl className="mission-progress-facts">
            <div>
              <dt>{phaseLabel}</dt>
              <dd>{phaseName}</dd>
            </div>
            <div>
              <dt>Last event</dt>
              <dd>{eventLabel(lastEventType)}</dd>
            </div>
            <div>
              <dt>Quiet time</dt>
              <dd>{formatDuration(secondsSinceEvent)}</dd>
            </div>
            <div>
              <dt>Refresh</dt>
              <dd>{lastUpdatedAt ? `${formatTime(lastUpdatedAt)} (${transportLabel})` : transportLabel}</dd>
            </div>
            <div>
              <dt>Active agents</dt>
              <dd>{activeAgentCount}</dd>
            </div>
            <div>
              <dt>Typical step estimate</dt>
              <dd>{eta}</dd>
            </div>
            <div>
              <dt>Next action</dt>
              <dd>{activity.nextAction}</dd>
            </div>
          </dl>
        </>
      )}
    </Panel>
  );
}
