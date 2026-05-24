'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import { formatTime } from '../../../../../lib/format';
import type { MissionChainTrace } from '../../../../../lib/types';

interface ChainOfCommandTracePanelProps {
  chainTrace: MissionChainTrace | null;
}

export function ChainOfCommandTracePanel({ chainTrace }: ChainOfCommandTracePanelProps) {
  return (
    <Panel title="Chain of Command Trace">
      {!chainTrace && <p className="muted">Chain trace not available yet.</p>}
      {chainTrace && (
        <>
          <dl>
            <div>
              <dt>Routing enforced</dt>
              <dd>{chainTrace.routing_enforced ? 'yes' : 'no'}</dd>
            </div>
            <div>
              <dt>Routing version</dt>
              <dd>{chainTrace.routing_version ?? 'n/a'}</dd>
            </div>
            <div>
              <dt>Selected agent</dt>
              <dd>{chainTrace.selected_agent_id ?? 'n/a'}</dd>
            </div>
            <div>
              <dt>Pod manager</dt>
              <dd>{chainTrace.assigned_pod_manager_agent_id ?? 'n/a'}</dd>
            </div>
            <div>
              <dt>Specialist</dt>
              <dd>{chainTrace.assigned_specialist_agent_id ?? 'n/a'}</dd>
            </div>
          </dl>
          {(chainTrace.events ?? []).length === 0 && (
            <p className="muted">No chain events recorded yet.</p>
          )}
          {(chainTrace.events ?? []).length > 0 && (
            <ul className="summary-list">
              {(chainTrace.events ?? []).slice(0, 20).map((event) => (
                <li key={`${event.event_type}-${event.ts}`}>
                  <strong>{formatTime(event.ts)}</strong>
                  <span>{event.event_type}</span>
                  <span className="muted">{event.agent_id ?? 'unassigned'}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Panel>
  );
}
