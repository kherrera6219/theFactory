"use client";

import { useState } from "react";
import { Panel } from "../../../components/panel";
import type { ClarificationPrompt } from "../chat-types";

export interface ChatClarificationPanelProps {
  clarificationPrompt: ClarificationPrompt;
  handleProceedWithClarificationDefaults: () => Promise<void>;
  handleSubmitClarificationAnswers?: (answers: Record<number, string>) => Promise<void>;
  handleEditClarificationAnswers: () => void;
  thinking: boolean;
  launching: boolean;
}

export function ChatClarificationPanel({
  clarificationPrompt,
  handleProceedWithClarificationDefaults,
  handleSubmitClarificationAnswers,
  handleEditClarificationAnswers,
  thinking,
  launching,
}: ChatClarificationPanelProps) {
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>(() => {
    const initial: Record<number, string> = {};
    clarificationPrompt.questions.forEach((_, idx) => {
      initial[idx] = clarificationPrompt.defaults[idx] ?? "";
    });
    return initial;
  });

  const structuredItems = clarificationPrompt.structured ?? [];

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
          {clarificationPrompt.questions.map((question, index) => {
            const structItem = structuredItems[index];
            const defaultVal = structItem?.recommended_default || clarificationPrompt.defaults[index] || "";
            const options = structItem?.options && structItem.options.length > 0
              ? structItem.options
              : [defaultVal].filter(Boolean);
            const currentAnswer = selectedAnswers[index] ?? defaultVal;

            return (
              <li key={`${question}-${index}`} className="clarification-card">
                <p>{structItem?.question || question}</p>
                {structItem?.impact && (
                  <div className="muted" style={{ fontSize: "0.78rem", marginBottom: "8px" }}>
                    Impact: {structItem.impact}
                  </div>
                )}
                {options.length > 0 && (
                  <div className="clarification-option-pills" role="group" aria-label={`Options for question ${index + 1}`}>
                    {options.map((option, optIdx) => {
                      const isRecommended = option === defaultVal || optIdx === 0;
                      const isSelected = currentAnswer === option;
                      return (
                        <button
                          key={`${index}-opt-${optIdx}`}
                          type="button"
                          className={`clarification-option-pill ${isSelected ? "selected" : ""}`}
                          onClick={() =>
                            setSelectedAnswers((prev) => ({
                              ...prev,
                              [index]: option,
                            }))
                          }
                          disabled={thinking || launching}
                        >
                          {isRecommended ? `★ ${option} (Recommended)` : option}
                        </button>
                      );
                    })}
                  </div>
                )}
                <div className="clarification-custom-answer">
                  <label htmlFor={`clarification-answer-${index}`} className="sr-only">
                    Answer for decision {index + 1}
                  </label>
                  <input
                    id={`clarification-answer-${index}`}
                    type="text"
                    className="contract-edit-input"
                    value={currentAnswer}
                    onChange={(e) =>
                      setSelectedAnswers((prev) => ({
                        ...prev,
                        [index]: e.target.value,
                      }))
                    }
                    placeholder="Select an option above or type a custom decision…"
                    disabled={thinking || launching}
                  />
                </div>
                <dl style={{ marginTop: "6px" }}>
                  <div>
                    <dt>Default</dt>
                    <dd>{defaultVal}</dd>
                  </div>
                </dl>
              </li>
            );
          })}
        </ul>
        <div className="inline-actions">
          {handleSubmitClarificationAnswers && (
            <button
              type="button"
              onClick={() => void handleSubmitClarificationAnswers(selectedAnswers)}
              disabled={thinking || launching}
            >
              Submit Answers &amp; Update SOW
            </button>
          )}
          <button
            type="button"
            className={handleSubmitClarificationAnswers ? "secondary-button" : undefined}
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
