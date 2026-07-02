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
import type { MissionBuildArtifactRecord } from '../../../../../lib/types';
import { copyToClipboard } from '../../../../../lib/clipboard';

interface DeliveryPanelProps {
  missionId: string;
  buildArtifacts: MissionBuildArtifactRecord[];
}

export function DeliveryPanel({ missionId, buildArtifacts }: DeliveryPanelProps) {
  const [openFolderStatus, setOpenFolderStatus] = useState<string | null>(null);
  const [outputFolder, setOutputFolder] = useState<MissionOutputFolderStatus | null>(null);
  const [outputFolderError, setOutputFolderError] = useState<string | null>(null);

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
  }, [missionId, buildArtifacts.length]);

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
