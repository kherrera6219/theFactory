'use client';

import React from 'react';
import { Panel } from '../../../../../components/panel';

interface QcAssessment {
  qc_verdict: string;
  deployment_safe: boolean;
  findings: string[];
}

interface RuntimeQcReport {
  verdict?: string;
  execution_type?: string;
  stdout_preview?: string | null;
  qc_assessment?: QcAssessment | null;
  skipped?: boolean;
  reason?: string | null;
  deployment_safe?: boolean | null;
}

interface TestDataManifest {
  base_image: string;
  test_framework: string;
  run_command: string;
  timeout_seconds: number;
  memory_limit_mb: number;
  synthetic_inputs: unknown[];
}

interface RuntimeQcPanelProps {
  runtimeQcReport: RuntimeQcReport | null;
  testdataManifest: TestDataManifest | null;
}

export function RuntimeQcPanel({ runtimeQcReport, testdataManifest }: RuntimeQcPanelProps) {
  if (!runtimeQcReport && !testdataManifest) return null;

  const skipped = Boolean(runtimeQcReport?.skipped);
  const deploymentSafe = runtimeQcReport?.qc_assessment?.deployment_safe ?? runtimeQcReport?.deployment_safe;

  return (
    <Panel title="Runtime QC">
      {runtimeQcReport && (
        <>
          {skipped && (
            <p className="warning-box" style={{ marginTop: 0 }}>
              Runtime QC was skipped: {runtimeQcReport.reason ?? 'not configured for this mission'}.
            </p>
          )}
          <dl>
            <div>
              <dt>Execution</dt>
              <dd>{runtimeQcReport.verdict ?? (skipped ? 'SKIPPED' : 'pending')}</dd>
            </div>
            <div>
              <dt>QC verdict</dt>
              <dd>{runtimeQcReport.qc_assessment?.qc_verdict ?? (skipped ? 'not run' : 'pending')}</dd>
            </div>
            <div>
              <dt>Execution type</dt>
              <dd>{runtimeQcReport.execution_type ?? (skipped ? 'not_run' : 'pending')}</dd>
            </div>
            <div>
              <dt>Deployment safe</dt>
              <dd>{deploymentSafe === null || deploymentSafe === undefined ? 'not assessed' : deploymentSafe ? 'yes' : 'no'}</dd>
            </div>
          </dl>
          {runtimeQcReport.stdout_preview && (
            <pre className="code-preview">{runtimeQcReport.stdout_preview}</pre>
          )}
          {(runtimeQcReport.qc_assessment?.findings ?? []).length > 0 && (
            <ul className="summary-list">
              {runtimeQcReport.qc_assessment?.findings.map((finding) => (
                <li key={`runtime-qc-finding-${finding}`}>
                  <span>{finding}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {testdataManifest && (
        <>
          <p className="muted">Test environment</p>
          <dl>
            <div>
              <dt>Base image</dt>
              <dd>{testdataManifest.base_image}</dd>
            </div>
            <div>
              <dt>Framework</dt>
              <dd>{testdataManifest.test_framework}</dd>
            </div>
            <div>
              <dt>Run command</dt>
              <dd>{testdataManifest.run_command}</dd>
            </div>
            <div>
              <dt>Limits</dt>
              <dd>
                {testdataManifest.timeout_seconds}s / {testdataManifest.memory_limit_mb}MB
              </dd>
            </div>
            <div>
              <dt>Synthetic inputs</dt>
              <dd>{testdataManifest.synthetic_inputs.length}</dd>
            </div>
          </dl>
        </>
      )}
    </Panel>
  );
}