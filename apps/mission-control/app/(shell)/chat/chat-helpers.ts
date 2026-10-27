import { fitConversationContext } from "../../lib/mission-metadata-budget";
import { sanitizeUserText } from "../../lib/security";
import { inferRequestedTargetLanguage } from "../../lib/language";
import {
  type ChatMessage,
  type ChatSession,
  type ClarificationPrompt,
  type ContinuationContext,
  type DisplayFeatureContract,
  type PmConversationContext,
  MAX_CONTEXT_MESSAGES,
  RASTER_IMAGE_EXTENSIONS,
  RASTER_IMAGE_MIME_TYPES,
} from "./chat-types";

export function safeFileName(file: File): string {
  return sanitizeUserText(file.name) || "attached-file";
}

export function isBinaryFile(file: File): boolean {
  const binaryExtensions = [
    ".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".bmp",
    ".pdf", ".docx", ".doc", ".xls", ".xlsx", ".ppt", ".pptx", ".zip"
  ];
  const lowerName = safeFileName(file).toLowerCase();
  return binaryExtensions.some(ext => lowerName.endsWith(ext));
}

export function isRasterImageFile(file: File): boolean {
  const lowerName = safeFileName(file).toLowerCase();
  return RASTER_IMAGE_MIME_TYPES.has(file.type.toLowerCase()) ||
    RASTER_IMAGE_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
}

export function makeId(prefix: string): string {
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

export function fileLabel(file: File): string {
  const sizeKb = Math.max(1, Math.round(file.size / 1024));
  return `${safeFileName(file)} (${sizeKb}KB)`;
}

export function detectLanguages(files: File[]): string {
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

export function summarizeScope(text: string): string {
  const normalized = sanitizeUserText(text);
  if (normalized.length <= 120) {
    return normalized || "General mission scope";
  }
  return `${normalized.slice(0, 117)}...`;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

export function formatFactoryTime(contract: {
  cost_estimate?: { estimated_minutes_low?: number; estimated_minutes_high?: number };
  timeline?: { estimated_minutes_low?: number; estimated_minutes_high?: number };
}): string {
  const low = contract.cost_estimate?.estimated_minutes_low ?? contract.timeline?.estimated_minutes_low;
  const high = contract.cost_estimate?.estimated_minutes_high ?? contract.timeline?.estimated_minutes_high;
  if (low && high) {
    return `${low}–${high} min factory time`;
  }
  return "Factory time after estimate";
}

export function emptySowFields() {
  return {
    outOfScope: [] as string[],
    deliverables: [] as string[],
    acceptance: [] as string[],
    assumptions: [] as string[],
    risks: [] as string[],
    engagementType: "BUILD_NEW",
  };
}

/** Approval phrases, including the misspellings people actually type. */
const APPROVAL_PHRASES = [
  "create the plan",
  "produce the plan",
  "finalize",
  "proceed",
  "procced",
  "procede",
  "use your best judgment",
  "use your best judgement",
  "figure out the rest",
  "firgure out the rest",
  "go ahead",
  "looks good",
  "lgtm",
  "ship it",
];

/**
 * Decide whether a message approves the current contract or continues drafting.
 *
 * This used to be a bare substring test, so any message containing "proceed"
 * launched the build the moment a contract existed. That fires on exactly the
 * phrasing people reach for while still deciding — "before we proceed, can it
 * also send email?" — turning a question into a launch and spending a full
 * mission on a scope the user was still editing.
 *
 * Two guards, both about intent rather than vocabulary:
 *  - a message ending in "?" is a question, whatever words it contains;
 *  - an approval phrase must lead the message, not merely appear in it, so
 *    "proceed" approves while "before we proceed, ..." does not.
 *
 * Being wrong in the safe direction costs one extra click on *Confirm and
 * Start*, which is on screen anyway. Being wrong the other way costs a build.
 */
export function detectUserIntent(text: string): PmConversationContext["user_intent"] {
  const normalized = text.trim().toLowerCase();
  if (!normalized || normalized.endsWith("?")) {
    return "draft";
  }
  // Strip a leading politeness so "please proceed" and "ok, proceed" still read
  // as approval.
  const lead = normalized.replace(/^(please|ok(ay)?|yes|yep|sure|alright)[\s,.:!-]+/, "");
  const approved = APPROVAL_PHRASES.some(
    (phrase) => lead === phrase || lead.startsWith(`${phrase} `) || lead.startsWith(`${phrase},`),
  );
  return approved ? "finalize_plan" : "draft";
}

export function extractDecisionMemory(messages: ChatMessage[]): string[] {
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

export function buildPmConversationContext(params: {
  messages: ChatMessage[];
  nextUserMessage: ChatMessage;
  contract: DisplayFeatureContract | null;
  files: File[];
  continuation?: ContinuationContext | null;
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
    change_order: params.continuation?.changeOrder === true,
    prior_cost: params.continuation?.priorCost,
    prior_mission_id: params.continuation?.missionId,
  };
}

export function buildFullLaunchPrompt(messages: ChatMessage[], nextUserMessage: ChatMessage): string {
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

export function compactLaunchConversationContext(
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
    change_order: context?.change_order === true,
    prior_cost: context?.prior_cost,
    prior_mission_id: context?.prior_mission_id,
  };
}

/** Derive a short title from the first user message. */
export function deriveTitle(msgs: ChatMessage[]): string {
  const first = msgs.find((m) => m.role === "user");
  if (!first) return "New conversation";
  const text = first.text.slice(0, 60);
  return text.length < first.text.length ? `${text}…` : text;
}

export function derivePreview(msgs: ChatMessage[]): string | undefined {
  const last = [...msgs].reverse().find((m) => m.id !== "welcome" && m.text.trim());
  if (!last) return undefined;
  const prefix = last.role === "pm" ? "PM: " : "You: ";
  const preview = `${prefix}${last.text.replace(/\s+/g, " ").trim()}`;
  return preview.length > 84 ? `${preview.slice(0, 81)}...` : preview;
}

export function isDegradedContract(contract: DisplayFeatureContract): boolean {
  const source = contract.source?.toLowerCase() ?? "";
  return contract.degraded === true || source.includes("fallback");
}

export function contractSourceLabel(contract: DisplayFeatureContract): string {
  const route = contract.modelProvider && contract.model
    ? `${contract.modelProvider}/${contract.model}`
    : contract.source;
  return route || "unknown";
}

export function recommendedDefaultFromQuestion(question: string, index: number): string {
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

export function buildClarificationPrompt(
  questions: string[],
  contract: DisplayFeatureContract,
): ClarificationPrompt {
  return {
    questions,
    defaults: questions.map(recommendedDefaultFromQuestion),
    contract,
  };
}

export function clarificationAnswersText(prompt: ClarificationPrompt): string {
  return [
    "Proceed with recommended defaults for the clarification questions.",
    ...prompt.questions.map((question, index) => (
      `${index + 1}. ${question}\nAnswer: ${prompt.defaults[index] ?? "Use PM recommended default."}`
    )),
    "Finalize the feature contract and prepare it for mission launch.",
  ].join("\n\n");
}

export function clarificationEditTemplate(prompt: ClarificationPrompt): string {
  return [
    "Here are my answers to the PM clarification questions:",
    ...prompt.questions.map((question, index) => (
      `${index + 1}. ${question}\nAnswer: ${prompt.defaults[index] ?? ""}`
    )),
    "Finalize the feature contract with these decisions.",
  ].join("\n\n");
}

export function artifactFilename(artifact: { manifest?: unknown; artifact_id: string }): string | undefined {
  const manifest = artifact.manifest;
  if (!manifest || typeof manifest !== "object") {
    return undefined;
  }
  const filename = (manifest as { filename?: unknown }).filename;
  return typeof filename === "string" && filename.trim() ? filename.trim() : undefined;
}

export function continuationPromptText(context: ContinuationContext): string {
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
export function buildSession(
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

export function initialWelcomeMessage(): ChatMessage {
  return {
    id: "welcome",
    role: "pm",
    text:
      "Hello. I am your PM Agent. Describe what you want to build, or attach a project ZIP " +
      "to rework, port, or update existing software. I will draft a Statement of Work with " +
      "scope, out of scope, and a factory cost estimate before you approve.",
    ts: "",
  };
}

