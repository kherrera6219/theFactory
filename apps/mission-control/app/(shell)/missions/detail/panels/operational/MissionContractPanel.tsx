'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';

interface LogicNodeRequirement {
  domain: string;
  concept: string;
  intent: string;
  priority: string;
}

interface MissionContract {
  mission_type: string;
  output_mode: string;
  output_format: string;
  source: string;
  contract_summary: string;
  logicnode_requirements: LogicNodeRequirement[];
}

interface MissionContractPanelProps {
  missionContract: MissionContract | null;
}

export function MissionContractPanel({ missionContract }: MissionContractPanelProps) {
  return (
    <Panel title="Mission Contract">
      {!missionContract && <p className="muted">No CEO mission contract recorded yet.</p>}
      {missionContract && (
        <>
          <dl>
            <div>
              <dt>Type</dt>
              <dd>{missionContract.mission_type}</dd>
            </div>
            <div>
              <dt>Output mode</dt>
              <dd>{missionContract.output_mode}</dd>
            </div>
            <div>
              <dt>Format</dt>
              <dd>{missionContract.output_format}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{missionContract.source}</dd>
            </div>
          </dl>
          <p>{missionContract.contract_summary}</p>
          {missionContract.logicnode_requirements.length > 0 && (
            <ul className="card-list">
              {missionContract.logicnode_requirements.map((requirement) => (
                <li
                  key={`${requirement.domain}-${requirement.concept}-${requirement.intent}`}
                  className="info-card"
                >
                  <h3>{requirement.concept}</h3>
                  <p>{requirement.intent}</p>
                  <p className="muted">
                    {requirement.domain} - {requirement.priority}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Panel>
  );
}
