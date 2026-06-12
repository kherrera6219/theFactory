'use client';

import React from 'react';
import Link from 'next/link';
import { humanizeState } from '../../../../lib/format';
import { missionApiUrl } from '../../../../lib/api-client';
import type { MissionRecord, MissionBuildArtifactRecord } from '../../../../lib/types';

interface OutputHeaderProps {
  missionId: string;
  mission: MissionRecord | null;
  generatedCodeArtifact: MissionBuildArtifactRecord | null;
  onCopy: () => void;
  copied: boolean;
}

export function OutputHeader({
  missionId,
  mission,
  generatedCodeArtifact,
  onCopy,
  copied,
}: OutputHeaderProps) {
  const missionName = String(
    (mission?.metadata as Record<string, unknown> | undefined)?.name ?? ''
  );
  const displayTitle = missionName || `Mission ${missionId.slice(0, 12)}\u2026`;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        marginBottom: '1.5rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        <Link
          href={`/missions/detail?id=${encodeURIComponent(missionId)}`}
          className="secondary-button shell-link-button"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
        >
          <span aria-hidden>&#8592;</span> Mission Detail
        </Link>
        <span
          style={{
            fontSize: 'var(--text-lg, 1.125rem)',
            fontWeight: 600,
            color: 'var(--color-text)',
          }}
        >
          {displayTitle}
        </span>
        {mission?.state && (
          <span
            className={`status-badge ${
              mission.state === 'COMPLETE' ? 'success' : 'default'
            }`}
          >
            {humanizeState(mission.state)}
          </span>
        )}
      </div>

      <div className="inline-actions">
        {generatedCodeArtifact && (
          <>
            <button
              type="button"
              className="secondary-button"
              onClick={onCopy}
              aria-label="Copy generated code to clipboard"
            >
              {copied ? '\u2713 Copied' : 'Copy Code'}
            </button>
            <a
              className="primary-button shell-link-button"
              href={missionApiUrl(
                `/v1/missions/${encodeURIComponent(missionId)}/artifact?artifact_type=generated_code`
              )}
            >
              Download
            </a>
          </>
        )}
      </div>
    </div>
  );
}
