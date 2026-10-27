"use client";

import { useState } from "react";
import { Panel } from "../../../components/panel";
import { EmptyState, SystemMessage } from "../../../components/status";
import { sanitizeUserText } from "../../../lib/security";
import { contractSourceLabel, isDegradedContract } from "../chat-helpers";
import type { ContinuationContext, DisplayFeatureContract } from "../chat-types";

export interface ChatSowSectionProps {
  contract: DisplayFeatureContract | null;
  hasClarificationPrompt: boolean;
  continuationContext: ContinuationContext | null;
  launching: boolean;
  confirmAndLaunch: (contractOverride?: DisplayFeatureContract) => Promise<void>;
  setContract: React.Dispatch<React.SetStateAction<DisplayFeatureContract | null>>;
}

export function ChatSowSection({
  contract,
  hasClarificationPrompt,
  continuationContext,
  launching,
  confirmAndLaunch,
  setContract,
}: ChatSowSectionProps) {
  const [editingContract, setEditingContract] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editLanguages, setEditLanguages] = useState("");
  const [editScope, setEditScope] = useState("");

  if (!contract && !hasClarificationPrompt) {
    return (
      <Panel title="Feature Contract">
        <EmptyState title="Contract appears after the PM Agent can process the request" compact>
          When backend services are live, this panel will show scope, language detection, estimated duration, and launch confirmation before creating a mission.
        </EmptyState>
      </Panel>
    );
  }

  if (!contract) {
    return null;
  }

  return (
    <>
      <Panel title={continuationContext?.changeOrder ? "Change order" : "Statement of Work"}>
        {!editingContract && (
          <>
            {isDegradedContract(contract) && (
              <SystemMessage tone="warning" title="Fallback planning output">
                <p>
                  This SOW was generated without a confirmed live PM model response (
                  {contractSourceLabel(contract)}). Treat it as degraded planning output until provider/key configuration is verified.
                </p>
                {contract.degradedReason && <p>Reason: {contract.degradedReason}</p>}
              </SystemMessage>
            )}
            <dl>
              <div>
                <dt>Engagement</dt>
                <dd>
                  {continuationContext?.changeOrder
                    ? `Change order on ${continuationContext.missionId}`
                    : contract.engagementType}
                </dd>
              </div>
              <div>
                <dt>Mission Title</dt>
                <dd>{contract.title}</dd>
              </div>
              <div>
                <dt>Languages</dt>
                <dd>{contract.languages}</dd>
              </div>
              <div>
                <dt>In scope</dt>
                <dd>{contract.scope}</dd>
              </div>
              <div>
                <dt>Out of scope</dt>
                <dd>
                  {contract.outOfScope.length ? contract.outOfScope.join("; ") : "PM must name at least one exclusion"}
                </dd>
              </div>
              <div>
                <dt>Deliverables</dt>
                <dd>{contract.deliverables.length ? contract.deliverables.join("; ") : "—"}</dd>
              </div>
              <div>
                <dt>Acceptance</dt>
                <dd>{contract.acceptance.length ? contract.acceptance.join("; ") : "—"}</dd>
              </div>
              <div>
                <dt>Factory estimate</dt>
                <dd>
                  {contract.pricingKnown && contract.likelyUsd != null
                    ? `Likely $${contract.likelyUsd.toFixed(2)} · High $${(contract.highUsd ?? 0).toFixed(2)} · Cap $${(contract.capUsd ?? 0).toFixed(2)}`
                    : "Unpriced — accept only if you acknowledge no quote"}
                  {contract.minutesLow && contract.minutesHigh
                    ? ` · ${contract.minutesLow}–${contract.minutesHigh} min factory time`
                    : ""}
                  <div className="muted">This is model spend for this run, not a human project quote.</div>
                </dd>
              </div>
            </dl>
            <div className="inline-actions">
              <button
                type="button"
                onClick={() => void confirmAndLaunch()}
                disabled={launching || (contract.outOfScope.length === 0 && !contract.degraded)}
              >
                {launching ? "Launching..." : "Accept SOW and start"}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  setEditTitle(contract.title);
                  setEditLanguages(contract.languages || "Auto-detect");
                  setEditScope(contract.scope);
                  setEditingContract(true);
                }}
              >
                Edit
              </button>
            </div>
          </>
        )}
      </Panel>

      {editingContract && (
        <div
          className="contract-edit-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="contract-edit-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setEditingContract(false);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") setEditingContract(false);
          }}
          tabIndex={-1}
        >
          <div className="contract-edit-modal">
            <div className="contract-edit-modal-header">
              <h2 id="contract-edit-title" style={{ margin: 0, fontSize: "1.15rem", fontWeight: 700 }}>
                ✏️ Edit Feature Contract
              </h2>
              <button
                type="button"
                className="contract-edit-close-btn"
                aria-label="Close editor"
                onClick={() => setEditingContract(false)}
              >
                ✕
              </button>
            </div>
            <form
              className="contract-edit-modal-body"
              onSubmit={(event) => {
                event.preventDefault();
                const newTitle = sanitizeUserText(editTitle);
                const newLangs = sanitizeUserText(editLanguages) || "Auto-detect";
                const newScope = editScope.trim();
                setContract((c) =>
                  c
                    ? {
                        ...c,
                        title: newTitle || c.title,
                        languages: newLangs,
                        scope: newScope || c.scope,
                      }
                    : c,
                );
                setEditingContract(false);
              }}
            >
              <div className="contract-edit-field">
                <label htmlFor="modal-contract-title" className="contract-edit-label">
                  Mission Title
                </label>
                <input
                  id="modal-contract-title"
                  type="text"
                  className="contract-edit-input"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  placeholder="Enter a descriptive mission title…"
                  autoFocus
                />
              </div>
              <div className="contract-edit-field">
                <label htmlFor="modal-contract-lang" className="contract-edit-label">
                  Languages
                </label>
                <input
                  id="modal-contract-lang"
                  type="text"
                  className="contract-edit-input"
                  value={editLanguages}
                  onChange={(e) => setEditLanguages(e.target.value)}
                  placeholder="e.g. Python, TypeScript…"
                />
              </div>
              <div className="contract-edit-field contract-edit-field--grow">
                <label htmlFor="modal-contract-scope" className="contract-edit-label">
                  Scope
                  <span className="contract-edit-label-hint">Describe the full requirements for this mission</span>
                </label>
                <textarea
                  id="modal-contract-scope"
                  className="contract-edit-textarea"
                  value={editScope}
                  onChange={(e) => setEditScope(e.target.value)}
                  placeholder="Describe the full requirements, constraints, and goals for this mission…"
                />
              </div>
              <div className="contract-edit-modal-footer">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setEditingContract(false)}
                >
                  Cancel
                </button>
                <button type="submit">Save Contract</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
