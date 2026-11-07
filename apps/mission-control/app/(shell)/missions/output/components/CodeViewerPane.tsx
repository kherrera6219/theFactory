'use client';

import React, { useMemo, useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { computeLineDiff, type VirtualFileEntry } from '../../../../lib/file-tree';
import { requestedLanguageFromPath } from '../../../../lib/language';
import type { MissionBuildArtifactRecord } from '../../../../lib/types';

interface CodeViewerPaneProps {
  artifact: MissionBuildArtifactRecord | null;
  loading: boolean;
  activeFile?: VirtualFileEntry | null;
  originalFileContent?: string | null;
}

function countLines(text: string): number {
  if (!text) return 0;
  return text.split('\n').length;
}

/**
 * Full-page syntax-highlighted code viewer with per-file selection and
 * Brownfield Diff View toggle when original source content is available.
 */
export function CodeViewerPane({
  artifact,
  loading,
  activeFile = null,
  originalFileContent = null,
}: CodeViewerPaneProps) {
  const [viewMode, setViewMode] = useState<'code' | 'diff'>('code');

  const filename = String(
    activeFile?.path ??
      (artifact?.manifest as { filename?: string } | undefined)?.filename ??
      artifact?.artifact_id ??
      'output',
  );

  const codeText = activeFile?.content ?? artifact?.artifact_text ?? '';

  const language = useMemo(() => {
    if (activeFile?.language && activeFile.language !== 'text') {
      return activeFile.language;
    }
    const routingKey = (artifact?.manifest as { language?: string } | undefined)?.language;
    if (routingKey) return routingKey;
    return requestedLanguageFromPath(filename) ?? 'text';
  }, [activeFile, artifact, filename]);

  const lineCount = codeText ? countLines(codeText.trimEnd()) : null;
  const hasDiff = Boolean(
    originalFileContent &&
      codeText &&
      originalFileContent.trim() !== codeText.trim(),
  );

  const diffLines = useMemo(() => {
    if (!hasDiff || viewMode !== 'diff' || !originalFileContent) return [];
    return computeLineDiff(originalFileContent, codeText);
  }, [hasDiff, viewMode, originalFileContent, codeText]);

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
        <div
          style={{
            height: '2.25rem',
            background: 'var(--color-surface-offset)',
            borderBottom: '1px solid var(--color-border)',
          }}
        />
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
          gap: '0.75rem',
          flexWrap: 'wrap',
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          {hasDiff && (
            <div className="inline-actions" role="group" aria-label="View mode toggle">
              <button
                type="button"
                className={viewMode === 'code' ? 'primary-button' : 'secondary-button'}
                style={{ padding: '2px 8px', fontSize: '0.72rem', minHeight: '24px' }}
                onClick={() => setViewMode('code')}
              >
                Code
              </button>
              <button
                type="button"
                className={viewMode === 'diff' ? 'primary-button' : 'secondary-button'}
                style={{ padding: '2px 8px', fontSize: '0.72rem', minHeight: '24px' }}
                onClick={() => setViewMode('diff')}
              >
                Diff vs Source
              </button>
            </div>
          )}
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
      </div>

      {/* Code or Diff */}
      {codeText ? (
        viewMode === 'diff' && hasDiff ? (
          <pre
            style={{
              margin: 0,
              padding: '0.75rem',
              fontSize: '0.8em',
              maxHeight: 'calc(100vh - 14rem)',
              overflowY: 'auto',
              background: '#1e1e1e',
              fontFamily: 'var(--font-mono, monospace)',
            }}
          >
            {diffLines.map((entry, idx) => {
              const bg =
                entry.type === 'add'
                  ? 'rgba(16, 185, 129, 0.16)'
                  : entry.type === 'del'
                  ? 'rgba(239, 68, 68, 0.16)'
                  : 'transparent';
              const prefix = entry.type === 'add' ? '+' : entry.type === 'del' ? '-' : ' ';
              return (
                <div
                  key={idx}
                  style={{
                    background: bg,
                    padding: '1px 6px',
                    whiteSpace: 'pre',
                  }}
                >
                  <span style={{ color: '#6b7280', display: 'inline-block', width: '2.5em', userSelect: 'none' }}>
                    {entry.newLine ?? entry.oldLine ?? ''}
                  </span>
                  <span>{prefix} {entry.line}</span>
                </div>
              );
            })}
          </pre>
        ) : (
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
            {codeText}
          </SyntaxHighlighter>
        )
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
