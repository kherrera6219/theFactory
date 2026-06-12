'use client';

import React, { useMemo } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { requestedLanguageFromPath } from '../../../../lib/language';
import type { MissionBuildArtifactRecord } from '../../../../lib/types';

interface CodeViewerPaneProps {
  artifact: MissionBuildArtifactRecord | null;
  loading: boolean;
}

function countLines(text: string): number {
  if (!text) return 0;
  return text.split('\n').length;
}

/**
 * Full-page syntax-highlighted code viewer.
 *
 * Language detection order:
 *  1. chainTrace.generated_output.language (routing key from the factory)
 *  2. manifest.filename extension via requestedLanguageFromPath()
 *  3. Falls back to plain text
 *
 * Uses react-syntax-highlighter Prism build with vscDarkPlus to match
 * the existing dark-mode operator console aesthetic.
 */
export function CodeViewerPane({ artifact, loading }: CodeViewerPaneProps) {
  const filename = String(
    (artifact?.manifest as { filename?: string } | undefined)?.filename ??
      artifact?.artifact_id ??
      'output',
  );

  const language = useMemo(() => {
    // Prefer the language routing key already set by the factory pipeline
    const routingKey = (artifact?.manifest as { language?: string } | undefined)?.language;
    if (routingKey) return routingKey;
    // Fall back to extension-based detection
    return requestedLanguageFromPath(filename) ?? 'text';
  }, [artifact, filename]);

  const lineCount = artifact?.artifact_text ? countLines(artifact.artifact_text) : null;

  if (loading) {
    return (
      <div
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
          overflow: 'hidden',
        }}
      >
        {/* Toolbar skeleton */}
        <div
          style={{
            height: '2.25rem',
            background: 'var(--color-surface-offset)',
            borderBottom: '1px solid var(--color-border)',
          }}
        />
        {/* Code area skeleton */}
        <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {Array.from({ length: 18 }).map((_, i) => (
            <div
              key={i}
              className="skeleton skeleton-text"
              style={{ width: `${55 + ((i * 17) % 40)}%` }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (!artifact) {
    return (
      <div
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
          padding: '3rem',
          textAlign: 'center',
          color: 'var(--color-text-muted)',
        }}
      >
        <p>No generated-code artifact recorded for this mission.</p>
      </div>
    );
  }

  return (
    <div
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
      }}
    >
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.35rem 0.75rem',
          borderBottom: '1px solid var(--color-border)',
          background: 'var(--color-surface-offset)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span
            className="mono-id"
            style={{ fontSize: '0.82em', color: 'var(--color-text-muted)' }}
          >
            {filename}
          </span>
          {lineCount !== null && (
            <span
              style={{
                fontSize: '0.72em',
                color: 'var(--color-text-faint)',
                background: 'var(--color-surface-offset-2)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-full)',
                padding: '0.1rem 0.5rem',
              }}
            >
              {lineCount.toLocaleString()} lines
            </span>
          )}
        </div>
        <span
          style={{
            fontSize: '0.72em',
            color: 'var(--color-text-faint)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          {language}
        </span>
      </div>

      {/* Code */}
      {artifact.artifact_text ? (
        <SyntaxHighlighter
          language={language}
          style={vscDarkPlus}
          showLineNumbers
          wrapLongLines={false}
          customStyle={{
            margin: 0,
            borderRadius: 0,
            fontSize: '0.82em',
            maxHeight: 'calc(100vh - 14rem)',
            overflowY: 'auto',
            background: '#1e1e1e',
          }}
          lineNumberStyle={{
            minWidth: '3em',
            paddingRight: '1em',
            color: '#555',
            userSelect: 'none',
          }}
        >
          {artifact.artifact_text}
        </SyntaxHighlighter>
      ) : (
        <div
          style={{
            padding: '2rem',
            color: 'var(--color-text-muted)',
            fontStyle: 'italic',
            textAlign: 'center',
          }}
        >
          Artifact recorded but text content is not available (stored externally).
        </div>
      )}
    </div>
  );
}
