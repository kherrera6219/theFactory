'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';

interface MasterLogicNode {
  node_id: string;
  concept: string;
  domain: string;
  source_pods: string[];
}

interface MasterLogicStreamReport {
  total_unified_nodes: number;
  eliminated_across_pods: number;
  source: string;
  master_logic_stream: MasterLogicNode[];
}

interface FusionPanelProps {
  masterLogicStream: MasterLogicStreamReport | null;
}

export function FusionPanel({ masterLogicStream }: FusionPanelProps) {
  if (
    !masterLogicStream ||
    !masterLogicStream.master_logic_stream ||
    masterLogicStream.master_logic_stream.length === 0
  ) {
    return null;
  }

  return (
    <Panel title="Master Logic Stream (FUSION)">
      <dl>
        <div>
          <dt>Unified nodes</dt>
          <dd>{masterLogicStream.total_unified_nodes}</dd>
        </div>
        <div>
          <dt>Duplicates eliminated across pods</dt>
          <dd>{masterLogicStream.eliminated_across_pods}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{masterLogicStream.source}</dd>
        </div>
      </dl>
      <ul className="summary-list">
        {masterLogicStream.master_logic_stream.map((node) => (
          <li key={node.node_id}>
            <strong>{node.concept}</strong>
            <span>{node.domain}</span>
            <span className="muted">{(node.source_pods ?? []).join(', ')}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
