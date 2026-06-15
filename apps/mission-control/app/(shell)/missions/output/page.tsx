"use client";

import React, { useState, useEffect, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useArtifactData } from './hooks/useArtifactData';
import { OutputHeader } from './components/OutputHeader';
import { FileTreePane } from './components/FileTreePane';
import { CodeViewerPane } from './components/CodeViewerPane';
import { ArtifactMetaPane } from './components/ArtifactMetaPane';
import { approveReviewArtifact } from '../../../lib/api-client';
import { copyToClipboard } from '../../../lib/clipboard';

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
function OutputPageContent() {
  const searchParams = useSearchParams();
  const missionId = searchParams.get('id') ?? '';

  const { mission, chainTrace, generatedCodeArtifact, allArtifacts, loading, error } =
    useArtifactData(missionId);

  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedPath, setCopiedPath] = useState(false);

  const [accepted, setAccepted] = useState(false);
  const [accepting, setAccepting] = useState(false);

  useEffect(() => {
    if (!missionId) return;
    const key = `mission-control:accepted-delivery:${missionId}`;
    const stored = localStorage.getItem(key);
    setAccepted(!!stored);
  }, [missionId]);

  const handleAccept = useCallback(async () => {
    if (!missionId) return;
    setAccepting(true);
    try {
      const receipt = await approveReviewArtifact({
        scope: 'delivery',
        fingerprint: missionId,
        summary: `Accepted code delivery for mission ${missionId}.`,
        metadata: {
          mission_id: missionId,
          accepted_at: new Date().toISOString(),
        },
      });
      const key = `mission-control:accepted-delivery:${missionId}`;
      localStorage.setItem(key, JSON.stringify(receipt));
      setAccepted(true);
    } catch (err) {
      console.error('Failed to accept code delivery:', err);
      alert(err instanceof Error ? err.message : 'Unable to accept delivery.');
    } finally {
      setAccepting(false);
    }
  }, [missionId]);

  // Active artifact: explicit selection → generated_code → first artifact → null
  const activeArtifact =
    allArtifacts.find((a) => a.artifact_id === selectedArtifactId) ??
    generatedCodeArtifact ??
    allArtifacts[0] ??
    null;

  const handleCopy = useCallback(async () => {
    if (!activeArtifact?.artifact_text) return;
    const success = await copyToClipboard(activeArtifact.artifact_text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }, [activeArtifact]);

  const handleCopyPath = useCallback(async () => {
    const success = await copyToClipboard(`output/${missionId}/`);
    if (success) {
      setCopiedPath(true);
      setTimeout(() => setCopiedPath(false), 1500);
    }
  }, [missionId]);

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
        accepted={accepted}
        accepting={accepting}
        onAccept={handleAccept}
      />

      {/* File System Path Card */}
      <div
        onClick={() => void handleCopyPath()}
        style={{
          padding: '0.5rem 1rem',
          background: 'var(--color-surface-offset)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)',
          fontSize: 'var(--text-sm, 0.875rem)',
          color: 'var(--color-text-muted)',
          marginBottom: 'var(--space-4)',
          cursor: 'pointer',
          transition: 'background 120ms, border-color 120ms',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
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
        <span>
          📁 Exported locally to: <code className="mono-id" style={{ color: 'var(--color-primary-light, #38bdf8)', textDecoration: 'underline' }}>output/{missionId}/</code>
        </span>
        <span style={{ fontSize: '0.85em', color: 'var(--color-primary-light, #38bdf8)' }}>
          {copiedPath ? '✓ Copied path' : 'Copy local path'}
        </span>
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

export default function OutputPage() {
  return (
    <Suspense fallback={<div className="panel-loading-state"><p>Loading output viewer...</p></div>}>
      <OutputPageContent />
    </Suspense>
  );
}
