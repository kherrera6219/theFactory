'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';
import { formatDateTime } from '../../../../../lib/format';
import type { OperationsAuditReportRecord } from '../../../../../lib/types';

interface AuditEvidencePanelProps {
  auditReports: OperationsAuditReportRecord[];
}

export function AuditEvidencePanel({ auditReports }: AuditEvidencePanelProps) {
  return (
    <Panel title="Audit Evidence">
      {auditReports.length === 0 && (
        <p className="muted">No audit reports recorded for this mission yet.</p>
      )}
      {auditReports.length > 0 && (
        <ul className="card-list">
          {auditReports.map((report) => {
            const summary =
              typeof report.report.summary === 'string'
                ? report.report.summary
                : null;
            const findings =
              Array.isArray(report.report.findings) ? report.report.findings : [];
            const score =
              typeof report.report.score === 'number' ? report.report.score : null;
            return (
              <li key={report.audit_id} className="info-card">
                <h3>{report.audit_id}</h3>
                <dl>
                  <div>
                    <dt>Status</dt>
                    <dd>
                      <span
                        className={`connection-chip ${
                          report.status === 'PASSED'
                            ? 'live'
                            : report.status === 'FAILED'
                              ? 'stale'
                              : 'retrying'
                        }`}
                      >
                        {report.status}
                      </span>
                    </dd>
                  </div>
                  {score !== null && (
                    <div>
                      <dt>Score</dt>
                      <dd>{score}</dd>
                    </div>
                  )}
                  <div>
                    <dt>Recorded</dt>
                    <dd>{formatDateTime(report.created_at)}</dd>
                  </div>
                </dl>
                {summary && <p>{summary}</p>}
                {findings.length > 0 && (
                  <>
                    <p className="muted">Findings</p>
                    <ul className="summary-list">
                      {(findings as unknown[]).slice(0, 10).map((finding, idx) => (
                        <li key={`${report.audit_id}-finding-${idx}`}>
                          <span>
                            {typeof finding === 'string' ? finding : JSON.stringify(finding)}
                          </span>
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
    </Panel>
  );
}
