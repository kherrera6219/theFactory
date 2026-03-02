"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { createBuilderPreview, createMission } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { sanitizeUserText } from "../../lib/security";

type ChatRole = "user" | "pm";

type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  ts: string;
};

type FeatureContract = {
  title: string;
  languages: string;
  scope: string;
  estimatedDuration: string;
  launchPrompt: string;
};

const CHAT_STORAGE_KEY = "mission-control:pm-chat-history";
const ACCEPTED_EXTENSIONS = [
  ".py",
  ".js",
  ".ts",
  ".java",
  ".c",
  ".cpp",
  ".rs",
  ".go",
  ".rb",
  ".php",
  ".cs",
  ".scala",
  ".r",
  ".m",
];

function makeId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function fileLabel(file: File): string {
  const sizeKb = Math.max(1, Math.round(file.size / 1024));
  return `${file.name} (${sizeKb}KB)`;
}

function detectLanguages(files: File[]): string {
  const languages = new Set<string>();
  for (const file of files) {
    const lower = file.name.toLowerCase();
    if (lower.endsWith(".py")) languages.add("Python");
    if (lower.endsWith(".js") || lower.endsWith(".ts")) languages.add("JavaScript/TypeScript");
    if (lower.endsWith(".java")) languages.add("Java");
    if (lower.endsWith(".c") || lower.endsWith(".cpp")) languages.add("C/C++");
    if (lower.endsWith(".rs")) languages.add("Rust");
    if (lower.endsWith(".go")) languages.add("Go");
    if (lower.endsWith(".rb")) languages.add("Ruby");
    if (lower.endsWith(".php")) languages.add("PHP");
    if (lower.endsWith(".cs")) languages.add("C#");
    if (lower.endsWith(".scala")) languages.add("Scala");
    if (lower.endsWith(".r")) languages.add("R");
    if (lower.endsWith(".m")) languages.add("MATLAB");
  }
  return languages.size > 0 ? Array.from(languages).join(", ") : "Auto-detect";
}

function summarizeScope(text: string): string {
  const normalized = sanitizeUserText(text);
  if (normalized.length <= 120) {
    return normalized || "General mission scope";
  }
  return `${normalized.slice(0, 117)}...`;
}

export default function ChatPage() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "pm",
      text:
        "Hello. I am your PM Agent. Describe what you want to build or analyze, " +
        "and attach source files if needed.",
      ts: new Date().toISOString(),
    },
  ]);
  const [contract, setContract] = useState<FeatureContract | null>(null);
  const [editingContract, setEditingContract] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const raw = window.sessionStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) {
      return;
    }
    try {
      const parsed = JSON.parse(raw) as ChatMessage[];
      if (Array.isArray(parsed) && parsed.length > 0) {
        setMessages(parsed);
      }
    } catch {
      // Ignore malformed session data.
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
  }, [messages]);

  const fileChips = useMemo(() => files.map((item) => fileLabel(item)), [files]);

  function resetConversation() {
    setMessages([
      {
        id: "welcome",
        role: "pm",
        text:
          "Hello. I am your PM Agent. Describe what you want to build or analyze, " +
          "and attach source files if needed.",
        ts: new Date().toISOString(),
      },
    ]);
    setFiles([]);
    setContract(null);
    setEditingContract(false);
    setInput("");
    setError(null);
  }

  function addFiles(items: FileList | File[]) {
    const incoming = Array.from(items);
    if (incoming.length === 0) {
      return;
    }
    setFiles((current) => [...current, ...incoming].slice(0, 20));
  }

  async function sendMessage() {
    const normalized = sanitizeUserText(input);
    if (normalized.length < 3) {
      setError("Enter at least 3 characters to continue.");
      return;
    }

    setError(null);
    setThinking(true);
    const timestamp = new Date().toISOString();

    const userText =
      files.length > 0
        ? `${normalized}\n\nAttached files: ${files.map((item) => item.name).join(", ")}`
        : normalized;

    setMessages((current) => [
      ...current,
      { id: makeId("user"), role: "user", text: userText, ts: timestamp },
    ]);

    try {
      const preview = await createBuilderPreview({
        request: normalized,
        constraints:
          files.length > 0 ? [`Attached files: ${files.map((item) => item.name).join(", ")}`] : [],
        viewMode: "desktop",
      });

      const acknowledgement =
        preview.plan.length > 0
          ? preview.plan.map((step) => `${step.title}: ${step.description}`).join(" ")
          : "Request received. I have prepared a feature contract.";

      const detected = detectLanguages(files);
      const generatedContract: FeatureContract = {
        title: normalized.split(" ").slice(0, 8).join(" ").replace(/[.?!]$/, "") || "New Mission",
        languages: detected,
        scope: summarizeScope(normalized),
        estimatedDuration: files.length > 10 ? "~12 minutes" : "~6 minutes",
        launchPrompt: normalized,
      };

      setMessages((current) => [
        ...current,
        { id: makeId("pm"), role: "pm", text: acknowledgement, ts: new Date().toISOString() },
      ]);
      setContract(generatedContract);
      setInput("");
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : "Unable to reach PM services.";
      setMessages((current) => [
        ...current,
        {
          id: makeId("pm-error"),
          role: "pm",
          text: `I could not process that request right now: ${message}`,
          ts: new Date().toISOString(),
        },
      ]);
      setError(message);
    } finally {
      setThinking(false);
    }
  }

  async function confirmAndLaunch() {
    if (!contract) {
      return;
    }
    setLaunching(true);
    setError(null);
    try {
      const mission = await createMission({
        prompt: contract.launchPrompt,
        requested_target_language: "python",
        metadata: {
          source: "mission-control-chat",
          attached_files: files.map((item) => item.name),
          contract: {
            title: contract.title,
            languages: contract.languages,
            scope: contract.scope,
            estimated_duration: contract.estimatedDuration,
          },
        },
      });
      router.push(`/missions/${mission.mission_id}`);
    } catch (launchError) {
      setError(launchError instanceof Error ? launchError.message : "Mission launch failed.");
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div className="page shell-page">
      <PageHeader
        eyebrow="PM Agent Chat"
        title="Mission Intake Conversation"
        description="Describe your request in natural language, attach source files, and confirm the generated feature contract."
        actions={
          <div className="inline-actions">
            <button type="button" className="secondary-button" onClick={resetConversation}>
              New Chat
            </button>
          </div>
        }
      />

      <Panel title="Conversation" className="chat-panel">
        <ul className="chat-list" role="log" aria-live="polite" aria-label="PM chat history">
          {messages.map((message) => (
            <li key={message.id} className={`chat-item ${message.role === "user" ? "user" : "pm"}`}>
              <div className="chat-meta">
                <strong>{message.role === "user" ? "You" : "PM Agent"}</strong>
                <span>{formatDateTime(message.ts)}</span>
              </div>
              <p>{message.text}</p>
            </li>
          ))}
          {thinking && (
            <li className="chat-item pm">
              <div className="chat-meta">
                <strong>PM Agent</strong>
                <span>Thinking...</span>
              </div>
              <p>...</p>
            </li>
          )}
        </ul>
      </Panel>

      <Panel title="Attach Files and Message">
        <p className="help-text">Accepted formats: {ACCEPTED_EXTENSIONS.join(" ")}</p>
        <div
          className="drop-zone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            addFiles(event.dataTransfer.files);
          }}
        >
          Drag and drop files here, or choose files below.
        </div>
        <input
          type="file"
          multiple
          onChange={(event) => {
            if (event.target.files) {
              addFiles(event.target.files);
            }
          }}
        />
        {fileChips.length > 0 && (
          <ul className="chip-list" aria-label="Attached files">
            {fileChips.map((chip) => (
              <li key={chip} className="chip-item">
                {chip}
              </li>
            ))}
          </ul>
        )}
        <label htmlFor="chat-input">Message</label>
        <textarea
          id="chat-input"
          value={input}
          rows={4}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void sendMessage();
            }
          }}
          placeholder="Analyze this repository and identify reliability risks before delivery."
          autoFocus
        />
        <div className="inline-actions">
          <button type="button" onClick={() => void sendMessage()} disabled={thinking || launching}>
            {thinking ? "Sending..." : "Send"}
          </button>
        </div>
        {error && <p className="error-box">{error}</p>}
      </Panel>

      {contract && (
        <Panel title="Feature Contract">
          {!editingContract && (
            <>
              <dl>
                <div>
                  <dt>Mission Title</dt>
                  <dd>{contract.title}</dd>
                </div>
                <div>
                  <dt>Languages</dt>
                  <dd>{contract.languages}</dd>
                </div>
                <div>
                  <dt>Scope</dt>
                  <dd>{contract.scope}</dd>
                </div>
                <div>
                  <dt>Estimated Duration</dt>
                  <dd>{contract.estimatedDuration}</dd>
                </div>
              </dl>
              <div className="inline-actions">
                <button type="button" onClick={() => void confirmAndLaunch()} disabled={launching}>
                  {launching ? "Launching..." : "Confirm and Start"}
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setEditingContract(true)}
                >
                  Edit
                </button>
              </div>
            </>
          )}

          {editingContract && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                setEditingContract(false);
              }}
            >
              <label htmlFor="contract-title">Mission Title</label>
              <input
                id="contract-title"
                type="text"
                value={contract.title}
                onChange={(event) =>
                  setContract((current) =>
                    current ? { ...current, title: sanitizeUserText(event.target.value) } : current,
                  )
                }
              />
              <label htmlFor="contract-lang">Languages</label>
              <input
                id="contract-lang"
                type="text"
                value={contract.languages}
                onChange={(event) =>
                  setContract((current) =>
                    current
                      ? { ...current, languages: sanitizeUserText(event.target.value) || "Auto-detect" }
                      : current,
                  )
                }
              />
              <label htmlFor="contract-scope">Scope</label>
              <textarea
                id="contract-scope"
                rows={3}
                value={contract.scope}
                onChange={(event) =>
                  setContract((current) =>
                    current ? { ...current, scope: summarizeScope(event.target.value) } : current,
                  )
                }
              />
              <div className="inline-actions">
                <button type="submit">Save Contract</button>
              </div>
            </form>
          )}
        </Panel>
      )}
    </div>
  );
}

