'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import type { OperationsAgentRecord } from '../../../../../lib/types';

interface ActiveAgentsPanelProps {
  activeAgents: OperationsAgentRecord[];
}

export function ActiveAgentsPanel({ activeAgents }: ActiveAgentsPanelProps) {
  return (
    <Panel title="Active Agents">
      {activeAgents.length === 0 && <p className="muted">No active agents currently assigned.</p>}
      {activeAgents.length > 0 && (
        <ul className="card-list">
          {activeAgents.map((agent) => (
            <li key={agent.agent_id} className="info-card">
              <h3>{agent.agent_id}</h3>
              <p>{agent.name}</p>
              <p className="muted">
                {/* Support/executive agents have pod === tier; don't print it twice. */}
                {(agent.pod === agent.tier ? [agent.tier] : [agent.pod, agent.tier])
                  .concat(agent.state)
                  .join(" · ")}
              </p>
              <p className="muted">Workload: {agent.workload_pct}%</p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
