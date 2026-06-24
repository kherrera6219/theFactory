'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import { formatDateTime } from '../../../../../lib/format';
import type { MissionCharter } from '../../../../../lib/types';

interface MissionCharterPanelProps {
  missionCharter: MissionCharter | null;
}

export function MissionCharterPanel({ missionCharter }: MissionCharterPanelProps) {
  return (
    <Panel title="Mission Charter">
      {!missionCharter && <p className="muted">No mission charter recorded yet.</p>}
      {missionCharter && (
        <>
          <dl>
            <div>
              <dt>Mode</dt>
              <dd>{missionCharter.mission_mode_label ?? missionCharter.mission_mode}</dd>
            </div>
            <div>
              <dt>Depth</dt>
              <dd>{missionCharter.depth_mode}</dd>
            </div>
            <div>
              <dt>Output</dt>
              <dd>{missionCharter.output_mode}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDateTime(missionCharter.created_at)}</dd>
            </div>
          </dl>
          <p>{missionCharter.objective}</p>
          {missionCharter.success_criteria.length > 0 && (
            <ul className="summary-list">
              {missionCharter.success_criteria.map((criterion) => (
                <li key={`charter-criterion-${criterion}`}>
                  <span>{criterion}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Panel>
  );
}
