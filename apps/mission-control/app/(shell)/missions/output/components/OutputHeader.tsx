'use client';

import React from 'react';
import Link from 'next/link';
import { missionApiUrl } from '../../../../../lib/api-client';
import { humanizeState } from '../../../../../lib/format';
import type { MissionRecord, MissionBuildArtifactRecord } from '../../../../../lib/types';

interface OutputHeaderProps {
  missionId: string;
  mission: MissionRecord | null;
  generatedCodeArtifact: MissionBuildArtifactRecord | null;
  onCopy: () => void;
  copied: boolean;
}

/**
 * Top bar for the Output page.
 * Shows: Back link | Mission name + state badge | Download anchor | Copy button.
 */
export function OutputHeader({
  missionId,
  mission,
  generatedCodeArtifact,
  onCopy,
  copied,
}: OutputHeaderProps) {
  const missionName = String(
    (mission?.metadata as Record<string, unknown> | undefined)?.name ?? '',
  );
  const displayName = missionName
    ? missionName
    : mission
    ? `Mission ${mission.mission_id.slice(0, 12)}…`
    : 'Mission Output';

  const stateLabel = mission ? humanizeState(mission.state) : null;

  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
        flexWrap: 'wrap',
        marginBottom: '1.25rem',
      }}
    >
      {/* Left: back + title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: 0 }}>
        <Link
          href={`/missions/detail?id=${encodeURIComponent(missionId)}`}
          className="secondary-button shell-link-button"
          aria-label="Back to mission detail"
        >
          ← Back
        </Link>
        <h1
          style={{
            fontSize: 'var(--text-xl, 1.5rem)',
            fontWeight: 600,
            margin: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {displayName}
        </h1>
        {stateLabel && (
          <span
            className={`status-badge ${mission?.state === 'COMPLETE' ? 'success' : ''}`}
            aria-label={`Mission state: ${stateLabel}`}
          >
            {stateLabel}
          </span>
        )}
      </div>

      {/* Right: actions */}
      <div className="inline-actions">
        {generatedCodeArtifact && (
          <a
            className="secondary-button shell-link-button"
            href={missionApiUrl(
              `/v1/missions/${encodeURIComponent(missionId)}/artifact?artifact_type=generated_code`,
            )}
            aria-label="Download generated code"
          >
            Download
          </a>
        )}
        {generatedCodeArtifact?.artifact_text && (
          <button
            type="button"
            className="secondary-button"
            onClick={onCopy}
            aria-label="Copy code to clipboard"
          >
            {copied ? '✓ Copied' : 'Copy'}
          </button>
        )}
      </div>
    </header>
  );
}
