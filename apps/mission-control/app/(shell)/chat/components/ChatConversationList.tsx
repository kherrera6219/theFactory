"use client";

import { Panel } from "../../../components/panel";
import { formatDateTime } from "../../../lib/format";
import type { ChatMessage } from "../chat-types";

export interface ChatConversationListProps {
  messages: ChatMessage[];
  thinking: boolean;
}

export function ChatConversationList({ messages, thinking }: ChatConversationListProps) {
  return (
    <Panel title="Conversation" className="chat-panel">
      <div className="chat-list" role="log" aria-live="polite" aria-label="PM chat history">
        {messages.map((message) => (
          <article key={message.id} className={`chat-item ${message.role === "user" ? "user" : "pm"}`}>
            <div className="chat-meta">
              <strong>{message.role === "user" ? "You" : "PM Agent"}</strong>
              <span>{message.ts ? formatDateTime(message.ts) : "Session start"}</span>
            </div>
            <p>{message.text}</p>
          </article>
        ))}
        {thinking && (
          <article className="chat-item pm" aria-label="PM Agent is preparing a response">
            <div className="chat-meta">
              <strong>PM Agent</strong>
              <span>Thinking...</span>
            </div>
            <p>...</p>
          </article>
        )}
      </div>
    </Panel>
  );
}
