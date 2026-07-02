"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, SystemMessage } from "../../components/status";
import {
  createBuilderPreview,
  createMission,
  createPmFeatureContract,
  getMission,
  getMissionChainTrace,
  getMissionOutputFolderStatus,
  listMissionBuildArtifacts,
  type MissionOutputFolderStatus,
} from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import { inferRequestedTargetLanguage } from "../../lib/language";
import { sanitizeUserText } from "../../lib/security";

type ChatRole = "user" | "pm";

type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  ts: string;
};

type DisplayFeatureContract = {
  title: string;
  languages: string;
  scope: string;
  estimatedDuration: string;
  launchPrompt: string;
  source?: string;
  degraded?: boolean;
  degradedReason?: string;
  modelProvider?: string | null;
  model?: string | null;
  conversationContext?: PmConversationContext;
  userIntent?: PmConversationContext["user_intent"];
};

type ClarificationPrompt = {
  questions: string[];
  defaults: string[];
  contract: DisplayFeatureContract;
};

type ContinuationContext = {
  missionId: string;
  state: string;
  title: string;
  targetLanguage?: string;
  outputFolder?: Pick<MissionOutputFolderStatus, "path" | "exists" | "fileCount" | "totalBytes">;
  artifactRefs: Array<{
    artifactId: string;
    artifactType: string;
    status: string;
    filename?: string;
  }>;
  deliveryTitle?: string;
  deliverySummary?: string;
};

type PmConversationContext = {
  transcript: Array<Pick<ChatMessage, "role" | "text" | "ts">>;
  decision_memory: string[];
  working_contract?: {
    title: string;
    languages: string;
    scope: string;
    source?: string;
  };
  attached_files: string[];
  user_intent: "clarify" | "draft" | "finalize_plan";
};

const CHAT_STORAGE_KEY = "mission-control:pm-chat-history";
const HISTORY_STORAGE_KEY = "mission-control:pm-chat-sessions";
const MAX_HISTORY_SESSIONS = 30;
const MAX_CONTEXT_MESSAGES = 12;
const RASTER_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"] as const;
const RASTER_IMAGE_MIME_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
  "image/bmp",
]);

type ChatSession = {
  id: string;
  title: string;
  savedAt: string;
  messageCount: number;
  lastPreview?: string;
  messages: ChatMessage[];
  contract?: DisplayFeatureContract | null;
};
function safeFileName(file: File): string {
  return sanitizeUserText(file.name) || "attached-file";
}

function isBinaryFile(file: File): boolean {
  const binaryExtensions = [
    ".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".bmp",
    ".pdf", ".docx", ".doc", ".xls", ".xlsx", ".ppt", ".pptx"
  ];
  const lowerName = safeFileName(file).toLowerCase();
  return binaryExtensions.some(ext => lowerName.endsWith(ext));
}

function isRasterImageFile(file: File): boolean {
  const lowerName = safeFileName(file).toLowerCase();
  return RASTER_IMAGE_MIME_TYPES.has(file.type.toLowerCase()) ||
    RASTER_IMAGE_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
}

function FileChipPreview({ file }: { file: File }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!isRasterImageFile(file)) return;

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  const sizeKb = Math.max(1, Math.round(file.size / 1024));
  const label = safeFileName(file);

  return (
    <li className="chip-item" style={{ display: "inline-flex", flexDirection: "column", gap: "6px", padding: "12px", border: "1px solid var(--border-strong)", borderRadius: "8px", background: "var(--bg-elevated)", color: "var(--ink)" }}>
      <span style={{ fontSize: "12px", fontWeight: "bold" }}>{label} ({sizeKb}KB)</span>
      {previewUrl && (
        <img
          src={previewUrl}
          alt={label}
          style={{ maxWidth: "200px", maxHeight: "150px", objectFit: "contain", borderRadius: "4px", marginTop: "4px" }}
        />
      )}
    </li>
  );
}

function makeId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = crypto.getRandomValues(new Uint8Array(8));
    const suffix = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    return `${prefix}-${Date.now()}-${suffix}`;
  }
  return `${prefix}-${Date.now()}`;
}

function fileLabel(file: File): string {
  const sizeKb = Math.max(1, Math.round(file.size / 1024));
  return `${safeFileName(file)} (${sizeKb}KB)`;
}

function detectLanguages(files: File[]): string {
  const languages = new Set<string>();
  for (const file of files) {
    const lower = safeFileName(file).toLowerCase();
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

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

function isOperatorAuthError(message: string): boolean {
  const normalized = message.toLowerCase();
  return (
    normalized.includes("operator authentication required") ||
    normalized.includes("operator session") ||
    normalized.includes("operator api key not found")
  );
}

function operatorRecoveryMessage(message: string): string {
  if (isOperatorAuthError(message)) {
    return (
      "Mission Control is unlocked for local operation, but the local runtime rejected the request. " +
      "Restart the app stack and confirm the gateway and orchestrator services are healthy."
    );
  }
  return message;
}

function detectUserIntent(text: string): PmConversationContext["user_intent"] {
  const normalized = text.toLowerCase();
  if (
    normalized.includes("create the plan") ||
    normalized.includes("produce the plan") ||
    normalized.includes("finalize") ||
    normalized.includes("proceed") ||
    normalized.includes("procced") ||
    normalized.includes("procede") ||
    normalized.includes("use your best judgment") ||
    normalized.includes("figure out the rest") ||
    normalized.includes("firgure out the rest")
  ) {
    return "finalize_plan";
  }
  return "draft";
}

function extractDecisionMemory(messages: ChatMessage[]): string[] {
  const decisions: string[] = [];
  const decisionMarkers = [
    "use these",
    "final decision",
    "final mvp",
    "target:",
    "build the mvp",
    "do not use",
    "for the mvp",
    "save file",
    "victory condition",
    "loss condition",
    "draw condition",
    "handling levels",
    "tech stack",
  ];

  for (const message of messages) {
    if (message.role !== "user") continue;
    const lines = message.text.split(/\r?\n/);
    for (const line of lines) {
      const cleaned = sanitizeUserText(line).trim();
      if (cleaned.length < 8) continue;
      const lower = cleaned.toLowerCase();
      if (
        decisionMarkers.some((marker) => lower.includes(marker)) ||
        /^[-*]\s+/.test(cleaned) ||
        /^\d+\.\s+/.test(cleaned)
      ) {
        decisions.push(cleaned.replace(/^[-*]\s+/, "").slice(0, 220));
      }
      if (decisions.length >= 80) return decisions;
    }
  }
  return decisions;
}

function buildPmConversationContext(params: {
  messages: ChatMessage[];
  nextUserMessage: ChatMessage;
  contract: DisplayFeatureContract | null;
  files: File[];
}): PmConversationContext {
  const combinedMessages = [...params.messages, params.nextUserMessage].filter(
    (message) => message.id !== "welcome",
  );
  const transcript = combinedMessages.slice(-MAX_CONTEXT_MESSAGES).map((message) => ({
    role: message.role,
    text: sanitizeUserText(message.text).slice(0, 1200),
    ts: message.ts,
  }));
  return {
    transcript,
    decision_memory: extractDecisionMemory(combinedMessages),
    working_contract: params.contract
      ? {
          title: params.contract.title,
          languages: params.contract.languages,
          scope: params.contract.scope,
          source: params.contract.source,
        }
      : undefined,
    attached_files: params.files.map(fileLabel),
    user_intent: detectUserIntent(params.nextUserMessage.text),
  };
}

function buildFullLaunchPrompt(messages: ChatMessage[], nextUserMessage: ChatMessage): string {
  const combinedMessages = [...messages, nextUserMessage].filter(
    (message) => message.id !== "welcome" && message.role === "user",
  );
  return (
    combinedMessages
      .map((message) => sanitizeUserText(message.text))
      .filter(Boolean)
      .join("\n\n")
      .slice(-20000) || sanitizeUserText(nextUserMessage.text)
  );
}

function compactLaunchConversationContext(
  context: PmConversationContext | undefined,
  contract: DisplayFeatureContract,
): PmConversationContext {
  const transcript = (context?.transcript ?? []).slice(-6).map((message) => ({
    role: message.role,
    text: sanitizeUserText(message.text).slice(0, 2000),
    ts: message.ts,
  }));
  const decisionMemory = (context?.decision_memory ?? [])
    .slice(-12)
    .map((item) => sanitizeUserText(item).slice(0, 500))
    .filter(Boolean);
  const attachedFiles = (context?.attached_files ?? [])
    .slice(0, 20)
    .map((item) => sanitizeUserText(item).slice(0, 120))
    .filter(Boolean);

  return {
    transcript,
    decision_memory: decisionMemory,
    working_contract: {
      title: contract.title.slice(0, 160),
      languages: contract.languages.slice(0, 160),
      scope: contract.scope.slice(0, 4000),
      source: contract.source,
    },
    attached_files: attachedFiles,
    user_intent: "finalize_plan",
  };
}

/** Derive a short title from the first user message. */
function deriveTitle(msgs: ChatMessage[]): string {
  const first = msgs.find((m) => m.role === "user");
  if (!first) return "New conversation";
  const text = first.text.slice(0, 60);
  return text.length < first.text.length ? `${text}…` : text;
}

function derivePreview(msgs: ChatMessage[]): string | undefined {
  const last = [...msgs].reverse().find((m) => m.id !== "welcome" && m.text.trim());
  if (!last) return undefined;
  const prefix = last.role === "pm" ? "PM: " : "You: ";
  const preview = `${prefix}${last.text.replace(/\s+/g, " ").trim()}`;
  return preview.length > 84 ? `${preview.slice(0, 81)}...` : preview;
}

function isDegradedContract(contract: DisplayFeatureContract): boolean {
  const source = contract.source?.toLowerCase() ?? "";
  return contract.degraded === true || source.includes("fallback");
}

function contractSourceLabel(contract: DisplayFeatureContract): string {
  const route = contract.modelProvider && contract.model
    ? `${contract.modelProvider}/${contract.model}`
    : contract.source;
  return route || "unknown";
}

function recommendedDefaultFromQuestion(question: string, index: number): string {
  const cleaned = sanitizeUserText(question);
  const explicit = cleaned.match(/recommended(?: default)?:\s*([^)]+)\)?\.?$/i);
  if (explicit?.[1]) {
    return explicit[1].trim().replace(/[.)]+$/, "");
  }
  const lower = cleaned.toLowerCase();
  if (lower.includes("visual") || lower.includes("style") || lower.includes("ui")) {
    return "Use a polished modern arcade style with responsive layout and clear game-state screens.";
  }
  if (lower.includes("score") || lower.includes("persistent") || lower.includes("save")) {
    return "Persist the high score locally in the browser and keep all game state client-side.";
  }
  if (lower.includes("packaging") || lower.includes("start.bat") || lower.includes("run")) {
    return "Include a Windows start.bat that installs dependencies if needed and starts the Angular dev server.";
  }
  if (lower.includes("acceptance") || lower.includes("done") || lower.includes("criteria")) {
    return "Done means the app builds, starts from start.bat, and supports a playable core loop.";
  }
  return `Use PM recommended default ${index + 1}.`;
}

function buildClarificationPrompt(
  questions: string[],
  contract: DisplayFeatureContract,
): ClarificationPrompt {
  return {
    questions,
    defaults: questions.map(recommendedDefaultFromQuestion),
    contract,
  };
}

function clarificationAnswersText(prompt: ClarificationPrompt): string {
  return [
    "Proceed with recommended defaults for the clarification questions.",
    ...prompt.questions.map((question, index) => (
      `${index + 1}. ${question}\nAnswer: ${prompt.defaults[index] ?? "Use PM recommended default."}`
    )),
    "Finalize the feature contract and prepare it for mission launch.",
  ].join("\n\n");
}

function clarificationEditTemplate(prompt: ClarificationPrompt): string {
  return [
    "Here are my answers to the PM clarification questions:",
    ...prompt.questions.map((question, index) => (
      `${index + 1}. ${question}\nAnswer: ${prompt.defaults[index] ?? ""}`
    )),
    "Finalize the feature contract with these decisions.",
  ].join("\n\n");
}

function artifactFilename(artifact: { manifest?: unknown; artifact_id: string }): string | undefined {
  const manifest = artifact.manifest;
  if (!manifest || typeof manifest !== "object") {
    return undefined;
  }
  const filename = (manifest as { filename?: unknown }).filename;
  return typeof filename === "string" && filename.trim() ? filename.trim() : undefined;
}

function continuationPromptText(context: ContinuationContext): string {
  const artifactLines = context.artifactRefs.length > 0
    ? context.artifactRefs
        .slice(0, 8)
        .map((artifact) => {
          const filename = artifact.filename ? ` (${artifact.filename})` : "";
          return `- ${artifact.artifactType}${filename}: ${artifact.status}, ${artifact.artifactId}`;
        })
    : ["- No build artifacts recorded yet."];

  return [
    `Continue work on existing mission ${context.missionId}.`,
    "Use the prior mission output as the project baseline.",
    `Previous mission status: ${context.state}.`,
    context.targetLanguage ? `Previous target language: ${context.targetLanguage}.` : null,
    context.deliveryTitle ? `Previous delivery: ${context.deliveryTitle}.` : null,
    context.deliverySummary ? `Delivery summary: ${context.deliverySummary}` : null,
    context.outputFolder
      ? `Output folder: ${context.outputFolder.path} (${context.outputFolder.exists ? `${context.outputFolder.fileCount} files` : "not written yet"}).`
      : null,
    "Prior artifacts:",
    ...artifactLines,
    "Next change request:",
  ]
    .filter((line): line is string => Boolean(line))
    .join("\n");
}

/** Build a persisted session snapshot from the current message list. */
function buildSession(
  messages: ChatMessage[],
  id: string,
  contract: DisplayFeatureContract | null,
): ChatSession {
  return {
    id,
    title: deriveTitle(messages),
    savedAt: new Date().toISOString(),
    messageCount: messages.length,
    lastPreview: derivePreview(messages),
    messages,
    contract,
  };
}

function initialWelcomeMessage(): ChatMessage {
  return {
    id: "welcome",
    role: "pm",
    text:
      "Hello. I am your PM Agent. Describe what you want to build or analyze, " +
      "and attach source files if needed. I will ask clarifying questions before launch when scope is not ready.",
    ts: "",
  };
}

export default function ChatPage() {
  const router = useRouter();
  const continueMissionRef = useRef<string | null>(null);
  const [continuationContext, setContinuationContext] = useState<ContinuationContext | null>(null);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([initialWelcomeMessage()]);
  const [contract, setContract] = useState<DisplayFeatureContract | null>(null);
  const [clarificationPrompt, setClarificationPrompt] = useState<ClarificationPrompt | null>(null);
  const [editingContract, setEditingContract] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editLanguages, setEditLanguages] = useState("");
  const [editScope, setEditScope] = useState("");
  const [thinking, setThinking] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

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
    const params = new URLSearchParams(window.location.search);
    const continueMissionId = params.get("continueMissionId")?.trim() ?? "";
    if (!continueMissionId || continueMissionRef.current === continueMissionId) {
      return;
    }
    continueMissionRef.current = continueMissionId;
    let cancelled = false;

    async function loadContinuingMission() {
      const timestamp = new Date().toISOString();
      try {
        const [mission, chainTraceResult, artifactsResult, outputFolderResult] =
          await Promise.all([
            getMission(continueMissionId),
            getMissionChainTrace(continueMissionId).catch(() => null),
            listMissionBuildArtifacts(continueMissionId, 25).catch(() => []),
            getMissionOutputFolderStatus(continueMissionId).catch(() => null),
          ]);
        if (cancelled) {
          return;
        }
        const chainTrace = chainTraceResult;
        const artifacts = artifactsResult;
        const outputFolder = outputFolderResult;
        const metadata = mission.metadata ?? {};
        const missionName =
          typeof metadata.name === "string" && metadata.name.trim()
            ? metadata.name.trim()
            : mission.prompt?.slice(0, 80) || continueMissionId;
        const context: ContinuationContext = {
          missionId: continueMissionId,
          state: mission.state,
          title: missionName,
          targetLanguage: mission.requested_target_language ?? undefined,
          outputFolder: outputFolder
            ? {
                path: outputFolder.path,
                exists: outputFolder.exists,
                fileCount: outputFolder.fileCount,
                totalBytes: outputFolder.totalBytes,
              }
            : undefined,
          artifactRefs: artifacts.map((artifact) => ({
            artifactId: artifact.artifact_id,
            artifactType: artifact.artifact_type,
            status: artifact.status,
            filename: artifactFilename(artifact),
          })),
          deliveryTitle: chainTrace?.delivery_summary?.delivery_title,
          deliverySummary: chainTrace?.delivery_summary?.delivery_summary,
        };
        setContinuationContext(context);
        setMessages([
          initialWelcomeMessage(),
          {
            id: makeId("pm-continue"),
            role: "pm",
            text:
              `Continuing mission ${continueMissionId} (${missionName}). ` +
              "I loaded the prior output location and artifact list so the follow-up mission can use that project as the baseline.",
            ts: timestamp,
          },
        ]);
        setInput(`${continuationPromptText(context)}\n`);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setContinuationContext({
          missionId: continueMissionId,
          state: "unknown",
          title: continueMissionId,
          artifactRefs: [],
        });
        setMessages([
          initialWelcomeMessage(),
          {
            id: makeId("pm-continue"),
            role: "pm",
            text:
              `Continuing mission ${continueMissionId}. ` +
              "I could not load the mission summary, but I can still use this mission ID as the baseline for your next change.",
            ts: timestamp,
          },
        ]);
        setInput(
          `Continue work on existing mission ${continueMissionId}.\n` +
            "Use the prior mission output as the project baseline.\n" +
            "Next change request:\n",
        );
        setError(error instanceof Error ? error.message : "Unable to load mission summary.");
      } finally {
        if (!cancelled) {
          setContract(null);
          setClarificationPrompt(null);
          setFiles([]);
          setActiveSessionId(null);
        }
      }
    }

    void loadContinuingMission();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
  }, [messages]);

  // Load persistent session list from localStorage.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(HISTORY_STORAGE_KEY);
      if (raw) setSessions(JSON.parse(raw) as ChatSession[]);
    } catch { /* ignore malformed data */ }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!messages.some((message) => message.role === "user")) return;

    const id = activeSessionId ?? makeId("session");
    const session = buildSession(messages, id, contract);

    setSessions((current) => {
      const updated = [session, ...current.filter((item) => item.id !== id)].slice(0, MAX_HISTORY_SESSIONS);
      try {
        window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(updated));
      } catch {
        // Storage quota exceeded; keep the in-memory session list for this page.
      }
      return updated;
    });
    if (!activeSessionId) {
      setActiveSessionId(id);
    }
  }, [messages, activeSessionId, contract]);

  function saveSessions(updated: ChatSession[]) {
    setSessions(updated);
    try {
      window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(updated));
    } catch { /* storage quota exceeded — silently ignore */ }
  }

  function saveCurrentSession() {
    const userMessages = messages.filter((m) => m.role === "user");
    if (userMessages.length === 0) return; // Nothing worth saving.
    const id = activeSessionId ?? makeId("session");
    const session = buildSession(messages, id, contract);
    const updated = [session, ...sessions.filter((s) => s.id !== id)]
      .slice(0, MAX_HISTORY_SESSIONS);
    saveSessions(updated);
    setActiveSessionId(id);
  }

  function loadSession(session: ChatSession) {
    saveCurrentSession(); // Persist current before switching.
    setMessages(session.messages);
    setActiveSessionId(session.id);
    setContract(session.contract ?? null);
    setClarificationPrompt(null);
    setContinuationContext(null);
    continueMissionRef.current = null;
    setEditingContract(false);
    setInput("");
    setError(null);
    setFiles([]);
  }



  function resetConversation() {
    saveCurrentSession();
    setMessages([initialWelcomeMessage()]);
    setFiles([]);
    setContract(null);
    setClarificationPrompt(null);
    setContinuationContext(null);
    continueMissionRef.current = null;
    setEditingContract(false);
    setInput("");
    setError(null);
    setActiveSessionId(null);
  }

  function addFiles(items: FileList | File[]) {
    const incoming = Array.from(items);
    if (incoming.length === 0) {
      return;
    }
    setFiles((current) => [...current, ...incoming].slice(0, 20));
  }

  async function sendMessage(messageOverride?: string) {
    const normalized = sanitizeUserText(messageOverride ?? input);
    if (normalized.length < 3) {
      setError("Enter at least 3 characters to continue.");
      return;
    }

    setError(null);
    setClarificationPrompt(null);
    setThinking(true);
    const timestamp = new Date().toISOString();
    const contextContract = contract ?? clarificationPrompt?.contract ?? null;

    const userText =
      files.length > 0
        ? `${normalized}\n\nAttached files: ${files.map((item) => item.name).join(", ")}`
        : normalized;
    const nextUserMessage: ChatMessage = {
      id: makeId("user"),
      role: "user",
      text: userText,
      ts: timestamp,
    };

    setMessages((current) => [...current, nextUserMessage]);

    try {
      if (contract && detectUserIntent(normalized) === "finalize_plan") {
        setInput("");
        await confirmAndLaunch(contract);
        return;
      }

      const sourceCode = await readFilesAsText(files);
      const detected = detectLanguages(files);
      const conversationContext = buildPmConversationContext({
        messages,
        nextUserMessage,
        contract: contextContract,
        files,
      });
      const launchPrompt = buildFullLaunchPrompt(messages, nextUserMessage);
      let acknowledgement = "Request received. I have prepared a feature contract.";
      let generatedContract: DisplayFeatureContract;
      let blocksLaunchForClarification = false;
      let pendingClarifyingQuestions: string[] = [];
      let pmPreviewError: unknown = null;
      try {
        const pmPreview = await createPmFeatureContract({
          prompt: normalized,
          conversation_context: conversationContext,
          user_intent: conversationContext.user_intent,
          source_code: sourceCode || undefined,
          requestedTargetLanguage: inferRequestedTargetLanguage({
            prompt: launchPrompt,
            filePaths: files.map((file) => file.name),
          }),
        });
        const featureContract = pmPreview.feature_contract;
        const clarifyingQuestions = featureContract.clarifying_questions ?? [];
        pendingClarifyingQuestions = clarifyingQuestions;
        const needsClarification =
          featureContract.intake_status === "needs_clarification" ||
          (typeof featureContract.ambiguity_score === "number" &&
            featureContract.ambiguity_score >= 0.7);
        blocksLaunchForClarification = needsClarification && clarifyingQuestions.length > 0;
        if (needsClarification && clarifyingQuestions.length > 0) {
          acknowledgement = [
            "I drafted the current scope and need a few product decisions before launch:",
            ...clarifyingQuestions.map((question, index) => `${index + 1}. ${question}`),
            "Answer these, edit the defaults, or proceed with the recommended defaults.",
          ].join("\n");
        }
        if (!needsClarification || clarifyingQuestions.length === 0) {
          acknowledgement =
          featureContract.acceptance_criteria.length > 0
            ? [
                `I drafted a feature contract for review. ${featureContract.summary}`,
                `Acceptance: ${featureContract.acceptance_criteria.slice(0, 2).join("; ")}`,
              ]
                .filter(Boolean)
                .join(" ")
            : featureContract.summary || acknowledgement;
        }
        generatedContract = {
          title: featureContract.title || "New Mission",
          languages:
            featureContract.target_languages.length > 0
              ? featureContract.target_languages.join(", ")
              : detected,
          scope: featureContract.summary || summarizeScope(normalized),
          estimatedDuration: files.length > 10 ? "~12 minutes" : "~6 minutes",
          launchPrompt,
          source: pmPreview.source,
          degraded: featureContract.degraded === true || pmPreview.source === "fallback",
          degradedReason: featureContract.degraded_reason,
          modelProvider: pmPreview.model_provider ?? featureContract.model_provider ?? null,
          model: pmPreview.model ?? featureContract.model ?? null,
          conversationContext,
          userIntent: conversationContext.user_intent,
        };
      } catch (contractError) {
        pmPreviewError = contractError;
        let preview;
        try {
          preview = await createBuilderPreview({
            request: normalized,
            constraints:
              files.length > 0
                ? [`Attached files: ${files.map((item) => item.name).join(", ")}`]
                : [],
            viewMode: "desktop",
          });
        } catch (fallbackError) {
          throw new Error(
            `PM feature contract failed: ${errorMessage(pmPreviewError)}. ` +
              `Fallback preview failed: ${errorMessage(fallbackError)}.`,
          );
        }
        acknowledgement =
          preview.plan.length > 0
            ? preview.plan.map((step) => `${step.title}: ${step.description}`).join(" ")
            : "Request received. I have prepared a local fallback feature contract.";
        generatedContract = {
          title:
            normalized.split(" ").slice(0, 8).join(" ").replace(/[.?!]$/, "") || "New Mission",
          languages: detected,
          scope: summarizeScope(normalized),
          estimatedDuration: files.length > 10 ? "~12 minutes" : "~6 minutes",
          launchPrompt,
          source: "local-fallback",
          degraded: true,
          degradedReason: "pm_feature_contract_unavailable",
          conversationContext,
          userIntent: conversationContext.user_intent,
        };
      }

      setMessages((current) => [
        ...current,
        { id: makeId("pm"), role: "pm", text: acknowledgement, ts: new Date().toISOString() },
      ]);
      setClarificationPrompt(
        blocksLaunchForClarification
          ? buildClarificationPrompt(pendingClarifyingQuestions, generatedContract)
          : null,
      );
      setContract(blocksLaunchForClarification ? null : generatedContract);
      setInput("");
    } catch (requestError) {
      const rawMessage =
        requestError instanceof Error ? requestError.message : "Unable to reach PM services.";
      const message = operatorRecoveryMessage(rawMessage);
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

  function handleEditClarificationAnswers() {
    if (!clarificationPrompt) return;
    setInput(clarificationEditTemplate(clarificationPrompt));
  }

  async function handleProceedWithClarificationDefaults() {
    if (!clarificationPrompt) return;
    await sendMessage(clarificationAnswersText(clarificationPrompt));
  }

  async function readFilesAsText(fileList: File[]): Promise<string> {
    if (fileList.length === 0) {
      return "";
    }
    const parts = await Promise.all(
      fileList.map(
        (file) =>
          new Promise<string>((resolve) => {
            const reader = new FileReader();
            const name = safeFileName(file);
            if (isBinaryFile(file)) {
              reader.onload = () =>
                resolve(`// --- ${name} (binary) ---\n${reader.result as string}`);
              reader.onerror = () => resolve(`// --- ${name} --- (unreadable)`);
              reader.readAsDataURL(file);
            } else {
              reader.onload = () =>
                resolve(`// --- ${name} ---\n${reader.result as string}`);
              reader.onerror = () => resolve(`// --- ${name} --- (unreadable)`);
              reader.readAsText(file);
            }
          }),
      ),
    );
    return parts.join("\n\n");
  }

  async function confirmAndLaunch(contractOverride?: DisplayFeatureContract) {
    const launchContract = contractOverride ?? contract;
    if (!launchContract) {
      return;
    }
    setLaunching(true);
    setError(null);
    try {
      const sourceCode = await readFilesAsText(files);
      const requestedTargetLanguage = inferRequestedTargetLanguage({
        prompt: launchContract.launchPrompt,
        filePaths: files.map((file) => file.name),
        contractLanguages: launchContract.languages,
      });
      const conversationContext = compactLaunchConversationContext(
        launchContract.conversationContext,
        launchContract,
      );
      const mission = await createMission({
        prompt: launchContract.launchPrompt,
        requested_target_language: requestedTargetLanguage,
        source_code: sourceCode || undefined,
        metadata: {
          source: "mission-control-chat",
          attached_files: files.map((item) => safeFileName(item)),
          inferred_requested_target_language: requestedTargetLanguage,
          conversation_context: conversationContext,
          user_intent: "finalize_plan",
          launch_confirmed_at: new Date().toISOString(),
          launch_source: "feature-contract-confirmation",
          continued_from_mission_id: continueMissionRef.current,
          continued_from: continuationContext
            ? {
                mission_id: continuationContext.missionId,
                state: continuationContext.state,
                title: continuationContext.title,
                output_folder: continuationContext.outputFolder,
                artifact_refs: continuationContext.artifactRefs,
                delivery_title: continuationContext.deliveryTitle,
              }
            : undefined,
          contract: {
            title: launchContract.title,
            languages: launchContract.languages,
            scope: launchContract.scope,
            estimated_duration: launchContract.estimatedDuration,
          },
        },
      });
      router.push(`/missions/detail?id=${mission.mission_id}`);
    } catch (launchError) {
      setError(launchError instanceof Error ? launchError.message : "Mission launch failed.");
    } finally {
      setLaunching(false);
    }
  }

  // Group sessions by "Today" / "Yesterday" / date label.
  const groupedSessions = useMemo(() => {
    const today = new Date().toDateString();
    const yesterday = new Date(Date.now() - 86400000).toDateString();
    const groups = new Map<string, ChatSession[]>();
    for (const s of sessions) {
      const label = new Date(s.savedAt).toDateString();
      const groupKey = label === today ? "Today" : label === yesterday ? "Yesterday" : label;
      const bucket = groups.get(groupKey) ?? [];
      bucket.push(s);
      groups.set(groupKey, bucket);
    }
    return Array.from(groups.entries());
  }, [sessions]);

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="PM Agent Chat"
        title="Mission Intake Conversation"
        description="Describe your request in natural language, attach source files, and confirm the generated feature contract."
      />

      <div className="chat-layout">
        {/* Phase 2H — persistent conversation history sidebar */}
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

        <div className="chat-main">
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

      <Panel title="Message & Files">

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
        <label className="file-input-label">
          <span>Choose files</span>
          <input
            type="file"
            multiple
            className="sr-only"
            aria-label="Choose files to attach"
            onChange={(event) => {
              if (event.target.files) {
                addFiles(event.target.files);
              }
            }}
          />
        </label>
        {files.length > 0 && (
          <ul className="chip-list" aria-label="Attached files" style={{ display: "flex", flexWrap: "wrap", gap: "10px", listStyle: "none", padding: 0, marginTop: "12px", marginBottom: "12px" }}>
            {files.map((file, idx) => (
              <FileChipPreview key={`${file.name}-${idx}`} file={file} />
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
        <div className="chat-send-row">
          <button type="button" onClick={() => void sendMessage()} disabled={thinking || launching}>
            {thinking ? "Sending..." : "Send"}
          </button>
        </div>
        {error && (
          <SystemMessage tone="warning" title="Message needs attention">
            <p>{error}</p>
            {isOperatorAuthError(error) && (
              <div className="inline-actions" style={{ marginTop: "12px" }}>
                <button type="button" className="secondary-button" onClick={() => router.push("/settings")}>
                  Open Settings
                </button>
              </div>
            )}
          </SystemMessage>
        )}
      </Panel>

      {clarificationPrompt && (
        <Panel title="PM Clarification">
          <div className="clarification-panel">
            <div className="clarification-header">
              <div>
                <span className="connection-chip retrying">Waiting for answers</span>
                <h2>{clarificationPrompt.contract.title}</h2>
              </div>
              <span className="clarification-count">
                {clarificationPrompt.questions.length} decision{clarificationPrompt.questions.length === 1 ? "" : "s"}
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
      )}

      {!contract && !clarificationPrompt && (
        <Panel title="Feature Contract">
          <EmptyState title="Contract appears after the PM Agent can process the request" compact>
            When backend services are live, this panel will show scope, language detection, estimated duration, and launch confirmation before creating a mission.
          </EmptyState>
        </Panel>
      )}

      {contract && (
        <Panel title="Feature Contract">
          {!editingContract && (
            <>
              {isDegradedContract(contract) && (
                <SystemMessage tone="warning" title="Fallback planning output">
                  <p>
                    This contract was generated without a confirmed live PM model response
                    ({contractSourceLabel(contract)}). Treat it as degraded planning output
                    until provider/key configuration is verified.
                  </p>
                  {contract.degradedReason && <p>Reason: {contract.degradedReason}</p>}
                </SystemMessage>
              )}
              <dl>
                <div>
                  <dt>Mission Title</dt>
                  <dd>{contract.title}</dd>
                </div>
                <div>
                  <dt>Planning Source</dt>
                  <dd>{contractSourceLabel(contract)}</dd>
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
                  onClick={() => {
                    if (contract) {
                      setEditTitle(contract.title);
                      setEditLanguages(contract.languages || "Auto-detect");
                      setEditScope(contract.scope);
                      setEditingContract(true);
                    }
                  }}
                >
                  Edit
                </button>
              </div>
            </>
          )}

        </Panel>
      )}
        </div>{/* end chat-main */}

      </div>


      {/* ── Feature Contract Edit Modal ──────────────────────────────── */}
      {editingContract && contract && (
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
    </div>
  );
}

