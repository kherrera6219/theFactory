"use client";

import { formatDateTime } from "../../../lib/format";
import type { ChatSession } from "../chat-types";

export interface ChatSidebarProps {
  groupedSessions: [string, ChatSession[]][];
  activeSessionId: string | null;
  resetConversation: () => void;
  loadSession: (session: ChatSession) => void;
}

export function ChatSidebar({
  groupedSessions,
  activeSessionId,
  resetConversation,
  loadSession,
}: ChatSidebarProps) {
  return (
    <aside className="chat-history-sidebar">
      <p className="chat-history-title">Conversations</p>
      <button
        type="button"
        className="secondary-button"
        style={{ width: "100%", marginBottom: "8px" }}
        onClick={resetConversation}
      >
        + New Chat
      </button>
      {groupedSessions.length === 0 && (
        <p className="muted" style={{ fontSize: "0.8rem" }}>
          No past sessions. Start a conversation to begin a mission.
        </p>
      )}
      {groupedSessions.map(([group, groupSessions]) => (
        <div key={group}>
          <span className="chat-history-group-label">{group}</span>
          <ul className="chat-history-list">
            {groupSessions.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={`chat-history-item${activeSessionId === s.id ? " active" : ""}`}
                  onClick={() => loadSession(s)}
                  title={s.title}
                >
                  <span className="chat-history-item-title">{s.title}</span>
                  {s.lastPreview ? (
                    <span className="chat-history-item-preview">{s.lastPreview}</span>
                  ) : null}
                  <span className="chat-history-item-meta">
                    {formatDateTime(s.savedAt)} · {s.messageCount} messages
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </aside>
  );
}
