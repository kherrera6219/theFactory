'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import { missionApiUrl } from '../../../../../lib/api-client';
import type { MissionBuildArtifactRecord } from '../../../../../lib/types';

interface GeneratedOutputPanelProps {
  missionId: string;
  generatedCodeArtifact: MissionBuildArtifactRecord | null;
}

export function GeneratedOutputPanel({
  missionId,
  generatedCodeArtifact,
}: GeneratedOutputPanelProps) {
  return (
    <Panel title="Generated Output">
      {!generatedCodeArtifact && <p className="muted">No generated-code artifact recorded yet.</p>}
      {generatedCodeArtifact && (
        <>
          <dl>
            <div>
              <dt>File</dt>
              <dd>
                {String(
                  (generatedCodeArtifact.manifest as { filename?: string } | undefined)?.filename ??
                    generatedCodeArtifact.artifact_id
                )}
              </dd>
            </div>
            <div>
              <dt>Digest</dt>
              <dd>{generatedCodeArtifact.digest_sha256 ?? 'n/a'}</dd>
            </div>
            <div>
              <dt>Size</dt>
              <dd>{generatedCodeArtifact.size_bytes} bytes</dd>
            </div>
          </dl>
          <div className="inline-actions">
            <a
              className="secondary-button shell-link-button"
              href={missionApiUrl(
                `/v1/missions/${encodeURIComponent(missionId)}/artifact?artifact_type=generated_code`
              )}
            >
              Download Generated Code
            </a>
          </div>
          {generatedCodeArtifact.artifact_text && (
            <div className="code-block">
              <pre>{generatedCodeArtifact.artifact_text}</pre>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
