'use client';

import React, { useEffect, useState } from 'react';
import { Panel } from '../../../../../components/panel';
import { formatDateTime } from '../../../../../lib/format';
import {
  getMissionOutputFolderStatus,
  openMissionOutputFolder,
  openMissionOutputInVsCode,
  type MissionOutputFolderStatus,
} from '../../../../../lib/api-client';
import type {
  MissionBuildArtifactRecord,
  MissionSlicePlanItem,
} from '../../../../../lib/types';
import {
  buildSliceTimelineItems,
  extractGithubPrResult,
  extractMigrationNotes,
} from '../../../../../lib/slice-delivery';
import { copyToClipboard } from '../../../../../lib/clipboard';

interface DeliveryPanelProps {
  missionId: string;
  buildArtifacts: MissionBuildArtifactRecord[];
  missionMetadata?: Record<string, unknown> | null;
  plannedSlices?: MissionSlicePlanItem[] | null;
}

export function DeliveryPanel({
  missionId,
  buildArtifacts,
  missionMetadata = null,
  plannedSlices = null,
}: DeliveryPanelProps) {
  const [openFolderStatus, setOpenFolderStatus] = useState<string | null>(null);
  const [outputFolder, setOutputFolder] = useState<MissionOutputFolderStatus | null>(null);
  const [outputFolderError, setOutputFolderError] = useState<string | null>(null);
  const [expandedSliceId, setExpandedSliceId] = useState<string | null>(null);

  const sliceTimeline = buildSliceTimelineItems(missionMetadata, plannedSlices);
  const migrationNotes = extractMigrationNotes(missionMetadata);
  const githubPr = extractGithubPrResult(missionMetadata);

  function handleDownloadMigrationNotes() {
    if (!migrationNotes || typeof window === 'undefined') return;
    const blob = new Blob([migrationNotes], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'MIGRATION_NOTES.md';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  // Refetch whenever the newest artifact's timestamp changes, not just when the
  // count changes — an existing artifact transitioning e.g. packaging -> complete
  // (exactly when the output folder gets written to disk) keeps the same array
  // length, so length alone misses it.
  const latestBuildArtifactUpdatedAt = buildArtifacts.reduce<string | undefined>(
    (latest, artifact) => (!latest || artifact.updated_at > latest ? artifact.updated_at : latest),
    undefined,
  );

  useEffect(() => {
    let cancelled = false;
    setOutputFolder(null);
    setOutputFolderError(null);

    void getMissionOutputFolderStatus(missionId)
      .then((status) => {
        if (!cancelled) setOutputFolder(status);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setOutputFolderError(error instanceof Error ? error.message : 'Unable to read output folder status.');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [missionId, buildArtifacts.length, latestBuildArtifactUpdatedAt]);

  async function handleCopyPath() {
    if (!outputFolder?.path) return;
    const success = await copyToClipboard(outputFolder.path);
    if (success) {
      setOpenFolderStatus('Copied output folder path.');
    }
  }

  async function handleOpenFolder() {
    setOpenFolderStatus(null);
    try {
      const result = await openMissionOutputFolder(missionId);
      setOpenFolderStatus(result.path ? `Opened ${result.path}` : 'Opened output folder.');
    } catch (error) {
      setOpenFolderStatus(error instanceof Error ? error.message : 'Unable to open output folder.');
    }
  }

  async function handleOpenVsCode() {
    setOpenFolderStatus(null);
    try {
      const result = await openMissionOutputInVsCode(missionId);
      setOpenFolderStatus(result.path ? `Opened ${result.path} in VS Code.` : 'Opened output folder in VS Code.');
    } catch (error) {
      setOpenFolderStatus(error instanceof Error ? error.message : 'Unable to open output folder in VS Code.');
    }
  }

  return (
    <Panel
      title="Build Artifacts"
      actions={
        <div className="inline-actions">
          {outputFolder?.path && (
            <button
              type="button"
              className="secondary-button"
              onClick={() => void handleCopyPath()}
            >
              Copy Path
            </button>
          )}
          {outputFolder?.canOpenFolder && (
            <button
              type="button"
              className="secondary-button"
              onClick={() => void handleOpenFolder()}
            >
              Open Folder
            </button>
          )}
          {outputFolder?.exists && (
            <button
              type="button"
              className="secondary-button"
              onClick={() => void handleOpenVsCode()}
            >
              VS Code
            </button>
          )}
        </div>
      }
    >
      {buildArtifacts.length === 0 && (
        <p className="muted">No build or package artifacts recorded for this mission yet.</p>
      )}
      <div className="info-card output-folder-card">
        <h3>Output location</h3>
        <dl>
          <div>
            <dt>Path</dt>
            <dd className="mono-id">{outputFolder?.path ?? 'Loading...'}</dd>
          </div>
          <div>
            <dt>Folder</dt>
            <dd>
              {outputFolderError
                ? outputFolderError
                : outputFolder?.exists
                  ? `${outputFolder.fileCount.toLocaleString()} files`
                  : 'Not written yet'}
            </dd>
          </div>
        </dl>
      </div>
      {openFolderStatus && (
        <p className="muted mono-id" style={{ marginTop: 0 }}>
          {openFolderStatus}
        </p>
      )}
      {sliceTimeline.length > 0 && (
        <div className="info-card" style={{ marginBottom: '0.75rem' }}>
          <h3>Slice Execution Timeline ({sliceTimeline.length})</h3>
          <ul className="card-list">
            {sliceTimeline.map((slice) => (
              <li key={slice.id} className="info-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                  <span>
                    <strong className="mono-id">{slice.id}</strong> — {slice.title}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="status-badge">
                      {slice.verdict ?? slice.status.toUpperCase()}
                    </span>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() =>
                        setExpandedSliceId(expandedSliceId === slice.id ? null : slice.id)
                      }
                    >
                      {expandedSliceId === slice.id ? 'Hide Files' : 'Inspect'}
                    </button>
                  </div>
                </div>
                {slice.commitSha && (
                  <p className="muted mono-id" style={{ marginTop: '0.25rem', marginBottom: 0 }}>
                    Commit: {slice.commitSha.slice(0, 12)}
                  </p>
                )}
                {expandedSliceId === slice.id && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <p className="muted" style={{ marginBottom: '0.25rem' }}>
                      Files ({slice.files.length}):
                    </p>
                    <p className="mono-id" style={{ margin: 0 }}>
                      {slice.files.join(', ') || 'None recorded'}
                    </p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {githubPr && (githubPr.pr_url || githubPr.reason) && (
        <div className="info-card" style={{ marginBottom: '0.75rem' }}>
          <h3>GitHub Pull Request Delivery</h3>
          {githubPr.pr_url ? (
            <p style={{ margin: 0 }}>
              PR #{githubPr.pr_number ?? 'created'} on{' '}
              <span className="mono-id">{githubPr.repo}</span>:{' '}
              <a href={githubPr.pr_url} target="_blank" rel="noreferrer">
                {githubPr.pr_url}
              </a>
            </p>
          ) : (
            <p className="muted" style={{ margin: 0 }}>
              Status: {githubPr.status ?? 'skipped'} ({githubPr.reason})
            </p>
          )}
        </div>
      )}
      {migrationNotes && (
        <div className="info-card" style={{ marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Migration Notes (MIGRATION_NOTES.md)</h3>
            <button
              type="button"
              className="secondary-button"
              onClick={handleDownloadMigrationNotes}
            >
              Download MIGRATION_NOTES.md
            </button>
          </div>
          <pre
            className="mono-id"
            style={{
              maxHeight: '14rem',
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
              marginTop: '0.5rem',
            }}
          >
            {migrationNotes}
          </pre>
        </div>
      )}
      {buildArtifacts.length > 0 && (
        <ul className="card-list">
          {buildArtifacts.map((artifact) => (
            <li key={artifact.artifact_id} className="info-card">
              <h3>{artifact.artifact_type}</h3>
              <dl>
                <div>
                  <dt>Status</dt>
                  <dd>{artifact.status}</dd>
                </div>
                <div>
                  <dt>Stage</dt>
                  <dd>{artifact.stage}</dd>
                </div>
                <div>
                  <dt>Storage</dt>
                  <dd>{artifact.storage_backend}</dd>
                </div>
                <div>
                  <dt>Digest</dt>
                  <dd>{artifact.digest_sha256 ?? 'n/a'}</dd>
                </div>
                <div>
                  <dt>Size</dt>
                  <dd>{artifact.size_bytes} bytes</dd>
                </div>
                <div>
                  <dt>Updated</dt>
                  <dd>{formatDateTime(artifact.updated_at)}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
