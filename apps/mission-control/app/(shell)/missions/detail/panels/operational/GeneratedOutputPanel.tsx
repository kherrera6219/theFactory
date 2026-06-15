'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Panel } from '../../../../../components/panel';
import { missionApiUrl } from '../../../../../lib/api-client';
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

/**
 * Artifacts tab summary card — shows a syntax-highlighted preview of the
 * generated code with copy-to-clipboard and a link to the full Output page.
 *
 * For the full-page viewer navigate to /missions/output?id={missionId}.
 */
export function GeneratedOutputPanel({
  missionId,
  generatedCodeArtifact,
}: GeneratedOutputPanelProps) {
  const [copied, setCopied] = useState(false);

  const filename = String(
    (generatedCodeArtifact?.manifest as { filename?: string } | undefined)?.filename ??
      generatedCodeArtifact?.artifact_id ??
      'output',
  );

  const language = useMemo(() => {
    const routingKey = (generatedCodeArtifact?.manifest as { language?: string } | undefined)
      ?.language;
    if (routingKey) return routingKey;
    return requestedLanguageFromPath(filename) ?? 'text';
  }, [generatedCodeArtifact, filename]);

  const lineCount = generatedCodeArtifact?.artifact_text
    ? countLines(generatedCodeArtifact.artifact_text)
    : null;

  async function handleCopy() {
    if (!generatedCodeArtifact?.artifact_text) return;
    const success = await copyToClipboard(generatedCodeArtifact.artifact_text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  const headerActions = (
    <div className="inline-actions">
      {generatedCodeArtifact?.artifact_text && (
        <button
          type="button"
          className="secondary-button"
          onClick={() => void handleCopy()}
          aria-label="Copy generated code to clipboard"
        >
          {copied ? '✓ Copied' : 'Copy'}
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
        View Full Output →
      </Link>
    </div>
  );

  return (
    <Panel title="Generated Output" actions={headerActions}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {/* File System Path Card */}
        <Link
          href={`/missions/output?id=${encodeURIComponent(missionId)}`}
          style={{
            padding: '0.4rem 0.8rem',
            background: 'var(--color-surface-offset)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.85em',
            color: 'var(--color-text-muted)',
            display: 'block',
            textDecoration: 'none',
            cursor: 'pointer',
            transition: 'background 120ms, border-color 120ms',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--color-surface-offset-2, #2d3748)';
            e.currentTarget.style.borderColor = '#4a5568';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--color-surface-offset)';
            e.currentTarget.style.borderColor = 'var(--color-border)';
          }}
        >
          📁 Exported locally to: <code className="mono-id" style={{ color: 'var(--color-primary-light, #38bdf8)', textDecoration: 'underline' }}>output/{missionId}/</code> <span style={{ float: 'right', fontSize: '0.9em', color: 'var(--color-primary-light, #38bdf8)' }}>Review Artifacts →</span>
        </Link>

        {!generatedCodeArtifact ? (
          <p className="muted" style={{ margin: '0.5rem 0 0' }}>No generated-code artifact recorded yet for this mission.</p>
        ) : (
          <>
            {/* Toolbar */}
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
                <span
                  className="mono-id"
                  style={{ fontSize: '0.8em', color: 'var(--color-text-muted)' }}
                >
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

            {/* Code viewer */}
            {generatedCodeArtifact.artifact_text ? (
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
                {generatedCodeArtifact.artifact_text}
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
                Artifact recorded — text content stored externally.
              </p>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}
