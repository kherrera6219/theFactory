'use client';

import React from 'react';
import type { VirtualFileEntry } from '../../../../lib/file-tree';
import type { MissionBuildArtifactRecord } from '../../../../lib/types';

interface FileTreePaneProps {
  artifacts: MissionBuildArtifactRecord[];
  selectedArtifactId: string | null;
  onSelect: (id: string) => void;
  virtualFiles?: VirtualFileEntry[];
  selectedFilePath?: string | null;
  onSelectFile?: (path: string) => void;
  modifiedPaths?: string[];
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * Sticky left sidebar listing unpacked multi-file bundle entries (`## FILE`)
 * or multiple build artifacts. Clicking a row sets it as the active file in CodeViewerPane.
 */
export function FileTreePane({
  artifacts,
  selectedArtifactId,
  onSelect,
  virtualFiles = [],
  selectedFilePath,
  onSelectFile,
  modifiedPaths = [],
}: FileTreePaneProps) {
  const modifiedSet = new Set(modifiedPaths);
  const useVirtualTree = virtualFiles.length > 1 && Boolean(onSelectFile);

  if (!useVirtualTree && artifacts.length === 0) return null;

  return (
    <nav
      aria-label="Artifact file tree"
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '0.5rem 0.75rem',
          borderBottom: '1px solid var(--color-border)',
          background: 'var(--color-surface-offset)',
          fontSize: 'var(--text-xs)',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--color-text-muted)',
        }}
      >
        Files ({useVirtualTree ? virtualFiles.length : artifacts.length})
      </div>
      <ul role="list" style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {useVirtualTree
          ? virtualFiles.map((file) => {
              const isSelected = file.path === selectedFilePath;
              const isModified = modifiedSet.has(file.path);
              return (
                <li key={file.path}>
                  <button
                    type="button"
                    onClick={() => onSelectFile?.(file.path)}
                    aria-current={isSelected ? 'true' : undefined}
                    style={{
                      width: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.15rem',
                      padding: '0.5rem 0.75rem',
                      background: isSelected ? 'var(--color-primary-highlight)' : 'transparent',
                      color: isSelected ? 'var(--color-primary)' : 'var(--color-text)',
                      textAlign: 'left',
                      border: 'none',
                      borderBottom: '1px solid var(--color-divider)',
                      cursor: 'pointer',
                      fontSize: 'var(--text-sm)',
                      transition: 'background var(--transition-interactive)',
                    }}
                  >
                    <span
                      className="mono-id"
                      style={{
                        fontSize: '0.82em',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={file.path}
                    >
                      {file.path}
                    </span>
                    <span style={{ fontSize: '0.75em', color: 'var(--color-text-muted)' }}>
                      {file.lineCount} lines · {formatBytes(file.sizeBytes)}
                      {isModified ? ' · modified' : ''}
                    </span>
                  </button>
                </li>
              );
            })
          : artifacts.map((artifact) => {
              const filename = String(
                (artifact.manifest as { filename?: string } | undefined)?.filename ??
                  artifact.artifact_id,
              );
              const isSelected = artifact.artifact_id === selectedArtifactId;
              return (
                <li key={artifact.artifact_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(artifact.artifact_id)}
                    aria-current={isSelected ? 'true' : undefined}
                    style={{
                      width: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.15rem',
                      padding: '0.5rem 0.75rem',
                      background: isSelected ? 'var(--color-primary-highlight)' : 'transparent',
                      color: isSelected ? 'var(--color-primary)' : 'var(--color-text)',
                      textAlign: 'left',
                      border: 'none',
                      borderBottom: '1px solid var(--color-divider)',
                      cursor: 'pointer',
                      fontSize: 'var(--text-sm)',
                      transition: 'background var(--transition-interactive)',
                    }}
                  >
                    <span
                      className="mono-id"
                      style={{
                        fontSize: '0.82em',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={filename}
                    >
                      {filename}
                    </span>
                    <span style={{ fontSize: '0.75em', color: 'var(--color-text-muted)' }}>
                      {formatBytes(artifact.size_bytes)}
                    </span>
                  </button>
                </li>
              );
            })}
      </ul>
    </nav>
  );
}
