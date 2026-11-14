import type { MissionOutputFolderStatus } from "../../lib/api-client";

export type ChatRole = "user" | "pm";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  ts: string;
};

export type BaselinePolicy = "preserve_existing_behaviour" | "update_behaviour" | "greenfield";

export type SowSlice = {
  id: string;
  title: string;
  description?: string;
  files: string[];
  acceptance_criteria?: string[];
  depends_on?: string[];
};

export type RecommendedTargetLanguage = {
  language: string;
  rationale?: string;
  maturity_tier?: string;
};

export type DisplayFeatureContract = {
  title: string;
  languages: string;
  scope: string;
  estimatedDuration: string;
  outOfScope: string[];
  deliverables: string[];
  acceptance: string[];
  assumptions: string[];
  risks: string[];
  functionalRequirements?: string[];
  nonFunctionalRequirements?: string[];
  engagementType: string;
  baselinePolicy?: BaselinePolicy;
  slices?: SowSlice[];
  targetVersions?: Record<string, string>;
  recommendedTargetLanguage?: RecommendedTargetLanguage;
  likelyUsd?: number | null;
  highUsd?: number | null;
  capUsd?: number | null;
  pricingKnown?: boolean;
  minutesLow?: number;
  minutesHigh?: number;
  rawContract?: Record<string, unknown>;
  launchPrompt: string;
  source?: string;
  degraded?: boolean;
  degradedReason?: string;
  modelProvider?: string | null;
  model?: string | null;
  conversationContext?: PmConversationContext;
  userIntent?: PmConversationContext["user_intent"];
};

export type StructuredClarificationItem = {
  id: string;
  question: string;
  recommended_default: string;
  options: string[];
  impact?: string;
};

export type ClarificationPrompt = {
  questions: string[];
  defaults: string[];
  structured?: StructuredClarificationItem[];
  contract: DisplayFeatureContract;
};

export type ContinuationContext = {
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
  changeOrder?: boolean;
  priorSowId?: string;
  priorCost?: {
    likely_usd?: number | null;
    high_usd?: number | null;
    cap_usd?: number | null;
    pricing_known?: boolean;
  };
};

export type PmConversationContext = {
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
  change_order?: boolean;
  prior_cost?: ContinuationContext["priorCost"];
  prior_mission_id?: string;
};

export type ChatSession = {
  id: string;
  title: string;
  savedAt: string;
  messageCount: number;
  lastPreview?: string;
  messages: ChatMessage[];
  contract?: DisplayFeatureContract | null;
};

export const CHAT_STORAGE_KEY = "mission-control:pm-chat-history";
export const HISTORY_STORAGE_KEY = "mission-control:pm-chat-sessions";
export const MAX_HISTORY_SESSIONS = 30;
export const MAX_CONTEXT_MESSAGES = 12;
export const RASTER_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"] as const;
export const RASTER_IMAGE_MIME_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
  "image/bmp",
]);
