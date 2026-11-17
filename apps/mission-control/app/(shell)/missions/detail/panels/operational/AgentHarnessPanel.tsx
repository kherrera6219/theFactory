"use client";

import React from "react";

export interface HarnessActivationEntry {
  agent_id?: string;
  stage?: string;
  status?: string;
  source?: string | null;
  turn_count?: number;
  tool_calls_count?: number;
  sandbox_runs_count?: number;
  duration_ms?: number;
  modified_files?: string[];
  escalations?: Array<{ escalation_id?: string; question?: string }>;
  user_questions?: Array<{ question_id?: string; question?: string; recommended_default?: string }>;
}

interface AgentHarnessPanelProps {
  activations: HarnessActivationEntry[];
}

export function AgentHarnessPanel({ activations }: AgentHarnessPanelProps) {
  const harnessRuns = activations.filter(
    (item) =>
      item.source === "agent_harness" ||
      typeof item.turn_count === "number" ||
      (Array.isArray(item.user_questions) && item.user_questions.length > 0) ||
      (Array.isArray(item.escalations) && item.escalations.length > 0),
  );

  if (harnessRuns.length === 0) {
    return null;
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2 className="card-title">Agent Harness Tool Runs &amp; Escalations</h2>
        <span className="badge">{harnessRuns.length} run(s)</span>
      </div>
      <div className="stack">
        {harnessRuns.map((run, idx) => {
          const modified = Array.isArray(run.modified_files) ? run.modified_files : [];
          const escalations = Array.isArray(run.escalations) ? run.escalations : [];
          const userQuestions = Array.isArray(run.user_questions) ? run.user_questions : [];
          return (
            <div key={`${run.agent_id ?? "agent"}-${run.stage ?? idx}`} className="panel-subtle">
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                <div>
                  <code>{run.agent_id ?? "unknown"}</code> · <span>{run.stage ?? "harness"}</span>
                </div>
                <div className="muted" style={{ fontSize: "0.85rem" }}>
                  status={run.status ?? "unknown"} · turns={run.turn_count ?? 0} · tools={run.tool_calls_count ?? 0} · sandbox={run.sandbox_runs_count ?? 0}
                </div>
              </div>
              {modified.length > 0 && (
                <div className="muted" style={{ fontSize: "0.85rem", marginTop: "0.35rem" }}>
                  Modified files: {modified.map((f) => <code key={f} style={{ marginRight: "0.4rem" }}>{f}</code>)}
                </div>
              )}
              {escalations.length > 0 && (
                <div style={{ marginTop: "0.4rem" }}>
                  <strong>PM Escalations:</strong>
                  <ul style={{ margin: "0.2rem 0 0 1.2rem" }}>
                    {escalations.map((esc, eIdx) => (
                      <li key={esc.escalation_id ?? eIdx}>{esc.question ?? "Escalated to PM"}</li>
                    ))}
                  </ul>
                </div>
              )}
              {userQuestions.length > 0 && (
                <div style={{ marginTop: "0.4rem" }}>
                  <strong>Operator Questions (<code>ask.user</code>):</strong>
                  <ul style={{ margin: "0.2rem 0 0 1.2rem" }}>
                    {userQuestions.map((uq, uIdx) => (
                      <li key={uq.question_id ?? uIdx}>
                        {uq.question ?? "Clarification requested"}
                        {uq.recommended_default ? ` (default: ${uq.recommended_default})` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
