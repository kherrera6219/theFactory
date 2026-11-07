"use client";

import React, { useState, useEffect, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useArtifactData } from './hooks/useArtifactData';
import { OutputHeader } from './components/OutputHeader';
import { FileTreePane } from './components/FileTreePane';
import { CodeViewerPane } from './components/CodeViewerPane';
import { ArtifactMetaPane } from './components/ArtifactMetaPane';
import { SystemMessage } from '../../../components/status';
import { approveReviewArtifact } from '../../../lib/api-client';
import { copyToClipboard } from '../../../lib/clipboard';

/**
 * Full-page Output viewer — the dedicated IDE workspace for "show me what you built".
 *
 * Route: /missions/output?id={missionId}
 */
function OutputPageContent() {
  const searchParams = useSearchParams();
  const missionId = searchParams.get('id') ?? '';

  const {
    mission,
    chainTrace,
    generatedCodeArtifact,
    allArtifacts,
    virtualFiles,
    sourceFilesByPath,
    loading,
    error,
  } = useArtifactData(missionId);

  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedPath, setCopiedPath] = useState(false);

  const [accepted, setAccepted] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);

  useEffect(() => {
    if (!missionId) return;
    const key = `mission-control:accepted-delivery:${missionId}`;
    const stored = localStorage.getItem(key);
    setAccepted(!!stored);
  }, [missionId]);

  const handleAccept = useCallback(async () => {
    if (!missionId) return;
    setAccepting(true);
    setAcceptError(null);
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
      setAcceptError(err instanceof Error ? err.message : 'Unable to accept delivery.');
    } finally {
      setAccepting(false);
    }
  }, [missionId]);

  const activeArtifact =
    allArtifacts.find((a) => a.artifact_id === selectedArtifactId) ??
    generatedCodeArtifact ??
    allArtifacts[0] ??
    null;

  const activeVirtualFile =
    virtualFiles.find((f) => f.path === selectedFilePath) ??
    virtualFiles[0] ??
    null;

  const originalFileContent = activeVirtualFile
    ? sourceFilesByPath[activeVirtualFile.path] ?? sourceFilesByPath[activeVirtualFile.name] ?? null
    : null;

  const handleCopy = useCallback(async () => {
    const textToCopy = activeVirtualFile?.content ?? activeArtifact?.artifact_text;
    if (!textToCopy) return;
    const success = await copyToClipboard(textToCopy);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }, [activeVirtualFile, activeArtifact]);

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

  const showFileTree = virtualFiles.length > 1 || allArtifacts.length > 1;

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
        onAccept={() => void handleAccept()}
      />

      {acceptError && (
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <SystemMessage tone="critical" title="Delivery acceptance failed">
            <p>{acceptError}</p>
          </SystemMessage>
        </div>
      )}

      {/* File System Path Card */}
      <button
        type="button"
        onClick={() => void handleCopyPath()}
        style={{
          width: '100%',
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
          textAlign: 'left',
          fontFamily: 'inherit',
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
      </button>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: showFileTree ? '220px 1fr 260px' : '1fr 260px',
          gap: 'var(--space-4)',
          alignItems: 'start',
        }}
      >
        {showFileTree && (
          <FileTreePane
            artifacts={allArtifacts}
            selectedArtifactId={selectedArtifactId ?? activeArtifact?.artifact_id ?? null}
            onSelect={setSelectedArtifactId}
            virtualFiles={virtualFiles}
            selectedFilePath={activeVirtualFile?.path ?? null}
            onSelectFile={setSelectedFilePath}
          />
        )}

        <CodeViewerPane
          artifact={activeArtifact}
          loading={loading}
          activeFile={activeVirtualFile}
          originalFileContent={originalFileContent}
        />

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
