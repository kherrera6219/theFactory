'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import { formatTime } from '../../../../../lib/format';
import { smeltPhaseFromEventType } from '../../../../../lib/smelt-cycle';
import type { MissionPhaseModel } from '../../../../../lib/smelt-cycle';
import type { MissionEvent } from '../../../../../lib/types';

interface MissionEventLogPanelProps {
  events: MissionEvent[];
  model: MissionPhaseModel;
}

export function MissionEventLogPanel({ events, model }: MissionEventLogPanelProps) {
  return (
    <Panel title="Mission Event Log">
      {events.length === 0 && <p className="muted">No mission events recorded yet.</p>}
      {events.length > 0 && (
        <ul className="summary-list">
          {events.slice(0, 25).map((event) => {
            const eventPhaseLabel = smeltPhaseFromEventType(event.event_type, model);
            return (
              <li key={`${event.event_type}-${event.ts}`}>
                <strong>{formatTime(event.ts)}</strong>
                <span>
                  {eventPhaseLabel ? `${event.event_type} · ${eventPhaseLabel}` : event.event_type}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
