"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { OperatorAuthErrorAction } from "../../components/operator-auth-error-action";
import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, SystemMessage } from "../../components/status";
import {
  createApprovedSow,
  createBuilderPreview,
  createMission,
  createPmFeatureContract,
  createRepoZipReview,
  getMission,
  getMissionChainTrace,
  getMissionOutputFolderStatus,
  importRepoZip,
  indexRepoImport,
  listMissionBuildArtifacts,
  type MissionOutputFolderStatus,
} from "../../lib/api-client";
import {
  REPO_HANDOFF_STORAGE_KEY,
  isProjectZipFile,
  officialMissionTypeFromIntent,
  officialMissionTypeFromRepoChoice,
  parseRepoPmHandoff,
  type OfficialFactoryMissionType,
} from "../../lib/chat-repo-import";
import { pruneExpiredSessions } from "../../lib/chat-session-retention";
import { formatDateTime } from "../../lib/format";
import { inferRequestedTargetLanguage } from "../../lib/language";
import { fitConversationContext } from "../../lib/mission-metadata-budget";
import { operatorRecoveryMessage } from "../../lib/operator-auth-error";
import { sanitizeUserText } from "../../lib/security";
import type { RepoReviewResponse } from "../../lib/types";

import {
  type ChatMessage,
  type ChatRole,
  type ChatSession,
  type ClarificationPrompt,
  type ContinuationContext,
  type DisplayFeatureContract,
  type PmConversationContext,
  CHAT_STORAGE_KEY,
  HISTORY_STORAGE_KEY,
  MAX_CONTEXT_MESSAGES,
  MAX_HISTORY_SESSIONS,
  RASTER_IMAGE_EXTENSIONS,
  RASTER_IMAGE_MIME_TYPES,
} from "./chat-types";
import {
  artifactFilename,
  buildClarificationPrompt,
  buildFullLaunchPrompt,
  buildPmConversationContext,
  buildSession,
  clarificationAnswersText,
  clarificationEditTemplate,
  compactLaunchConversationContext,
  continuationPromptText,
  contractSourceLabel,
  derivePreview,
  deriveTitle,
  detectLanguages,
  detectUserIntent,
  emptySowFields,
  errorMessage,
  extractDecisionMemory,
  fileLabel,
  formatFactoryTime,
  initialWelcomeMessage,
  isBinaryFile,
  isDegradedContract,
  isRasterImageFile,
  makeId,
  recommendedDefaultFromQuestion,
  safeFileName,
  summarizeScope,
} from "./chat-helpers";

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

export default function ChatPage() {
  const router = useRouter();
  const continueMissionRef = useRef<string | null>(null);
  const repoHandoffRef = useRef<string | null>(null);
  const zipArchiveRef = useRef<File | null>(null);
  const repoImportRef = useRef<RepoReviewResponse | null>(null);
  const [continuationContext, setContinuationContext] = useState<ContinuationContext | null>(null);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [repoImport, setRepoImport] = useState<RepoReviewResponse | null>(null);
  const [repoImporting, setRepoImporting] = useState(false);
  const [preferredOfficialType, setPreferredOfficialType] = useState<OfficialFactoryMissionType | null>(null);
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
        const priorContract = chainTrace?.feature_contract;
        const priorCost = priorContract?.cost_estimate;
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
          changeOrder: true,
          priorSowId: typeof mission.metadata?.sow_id === "string" ? mission.metadata.sow_id : undefined,
          priorCost: priorCost
            ? {
                likely_usd: priorCost.likely_usd,
                high_usd: priorCost.high_usd,
                cap_usd: priorCost.cap_usd,
                pricing_known: priorCost.pricing_known,
              }
            : undefined,
        };
        setContinuationContext(context);
        setMessages([
          initialWelcomeMessage(),
          {
            id: makeId("pm-continue"),
            role: "pm",
            text:
              `Continuing mission ${continueMissionId} (${missionName}) as a change order. ` +
              "I loaded the prior output and the last factory quote so we can scope the delta before you accept a new SOW.",
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
          changeOrder: true,
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
    if (typeof window === "undefined") {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    if (params.get("fromRepo") !== "1") {
      return;
    }
    const raw = window.sessionStorage.getItem(REPO_HANDOFF_STORAGE_KEY);
    const parsed = parseRepoPmHandoff(raw);
    if (!parsed) {
      return;
    }
    const handoffKey = `${parsed.review.repository.archive_id}:${parsed.officialMissionType}`;
    if (repoHandoffRef.current === handoffKey) {
      return;
    }
    repoHandoffRef.current = handoffKey;
    repoImportRef.current = parsed.review;
    setRepoImport(parsed.review);
    setPreferredOfficialType(parsed.officialMissionType);
    const description =
      parsed.description.trim() ||
      `Draft a Statement of Work to ${parsed.officialMissionType} the imported project ${parsed.review.repository.display_name}.`;
    setMessages([
      initialWelcomeMessage(),
      {
        id: makeId("pm-repo"),
        role: "pm",
        text:
          `I have the reviewed ZIP for ${parsed.review.repository.display_name} ` +
          `(${parsed.review.source_stats.bundled_files} bundled files). ` +
          `Recommended engagement: ${parsed.officialMissionType}. I will draft the SOW next.`,
        ts: new Date().toISOString(),
      },
    ]);
    setInput(description);
    void sendMessage(description);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
  }, [messages]);

  // Load persistent session list from localStorage, dropping any session
  // older than MAX_SESSION_AGE_DAYS so old full-text transcripts don't
  // accumulate indefinitely just because the 30-session cap was never hit.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(HISTORY_STORAGE_KEY);
      if (raw) {
        const fresh = pruneExpiredSessions(JSON.parse(raw) as ChatSession[]);
        setSessions(fresh);
        window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(fresh));
      }
    } catch { /* ignore malformed data */ }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!messages.some((message) => message.role === "user")) return;

    const id = activeSessionId ?? makeId("session");
    const session = buildSession(messages, id, contract);

    setSessions((current) => {
      const updated = pruneExpiredSessions(
        [session, ...current.filter((item) => item.id !== id)],
      ).slice(0, MAX_HISTORY_SESSIONS);
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
    const fresh = pruneExpiredSessions(updated);
    setSessions(fresh);
    try {
      window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(fresh));
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
    repoImportRef.current = null;
    setRepoImport(null);
    setPreferredOfficialType(null);
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
    repoImportRef.current = null;
    setRepoImport(null);
    setPreferredOfficialType(null);
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
    const zip = incoming.find((file) => isProjectZipFile(file));
    const rest = incoming.filter((file) => !isProjectZipFile(file));
    if (rest.length > 0) {
      setFiles((current) => [...current, ...rest].slice(0, 20));
    }
    if (zip) {
      void importAttachedZip(zip);
    }
  }

  async function importAttachedZip(archiveFile: File) {
    setRepoImporting(true);
    setError(null);
    zipArchiveRef.current = archiveFile;
    try {
      const importData = new FormData();
      importData.set("archive", archiveFile);
      importData.set("display_name", sanitizeUserText(archiveFile.name.replace(/\.zip$/i, "")));
      importData.set("source_ref", "main");
      importData.set("subdirectory", "/");
      const imported = await importRepoZip(importData);
      const selected = imported.files.slice(0, 120).map((file) => ({
        path: file.path,
        overlay_action: "include" as const,
        language: file.language,
        bytes: file.bytes,
        estimated_lines: file.estimated_lines,
      }));
      if (selected.length === 0) {
        throw new Error("The ZIP did not contain any reviewable source files.");
      }
      const reviewData = new FormData();
      reviewData.set("archive", archiveFile);
      reviewData.set("display_name", imported.repository.display_name);
      reviewData.set("source_ref", imported.repository.source_ref);
      reviewData.set("subdirectory", imported.stats.selected_subdirectory || "/");
      reviewData.set("archive_sha256", imported.repository.archive_sha256);
      reviewData.set("mission_type", "update");
      reviewData.set("description", "Imported through PM chat");
      reviewData.set("selected_files", JSON.stringify(selected));
      const review = await createRepoZipReview(reviewData);
      repoImportRef.current = review;
      setRepoImport(review);
      setPreferredOfficialType((current) => current ?? "IMPORT_MODERNIZE");
      setMessages((current) => [
        ...current,
        {
          id: makeId("pm-zip"),
          role: "pm",
          text:
            `Imported ${review.repository.display_name}: ${review.source_stats.bundled_files} files ready for the SOW. ` +
            "Tell me whether this is a rework, port, update, or analysis.",
          ts: new Date().toISOString(),
        },
      ]);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "Unable to import project ZIP.");
      repoImportRef.current = null;
      setRepoImport(null);
    } finally {
      setRepoImporting(false);
    }
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

      const sourceCode =
        repoImportRef.current?.source_code || (await readFilesAsText(files));
      const detected = detectLanguages(files);
      const conversationContext = buildPmConversationContext({
        messages,
        nextUserMessage,
        contract: contextContract,
        files,
        continuation: continuationContext,
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
          estimatedDuration: formatFactoryTime(featureContract),
          outOfScope: featureContract.out_of_scope ?? [],
          deliverables: (featureContract.deliverables ?? []).map((item) =>
            typeof item === "string" ? item : item.name,
          ),
          acceptance: featureContract.acceptance_criteria ?? [],
          assumptions: featureContract.assumptions ?? [],
          risks: featureContract.risk_notes ?? [],
          engagementType:
            officialMissionTypeFromRepoChoice(
              featureContract.engagement_type ||
                preferredOfficialType ||
                (repoImportRef.current
                  ? officialMissionTypeFromIntent(normalized)
                  : "BUILD_NEW"),
            ),
          likelyUsd: featureContract.cost_estimate?.likely_usd,
          highUsd: featureContract.cost_estimate?.high_usd,
          capUsd: featureContract.cost_estimate?.cap_usd,
          pricingKnown: featureContract.cost_estimate?.pricing_known,
          minutesLow: featureContract.cost_estimate?.estimated_minutes_low
            ?? featureContract.timeline?.estimated_minutes_low,
          minutesHigh: featureContract.cost_estimate?.estimated_minutes_high
            ?? featureContract.timeline?.estimated_minutes_high,
          rawContract: featureContract as unknown as Record<string, unknown>,
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
          estimatedDuration: formatFactoryTime({}),
          ...emptySowFields(),
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
    const readable = fileList.filter((file) => !isProjectZipFile(file));
    if (readable.length === 0) {
      return repoImportRef.current?.source_code ?? "";
    }
    const parts = await Promise.all(
      readable.map(
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
      const imported = repoImportRef.current;
      const sourceCode = imported?.source_code || (await readFilesAsText(files));
      const officialType = officialMissionTypeFromRepoChoice(
        launchContract.engagementType || preferredOfficialType || (imported ? "IMPORT_MODERNIZE" : "BUILD_NEW"),
      );
      const requestedTargetLanguage = inferRequestedTargetLanguage({
        prompt: launchContract.launchPrompt,
        filePaths: [
          ...files.map((file) => file.name),
          ...(imported?.files.map((file) => file.path) ?? []),
        ],
        contractLanguages: launchContract.languages,
      });
      const compactedContext = compactLaunchConversationContext(
        launchContract.conversationContext,
        launchContract,
      );
      // The gateway rejects the whole request with 422 when serialized metadata
      // exceeds 4096 bytes. Per-field caps above allow far more than that, so
      // budget the assembled object and shed context until it actually fits —
      // otherwise a thorough PM clarification makes the mission unlaunchable.
      let sowId: string | undefined;
      if (launchContract.rawContract) {
        const approved = await createApprovedSow({
          feature_contract: launchContract.rawContract,
          approved_by: "operator",
          unpriced_ack: launchContract.pricingKnown === false,
        });
        sowId = approved.sow_id;
      }
      const { metadata: launchMetadata } = fitConversationContext(
        compactedContext,
        (conversationContext) => ({
          source: "mission-control-chat",
          attached_files: files.map((item) => safeFileName(item)),
          inferred_requested_target_language: requestedTargetLanguage,
          conversation_context: conversationContext,
          user_intent: "finalize_plan",
          sow_id: sowId,
          mission_type: officialType,
          launch_confirmed_at: new Date().toISOString(),
          launch_source: "feature-contract-confirmation",
          continued_from_mission_id: continueMissionRef.current,
          change_order: continueMissionRef.current
            ? {
                prior_mission_id: continueMissionRef.current,
                prior_sow_id: continuationContext?.priorSowId,
                prior_likely_usd: continuationContext?.priorCost?.likely_usd,
                prior_cap_usd: continuationContext?.priorCost?.cap_usd,
              }
            : undefined,
          repo_import: imported
            ? {
                source: "repo_zip_import",
                import_id: imported.repository.archive_id,
                archive_sha256: imported.repository.archive_sha256,
                index_required: true,
                index_status: "pending",
              }
            : undefined,
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
        }),
      );
      const mission = await createMission({
        prompt: launchContract.launchPrompt,
        requested_target_language: requestedTargetLanguage,
        mission_type: officialType,
        source_code: sourceCode || undefined,
        metadata: launchMetadata,
      });
      if (imported) {
        try {
          await indexRepoImport({
            mission_id: mission.mission_id,
            import_id: imported.repository.archive_id,
            archive_sha256: imported.repository.archive_sha256,
            display_name: imported.repository.display_name,
            source_ref: imported.repository.source_ref,
            files: imported.files
              .filter((file) => file.text_available)
              .map((file) => ({
                path: file.path,
                language: file.language,
                content_excerpt: file.content_excerpt,
                bytes: file.bytes,
                estimated_lines: file.estimated_lines,
                sha: file.sha,
                overlay_action: file.overlay_action,
              })),
          });
        } catch (indexError) {
          setError(
            `Mission launched, but repository indexing failed: ${
              indexError instanceof Error ? indexError.message : "unknown error"
            }. PM intake may stay paused until indexing succeeds.`,
          );
        }
      }
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
        description="Describe new work or attach a project ZIP to rework, port, or update existing software. Accept the Statement of Work before the factory starts."
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
          Drag and drop files here, or attach a project ZIP to import existing software.
        </div>
        <label className="file-input-label">
          <span>Choose files</span>
          <input
            type="file"
            multiple
            accept=".zip,application/zip,text/plain,text/*,.py,.js,.ts,.go,.rs,.java"
            className="sr-only"
            aria-label="Choose files or a project ZIP to attach"
            onChange={(event) => {
              if (event.target.files) {
                addFiles(event.target.files);
              }
            }}
          />
        </label>
        <label className="file-input-label" style={{ marginLeft: "8px" }}>
          <span>{repoImporting ? "Importing ZIP..." : "Attach project (ZIP)"}</span>
          <input
            type="file"
            accept=".zip,application/zip"
            className="sr-only"
            aria-label="Attach a project ZIP for rework, port, or update"
            disabled={repoImporting || launching}
            onChange={(event) => {
              const zip = event.target.files?.[0];
              if (zip) {
                void importAttachedZip(zip);
              }
              event.currentTarget.value = "";
            }}
          />
        </label>
        {repoImport && (
          <p className="muted" style={{ marginTop: "8px" }}>
            Imported project: {repoImport.repository.display_name} · {repoImport.source_stats.bundled_files} files
            {preferredOfficialType ? ` · ${preferredOfficialType}` : ""}
          </p>
        )}
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
            <OperatorAuthErrorAction error={error} />
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
        <Panel title={continuationContext?.changeOrder ? "Change order" : "Statement of Work"}>
          {!editingContract && (
            <>
              {isDegradedContract(contract) && (
                <SystemMessage tone="warning" title="Fallback planning output">
                  <p>
                    This SOW was generated without a confirmed live PM model response
                    ({contractSourceLabel(contract)}). Treat it as degraded planning output
                    until provider/key configuration is verified.
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
                  <dd>{contract.outOfScope.length ? contract.outOfScope.join("; ") : "PM must name at least one exclusion"}</dd>
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

