'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import { formatDateTime } from '../../../../../lib/format';
import type { MissionBuildArtifactRecord } from '../../../../../lib/types';

interface DeliveryPanelProps {
  buildArtifacts: MissionBuildArtifactRecord[];
}

export function DeliveryPanel({ buildArtifacts }: DeliveryPanelProps) {
  return (
    <Panel title="Build Artifacts">
      {buildArtifacts.length === 0 && (
        <p className="muted">No build or package artifacts recorded for this mission yet.</p>
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
