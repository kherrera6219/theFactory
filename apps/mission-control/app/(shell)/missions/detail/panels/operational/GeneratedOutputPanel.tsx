'use client';

import React, { useCallback, useState } from 'react';
import Link from 'next/link';
import { Panel } from '../../../../../components/panel';
import { missionApiUrl } from '../../../../../lib/api-client';
import type { MissionBuildArtifactRecord } from '../../../../../lib/types';

interface GeneratedOutputPanelProps {
  missionId: string;
  generatedCodeArtifact: MissionBuildArtifactRecord | null;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function countLines(text: string): number {
  if (!text) return 0;
  return text.split('\n').length;
}

export function GeneratedOutputPanel({
  missionId,
  generatedCodeArtifact,
}: GeneratedOutputPanelProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    if (!generatedCodeArtifact?.artifact_text) return;
    void navigator.clipboard.writeText(generatedCodeArtifact.artifact_text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [generatedCodeArtifact?.artifact_text]);

  const filename = String(
    (generatedCodeArtifact?.manifest as { filename?: string } | undefined)?.filename ??
      generatedCodeArtifact?.artifact_id ??
      'output'
  );

  const lineCount = generatedCodeArtifact?.artifact_text
    ? countLines(generatedCodeArtifact.artifact_text)
    : null;

  return (
    <Panel title="Generated Output">
      {!generatedCodeArtifact && (
        <p className="muted">No generated-code artifact recorded yet.</p>
      )}
      {generatedCodeArtifact && (
        <>
          <dl>
            <div>
              <dt>File</dt>
              <dd className="mono-id">{filename}</dd>
            </div>
            <div>
              <dt>Size</dt>
              <dd>
                {formatBytes(generatedCodeArtifact.size_bytes)}
                {lineCount !== null && (
                  <span className="muted" style={{ marginLeft: '0.5rem' }}>
                    &mdash; {lineCount.toLocaleString()} lines
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt>Digest</dt>
              <dd className="mono-id" style={{ fontSize: '0.78em', wordBreak: 'break-all' }}>
                {generatedCodeArtifact.digest_sha256 ?? 'n/a'}
              </dd>
            </div>
            <div>
              <dt>Storage</dt>
              <dd>{generatedCodeArtifact.storage_backend}</dd>
            </div>
          </dl>

          <div className="inline-actions" style={{ marginTop: '0.75rem' }}>
            <Link
              href={`/missions/output?id=${encodeURIComponent(missionId)}`}
              className="primary-button shell-link-button"
            >
              View Output
            </Link>
            <a
              className="secondary-button shell-link-button"
              href={missionApiUrl(
                `/v1/missions/${encodeURIComponent(missionId)}/artifact?artifact_type=generated_code`
              )}
            >
              Download
            </a>
          </div>

          {generatedCodeArtifact.artifact_text && (
            <div className="code-block" style={{ position: 'relative', marginTop: '1rem' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.35rem 0.75rem',
                  borderBottom: '1px solid var(--color-border)',
                  background: 'var(--color-surface-offset)',
                  borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
                }}
              >
                <span className="mono-id" style={{ fontSize: '0.78em', color: 'var(--color-text-muted)' }}>
                  {filename}
                </span>
                <button
                  type="button"
                  className="secondary-button"
                  style={{ padding: '0.2rem 0.6rem', fontSize: '0.78em' }}
                  onClick={handleCopy}
                  aria-label="Copy code to clipboard"
                >
                  {copied ? '✓ Copied' : 'Copy'}
                </button>
              </div>
              <pre
                style={{
                  margin: 0,
                  borderRadius: '0 0 var(--radius-md) var(--radius-md)',
                  maxHeight: '380px',
                  overflow: 'auto',
                }}
              >
                {generatedCodeArtifact.artifact_text}
              </pre>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
