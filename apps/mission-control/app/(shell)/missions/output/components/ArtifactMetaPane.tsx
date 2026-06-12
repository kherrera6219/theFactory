'use client';

import React from 'react';
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

function countLines(text: string): number {
  if (!text) return 0;
  return text.split('\n').length;
}

/**
 * Right-column metadata pane for the Output page.
 * Shows artifact identity fields, storage provenance, and the
 * delivery_summary from the chain trace.
 */
export function ArtifactMetaPane({ artifact, chainTrace }: ArtifactMetaPaneProps) {
  const deliverySummary = chainTrace?.delivery_summary ?? null;
  const filename = String(
    (artifact?.manifest as { filename?: string } | undefined)?.filename ??
      artifact?.artifact_id ??
      '—',
  );
  const lineCount = artifact?.artifact_text ? countLines(artifact.artifact_text) : null;

  return (
    <aside
      aria-label="Artifact metadata"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
      }}
    >
      {/* Artifact identity */}
      <section
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
          Artifact
        </div>
        {artifact ? (
          <dl style={{ margin: 0, padding: '0.75rem' }}>
            <MetaRow label="File">
              <span className="mono-id" style={{ fontSize: '0.82em', wordBreak: 'break-all' }}>
                {filename}
              </span>
            </MetaRow>
            <MetaRow label="Size">
              {formatBytes(artifact.size_bytes)}
              {lineCount !== null && (
                <span style={{ marginLeft: '0.4rem', color: 'var(--color-text-muted)' }}>
                  &mdash; {lineCount.toLocaleString()} lines
                </span>
              )}
            </MetaRow>
            <MetaRow label="Type">{artifact.artifact_type}</MetaRow>
            <MetaRow label="Storage">{artifact.storage_backend}</MetaRow>
            {artifact.digest_sha256 && (
              <MetaRow label="SHA-256">
                <span
                  className="mono-id"
                  style={{
                    fontSize: '0.72em',
                    wordBreak: 'break-all',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  {artifact.digest_sha256}
                </span>
              </MetaRow>
            )}
            {artifact.created_at && (
              <MetaRow label="Created">
                <time dateTime={artifact.created_at} style={{ fontSize: '0.85em' }}>
                  {new Date(artifact.created_at).toLocaleString()}
                </time>
              </MetaRow>
            )}
          </dl>
        ) : (
          <p style={{ padding: '0.75rem', color: 'var(--color-text-muted)', fontSize: '0.85em' }}>
            No artifact data.
          </p>
        )}
      </section>

      {/* Delivery summary */}
      {deliverySummary && (
        <section
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
            Delivery
          </div>
          <div style={{ padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {deliverySummary.delivery_title && (
              <p
                style={{
                  fontWeight: 600,
                  fontSize: '0.9em',
                  margin: 0,
                  color: 'var(--color-text)',
                }}
              >
                {deliverySummary.delivery_title}
              </p>
            )}
            {deliverySummary.delivery_summary && (
              <p style={{ fontSize: '0.85em', margin: 0, color: 'var(--color-text-muted)' }}>
                {deliverySummary.delivery_summary}
              </p>
            )}
            {deliverySummary.usage_notes && (
              <p
                style={{
                  fontSize: '0.8em',
                  margin: 0,
                  color: 'var(--color-text-faint)',
                  fontStyle: 'italic',
                }}
              >
                {deliverySummary.usage_notes}
              </p>
            )}
          </div>
        </section>
      )}
    </aside>
  );
}

// ── helpers ──────────────────────────────────────────────────────────────────

function MetaRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '5rem 1fr',
        gap: '0.25rem',
        padding: '0.3rem 0',
        borderBottom: '1px solid var(--color-divider)',
        alignItems: 'start',
      }}
    >
      <dt
        style={{
          fontSize: '0.78em',
          color: 'var(--color-text-muted)',
          fontWeight: 500,
          paddingTop: '0.1rem',
        }}
      >
        {label}
      </dt>
      <dd style={{ margin: 0, fontSize: '0.85em' }}>{children}</dd>
    </div>
  );
}
