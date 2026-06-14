'use client';

import React, { useState, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { useArtifactData } from './hooks/useArtifactData';
import { OutputHeader } from './components/OutputHeader';
import { FileTreePane } from './components/FileTreePane';
import { CodeViewerPane } from './components/CodeViewerPane';
import { ArtifactMetaPane } from './components/ArtifactMetaPane';

/**
 * Full-page Output viewer — the dedicated destination for "show me what you built".
 *
 * Route: /missions/output?id={missionId}
 * (Flat query-param pattern matching /missions/detail — no [id] dynamic segment.)
 *
 * Layout:
 *   Desktop: [FileTree (if >1 file)] | [CodeViewer] | [ArtifactMeta]
 *   Mobile:  stacked single column
 *
 * No new API endpoints. All data comes from getMissionChainTrace which already
 * returns build_artifacts, generated_output, and delivery_summary.
 */
export default function OutputPage() {
  const searchParams = useSearchParams();
  const missionId = searchParams.get('id') ?? '';

  const { mission, chainTrace, generatedCodeArtifact, allArtifacts, loading, error } =
    useArtifactData(missionId);

  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Active artifact: explicit selection → generated_code → first artifact → null
  const activeArtifact =
    allArtifacts.find((a) => a.artifact_id === selectedArtifactId) ??
    generatedCodeArtifact ??
    allArtifacts[0] ??
    null;

  const handleCopy = useCallback(async () => {
    if (!activeArtifact?.artifact_text) return;
    await navigator.clipboard.writeText(activeArtifact.artifact_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [activeArtifact]);

  if (error) {
    return (
      <div className="panel-error-state" role="alert">
        <p>{error}</p>
      </div>
    );
  }

  const showFileTree = allArtifacts.length > 1;

  return (
    <div
      style={{
        padding: 'var(--space-6)',
        maxWidth: 'var(--content-wide)',
        margin: '0 auto',
      }}
    >
      <OutputHeader
        missionId={missionId}
        mission={mission}
        generatedCodeArtifact={activeArtifact}
        onCopy={() => void handleCopy()}
        copied={copied}
      />

      {/* File System Path Card */}
      <div
        style={{
          padding: '0.5rem 1rem',
          background: 'var(--color-surface-offset)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)',
          fontSize: 'var(--text-sm, 0.875rem)',
          color: 'var(--color-text-muted)',
          marginBottom: 'var(--space-4)',
        }}
      >
        📁 Exported locally to: <code className="mono-id" style={{ color: 'var(--color-primary-light, #38bdf8)' }}>output/{missionId}/</code>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: showFileTree ? '200px 1fr 260px' : '1fr 260px',
          gap: 'var(--space-4)',
          alignItems: 'start',
        }}
      >
        {showFileTree && (
          <FileTreePane
            artifacts={allArtifacts}
            selectedArtifactId={selectedArtifactId ?? activeArtifact?.artifact_id ?? null}
            onSelect={setSelectedArtifactId}
          />
        )}

        <CodeViewerPane artifact={activeArtifact} loading={loading} />

        <ArtifactMetaPane artifact={activeArtifact} chainTrace={chainTrace} />
      </div>
    </div>
  );
}
