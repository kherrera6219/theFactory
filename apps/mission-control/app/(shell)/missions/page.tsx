"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
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

  const promptTooShort = prompt.trim().length > 0 && prompt.trim().length < 3;
  const normalizedState = normalizeState(mission?.state);
  const progress = PROGRESS_BY_STATE[normalizedState] ?? 0;
  const etaText = ETA_BY_STATE[normalizedState] ?? "calculating";
  const selectedMissionId = mission?.mission_id ?? null;
  const canPoll = mission !== null && !isTerminalState(mission.state);

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
    } catch (error) {
      setMissionListError(error instanceof Error ? error.message : "Unable to load recent missions.");
    } finally {
      setMissionListLoading(false);
    }
  }

  async function loadMissionDetails(missionId: string) {
    try {
      const [missionData, eventData] = await Promise.all([
        getMission(missionId),
        getMissionEvents(missionId, 20),
      ]);
      setMission(missionData);
      setEvents(eventData);
      setConnectionState("live");
      setPollFailures(0);
      setPollError(null);
      setLastUpdatedAt(new Date().toISOString());
      upsertRecentMission(missionData);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to load mission details right now.";
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
        metadata: { source: "mission-control-ui" },
      });
      setMission(created);
      setPrompt("");
      rememberSelectedMission(created.mission_id);
      upsertRecentMission(created);
      setSuccessNotice(`Mission ${created.mission_id} accepted and queued.`);
      await loadMissionDetails(created.mission_id);
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? `${error.message} Review mission prompt and retry.`
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
          <label htmlFor="prompt">Mission prompt</label>
          <p id="promptHelp" className="help-text">
            Include intent, constraints, and expected outputs. Minimum 3 characters.
          </p>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(eventChange) => setPrompt(eventChange.target.value)}
            placeholder="Build an internal API that translates payroll rules into testable logic nodes."
            rows={6}
            required
            aria-describedby="promptHelp promptValidation"
            aria-invalid={promptTooShort}
          />
          <p id="promptValidation" className={promptTooShort ? "field-error" : "help-text"}>
            {promptTooShort
              ? "Prompt is too short. Add enough context before submission."
              : "Tip: include functional boundaries and quality expectations."}
          </p>

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
          <button type="button" className="secondary-button" onClick={() => void loadRecentMissions()}>
            Refresh
          </button>
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
        {missionListError && <p className="error-box">{missionListError}</p>}
        {!missionListLoading && !missionListError && recentMissions.length === 0 && (
          <p className="muted">No recent missions found. Submit your first mission above.</p>
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
                      <span className="mission-item-id">{item.mission_id}</span>
                      <span className="mission-item-meta">
                        {humanizeState(item.state)} • {formatDateTime(item.created_at)}
                      </span>
                    </button>
                    <Link
                      href={`/missions/${item.mission_id}`}
                      className="secondary-button shell-link-button mission-live-link"
                    >
                      View Live
                    </Link>
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
          <span className={`connection-chip ${connectionState}`}>
            {connectionState === "idle" && "Idle"}
            {connectionState === "live" && "Live"}
            {connectionState === "retrying" && "Retrying"}
            {connectionState === "stale" && "Stale"}
          </span>
        }
      >
        {successNotice && <p className="success-box">{successNotice}</p>}
        {submitError && <p className="error-box">{submitError}</p>}
        {pollError && (
          <div className="error-box">
            <p>{pollError}</p>
            {mission && (
              <button
                type="button"
                className="secondary-button"
                onClick={() => void loadMissionDetails(mission.mission_id)}
              >
                Retry Now
              </button>
            )}
          </div>
        )}
        {!mission && <p className="muted">No mission selected.</p>}
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
        {!mission && <p className="muted">Mission events appear after submission.</p>}
        {mission && events.length === 0 && <p className="muted">Waiting for state events...</p>}
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
