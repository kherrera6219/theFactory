'use client';

import React from 'react';
import { Panel } from '../../../../components/panel';
import { formatDateTime } from '../../../../lib/format';
import type { MissionBuildArtifactRecord, MissionChainTrace } from '../../../../lib/types';

interface ArtifactMetaPaneProps {
  artifact: MissionBuildArtifactRecord | null;
  chainTrace: MissionChainTrace | null;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function countLines(text: string | null | undefined): number | null {
  if (!text) return null;
  return text.split('\n').length;
}

export function ArtifactMetaPane({ artifact, chainTrace }: ArtifactMetaPaneProps) {
  const delivery = chainTrace?.delivery_summary ?? null;
  const lineCount = artifact ? countLines(artifact.artifact_text) : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {delivery && (
        <Panel title="Delivery Summary">
          <p style={{ marginBottom: '0.5rem', fontWeight: 600 }}>{delivery.delivery_title}</p>
          <p className="muted" style={{ marginBottom: '0.75rem' }}>{delivery.delivery_summary}</p>
          {delivery.usage_notes && (
            <p className="muted" style={{ marginBottom: '0.75rem', fontStyle: 'italic' }}>
              {delivery.usage_notes}
            </p>
          )}
          {delivery.criteria_met.length > 0 && (
            <div style={{ marginBottom: '0.5rem' }}>
              <p style={{ fontWeight: 600, fontSize: '0.82em', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
                Criteria Met
              </p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {delivery.criteria_met.map((c, i) => (
                  <li key={i} style={{ display: 'flex', gap: '0.4rem', padding: '0.15rem 0', fontSize: '0.85em' }}>
                    <span style={{ color: 'var(--color-success)', flexShrink: 0 }} aria-hidden>\u2713</span>
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {delivery.criteria_unmet.length > 0 && (
            <div>
              <p style={{ fontWeight: 600, fontSize: '0.82em', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
                Outstanding
              </p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {delivery.criteria_unmet.map((c, i) => (
                  <li key={i} style={{ display: 'flex', gap: '0.4rem', padding: '0.15rem 0', fontSize: '0.85em' }}>
                    <span style={{ color: 'var(--color-text-faint)', flexShrink: 0 }} aria-hidden>&#9675;</span>
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>
      )}

      {artifact && (
        <Panel title="Artifact Metadata">
          <dl>
            <div>
              <dt>File</dt>
              <dd className="mono-id" style={{ wordBreak: 'break-all', fontSize: '0.85em' }}>
                {String((artifact.manifest as { filename?: string } | undefined)?.filename ?? artifact.artifact_id)}
              </dd>
            </div>
            <div>
              <dt>Size</dt>
              <dd>
                {formatBytes(artifact.size_bytes)}
                {lineCount !== null && (
                  <span className="muted" style={{ marginLeft: '0.4rem' }}>
                    ({lineCount.toLocaleString()} lines)
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <span className={`status-badge ${artifact.status === 'complete' ? 'success' : 'default'}`}>
                  {artifact.status}
                </span>
              </dd>
            </div>
            <div>
              <dt>Stage</dt>
              <dd>{artifact.stage}</dd>
            </div>
            <div>
              <dt>Storage</dt>
              <dd>{artifact.storage_backend}</dd>
            </div>
            {artifact.storage_ref && (
              <div>
                <dt>Ref</dt>
                <dd className="mono-id" style={{ wordBreak: 'break-all', fontSize: '0.82em' }}>
                  {artifact.storage_ref}
                </dd>
              </div>
            )}
            <div>
              <dt>SHA-256</dt>
              <dd
                className="mono-id"
                style={{ wordBreak: 'break-all', fontSize: '0.78em' }}
                title={artifact.digest_sha256 ?? undefined}
              >
                {artifact.digest_sha256 ?? 'n/a'}
              </dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDateTime(artifact.created_at)}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{formatDateTime(artifact.updated_at)}</dd>
            </div>
          </dl>
        </Panel>
      )}
    </div>
  );
}
