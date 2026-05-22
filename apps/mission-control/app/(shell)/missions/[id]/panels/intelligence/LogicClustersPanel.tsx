'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';

interface LogicCluster {
  cluster_id: string;
  title: string;
  domain: string;
  priority: string;
  pod_manager_agent_id: string;
  specialist_agent_id: string;
  rationale: string;
}

interface LogicClustersPanelProps {
  logicClusters: LogicCluster[];
}

export function LogicClustersPanel({ logicClusters }: LogicClustersPanelProps) {
  return (
    <Panel title="Logic Clusters">
      {logicClusters.length === 0 && <p className="muted">No logic clusters recorded yet.</p>}
      {logicClusters.length > 0 && (
        <ul className="card-list">
          {logicClusters.map((cluster) => (
            <li key={cluster.cluster_id} className="info-card">
              <h3>{cluster.title}</h3>
              <dl>
                <div>
                  <dt>Domain</dt>
                  <dd>{cluster.domain}</dd>
                </div>
                <div>
                  <dt>Priority</dt>
                  <dd>{cluster.priority}</dd>
                </div>
                <div>
                  <dt>Pod manager</dt>
                  <dd>{cluster.pod_manager_agent_id}</dd>
                </div>
                <div>
                  <dt>Specialist</dt>
                  <dd>{cluster.specialist_agent_id}</dd>
                </div>
              </dl>
              <p>{cluster.rationale}</p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
