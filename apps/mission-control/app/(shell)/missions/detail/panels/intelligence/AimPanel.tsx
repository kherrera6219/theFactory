'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import type { ApplicationIntelligenceMap } from '../../../../../lib/types';

interface AimPanelProps {
  applicationIntelligenceMap: ApplicationIntelligenceMap | null;
}

export function AimPanel({ applicationIntelligenceMap }: AimPanelProps) {
  if (!applicationIntelligenceMap) return null;

  return (
    <Panel title="Application Intelligence Map">
      <dl>
        <div>
          <dt>Primary language</dt>
          <dd>{applicationIntelligenceMap.primary_language ?? 'n/a'}</dd>
        </div>
        <div>
          <dt>Complexity</dt>
          <dd>{applicationIntelligenceMap.complexity_assessment}</dd>
        </div>
        <div>
          <dt>Functions</dt>
          <dd>{applicationIntelligenceMap.total_functions}</dd>
        </div>
        <div>
          <dt>Classes</dt>
          <dd>{applicationIntelligenceMap.total_classes}</dd>
        </div>
        <div>
          <dt>Files analyzed</dt>
          <dd>
            {applicationIntelligenceMap.extraction_summary?.files_analyzed ?? 0} /{' '}
            {applicationIntelligenceMap.extraction_summary?.files_seen ?? 0}
          </dd>
        </div>
        <div>
          <dt>Approval</dt>
          <dd>
            {applicationIntelligenceMap.human_approval_recommended
              ? 'recommended'
              : 'not recommended'}
          </dd>
        </div>
      </dl>
      <p>{applicationIntelligenceMap.repository_summary}</p>
      {applicationIntelligenceMap.detected_languages.length > 0 && (
        <>
          <p className="muted">Detected languages</p>
          <ul className="chip-list">
            {applicationIntelligenceMap.detected_languages.map((language) => (
              <li key={`aim-language-${language}`} className="chip-item">
                {language}
              </li>
            ))}
          </ul>
        </>
      )}
      {applicationIntelligenceMap.detected_dependencies.length > 0 && (
        <>
          <p className="muted">Detected dependencies</p>
          <ul className="chip-list">
            {applicationIntelligenceMap.detected_dependencies.slice(0, 16).map((dependency) => (
              <li key={`aim-dependency-${dependency}`} className="chip-item">
                {dependency}
              </li>
            ))}
          </ul>
        </>
      )}
      {applicationIntelligenceMap.risks.length > 0 && (
        <>
          <p className="muted">Risks</p>
          <ul className="summary-list">
            {applicationIntelligenceMap.risks.map((risk) => (
              <li key={`aim-risk-${risk}`}>
                <span>{risk}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {applicationIntelligenceMap.recommended_approach && (
        <p>{applicationIntelligenceMap.recommended_approach}</p>
      )}
    </Panel>
  );
}
