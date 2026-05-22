'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import { humanizeState, formatDateTime, formatTime } from '../../../../../lib/format';
import type { MissionRecord, MissionChainTrace } from '../../../../../lib/types';

interface MissionSignalsPanelProps {
  loading: boolean;
  mission: MissionRecord | null;
  chainTrace: MissionChainTrace | null;
  lifecycleEngine: string;
  phaseLabel: string;
  phaseName: string;
  lastUpdatedAt: string | null;
  transportMode: string;
  streamEventsSeen: number;
  streamErrors: number;
  pollFallbackTicks: number;
}

export function MissionSignalsPanel({
  loading,
  mission,
  chainTrace,
  lifecycleEngine,
  phaseLabel,
  phaseName,
  lastUpdatedAt,
  transportMode,
  streamEventsSeen,
  streamErrors,
  pollFallbackTicks,
}: MissionSignalsPanelProps) {
  return (
    <Panel title="Mission Signals">
      {loading && <p className="muted">Loading mission signals...</p>}
      {!loading && mission && (
        <dl>
          <div>
            <dt>Status</dt>
            <dd>{humanizeState(mission.state)}</dd>
          </div>
          <div>
            <dt>Lifecycle engine</dt>
            <dd>
              <span
                className={`connection-chip ${
                  lifecycleEngine === "MissionFlow V2"
                    ? "live"
                    : lifecycleEngine === "LangGraph"
                      ? "retrying"
                      : "stale"
                }`}
                title={`Active lifecycle engine: ${lifecycleEngine}`}
              >
                {lifecycleEngine}
              </span>
            </dd>
          </div>
          <div>
            <dt>{phaseLabel}</dt>
            <dd>{phaseName}</dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd>{formatDateTime(mission.created_at)}</dd>
          </div>
          <div>
            <dt>Target language</dt>
            <dd>{mission.requested_target_language ?? "n/a"}</dd>
          </div>
          {chainTrace?.mission_type === "PORT" &&
            chainTrace?.port_source_language && (
              <div>
                <dt>PORT phases</dt>
                <dd>
                  <span
                    className={`connection-chip ${chainTrace?.port_source_logicnodes?.length ? "live" : "retrying"}`}
                    title="Source extraction phase"
                  >
                    EXTRACTION: {String(chainTrace?.port_source_language ?? "?")}
                    {chainTrace?.port_source_logicnodes?.length ? " ✓" : " ●"}
                  </span>
                  {" → "}
                  <span
                    className={`connection-chip ${chainTrace?.port_phase === "generation" ? "retrying" : chainTrace?.generated_output ? "live" : "stale"}`}
                    title="Target generation phase"
                  >
                    GENERATION: {String(chainTrace?.port_target_language ?? mission.requested_target_language ?? "?")}
                    {chainTrace?.generated_output ? " ✓" : " ●"}
                  </span>
                </dd>
              </div>
            )}
          <div>
            <dt>Last refresh</dt>
            <dd>{lastUpdatedAt ? formatTime(lastUpdatedAt) : "n/a"}</dd>
          </div>
          <div>
            <dt>Transport mode</dt>
            <dd>{transportMode}</dd>
          </div>
          <div>
            <dt>Stream events</dt>
            <dd>{streamEventsSeen}</dd>
          </div>
          <div>
            <dt>Stream errors</dt>
            <dd>{streamErrors}</dd>
          </div>
          <div>
            <dt>Poll fallback ticks</dt>
            <dd>{pollFallbackTicks}</dd>
          </div>
        </dl>
      )}
    </Panel>
  );
}
