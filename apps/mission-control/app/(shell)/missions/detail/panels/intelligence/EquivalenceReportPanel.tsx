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

interface BehaviouralVectorResult {
  fn_name?: string | null;
  case?: string | null;
  outcome: string;
  message: string;
}

interface BehaviouralReport {
  status: string;
  reason?: string | null;
  equivalence_vectors_passed: number;
  equivalence_vectors_total: number;
  equivalence_vectors_executed_without_error?: number;
  equivalence_vectors_failed?: number;
  equivalence_vectors_skipped?: number;
  findings?: string[];
  vector_results?: BehaviouralVectorResult[];
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
  behavioural?: BehaviouralReport | null;
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
      {equivalenceReport.behavioural ? (
        <BehaviouralSection behavioural={equivalenceReport.behavioural} />
      ) : null}
    </Panel>
  );
}

function BehaviouralSection({ behavioural }: { behavioural: BehaviouralReport }) {
  const total = behavioural.equivalence_vectors_total ?? 0;
  const passed = behavioural.equivalence_vectors_passed ?? 0;
  const ranClean = behavioural.equivalence_vectors_executed_without_error ?? 0;
  const failed = behavioural.equivalence_vectors_failed ?? 0;
  const skipped = behavioural.equivalence_vectors_skipped ?? 0;

  return (
    <section aria-labelledby="behavioural-equivalence-heading">
      <h3 id="behavioural-equivalence-heading">Behavioural Verification</h3>
      <p className="muted">
        A separate scope from the correctness checks above. Behavioural
        verification executes the artifact against generated input vectors in a
        sandbox and reports what actually happened. It is advisory — a
        behavioural failure does not block delivery while pass rates are still
        being measured.
      </p>
      {behavioural.status === 'skipped' ? (
        <p className="muted">
          Not executed{behavioural.reason ? `: ${behavioural.reason}` : '.'} This is
          not a pass — nothing was verified.
        </p>
      ) : (
        <>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{behavioural.status}</dd>
            </div>
            <div>
              <dt>Vectors passed</dt>
              <dd>
                {passed} / {total}
              </dd>
            </div>
            <div>
              <dt>Ran without error</dt>
              <dd>{ranClean}</dd>
            </div>
            <div>
              <dt>Failed</dt>
              <dd>{failed}</dd>
            </div>
            <div>
              <dt>Skipped</dt>
              <dd>{skipped}</dd>
            </div>
          </dl>
          <p className="muted">
            &ldquo;Passed&rdquo; counts only vectors with a recorded expected output that
            the artifact matched. &ldquo;Ran without error&rdquo; means the function
            executed on those inputs — evidence it runs, not evidence it is correct.
          </p>
          {behavioural.vector_results && behavioural.vector_results.length > 0 && (
            <ul className="summary-list">
              {behavioural.vector_results.map((result, index) => (
                <li key={`behavioural-vector-${result.fn_name ?? 'fn'}-${result.case ?? index}`}>
                  <span>
                    {result.outcome}: {result.message}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
