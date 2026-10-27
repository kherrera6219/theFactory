"use client";

import { Panel } from "../../../components/panel";
import type { ClarificationPrompt } from "../chat-types";

export interface ChatClarificationPanelProps {
  clarificationPrompt: ClarificationPrompt;
  handleProceedWithClarificationDefaults: () => Promise<void>;
  handleEditClarificationAnswers: () => void;
  thinking: boolean;
  launching: boolean;
}

export function ChatClarificationPanel({
  clarificationPrompt,
  handleProceedWithClarificationDefaults,
  handleEditClarificationAnswers,
  thinking,
  launching,
}: ChatClarificationPanelProps) {
  return (
    <Panel title="PM Clarification">
      <div className="clarification-panel">
        <div className="clarification-header">
          <div>
            <span className="connection-chip retrying">Waiting for answers</span>
            <h2>{clarificationPrompt.contract.title}</h2>
          </div>
          <span className="clarification-count">
            {clarificationPrompt.questions.length} decision
            {clarificationPrompt.questions.length === 1 ? "" : "s"}
          </span>
        </div>
        <ul className="clarification-list">
          {clarificationPrompt.questions.map((question, index) => (
            <li key={`${question}-${index}`} className="clarification-card">
              <p>{question}</p>
              <dl>
                <div>
                  <dt>Default</dt>
                  <dd>{clarificationPrompt.defaults[index]}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>
        <div className="inline-actions">
          <button
            type="button"
            onClick={() => void handleProceedWithClarificationDefaults()}
            disabled={thinking || launching}
          >
            Proceed with Defaults
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={handleEditClarificationAnswers}
            disabled={thinking || launching}
          >
            Edit Answers
          </button>
        </div>
      </div>
    </Panel>
  );
}
