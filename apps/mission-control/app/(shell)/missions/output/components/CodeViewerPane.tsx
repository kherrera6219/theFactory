'use client';

import React, { useMemo } from 'react';
import { Panel } from '../../../../components/panel';
import type { MissionBuildArtifactRecord } from '../../../../lib/types';

interface CodeViewerPaneProps {
  artifact: MissionBuildArtifactRecord | null;
  loading: boolean;
}

function getFilename(artifact: MissionBuildArtifactRecord): string {
  return String(
    (artifact.manifest as { filename?: string } | undefined)?.filename ?? artifact.artifact_id
  );
}

function buildNumberedLines(text: string): Array<{ number: number; content: string }> {
  return text.split('\n').map((line, index) => ({ number: index + 1, content: line }));
}

function SkeletonViewer() {
  return (
    <div style={{ padding: '1rem' }}>
      {[60, 80, 45, 75, 55, 90, 40, 70].map((width, i) => (
        <div
          key={i}
          className="skeleton skeleton-text"
          style={{ width: `${width}%`, marginBottom: '0.5rem', height: '0.9em' }}
        />
      ))}
    </div>
  );
}

export function CodeViewerPane({ artifact, loading }: CodeViewerPaneProps) {
  const filename = artifact ? getFilename(artifact) : null;

  const lines = useMemo(() => {
    if (!artifact?.artifact_text) return null;
    return buildNumberedLines(artifact.artifact_text);
  }, [artifact?.artifact_text]);

  const panelTitle = filename ? `Output \u2014 ${filename}` : 'Output';

  return (
    <Panel title={panelTitle}>
      {loading && <SkeletonViewer />}

      {!loading && !artifact && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            padding: '3rem 1.5rem',
            color: 'var(--color-text-muted)',
          }}
        >
          <span style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }} aria-hidden>&#128196;</span>
          <p style={{ margin: 0 }}>No generated-code artifact recorded for this mission yet.</p>
        </div>
      )}

      {!loading && artifact && !artifact.artifact_text && (
        <div style={{ padding: '1rem' }}>
          <p className="muted">
            Artifact metadata recorded but inline text is not available. Use the Download button to
            retrieve the file.
          </p>
          <dl style={{ marginTop: '0.75rem' }}>
            <div><dt>Artifact ID</dt><dd className="mono-id">{artifact.artifact_id}</dd></div>
            <div><dt>Storage</dt><dd>{artifact.storage_backend}</dd></div>
            <div><dt>Ref</dt><dd className="mono-id">{artifact.storage_ref ?? 'n/a'}</dd></div>
          </dl>
        </div>
      )}

      {!loading && lines && (
        <div
          className="code-block"
          style={{
            margin: 0,
            borderRadius: 'var(--radius-md)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              overflowY: 'auto',
              maxHeight: 'calc(100vh - 280px)',
              minHeight: '320px',
            }}
          >
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontFamily: 'var(--font-mono, ui-monospace, monospace)',
                fontSize: '0.82em',
                lineHeight: 1.6,
              }}
              aria-label={`Source code: ${filename ?? 'output'}`}
            >
              <tbody>
                {lines.map(({ number, content }) => (
                  <tr
                    key={number}
                    style={{ verticalAlign: 'top' }}
                  >
                    <td
                      aria-hidden
                      style={{
                        padding: '0 0.75rem 0 0.5rem',
                        userSelect: 'none',
                        color: 'var(--color-text-faint)',
                        textAlign: 'right',
                        minWidth: '3ch',
                        width: '1%',
                        whiteSpace: 'nowrap',
                        borderRight: '1px solid var(--color-border)',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {number}
                    </td>
                    <td
                      style={{
                        padding: '0 0.75rem',
                        whiteSpace: 'pre',
                        color: 'var(--color-text)',
                      }}
                    >
                      {content || '\u00A0'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Panel>
  );
}
