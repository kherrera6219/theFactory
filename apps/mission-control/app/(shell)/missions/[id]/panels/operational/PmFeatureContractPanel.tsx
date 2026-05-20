'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';

interface FeatureContract {
  title: string;
  source: string;
  estimated_complexity: string;
  human_approval_required: boolean;
  summary: string;
  acceptance_criteria: string[];
}

interface PmFeatureContractPanelProps {
  featureContract: FeatureContract | null;
}

export function PmFeatureContractPanel({ featureContract }: PmFeatureContractPanelProps) {
  return (
    <Panel title="PM Feature Contract">
      {!featureContract && <p className="muted">No PM feature contract recorded yet.</p>}
      {featureContract && (
        <>
          <dl>
            <div>
              <dt>Title</dt>
              <dd>{featureContract.title}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{featureContract.source}</dd>
            </div>
            <div>
              <dt>Complexity</dt>
              <dd>{featureContract.estimated_complexity}</dd>
            </div>
            <div>
              <dt>Approval</dt>
              <dd>{featureContract.human_approval_required ? 'required' : 'not required'}</dd>
            </div>
          </dl>
          <p>{featureContract.summary}</p>
          {featureContract.acceptance_criteria.length > 0 && (
            <ul className="summary-list">
              {featureContract.acceptance_criteria.map((criterion) => (
                <li key={`feature-criterion-${criterion}`}>
                  <span>{criterion}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Panel>
  );
}
