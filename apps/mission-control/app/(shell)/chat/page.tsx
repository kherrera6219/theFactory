"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { PageHeader } from "../../components/page-header";
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
import { inferRequestedTargetLanguage } from "../../lib/language";
import { fitConversationContext } from "../../lib/mission-metadata-budget";
import { operatorRecoveryMessage } from "../../lib/operator-auth-error";
import { sanitizeUserText } from "../../lib/security";
import type { RepoReviewResponse } from "../../lib/types";

import {
  type ChatMessage,
  type ChatSession,
  type ClarificationPrompt,
  type ContinuationContext,
  type DisplayFeatureContract,
  type PmConversationContext,
  CHAT_STORAGE_KEY,
  HISTORY_STORAGE_KEY,
  MAX_HISTORY_SESSIONS,
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
  deriveTitle,
  detectLanguages,
  detectUserIntent,
  emptySowFields,
  errorMessage,
  extractDecisionMemory,
  formatFactoryTime,
  initialWelcomeMessage,
  isBinaryFile,
  makeId,
  safeFileName,
  summarizeScope,
} from "./chat-helpers";
import { ChatSidebar } from "./components/ChatSidebar";
import { ChatConversationList } from "./components/ChatConversationList";
import { ChatInputArea } from "./components/ChatInputArea";
import { ChatClarificationPanel } from "./components/ChatClarificationPanel";
import { ChatSowSection } from "./components/ChatSowSection";

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
        <ChatSidebar
          groupedSessions={groupedSessions}
          activeSessionId={activeSessionId}
          resetConversation={resetConversation}
          loadSession={loadSession}
        />

        <div className="chat-main">
          <ChatConversationList messages={messages} thinking={thinking} />

          <ChatInputArea
            input={input}
            setInput={setInput}
            files={files}
            addFiles={addFiles}
            repoImporting={repoImporting}
            repoImport={repoImport}
            preferredOfficialType={preferredOfficialType}
            importAttachedZip={importAttachedZip}
            sendMessage={sendMessage}
            thinking={thinking}
            launching={launching}
            error={error}
          />

          {clarificationPrompt && (
            <ChatClarificationPanel
              clarificationPrompt={clarificationPrompt}
              handleProceedWithClarificationDefaults={handleProceedWithClarificationDefaults}
              handleEditClarificationAnswers={handleEditClarificationAnswers}
              thinking={thinking}
              launching={launching}
            />
          )}

          <ChatSowSection
            contract={contract}
            hasClarificationPrompt={Boolean(clarificationPrompt)}
            continuationContext={continuationContext}
            launching={launching}
            confirmAndLaunch={confirmAndLaunch}
            setContract={setContract}
          />
        </div>
      </div>
    </div>
  );
}

