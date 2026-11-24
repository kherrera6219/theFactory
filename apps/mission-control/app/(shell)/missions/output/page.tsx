"use client";

import React, { useState, useEffect, useCallback, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useArtifactData } from './hooks/useArtifactData';
import { OutputHeader } from './components/OutputHeader';
import { FileTreePane } from './components/FileTreePane';
import { CodeViewerPane } from './components/CodeViewerPane';
import { ArtifactMetaPane } from './components/ArtifactMetaPane';
import { EmptyState, SystemMessage } from '../../../components/status';
import {
  approveReviewArtifact,
  getMissionOutputFolderStatus,
  type MissionOutputFolderStatus,
} from '../../../lib/api-client';
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
    workspaceTree,
    workspaceDiff,
    modifiedPaths,
    loadWorkspaceFile,
    loading,
    error,
  } = useArtifactData(missionId);

  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedPath, setCopiedPath] = useState(false);

  const [folderStatus, setFolderStatus] = useState<MissionOutputFolderStatus | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);

  // The real delivery folder (or none): this card used to print "output/<id>/"
  // whether or not anything had been written there.
  useEffect(() => {
    if (!missionId) return;
    let cancelled = false;
    getMissionOutputFolderStatus(missionId)
      .then((status) => {
        if (!cancelled) setFolderStatus(status);
      })
      .catch(() => {
        if (!cancelled) setFolderStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, [missionId]);

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
    (modifiedPaths.length > 0
      ? virtualFiles.find((f) => f.path === modifiedPaths[0])
      : undefined) ??
    virtualFiles[0] ??
    null;

  const handleSelectVirtualFile = useCallback(
    (filePath: string) => {
      setSelectedFilePath(filePath);
      if (workspaceTree?.workspace_id) {
        void loadWorkspaceFile(filePath);
      }
    },
    [workspaceTree?.workspace_id, loadWorkspaceFile],
  );

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
    if (!folderStatus?.exists) return;
    const success = await copyToClipboard(folderStatus.path);
    if (success) {
      setCopiedPath(true);
      setTimeout(() => setCopiedPath(false), 1500);
    }
  }, [folderStatus]);

  if (!missionId) {
    return (
      <div className="page shell-page">
        <EmptyState
          title="Choose a mission to view its output"
          action={
            <Link href="/missions/history" className="secondary-button shell-link-button">
              Open Mission History
            </Link>
          }
        >
          This page shows the code a mission generated. Open it from a mission&apos;s detail page,
          or pick one from Mission History.
        </EmptyState>
      </div>
    );
  }

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

      {/* File System Path Card — only when the delivery folder really exists */}
      {folderStatus?.exists ? (
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
          📁 Delivered to: <code className="mono-id" style={{ color: 'var(--color-primary-light, #38bdf8)' }}>{folderStatus.path}</code>
          {' '}({folderStatus.fileCount} file{folderStatus.fileCount === 1 ? '' : 's'})
        </span>
        <span style={{ fontSize: '0.85em', color: 'var(--color-primary-light, #38bdf8)' }}>
          {copiedPath ? '✓ Copied path' : 'Copy local path'}
        </span>
      </button>
      ) : null}

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
            onSelectFile={handleSelectVirtualFile}
            modifiedPaths={modifiedPaths}
          />
        )}

        <CodeViewerPane
          artifact={activeArtifact}
          loading={loading}
          activeFile={activeVirtualFile}
          originalFileContent={originalFileContent}
          workspaceDiffText={workspaceDiff?.diff ?? null}
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
