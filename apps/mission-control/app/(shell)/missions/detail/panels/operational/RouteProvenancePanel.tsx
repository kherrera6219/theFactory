'use client';

import React, { useMemo } from 'react';
import { Panel } from '../../../../../components/panel';
import type { MissionChainTrace } from '../../../../../lib/types';

interface RouteProvenancePanelProps {
  chainTrace: MissionChainTrace | null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0);
}

export function RouteProvenancePanel({ chainTrace }: RouteProvenancePanelProps) {
  const routeStages = useMemo(() => {
    const provenance = chainTrace?.route_provenance;
    if (!provenance) {
      return [];
    }
    return [
      { key: 'ceo', title: 'CEO Delegation', value: provenance.ceo ?? null },
      { key: 'pod_manager', title: 'Pod Manager Delegation', value: provenance.pod_manager ?? null },
      { key: 'specialist', title: 'Specialist Planning', value: provenance.specialist ?? null },
    ].filter((item) => item.value);
  }, [chainTrace]);

  const artifactEntries = useMemo(
    () => Object.entries(chainTrace?.artifact_summary ?? {}),
    [chainTrace],
  );

  return (
    <Panel title="Route Provenance">
      {!chainTrace?.route_provenance && <p className="muted">Route provenance not available yet.</p>}
      {chainTrace?.route_provenance && (
        <>
          <dl>
            <div>
              <dt>Fallback used</dt>
              <dd>{chainTrace.route_provenance.fallback_used ? 'yes' : 'no'}</dd>
            </div>
          </dl>
          {routeStages.length === 0 && <p className="muted">No delegation snapshots recorded yet.</p>}
          {routeStages.length > 0 && (
            <ul className="card-list">
              {routeStages.map((stage) => {
                const deliverables = asStringArray(stage.value?.deliverables);
                const riskNotes = asStringArray(stage.value?.risk_notes);
                return (
                  <li key={stage.key} className="info-card">
                    <h3>{stage.title}</h3>
                    <dl>
                      <div>
                        <dt>Source</dt>
                        <dd>{stage.value?.source ?? 'n/a'}</dd>
                      </div>
                      <div>
                        <dt>LLM route</dt>
                        <dd>{stage.value?.llm_route ?? 'n/a'}</dd>
                      </div>
                      <div>
                        <dt>Model</dt>
                        <dd>
                          {stage.value?.model_provider ?? 'n/a'} / {stage.value?.model ?? 'n/a'}
                        </dd>
                      </div>
                      {stage.value?.target_agent_id && (
                        <div>
                          <dt>Target agent</dt>
                          <dd>{stage.value.target_agent_id}</dd>
                        </div>
                      )}
                      {stage.value?.specialist_agent_id && (
                        <div>
                          <dt>Specialist</dt>
                          <dd>{stage.value.specialist_agent_id}</dd>
                        </div>
                      )}
                      {stage.value?.pod_manager_agent_id && (
                        <div>
                          <dt>Pod manager</dt>
                          <dd>{stage.value.pod_manager_agent_id}</dd>
                        </div>
                      )}
                    </dl>
                    {stage.value?.rationale && <p>{stage.value.rationale}</p>}
                    {stage.value?.plan_summary && <p>{stage.value.plan_summary}</p>}
                    {deliverables.length > 0 && (
                      <>
                        <p className="muted">Deliverables</p>
                        <ul className="summary-list">
                          {deliverables.map((item) => (
                            <li key={`${stage.key}-deliverable-${item}`}>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                    {riskNotes.length > 0 && (
                      <>
                        <p className="muted">Risk notes</p>
                        <ul className="summary-list">
                          {riskNotes.map((item) => (
                            <li key={`${stage.key}-risk-${item}`}>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {artifactEntries.length > 0 && (
            <>
              <p className="muted">Stage artifacts</p>
              <ul className="summary-list">
                {artifactEntries.map(([stage, artifact]) => (
                  <li key={stage}>
                    <strong>{stage}</strong>
                    <span>{String((artifact as Record<string, unknown>).event_type ?? 'artifact')}</span>
                    <span className="muted">{String((artifact as Record<string, unknown>).agent_id ?? 'unassigned')}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </Panel>
  );
}
