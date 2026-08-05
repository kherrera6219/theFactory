'use client';

import React from 'react';
import Link from 'next/link';
import { Panel } from '../../../../../components/panel';
import type { OperationsLogicNodeRecord } from '../../../../../lib/types';

interface LogicNodeProgressPanelProps {
  missionId: string;
  missionType?: string | null;
  logicNodes: OperationsLogicNodeRecord[];
  verifiedCount: number;
  avgConfidence: string;
}

/**
 * Mission types that extract LogicNodes from existing source code. Everything
 * else — BUILD_NEW above all — synthesises its logic from the mission contract
 * instead and legitimately has zero LogicNodes, because the only writers of the
 * logicnode store require source to extract from. Rendering a bare
 * "0 LogicNodes" for those missions reads as a failure rather than as
 * "not applicable".
 */
const EXTRACTION_MISSION_TYPES = new Set([
  'IMPORT_MODERNIZE',
  'PORT',
  'DEBUG_REPAIR',
  'ANALYZE_ONLY',
]);

function extractsLogicNodes(missionType?: string | null): boolean {
  const normalized = (missionType ?? '').trim().toUpperCase();
  // Unknown mission type: keep the extraction view rather than hiding counts
  // that may well be real.
  if (normalized.length === 0) {
    return true;
  }
  return EXTRACTION_MISSION_TYPES.has(normalized);
}

export function LogicNodeProgressPanel({
  missionId,
  missionType,
  logicNodes,
  verifiedCount,
  avgConfidence,
}: LogicNodeProgressPanelProps) {
  // Only substitute the explanatory copy when there is genuinely nothing to
  // show — if a generative mission somehow carries LogicNodes, display them.
  if (!extractsLogicNodes(missionType) && logicNodes.length === 0) {
    return (
      <Panel title="LogicNode Progress">
        {/*
          One expression rather than JSX text around {missionType}: the JSX
          transform drops the space between an expression container and the text
          that follows it on the same line, which rendered "BUILD_NEWmissions".
        */}
        <p className="muted">
          {`Not applicable — ${missionType} missions generate logic from the mission ` +
            "contract rather than extracting LogicNodes from existing source. This " +
            "mission's logic decomposition is in its mission contract and pod group " +
            "standards."}
        </p>
      </Panel>
    );
  }

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
