'use client';

import React from 'react';
import Link from 'next/link';
import { Panel } from '../../../../../components/panel';
import type { OperationsLogicNodeRecord } from '../../../../../lib/types';

interface LogicNodeProgressPanelProps {
  missionId: string;
  logicNodes: OperationsLogicNodeRecord[];
  verifiedCount: number;
  avgConfidence: string;
}

export function LogicNodeProgressPanel({
  missionId,
  logicNodes,
  verifiedCount,
  avgConfidence,
}: LogicNodeProgressPanelProps) {
  return (
    <Panel title="LogicNode Progress">
      <dl>
        <div>
          <dt>Extracted</dt>
          <dd>{logicNodes.length} LogicNodes</dd>
        </div>
        <div>
          <dt>Verified</dt>
          <dd>{verifiedCount}</dd>
        </div>
        <div>
          <dt>Average confidence</dt>
          <dd>{avgConfidence}</dd>
        </div>
      </dl>
      <div className="inline-actions">
        <Link
          href={`/logicnodes?mission=${encodeURIComponent(missionId)}`}
          className="secondary-button shell-link-button"
        >
          Open LogicNode Explorer
        </Link>
      </div>
    </Panel>
  );
}
