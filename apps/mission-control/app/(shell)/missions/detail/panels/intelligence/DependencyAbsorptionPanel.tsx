'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';

interface DependencyInventory {
  dependency_count: number;
  sources: string[];
  inventory_id: string;
}

interface PlannedReplacement {
  dependency_id: string;
  name: string;
  status: string;
  blocked_by: string[];
}

interface DependencyAbsorptionReport {
  status: string;
  blocking: boolean;
  safety_block_count: number;
  modified_output_created: boolean;
  equivalence_passed: boolean;
  security_compliance_passed: boolean;
  recommendations: string[];
  planned_replacements: PlannedReplacement[];
}

interface DependencyClassification {
  dependency_id: string;
  name: string;
  decision: string;
  risk_level: string;
  safety_blocked: boolean;
  blocking: boolean;
  rationale: string;
  source_refs: string[];
}

interface DependencyClassificationReport {
  classifications: DependencyClassification[];
}

interface DepabsSplice {
  library: string;
  status: string;
  reason?: string | null;
}

interface DepabsExecution {
  status: string;
  absorption_count: number;
  splices: DepabsSplice[];
}

interface SbomDelta {
  reduction_percent: number;
  original_dependency_count: number;
  removed: string[];
  remaining: string[];
}

interface DependencySurvivalJustification {
  justification_id: string;
  name: string;
  decision: string;
  rationale: string;
}

interface DependencyAbsorptionPanelProps {
  dependencyInventory: DependencyInventory | null;
  dependencyClassificationReport: DependencyClassificationReport | null;
  dependencyAbsorptionReport: DependencyAbsorptionReport | null;
  depabsExecution: DepabsExecution | null;
  sbomDelta: SbomDelta | null;
  dependencySurvivalJustifications: DependencySurvivalJustification[];
}

export function DependencyAbsorptionPanel({
  dependencyInventory,
  dependencyClassificationReport,
  dependencyAbsorptionReport,
  depabsExecution,
  sbomDelta,
  dependencySurvivalJustifications,
}: DependencyAbsorptionPanelProps) {
  if (!dependencyInventory && !dependencyClassificationReport && !dependencyAbsorptionReport) {
    return null;
  }

  return (
    <Panel title="Dependency Absorption">
      {dependencyInventory && (
        <dl>
          <div>
            <dt>Dependencies</dt>
            <dd>{dependencyInventory.dependency_count}</dd>
          </div>
          <div>
            <dt>Sources</dt>
            <dd>
              {dependencyInventory.sources.length > 0
                ? dependencyInventory.sources.join(', ')
                : 'none'}
            </dd>
          </div>
          <div>
            <dt>Inventory</dt>
            <dd>{dependencyInventory.inventory_id}</dd>
          </div>
        </dl>
      )}
      {dependencyAbsorptionReport && (
        <>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{dependencyAbsorptionReport.status}</dd>
            </div>
            <div>
              <dt>Blocking</dt>
              <dd>{dependencyAbsorptionReport.blocking ? 'yes' : 'no'}</dd>
            </div>
            <div>
              <dt>Safety blocks</dt>
              <dd>{dependencyAbsorptionReport.safety_block_count}</dd>
            </div>
            <div>
              <dt>Modified output</dt>
              <dd>{dependencyAbsorptionReport.modified_output_created ? 'yes' : 'no'}</dd>
            </div>
            <div>
              <dt>Equivalence</dt>
              <dd>{dependencyAbsorptionReport.equivalence_passed ? 'passed' : 'gated'}</dd>
            </div>
            <div>
              <dt>Security</dt>
              <dd>
                {dependencyAbsorptionReport.security_compliance_passed
                  ? 'passed'
                  : 'gated'}
              </dd>
            </div>
          </dl>
          {dependencyAbsorptionReport.recommendations.length > 0 && (
            <>
              <p className="muted">Recommendations</p>
              <ul className="summary-list">
                {dependencyAbsorptionReport.recommendations.map((recommendation) => (
                  <li key={`dependency-recommendation-${recommendation}`}>
                    <span>{recommendation}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
      {dependencyClassificationReport &&
        dependencyClassificationReport.classifications.length > 0 && (
          <ul className="card-list">
            {dependencyClassificationReport.classifications.map((dependency) => (
              <li key={dependency.dependency_id} className="info-card">
                <h3>{dependency.name}</h3>
                <dl>
                  <div>
                    <dt>Decision</dt>
                    <dd>{dependency.decision}</dd>
                  </div>
                  <div>
                    <dt>Risk</dt>
                    <dd>{dependency.risk_level}</dd>
                  </div>
                  <div>
                    <dt>Safety block</dt>
                    <dd>{dependency.safety_blocked ? 'yes' : 'no'}</dd>
                  </div>
                  <div>
                    <dt>Blocking</dt>
                    <dd>{dependency.blocking ? 'yes' : 'no'}</dd>
                  </div>
                </dl>
                <p>{dependency.rationale}</p>
                {dependency.source_refs.length > 0 && (
                  <p className="muted">{dependency.source_refs.join(', ')}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      {dependencyAbsorptionReport &&
        dependencyAbsorptionReport.planned_replacements.length > 0 && (
          <>
            <p className="muted">Planned replacements</p>
            <ul className="summary-list">
              {dependencyAbsorptionReport.planned_replacements.map((plan) => (
                <li key={`dependency-plan-${plan.dependency_id}`}>
                  <strong>{plan.name}</strong>
                  <span>{plan.status}</span>
                  {plan.blocked_by.length > 0 && (
                    <span className="muted">Gated by {plan.blocked_by.join(', ')}</span>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      {depabsExecution && (
        <>
          <p className="muted">DEPABS execution</p>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{depabsExecution.status}</dd>
            </div>
            <div>
              <dt>Absorbed</dt>
              <dd>{depabsExecution.absorption_count}</dd>
            </div>
          </dl>
          {depabsExecution.splices.length > 0 && (
            <ul className="summary-list">
              {depabsExecution.splices.map((splice) => (
                <li key={`depabs-splice-${splice.library}-${splice.status}`}>
                  <strong>{splice.library}</strong>
                  <span>{splice.status}</span>
                  {splice.reason && <span className="muted">{splice.reason}</span>}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {sbomDelta && (
        <>
          <p className="muted">SBOM delta</p>
          <dl>
            <div>
              <dt>Reduction</dt>
              <dd>{sbomDelta.reduction_percent}%</dd>
            </div>
            <div>
              <dt>Original</dt>
              <dd>{sbomDelta.original_dependency_count}</dd>
            </div>
            <div>
              <dt>Removed</dt>
              <dd>{sbomDelta.removed.length ? sbomDelta.removed.join(', ') : 'none'}</dd>
            </div>
            <div>
              <dt>Remaining</dt>
              <dd>
                {sbomDelta.remaining.length ? sbomDelta.remaining.join(', ') : 'none'}
              </dd>
            </div>
          </dl>
        </>
      )}
      {dependencySurvivalJustifications.length > 0 && (
        <>
          <p className="muted">Survival justifications</p>
          <ul className="summary-list">
            {dependencySurvivalJustifications.slice(0, 12).map((justification) => (
              <li key={justification.justification_id}>
                <strong>{justification.name}</strong>
                <span>{justification.decision}</span>
                <span className="muted">{justification.rationale}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}
