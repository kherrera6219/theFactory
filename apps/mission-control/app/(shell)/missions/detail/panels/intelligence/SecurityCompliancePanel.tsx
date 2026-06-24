'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import type { SecurityComplianceReport } from '../../../../../lib/types';

interface SecurityCompliancePanelProps {
  securityComplianceReport: SecurityComplianceReport | null;
}

export function SecurityCompliancePanel({
  securityComplianceReport,
}: SecurityCompliancePanelProps) {
  if (!securityComplianceReport) return null;

  const allChecks = [
    ...(securityComplianceReport.security?.checks ?? []),
    ...(securityComplianceReport.compliance?.checks ?? []),
  ];

  return (
    <Panel title="Security and Compliance">
      <dl>
        <div>
          <dt>Status</dt>
          <dd>{securityComplianceReport.status}</dd>
        </div>
        <div>
          <dt>Passed</dt>
          <dd>{securityComplianceReport.passed ? 'yes' : 'no'}</dd>
        </div>
        <div>
          <dt>Blocking</dt>
          <dd>{securityComplianceReport.blocking ? 'yes' : 'no'}</dd>
        </div>
        <div>
          <dt>Risk</dt>
          <dd>{securityComplianceReport.risk_level}</dd>
        </div>
        <div>
          <dt>Enforcement</dt>
          <dd>{securityComplianceReport.enforcement_enabled ? 'enabled' : 'advisory'}</dd>
        </div>
        <div>
          <dt>Regulated context</dt>
          <dd>{securityComplianceReport.regulated_context ? 'yes' : 'no'}</dd>
        </div>
      </dl>
      {securityComplianceReport.findings.length > 0 && (
        <>
          <p className="muted">Findings</p>
          <ul className="summary-list">
            {securityComplianceReport.findings.map((finding) => (
              <li key={`security-compliance-finding-${finding}`}>
                <span>{finding}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {securityComplianceReport.recommendations.length > 0 && (
        <>
          <p className="muted">Recommendations</p>
          <ul className="summary-list">
            {securityComplianceReport.recommendations.map((recommendation) => (
              <li key={`security-compliance-recommendation-${recommendation}`}>
                <span>{recommendation}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {allChecks.length > 0 && (
        <ul className="card-list">
          {allChecks.map((check) => (
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
