'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';

interface StandardNode {
  standard_node_id: string;
  concept: string;
  domain: string;
  languages: string[];
}

interface PodStandard {
  pod_manager_agent_id: string;
  canonical_logicnodes: StandardNode[];
  eliminated_duplicates: number;
  source: string;
  summary: string;
}

interface PodGroupStandardsPanelProps {
  podGroupStandards: Array<[string, PodStandard]>;
}

export function PodGroupStandardsPanel({ podGroupStandards }: PodGroupStandardsPanelProps) {
  return (
    <Panel title="Pod Group Standards">
      {podGroupStandards.length === 0 && (
        <p className="muted">No pod group standards recorded yet.</p>
      )}
      {podGroupStandards.length > 0 && (
        <ul className="card-list">
          {podGroupStandards.map(([pod, standard]) => (
            <li key={pod} className="info-card">
              <h3>{pod}</h3>
              <dl>
                <div>
                  <dt>Pod manager</dt>
                  <dd>{standard.pod_manager_agent_id}</dd>
                </div>
                <div>
                  <dt>Canonical LogicNodes</dt>
                  <dd>{standard.canonical_logicnodes.length}</dd>
                </div>
                <div>
                  <dt>Duplicates removed</dt>
                  <dd>{standard.eliminated_duplicates}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>{standard.source}</dd>
                </div>
              </dl>
              <p>{standard.summary}</p>
              {standard.canonical_logicnodes.length > 0 && (
                <ul className="summary-list">
                  {standard.canonical_logicnodes.slice(0, 8).map((node) => (
                    <li key={node.standard_node_id}>
                      <strong>{node.concept}</strong>
                      <span>{node.domain}</span>
                      <span className="muted">
                        {node.languages.length > 0 ? node.languages.join(', ') : 'language n/a'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
