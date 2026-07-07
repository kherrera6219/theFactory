"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { CopyId } from "../../components/copy-id";
import { OperatorAuthErrorAction } from "../../components/operator-auth-error-action";
import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, StatusBadge, SystemMessage } from "../../components/status";
import { useLastRefreshed } from "../../lib/use-last-refreshed";
import { createMission, getMission, getMissionEvents, listMissions } from "../../lib/api-client";
import {
  ETA_BY_STATE,
  PROGRESS_BY_STATE,
  formatDateTime,
  formatTime,
  humanizeState,
  isTerminalState,
  normalizeState,
} from "../../lib/format";
import type {
  DataClassification,
  DepthMode,
  MissionEvent,
  MissionRecord,
  MissionType,
  OutputMode,
} from "../../lib/types";
import { operatorRecoveryMessage } from "../../lib/operator-auth-error";
import { sanitizeUserText } from "../../lib/security";

const TARGET_LANGUAGES = ["python", "typescript", "go", "rust", "java", "csharp"] as const;
type TargetLanguage = (typeof TARGET_LANGUAGES)[number];

const MISSION_TYPES: { value: MissionType; label: string }[] = [
  { value: "BUILD_NEW", label: "Build a new application from scratch" },
  { value: "IMPORT_MODERNIZE", label: "Import and modernize an existing repo" },
  { value: "PORT", label: "Port to another OS, platform, or language" },
  { value: "DEBUG_REPAIR", label: "Debug or repair a repo" },
  { value: "SECURITY_HARDEN", label: "Security harden a repo" },
  { value: "REDUCE_DEPENDENCIES", label: "Reduce dependencies and code bloat" },
  { value: "RUN_QC", label: "Run and QC a built or patched app" },
  { value: "ARCHITECTURE_DOCS", label: "Generate architecture and documentation only" },
  { value: "ANALYZE_ONLY", label: "Analyze only — no code changes" },
  { value: "SELF_ANALYZE", label: "Self-analyze theFactory itself" },
];

const DEPTH_MODES: { value: DepthMode; label: string }[] = [
  { value: "SPRINT", label: "Sprint — fast prototype / first pass" },
  { value: "STANDARD", label: "Standard — normal engineering workflow" },
  { value: "PRODUCTION", label: "Production — full docs, tests, security, runtime QC" },
  { value: "REGULATED", label: "Regulated — compliance gates and stronger evidence" },
  { value: "AUTONOMOUS_LONG_RUN", label: "Autonomous Long Run — multi-hour work with checkpoints" },
];

const OUTPUT_MODES: { value: OutputMode; label: string }[] = [
  { value: "ANALYZE_ONLY", label: "Analyze only — reports, no changes" },
  { value: "PLAN_ONLY", label: "Plan only — charters and plans" },
  { value: "PATCH_PROPOSAL", label: "Patch proposal — diffs without applying" },
  { value: "APPLY_PATCH", label: "Apply patch — apply approved changes" },
  { value: "FULL_BUILD", label: "Full build — apply, test, document, package" },
  { value: "DEPENDENCY_REDUCTION", label: "Dependency reduction only" },
  { value: "RUN_QC", label: "Run / QC only — launch and validate existing app" },
  { value: "FULL_TRANSFORMATION", label: "Full transformation — multi-phase port / modernization" },
];

const DATA_CLASSIFICATIONS: { value: DataClassification; label: string }[] = [
  { value: "TIER_0_PUBLIC", label: "Tier 0 — Public (open-source or demo repo)" },
  { value: "TIER_1_INTERNAL", label: "Tier 1 — Internal (proprietary, no regulated data)" },
  { value: "TIER_2_SENSITIVE", label: "Tier 2 — Sensitive (credentials patterns, PII, trade secrets)" },
  { value: "TIER_3_REGULATED", label: "Tier 3 — Regulated (HIPAA, PCI, CUI, ITAR)" },
];

const MISSION_LIST_LIMIT = 20;
const POLL_INTERVAL_MS = 2500;
const STALE_POLL_THRESHOLD = 3;

function upsertMission(records: MissionRecord[], candidate: MissionRecord): MissionRecord[] {
  const withoutCurrent = records.filter((item) => item.mission_id !== candidate.mission_id);
  return [candidate, ...withoutCurrent]
    .sort(
      (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    )
    .slice(0, MISSION_LIST_LIMIT);
}

export default function MissionsPage() {
  const [missionName, setMissionName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [targetLanguage, setTargetLanguage] = useState<TargetLanguage>("python");
  const [missionType, setMissionType] = useState<MissionType>("BUILD_NEW");
  const [depthMode, setDepthMode] = useState<DepthMode>("STANDARD");
  const [outputMode, setOutputMode] = useState<OutputMode>("FULL_BUILD");
  const [dataClassification, setDataClassification] = useState<DataClassification>("TIER_1_INTERNAL");
  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [recentMissions, setRecentMissions] = useState<MissionRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [missionListLoading, setMissionListLoading] = useState(true);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [missionListError, setMissionListError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<"idle" | "live" | "retrying" | "stale">(
    "idle",
  );
  const [pollFailures, setPollFailures] = useState(0);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [lastFetchAt, setLastFetchAt] = useState<string | null>(null);
  // Monotonic request id shared by every loadMissionDetails caller (select,
  // submit, polling interval) — a response for a mission the user has since
  // navigated away from must never overwrite the currently-selected mission.
  const missionDetailsRequestIdRef = useRef(0);

  const lastRefreshedLabel = useLastRefreshed(lastFetchAt);
  const promptTooShort = prompt.trim().length > 0 && prompt.trim().length < 3;

  /** Phase 2D — pre-populate the launch form from a previous mission. */
  function duplicateMission(source: MissionRecord) {
    setPrompt(source.prompt ?? "");
    setMissionName(`Re-run: ${source.mission_id.slice(8, 16)}`);
    if (source.mission_type) setMissionType(source.mission_type);
    if (source.depth_mode) setDepthMode(source.depth_mode);
    if (source.output_mode) setOutputMode(source.output_mode);
    if (source.requested_target_language && TARGET_LANGUAGES.includes(source.requested_target_language as TargetLanguage)) {
      setTargetLanguage(source.requested_target_language as TargetLanguage);
    }
    if (source.data_classification) setDataClassification(source.data_classification);
    // Scroll the form panel into view so the operator can see what was pre-filled.
    document.querySelector(".form-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  const normalizedState = normalizeState(mission?.state);
  const progress = PROGRESS_BY_STATE[normalizedState] ?? 0;
  const etaText = ETA_BY_STATE[normalizedState] ?? "calculating";
  const selectedMissionId = mission?.mission_id ?? null;
  const canPoll = mission !== null && !isTerminalState(mission.state);
  const runtimeUnavailable = Boolean(missionListError && !mission);

  function rememberSelectedMission(missionId: string) {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("mission-control:selected-mission", missionId);
    }
  }

  function upsertRecentMission(candidate: MissionRecord) {
    setRecentMissions((existing) => upsertMission(existing, candidate));
  }

  async function loadRecentMissions() {
    setMissionListLoading(true);
    setMissionListError(null);
    try {
      const data = await listMissions(MISSION_LIST_LIMIT);
      setRecentMissions(data);
      setLastFetchAt(new Date().toISOString());
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Unable to load recent missions.";
      setMissionListError(operatorRecoveryMessage(rawMessage));
    } finally {
      setMissionListLoading(false);
    }
  }

  async function loadMissionDetails(missionId: string) {
    const requestId = ++missionDetailsRequestIdRef.current;
    try {
      const [missionData, eventData] = await Promise.all([
        getMission(missionId),
        getMissionEvents(missionId, 20),
      ]);
      if (missionDetailsRequestIdRef.current !== requestId) {
        return;
      }
      setMission(missionData);
      setEvents(eventData);
      setConnectionState("live");
      setPollFailures(0);
      setPollError(null);
      setLastUpdatedAt(new Date().toISOString());
      upsertRecentMission(missionData);
    } catch (error) {
      if (missionDetailsRequestIdRef.current !== requestId) {
        return;
      }
      const rawMessage =
        error instanceof Error ? error.message : "Unable to load mission details right now.";
      const message = operatorRecoveryMessage(rawMessage);
      setPollError(`${message} Use Retry to refresh status.`);
      setConnectionState((current) => (current === "stale" ? current : "retrying"));
      setPollFailures((count) => {
        const next = count + 1;
        if (next >= STALE_POLL_THRESHOLD) {
          setConnectionState("stale");
        }
        return next;
      });
    }
  }

  async function submitMission(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedPrompt = sanitizeUserText(prompt);
    if (trimmedPrompt.length < 3) {
      setSubmitError("Prompt must include at least 3 characters.");
      return;
    }

    setLoading(true);
    setSubmitError(null);
    setPollError(null);
    setSuccessNotice(null);

    try {
      const created = await createMission({
        prompt: trimmedPrompt,
        requested_target_language: targetLanguage,
        mission_type: missionType,
        depth_mode: depthMode,
        output_mode: outputMode,
        data_classification: dataClassification,
        metadata: {
          source: "mission-control-ui",
          ...(missionName.trim() ? { name: sanitizeUserText(missionName) } : {}),
        },
      });
      setMission(created);
      setPrompt("");
      setMissionName("");
      rememberSelectedMission(created.mission_id);
      upsertRecentMission(created);
      setSuccessNotice(`Mission ${created.mission_id} accepted and queued.`);
      await loadMissionDetails(created.mission_id);
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? `${operatorRecoveryMessage(error.message)} Review mission prompt and retry.`
          : "Unable to submit mission. Check service health and retry.",
      );
    } finally {
      setLoading(false);
    }
  }

  function selectMission(candidate: MissionRecord) {
    setMission(candidate);
    setEvents([]);
    setSuccessNotice(null);
    setSubmitError(null);
    setPollError(null);
    rememberSelectedMission(candidate.mission_id);
    void loadMissionDetails(candidate.mission_id);
  }

  useEffect(() => {
    void loadRecentMissions();
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const rememberedMissionId = window.localStorage.getItem("mission-control:selected-mission");
    if (rememberedMissionId) {
      void loadMissionDetails(rememberedMissionId);
    }
  }, []);

  useEffect(() => {
    if (!selectedMissionId || !canPoll) {
      if (!selectedMissionId) {
        setConnectionState("idle");
      }
      return;
    }
    let cancelled = false;
    const interval = window.setInterval(() => {
      if (!cancelled) {
        void loadMissionDetails(selectedMissionId);
      }
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [selectedMissionId, canPoll]);

  const liveAnnouncement = mission
    ? `Mission ${mission.mission_id} is ${humanizeState(mission.state)} with progress ${progress} percent.`
    : "No mission selected.";

  return (
    <div className="page shell-page mission-console">
      <p className="sr-only" role="status" aria-live="polite">
        {liveAnnouncement}
      </p>
      <p className="sr-only" role="alert" aria-live="assertive">
        {submitError ?? pollError ?? missionListError ?? ""}
      </p>

      <PageHeader
        compact
        eyebrow="Missions"
        title="Mission Intake and Lifecycle"
        description="Submit new refinery missions, monitor transition states, and recover safely from runtime interruptions."
      />

      <Panel className="form-panel" title="Launch Mission">
        <form onSubmit={submitMission}>
          {/* Phase 2C — optional human-readable mission name */}
          <div className="mission-name-field">
            <label htmlFor="missionName">Mission name <span className="muted">(optional)</span></label>
            <input
              id="missionName"
              type="text"
              value={missionName}
              onChange={(e) => setMissionName(e.target.value)}
              placeholder="e.g. Payroll API v2 — refactor"
              maxLength={120}
            />
          </div>

          <label htmlFor="prompt">Mission prompt</label>
          <p id="promptHelp" className="help-text">
            Describe the goal, constraints, and expected outputs of this mission. Minimum 3 characters.
          </p>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(eventChange) => setPrompt(eventChange.target.value)}
            placeholder="Describe what you want to build, analyze, or transform. Include scope, constraints, and quality expectations."
            rows={6}
            required
            aria-describedby="promptHelp promptValidation"
            aria-invalid={promptTooShort}
          />
          {/* Phase 2L — char counter */}
          <div className="prompt-footer">
            <p id="promptValidation" className={promptTooShort ? "field-error" : "help-text"}>
              {promptTooShort
                ? "Prompt is too short. Add enough context before submission."
                : "Tip: include functional boundaries and quality expectations."}
            </p>
            <span
              className={`char-counter${prompt.length >= 2800 ? " at-limit" : prompt.length >= 2000 ? " warn" : ""}`}
              aria-live="polite"
            >
              {prompt.length} / 3000
            </span>
          </div>

          <label htmlFor="missionType">Mission type</label>
          <p id="missionTypeHelp" className="help-text">
            What kind of work should theFactory perform?
          </p>
          <select
            id="missionType"
            value={missionType}
            aria-describedby="missionTypeHelp"
            onChange={(eventChange) => setMissionType(eventChange.target.value as MissionType)}
          >
            {MISSION_TYPES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <label htmlFor="depthMode">Depth mode</label>
          <p id="depthModeHelp" className="help-text">
            How thoroughly should this mission be executed?
          </p>
          <select
            id="depthMode"
            value={depthMode}
            aria-describedby="depthModeHelp"
            onChange={(eventChange) => setDepthMode(eventChange.target.value as DepthMode)}
          >
            {DEPTH_MODES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <label htmlFor="outputMode">Output mode</label>
          <p id="outputModeHelp" className="help-text">
            What is this mission permitted to produce or apply?
          </p>
          <select
            id="outputMode"
            value={outputMode}
            aria-describedby="outputModeHelp"
            onChange={(eventChange) => setOutputMode(eventChange.target.value as OutputMode)}
          >
            {OUTPUT_MODES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <label htmlFor="dataClassification">Data classification</label>
          <p id="dataClassHelp" className="help-text">
            Tier 2+ restricts LLM routing to local models only.
          </p>
          <select
            id="dataClassification"
            value={dataClassification}
            aria-describedby="dataClassHelp"
            onChange={(eventChange) =>
              setDataClassification(eventChange.target.value as DataClassification)
            }
          >
            {DATA_CLASSIFICATIONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <label htmlFor="targetLanguage">Target language</label>
          <select
            id="targetLanguage"
            value={targetLanguage}
            onChange={(eventChange) => setTargetLanguage(eventChange.target.value as TargetLanguage)}
          >
            {TARGET_LANGUAGES.map((language) => (
              <option key={language} value={language}>
                {language}
              </option>
            ))}
          </select>

          <button type="submit" disabled={loading || prompt.trim().length < 3}>
            {loading ? "Submitting..." : "Launch Mission"}
          </button>
        </form>
      </Panel>

      <Panel
        title="My Recent Missions"
        actions={
          <>
            {lastRefreshedLabel && (
              <span className="last-refreshed">{lastRefreshedLabel}</span>
            )}
            <button type="button" className="secondary-button" onClick={() => void loadRecentMissions()}>
              Refresh
            </button>
          </>
        }
      >
        {missionListLoading && (
          <ul className="mission-list" aria-label="Loading recent missions">
            {[0, 1, 2, 3].map((index) => (
              <li key={`mission-skeleton-${index}`}>
                <div className="mission-item">
                  <div className="mission-item-skeleton-main" aria-hidden="true">
                    <span className="skeleton-line skeleton-mission-id" />
                    <span className="skeleton-line skeleton-mission-meta" />
                  </div>
                  <span className="skeleton-button" aria-hidden="true" />
                </div>
              </li>
            ))}
          </ul>
        )}
        {missionListError && (
          <SystemMessage
            tone="critical"
            title="Recent missions are unavailable"
            action={
              <Link href="/settings" className="secondary-button shell-link-button">
                Configure Runtime
              </Link>
            }
          >
            {missionListError} Start the local runtime or update the API base URL, then refresh this panel.
          </SystemMessage>
        )}
        {!missionListLoading && !missionListError && recentMissions.length === 0 && (
          <EmptyState title="No recent missions yet" compact>
            Submitted missions will appear here with their latest state, timestamp, and live detail link.
          </EmptyState>
        )}
        {!missionListLoading && recentMissions.length > 0 && (
          <ul className="mission-list">
            {recentMissions.map((item) => {
              const isActive = item.mission_id === selectedMissionId;
              return (
                <li key={item.mission_id}>
                  <div className={`mission-item ${isActive ? "active" : ""}`}>
                    <button
                      type="button"
                      className="mission-item-action"
                      onClick={() => selectMission(item)}
                      aria-current={isActive ? "true" : undefined}
                    >
                      {/* Phase 2C — show human name when available */}
                      {(item.metadata as Record<string, unknown> | undefined)?.name
                        ? <span className="mission-item-name">{String((item.metadata as Record<string, unknown>).name)}</span>
                        : null}
                      <span className="mono-id">{item.mission_id.slice(0, 8)}…</span>
                      <span className="mission-item-meta">
                        {humanizeState(item.state)} • {formatDateTime(item.created_at)}
                      </span>
                    </button>
                    <div className="mission-item-actions">
                      {/* Phase 2I — copy full mission ID to clipboard */}
                      <CopyId id={item.mission_id} display={item.mission_id.slice(0, 8) + "…"} />
                      <button
                        type="button"
                        className="secondary-button"
                        title="Pre-fill the launch form with this mission's settings"
                        onClick={() => duplicateMission(item)}
                      >
                        Duplicate
                      </button>
                      <Link
                        href={`/missions/detail?id=${item.mission_id}`}
                        className="secondary-button shell-link-button mission-live-link"
                      >
                        View Live
                      </Link>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>

      <Panel
        className="status-panel"
        title="Mission Status"
        actions={
          <StatusBadge
            tone={
              connectionState === "live"
                ? "healthy"
                : runtimeUnavailable
                  ? "critical"
                  : connectionState === "retrying"
                  ? "warning"
                  : connectionState === "stale"
                    ? "critical"
                    : "neutral"
            }
          >
            {runtimeUnavailable && "Offline"}
            {!runtimeUnavailable && connectionState === "idle" && "Idle"}
            {connectionState === "live" && "Live"}
            {!runtimeUnavailable && connectionState === "retrying" && "Retrying"}
            {!runtimeUnavailable && connectionState === "stale" && "Stale"}
          </StatusBadge>
        }
      >
        {successNotice && (
          <SystemMessage tone="success" title="Mission accepted">
            {successNotice}
          </SystemMessage>
        )}
        {submitError && (
          <SystemMessage tone="critical" title="Mission could not be submitted">
            {submitError}
            <OperatorAuthErrorAction error={submitError} />
          </SystemMessage>
        )}
        {pollError && (
          <SystemMessage
            tone="critical"
            title="Mission status is stale"
            action={
              mission ? (
              <button
                type="button"
                className="secondary-button"
                onClick={() => void loadMissionDetails(mission.mission_id)}
              >
                Retry Now
              </button>
              ) : null
            }
          >
            {pollError}
            <OperatorAuthErrorAction error={pollError} />
          </SystemMessage>
        )}
        {!mission && (
          <EmptyState title={runtimeUnavailable ? "Runtime is offline" : "No mission selected"} compact variant={runtimeUnavailable ? "offline" : "empty"}>
            {runtimeUnavailable
              ? "Mission status will become available after the local runtime accepts authenticated requests."
              : "Launch a new mission or select one from recent missions to monitor progress, events, and retry state."}
          </EmptyState>
        )}
        {mission && (
          <>
            <div className="progress-block" aria-label={`Progress ${progress}%`}>
              <div className="progress-meta">
                <span>Progress</span>
                <strong>{progress}%</strong>
              </div>
              <div
                className="progress-track"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={progress}
              >
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <p className="help-text">Estimated completion: {etaText}</p>
            </div>

            <dl>
              <div>
                <dt>ID</dt>
                <dd>{mission.mission_id}</dd>
              </div>
              <div>
                <dt>State</dt>
                <dd>{humanizeState(mission.state)}</dd>
              </div>
              <div>
                <dt>Target</dt>
                <dd>{mission.requested_target_language ?? "auto"}</dd>
              </div>
              {mission.mission_type && (
                <div>
                  <dt>Mission Type</dt>
                  <dd>{mission.mission_type}</dd>
                </div>
              )}
              {mission.depth_mode && (
                <div>
                  <dt>Depth</dt>
                  <dd>{mission.depth_mode}</dd>
                </div>
              )}
              {mission.output_mode && (
                <div>
                  <dt>Output</dt>
                  <dd>{mission.output_mode}</dd>
                </div>
              )}
              {mission.data_classification && (
                <div>
                  <dt>Classification</dt>
                  <dd>{mission.data_classification}</dd>
                </div>
              )}
              <div>
                <dt>Created</dt>
                <dd>{formatDateTime(mission.created_at)}</dd>
              </div>
              <div>
                <dt>Last UI Update</dt>
                <dd>{lastUpdatedAt ? formatDateTime(lastUpdatedAt) : "Waiting for refresh"}</dd>
              </div>
            </dl>
          </>
        )}
      </Panel>

      <Panel title="Transition Timeline">
        {!mission && (
          <EmptyState title="No timeline yet" compact>
            Mission events appear here after submission or after selecting a recent mission.
          </EmptyState>
        )}
        {mission && events.length === 0 && (
          <EmptyState title="Waiting for state events" compact>
            The mission is selected, but no transition events have been returned by the runtime yet.
          </EmptyState>
        )}
        {events.length > 0 && (
          <dl>
            {events.map((missionEvent, index) => (
              <div key={`${missionEvent.ts}-${index}`}>
                <dt>{missionEvent.event_type}</dt>
                <dd>
                  {missionEvent.previous_state ? `${humanizeState(missionEvent.previous_state)} -> ` : ""}
                  {humanizeState(missionEvent.new_state)} at {formatTime(missionEvent.ts)}
                </dd>
              </div>
            ))}
          </dl>
        )}
        {pollFailures > 0 && (
          <p className="help-text">
            Poll retries: {pollFailures}. If this keeps increasing, check API availability and network health.
          </p>
        )}
      </Panel>
    </div>
  );
}
