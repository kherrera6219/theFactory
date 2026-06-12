'use client';

import React from 'react';
import { Panel } from '../../../../components/panel';
import type { MissionBuildArtifactRecord } from '../../../../lib/types';

interface FileTreePaneProps {
  artifacts: MissionBuildArtifactRecord[];
  selectedArtifactId: string | null;
  onSelect: (artifactId: string) => void;
}

function artifactIcon(artifactType: string): string {
  if (artifactType === 'generated_code') return '\u{1F4C4}';
  if (artifactType.includes('test')) return '\u2705';
  if (artifactType.includes('doc')) return '\u{1F4D6}';
  if (artifactType.includes('audit') || artifactType.includes('report')) return '\u{1F4CB}';
  return '\u{1F4E6}';
}

function artifactFilename(artifact: MissionBuildArtifactRecord): string {
  const manifestFilename = (artifact.manifest as { filename?: string } | undefined)?.filename;
  if (manifestFilename) return manifestFilename;
  return artifact.artifact_type.replace(/_/g, '-') + '.' + artifact.artifact_id.slice(0, 6);
}

export function FileTreePane({
  artifacts,
  selectedArtifactId,
  onSelect,
}: FileTreePaneProps) {
  if (artifacts.length <= 1) return null;

  return (
    <Panel title="Files">
      <ul role="listbox" aria-label="Mission artifacts" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {artifacts.map((artifact) => {
          const isSelected = artifact.artifact_id === selectedArtifactId;
          return (
            <li key={artifact.artifact_id}>
              <button
                type="button"
                role="option"
                aria-selected={isSelected}
                onClick={() => onSelect(artifact.artifact_id)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '0.4rem 0.6rem',
                  borderRadius: 'var(--radius-sm)',
                  background: isSelected ? 'var(--color-primary-highlight)' : 'transparent',
                  color: isSelected ? 'var(--color-primary)' : 'var(--color-text)',
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: '0.82em',
                  cursor: 'pointer',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  transition: 'background var(--transition-interactive)',
                }}
              >
                <span aria-hidden>{artifactIcon(artifact.artifact_type)}</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {artifactFilename(artifact)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
