'use client';

import React, { useCallback, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useArtifactData } from './hooks/useArtifactData';
import { OutputHeader } from './components/OutputHeader';
import { FileTreePane } from './components/FileTreePane';
import { CodeViewerPane } from './components/CodeViewerPane';
import { ArtifactMetaPane } from './components/ArtifactMetaPane';

export default function MissionOutputPage() {
  const searchParams = useSearchParams();
  const missionId = searchParams.get('id') ?? '';

  const { mission, chainTrace, generatedCodeArtifact, allArtifacts, loading, error } =
    useArtifactData(missionId);

  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const activeArtifact = useMemo(() => {
    if (selectedArtifactId) {
      return allArtifacts.find((a) => a.artifact_id === selectedArtifactId) ?? generatedCodeArtifact;
    }
    return generatedCodeArtifact;
  }, [selectedArtifactId, allArtifacts, generatedCodeArtifact]);

  const handleCopy = useCallback(() => {
    const text = activeArtifact?.artifact_text;
    if (!text) return;
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [activeArtifact?.artifact_text]);

  const showFileTree = allArtifacts.length > 1;

  return (
    <div className="page shell-page">
      {error && <p className="error-box">{error}</p>}

      <OutputHeader
        missionId={missionId}
        mission={mission}
        generatedCodeArtifact={generatedCodeArtifact}
        onCopy={handleCopy}
        copied={copied}
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: showFileTree
            ? '220px 1fr minmax(260px, 320px)'
            : '1fr minmax(260px, 320px)',
          gap: '1rem',
          alignItems: 'start',
        }}
      >
        {showFileTree && (
          <div style={{ position: 'sticky', top: '1rem' }}>
            <FileTreePane
              artifacts={allArtifacts}
              selectedArtifactId={selectedArtifactId ?? generatedCodeArtifact?.artifact_id ?? null}
              onSelect={setSelectedArtifactId}
            />
          </div>
        )}

        <div style={{ minWidth: 0 }}>
          <CodeViewerPane artifact={activeArtifact} loading={loading} />
        </div>

        <div style={{ position: 'sticky', top: '1rem' }}>
          <ArtifactMetaPane artifact={activeArtifact} chainTrace={chainTrace} />
        </div>
      </div>
    </div>
  );
}
