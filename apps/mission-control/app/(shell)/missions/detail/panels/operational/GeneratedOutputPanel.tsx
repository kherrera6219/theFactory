'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Panel } from '../../../../../components/panel';
import { getMissionBuildArtifact, missionApiUrl } from '../../../../../lib/api-client';
import { requestedLanguageFromPath } from '../../../../../lib/language';
import type { MissionBuildArtifactRecord } from '../../../../../lib/types';
import { copyToClipboard } from '../../../../../lib/clipboard';

interface GeneratedOutputPanelProps {
  missionId: string;
  generatedCodeArtifact: MissionBuildArtifactRecord | null;
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
  const [artifactDetail, setArtifactDetail] = useState<MissionBuildArtifactRecord | null>(null);
  const [artifactDetailError, setArtifactDetailError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setArtifactDetail(null);
    setArtifactDetailError(null);
    if (!generatedCodeArtifact || generatedCodeArtifact.artifact_text) return;

    void getMissionBuildArtifact(missionId, generatedCodeArtifact.artifact_id)
      .then((record) => {
        if (!cancelled) setArtifactDetail(record);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setArtifactDetailError(error instanceof Error ? error.message : 'Unable to load artifact content.');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [generatedCodeArtifact, missionId]);

  const effectiveArtifact = artifactDetail ?? generatedCodeArtifact;
  const filename = String(
    (effectiveArtifact?.manifest as { filename?: string } | undefined)?.filename ??
      effectiveArtifact?.artifact_id ??
      'output',
  );

  const language = useMemo(() => {
    const routingKey = (effectiveArtifact?.manifest as { language?: string } | undefined)?.language;
    if (routingKey) return routingKey;
    return requestedLanguageFromPath(filename) ?? 'text';
  }, [effectiveArtifact, filename]);

  const lineCount = effectiveArtifact?.artifact_text
    ? countLines(effectiveArtifact.artifact_text)
    : null;

  async function handleCopy() {
    if (!effectiveArtifact?.artifact_text) return;
    const success = await copyToClipboard(effectiveArtifact.artifact_text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  const headerActions = (
    <div className="inline-actions">
      {effectiveArtifact?.artifact_text && (
        <button
          type="button"
          className="secondary-button"
          onClick={() => void handleCopy()}
          aria-label="Copy generated code to clipboard"
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      )}
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
      <Link
        href={`/missions/output?id=${encodeURIComponent(missionId)}`}
        className="primary-button shell-link-button"
      >
        View Full Output
      </Link>
    </div>
  );

  return (
    <Panel title="Generated Output" actions={headerActions}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {!generatedCodeArtifact ? (
          <p className="muted" style={{ margin: '0.5rem 0 0' }}>No generated-code artifact recorded yet for this mission.</p>
        ) : (
          <>
            <div className="info-card">
              <h3>Generated code artifact</h3>
              <dl>
                <div>
                  <dt>Filename</dt>
                  <dd>{filename}</dd>
                </div>
                <div>
                  <dt>Storage</dt>
                  <dd>{generatedCodeArtifact.storage_backend}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{generatedCodeArtifact.status}</dd>
                </div>
                <div>
                  <dt>Digest</dt>
                  <dd className="mono-id">{generatedCodeArtifact.digest_sha256 ?? 'n/a'}</dd>
                </div>
                <div>
                  <dt>Size</dt>
                  <dd>{generatedCodeArtifact.size_bytes.toLocaleString()} bytes</dd>
                </div>
              </dl>
              <p className="muted" style={{ margin: 0 }}>
                This is a persisted build artifact from the mission database, not a file written into the repository checkout.
              </p>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.3rem 0.6rem',
                background: 'var(--color-surface-offset)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                marginTop: '0.2rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <span className="mono-id" style={{ fontSize: '0.8em', color: 'var(--color-text-muted)' }}>
                  {filename}
                </span>
                {lineCount !== null && (
                  <span
                    style={{
                      fontSize: '0.7em',
                      color: 'var(--color-text-faint)',
                      background: 'var(--color-surface-offset-2)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 'var(--radius-full)',
                      padding: '0.1rem 0.45rem',
                    }}
                  >
                    {lineCount.toLocaleString()} lines
                  </span>
                )}
              </div>
              <span
                style={{
                  fontSize: '0.7em',
                  color: 'var(--color-text-faint)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {language}
              </span>
            </div>

            {effectiveArtifact?.artifact_text ? (
              <SyntaxHighlighter
                language={language}
                style={vscDarkPlus}
                showLineNumbers
                wrapLongLines={false}
                customStyle={{
                  margin: 0,
                  borderRadius: '0 0 var(--radius-sm) var(--radius-sm)',
                  fontSize: '0.78em',
                  maxHeight: '420px',
                  overflowY: 'auto',
                  background: '#1e1e1e',
                }}
                lineNumberStyle={{
                  minWidth: '2.8em',
                  paddingRight: '0.8em',
                  color: '#555',
                  userSelect: 'none',
                }}
              >
                {effectiveArtifact.artifact_text}
              </SyntaxHighlighter>
            ) : (
              <p
                style={{
                  padding: '1rem',
                  color: 'var(--color-text-muted)',
                  fontStyle: 'italic',
                  background: '#1e1e1e',
                  margin: 0,
                  borderRadius: '0 0 var(--radius-sm) var(--radius-sm)',
                }}
              >
                {artifactDetailError ?? 'Artifact recorded. Loading stored text content from the artifact detail endpoint.'}
              </p>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}