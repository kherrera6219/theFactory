'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Panel } from '../../../../../components/panel';
import {
  getMissionBuildArtifact,
  getMissionOutputFolderStatus,
  missionApiUrl,
  openMissionOutputFolder,
  openMissionOutputInVsCode,
  type MissionOutputFolderStatus,
} from '../../../../../lib/api-client';
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

function artifactSizeBytes(artifact: MissionBuildArtifactRecord | null): number | null {
  if (!artifact) return null;
  const sizeBytes = artifact.size_bytes;
  if (typeof sizeBytes === 'number') return sizeBytes;
  const legacyBytes = (artifact as { bytes?: unknown }).bytes;
  return typeof legacyBytes === 'number' ? legacyBytes : null;
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value.toLocaleString()} bytes`;
  const kb = value / 1024;
  if (kb < 1024) return `${kb.toFixed(kb >= 10 ? 0 : 1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(mb >= 10 ? 0 : 1)} MB`;
}

export function GeneratedOutputPanel({
  missionId,
  generatedCodeArtifact,
}: GeneratedOutputPanelProps) {
  const [copied, setCopied] = useState(false);
  const [artifactDetail, setArtifactDetail] = useState<MissionBuildArtifactRecord | null>(null);
  const [artifactDetailError, setArtifactDetailError] = useState<string | null>(null);
  const [openFolderStatus, setOpenFolderStatus] = useState<string | null>(null);
  const [outputFolder, setOutputFolder] = useState<MissionOutputFolderStatus | null>(null);
  const [outputFolderError, setOutputFolderError] = useState<string | null>(null);

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
  }, [missionId, generatedCodeArtifact?.updated_at]);

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
  const displaySizeBytes = artifactSizeBytes(generatedCodeArtifact);

  async function handleCopy() {
    if (!effectiveArtifact?.artifact_text) return;
    const success = await copyToClipboard(effectiveArtifact.artifact_text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

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
      {outputFolder?.path && (
        <button
          type="button"
          className="secondary-button"
          onClick={() => void handleCopyPath()}
          aria-label="Copy generated code output folder path"
        >
          Copy Path
        </button>
      )}
      {outputFolder?.canOpenFolder && (
        <button
          type="button"
          className="secondary-button"
          onClick={() => void handleOpenFolder()}
          aria-label="Open generated code output folder"
        >
          Open Folder
        </button>
      )}
      {outputFolder?.exists && (
        <button
          type="button"
          className="secondary-button"
          onClick={() => void handleOpenVsCode()}
          aria-label="Open generated code output folder in VS Code"
        >
          VS Code
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
        <div className="info-card output-folder-card">
          <h3>Mission output folder</h3>
          <dl>
            <div>
              <dt>Path</dt>
              <dd className="mono-id">{outputFolder?.path ?? 'Loading...'}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                {outputFolderError
                  ? outputFolderError
                  : outputFolder?.exists
                    ? `${outputFolder.fileCount.toLocaleString()} files, ${formatBytes(outputFolder.totalBytes)}`
                    : 'Folder not written yet'}
              </dd>
            </div>
            {outputFolder?.exists && outputFolder.files.length > 0 && (
              <div>
                <dt>Recent files</dt>
                <dd>
                  {outputFolder.files.slice(0, 5).map((file) => file.path).join(', ')}
                  {outputFolder.fileCount > 5 ? `, +${outputFolder.fileCount - 5} more` : ''}
                </dd>
              </div>
            )}
          </dl>
          {openFolderStatus && (
            <p className="muted mono-id" style={{ margin: '0 0 0.5rem' }}>
              {openFolderStatus}
            </p>
          )}
        </div>
        {!generatedCodeArtifact ? (
          <p className="muted" style={{ margin: '0.5rem 0 0' }}>
            No generated-code artifact recorded yet for this mission. The folder path above is where packaged output will appear when delivery succeeds.
          </p>
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
                  <dd>{displaySizeBytes === null ? 'n/a' : displaySizeBytes.toLocaleString() + ' bytes'}</dd>
                </div>
              </dl>
              <p className="muted" style={{ margin: 0 }}>
                This artifact is persisted in the mission database and mirrored to the mission output folder when packaging succeeds.
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
