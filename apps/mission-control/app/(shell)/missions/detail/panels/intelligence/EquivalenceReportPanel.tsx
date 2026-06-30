'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';

interface EquivalenceCheck {
  check_id: string;
  title: string;
  status: string;
  required: boolean;
  message: string;
}

interface EquivalenceReport {
  status: string;
  passed: boolean;
  blocking: boolean;
  risk_level: string;
  target_language?: string | null;
  enforcement_enabled: boolean;
  verification_scope?: string;
  findings: string[];
  checks: EquivalenceCheck[];
}

interface EquivalenceReportPanelProps {
  equivalenceReport: EquivalenceReport | null;
}

export function EquivalenceReportPanel({ equivalenceReport }: EquivalenceReportPanelProps) {
  if (!equivalenceReport) return null;

  return (
    <Panel title="Correctness Verification (Equivalence)">
      <p className="muted">
        Correctness checks: does the artifact match the contract (format,
        language, acceptance criteria)? This is separate from artifact integrity
        (digest/signature), which only attests the bytes are intact. A passing
        integrity check does not mean the artifact runs or meets the contract.
      </p>
      <dl>
        <div>
          <dt>Status</dt>
          <dd>{equivalenceReport.status}</dd>
        </div>
        <div>
          <dt>Passed</dt>
          <dd>{equivalenceReport.passed ? 'yes' : 'no'}</dd>
        </div>
        <div>
          <dt>Blocking</dt>
          <dd>{equivalenceReport.blocking ? 'yes' : 'no'}</dd>
        </div>
        <div>
          <dt>Risk</dt>
          <dd>{equivalenceReport.risk_level}</dd>
        </div>
        <div>
          <dt>Target language</dt>
          <dd>{equivalenceReport.target_language ?? 'n/a'}</dd>
        </div>
        <div>
          <dt>Enforcement</dt>
          <dd>{equivalenceReport.enforcement_enabled ? 'enabled' : 'advisory'}</dd>
        </div>
      </dl>
      {equivalenceReport.findings.length > 0 && (
        <>
          <p className="muted">Findings</p>
          <ul className="summary-list">
            {equivalenceReport.findings.map((finding) => (
              <li key={`equivalence-finding-${finding}`}>
                <span>{finding}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {equivalenceReport.checks.length > 0 && (
        <ul className="card-list">
          {equivalenceReport.checks.map((check) => (
            <li key={check.check_id} className="info-card">
              <h3>{check.title}</h3>
              <dl>
                <div>
                  <dt>Status</dt>
                  <dd>{check.status}</dd>
                </div>
                <div>
                  <dt>Required</dt>
                  <dd>{check.required ? 'yes' : 'no'}</dd>
                </div>
              </dl>
              <p>{check.message}</p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
