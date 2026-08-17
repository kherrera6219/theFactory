import type {
  BuilderPreviewResponse,
  PmFeatureContractResponse,
  DataClassification,
  DepthMode,
  GatewayHealth,
  MissionBuildArtifactRecord,
  MissionChainTrace,
  LiveStateStreamEvent,
  MissionEvent,
  MissionRecord,
  MissionType,
  OperationsAgentIntegrationsSnapshot,
  OperationsAgentsSnapshot,
  OperationsAlertRecord,
  OperationsAuditEventRecord,
  OperationsAuditReportRecord,
  OperationsLogicNodeRecord,
  OperationsProjectRecord,
  OperationsSummary,
  OutputMode,
  PodAssignmentRecord,
  RepoImportResponse,
  RepoReviewResponse,
  ReviewApprovalReceipt,
  ReviewApprovalVerificationResult,
} from "./types";
import type { LlmUsageSummary } from "./types";
import type {
  BuilderPreviewRequest,
  ErrorResponseBody,
  FactoryErrorPayload,
  MissionCreatePayload,
  MissionStateVaultUpdate,
  OperationsAgentsQuery,
  OperationsLogicNodesQuery,
  PmFeatureContractRequest,
  ProjectAuditEventsQuery,
  RepoIndexRequest,
  RepoIndexResponse,
  RepoReviewRequest,
  ReviewApprovalRequest,
} from "./types/api";

const DEFAULT_TIMEOUT_MS = 10_000;

// Browser and Electron both go through the Next.js /api/gateway proxy so the
// session cookie can inject x-api-key. Talking to :8100 directly 401s because
// the renderer has no operator key. Override only via NEXT_PUBLIC_API_PROXY_BASE_URL.
const getMissionApiBase = () => {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_PROXY_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_PROXY_BASE_URL;
  }
  return "/api/gateway";
};

const missionApiBase = getMissionApiBase();

export class ApiError extends Error {
  statusCode: number;
  // Populated when the backend sends a Local-First standard error payload
  // ({ user_message, recovery_action, error_code }). Absent for plain errors.
  errorCode?: string;
  recoveryAction?: string;

  constructor(
    message: string,
    statusCode: number,
    extra?: { errorCode?: string; recoveryAction?: string },
  ) {
    super(message);
    this.statusCode = statusCode;
    this.errorCode = extra?.errorCode;
    this.recoveryAction = extra?.recoveryAction;
  }
}

type ParsedError = {
  message: string;
  errorCode?: string;
  recoveryAction?: string;
};

function normalizeApiErrorMessage(message: string): ParsedError {
  const normalized = message.trim();
  const lower = normalized.toLowerCase();

  if (lower.includes("x-api-key") || lower.includes("api key")) {
    return {
      message: "Mission Control is not authorized to read live runtime data.",
      recoveryAction:
        "Restart the local runtime stack and confirm INTERNAL_SERVICE_API_KEY is configured consistently for the gateway and orchestrator.",
      errorCode: "MISSION_CONTROL_API_KEY_REQUIRED",
    };
  }

  if (lower.includes("failed to fetch") || lower.includes("gateway is unavailable")) {
    return {
      message: "The local runtime gateway is not reachable.",
      recoveryAction:
        "Start the Docker runtime stack, verify http://localhost:8100/health, then retry.",
      errorCode: "LOCAL_RUNTIME_UNREACHABLE",
    };
  }

  if (lower.includes("orchestrator unavailable")) {
    return {
      message: "The orchestrator service is not reachable.",
      recoveryAction: "Wait for the runtime health checks to settle, then refresh this view.",
      errorCode: "ORCHESTRATOR_UNREACHABLE",
    };
  }

  return { message: normalized };
}

function withTimeout(timeoutMs: number): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  return {
    signal: controller.signal,
    cleanup: () => clearTimeout(timeoutId),
  };
}

function _extractFactoryUserPayload(detail: unknown): ParsedError | null {
  // Local-First standard user payload: { user_message, recovery_action, error_code }.
  if (detail && typeof detail === "object") {
    const candidate = detail as FactoryErrorPayload;
    if (typeof candidate.user_message === "string" && candidate.user_message.trim().length > 0) {
      return {
        message: candidate.user_message,
        errorCode: typeof candidate.error_code === "string" ? candidate.error_code : undefined,
        recoveryAction:
          typeof candidate.recovery_action === "string" ? candidate.recovery_action : undefined,
      };
    }
  }
  return null;
}

function _extractFastApiValidationErrors(detail: unknown): ParsedError | null {
  if (!Array.isArray(detail)) {
    return null;
  }

  const messages = detail
    .map((item) => {
      if (!item || typeof item !== "object") {
        return "";
      }
      const candidate = item as { loc?: unknown; msg?: unknown };
      const path = Array.isArray(candidate.loc)
        ? candidate.loc.map((part) => String(part)).join(".")
        : "";
      const msg = typeof candidate.msg === "string" ? candidate.msg.trim() : "";
      if (!msg) {
        return "";
      }
      return path ? `${path}: ${msg}` : msg;
    })
    .filter(Boolean);

  if (messages.length === 0) {
    return null;
  }

  return {
    message: `Validation failed: ${messages.slice(0, 4).join("; ")}`,
    errorCode: "REQUEST_VALIDATION_FAILED",
    recoveryAction: "Review the highlighted request fields and retry.",
  };
}

async function parseError(response: Response): Promise<ParsedError> {
  try {
    const payload = (await response.json()) as ErrorResponseBody;
    // Structured FactoryError payload may arrive under `detail` or at the top level.
    const structured =
      _extractFactoryUserPayload(payload.detail) ?? _extractFactoryUserPayload(payload);
    if (structured) {
      return structured;
    }
    const validation = _extractFastApiValidationErrors(payload.detail);
    if (validation) {
      return validation;
    }
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return normalizeApiErrorMessage(payload.detail);
    }
    if (
      payload.detail &&
      typeof payload.detail === "object" &&
      "message" in payload.detail &&
      typeof (payload.detail as { message?: unknown }).message === "string"
    ) {
      return normalizeApiErrorMessage((payload.detail as { message: string }).message);
    }
  } catch {
    // ignore
  }

  if (response.status === 429) {
    return { message: "Rate limit exceeded. Retry shortly." };
  }
  if (response.status >= 500) {
    return { message: "Service is temporarily unavailable." };
  }
  return { message: `Request failed with status ${response.status}` };
}

function isAbortOrTimeoutError(error: unknown): boolean {
  if (!error || typeof error !== "object") {
    return false;
  }
  const candidate = error as { name?: unknown; message?: unknown };
  const marker = `${String(candidate.name ?? "")} ${String(candidate.message ?? "")}`.toLowerCase();
  return marker.includes("abort") || marker.includes("timeout") || marker.includes("timed out");
}

export async function fetchJson<T>(input: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...requestInit } = init ?? {};
  const { signal, cleanup } = withTimeout(timeoutMs);
  try {
    const response = await fetch(input, {
      ...requestInit,
      cache: "no-store",
      signal: requestInit.signal ?? signal,
      headers: {
        "Content-Type": "application/json",
        ...(requestInit.headers ?? {}),
      },
    });

    if (!response.ok) {
      const parsed = await parseError(response);
      throw new ApiError(parsed.message, response.status, {
        errorCode: parsed.errorCode,
        recoveryAction: parsed.recoveryAction,
      });
    }
    return (await response.json()) as T;
  } catch (error) {
    if (isAbortOrTimeoutError(error)) {
      throw new ApiError("The local runtime took too long to respond.", 408, {
        errorCode: "LOCAL_RUNTIME_REQUEST_TIMEOUT",
        recoveryAction: "Wait for the runtime to finish warming up, then retry the request.",
      });
    }
    throw error;
  } finally {
    cleanup();
  }
}

export async function fetchFormData<T>(
  input: string,
  formData: FormData,
  init?: Omit<RequestInit, "body" | "headers"> & { timeoutMs?: number; headers?: HeadersInit },
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...requestInit } = init ?? {};
  const { signal, cleanup } = withTimeout(timeoutMs);
  try {
    const response = await fetch(input, {
      ...requestInit,
      method: requestInit.method ?? "POST",
      cache: "no-store",
      signal: requestInit.signal ?? signal,
      headers: requestInit.headers,
      body: formData,
    });

    if (!response.ok) {
      const parsed = await parseError(response);
      throw new ApiError(parsed.message, response.status, {
        errorCode: parsed.errorCode,
        recoveryAction: parsed.recoveryAction,
      });
    }
    return (await response.json()) as T;
  } catch (error) {
    if (isAbortOrTimeoutError(error)) {
      throw new ApiError("The local runtime took too long to respond.", 408, {
        errorCode: "LOCAL_RUNTIME_REQUEST_TIMEOUT",
        recoveryAction: "Wait for the runtime to finish warming up, then retry the request.",
      });
    }
    throw error;
  } finally {
    cleanup();
  }
}

/**
 * Structured, secret-free view of an error for user-facing display, following the
 * Local-First Error Handling Standard §4 (Something went wrong / What happened /
 * What you can do / Error code). Works for ApiError (with or without structured
 * fields) and any other Error or string.
 */
export type DisplayError = {
  whatHappened: string;
  whatYouCanDo: string;
  errorCode?: string;
};

export function toDisplayError(err: unknown): DisplayError {
  if (err instanceof ApiError) {
    return {
      whatHappened: err.message,
      whatYouCanDo: err.recoveryAction ?? "Try again. If the problem persists, retry shortly.",
      errorCode: err.errorCode,
    };
  }
  if (err instanceof Error) {
    return {
      whatHappened: err.message || "An unexpected error occurred.",
      whatYouCanDo: "Try again. If the problem persists, retry shortly.",
    };
  }
  return {
    whatHappened: typeof err === "string" && err ? err : "An unexpected error occurred.",
    whatYouCanDo: "Try again. If the problem persists, retry shortly.",
  };
}

export function missionApiUrl(path: string): string {
    const base = missionApiBase.endsWith("/") ? missionApiBase.slice(0, -1) : missionApiBase;
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    // Collapse /v1/v1 when a custom base already ends with /v1.
    if (base.endsWith("/v1") && cleanPath.startsWith("/v1/")) {
        return `${base}${cleanPath.slice(3)}`;
    }
    return `${base}${cleanPath}`;
}

export function missionStateStreamUrl(params?: {
  missionId?: string;
  includeAgentEvents?: boolean;
}): string {
  const searchParams = new URLSearchParams();
  if (params?.missionId) {
    searchParams.set("mission_id", params.missionId);
  }
  if (params?.includeAgentEvents === false) {
    searchParams.set("include_agent_events", "false");
  }
  const query = searchParams.toString();
  const base = missionApiUrl("/v1/stream/state");
  return query ? `${base}?${query}` : base;
}

export function parseLiveStateStreamMessage(raw: string): LiveStateStreamEvent | null {
  try {
    const parsed = JSON.parse(raw) as LiveStateStreamEvent;
    if (!parsed || typeof parsed !== "object") return null;
    if (typeof parsed.event_type !== "string" || typeof parsed.stream_id !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function buildIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `mission-control-${crypto.randomUUID()}`;
  }
  return `mission-control-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function listMissions(limit: number): Promise<MissionRecord[]> {
  return fetchJson<MissionRecord[]>(missionApiUrl(`/v1/missions?limit=${limit}`));
}

export async function getMission(missionId: string, maxRetries = 3): Promise<MissionRecord> {
  let attempt = 0;
  while (true) {
    try {
      return await fetchJson<MissionRecord>(missionApiUrl(`/v1/missions/${missionId}`));
    } catch (error) {
      if (error instanceof ApiError && error.statusCode === 404 && attempt < maxRetries) {
        attempt++;
        await new Promise((resolve) => setTimeout(resolve, 500 * attempt));
        continue;
      }
      throw error;
    }
  }
}

export async function getMissionEvents(missionId: string, limit: number): Promise<MissionEvent[]> {
  return fetchJson<MissionEvent[]>(missionApiUrl(`/v1/missions/${missionId}/events?limit=${limit}`));
}

export async function getMissionChainTrace(missionId: string): Promise<MissionChainTrace> {
  return fetchJson<MissionChainTrace>(missionApiUrl(`/v1/missions/${missionId}/chain-trace`), { method: "GET" });
}

export async function getMissionBuildArtifact(
  missionId: string,
  artifactId: string,
): Promise<MissionBuildArtifactRecord> {
  return fetchJson<MissionBuildArtifactRecord>(
    missionApiUrl(
      `/v1/missions/${encodeURIComponent(missionId)}/build-artifacts/${encodeURIComponent(artifactId)}`,
    ),
    { method: "GET" },
  );
}

export async function listMissionBuildArtifacts(
  missionId: string,
  limit = 25,
): Promise<MissionBuildArtifactRecord[]> {
  return fetchJson<MissionBuildArtifactRecord[]>(
    missionApiUrl(
      `/v1/missions/${encodeURIComponent(missionId)}/build-artifacts?limit=${encodeURIComponent(String(limit))}`,
    ),
    { method: "GET" },
  );
}

export type MissionOutputFolderStatus = {
  missionId: string;
  path: string;
  exists: boolean;
  fileCount: number;
  totalBytes: number;
  files: Array<{
    path: string;
    sizeBytes: number;
  }>;
  canOpenFolder: boolean;
  canOpenVsCode: boolean;
};

export async function getMissionOutputFolderStatus(
  missionId: string,
): Promise<MissionOutputFolderStatus> {
  const query = new URLSearchParams({ missionId });
  const response = await fetch(`/api/local/output-folder-status?${query.toString()}`, {
    method: "GET",
  });
  const payload = (await response.json().catch(() => ({}))) as MissionOutputFolderStatus & {
    error?: string;
  };
  if (!response.ok) {
    throw new Error(payload.error ?? "Unable to read output folder status.");
  }
  return payload;
}

export async function openMissionOutputFolder(
  missionId: string,
): Promise<{ opened?: boolean; path?: string; error?: string }> {
  const response = await fetch("/api/local/open-output-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ missionId }),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    opened?: boolean;
    path?: string;
    error?: string;
  };
  if (!response.ok) {
    throw new Error(payload.error ?? "Unable to open output folder.");
  }
  return payload;
}

export async function openMissionOutputInVsCode(
  missionId: string,
): Promise<{ opened?: boolean; path?: string; error?: string }> {
  const response = await fetch("/api/local/open-vscode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ missionId }),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    opened?: boolean;
    path?: string;
    error?: string;
  };
  if (!response.ok) {
    throw new Error(payload.error ?? "Unable to open output folder in VS Code.");
  }
  return payload;
}

export async function createMission(payload: MissionCreatePayload): Promise<MissionRecord> {
  return fetchJson<MissionRecord>(missionApiUrl("/v1/missions"), {
    method: "POST",
    headers: { "Idempotency-Key": buildIdempotencyKey() },
    body: JSON.stringify(payload),
  });
}

export async function updateMissionMetadata(
  missionId: string,
  metadata: Record<string, unknown>,
): Promise<MissionRecord> {
  return fetchJson<MissionRecord>(missionApiUrl(`/v1/missions/${encodeURIComponent(missionId)}`), {
    method: "PATCH",
    body: JSON.stringify({ metadata }),
  });
}

export async function updateMissionStateWithVault(
  payload: MissionStateVaultUpdate,
): Promise<MissionRecord> {
  // In Admin Mode, this might be simplified, but keep for compat
  return fetchJson<MissionRecord>("/api/operator/mission-state", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getGatewayHealth(): Promise<GatewayHealth> {
  return fetchJson<GatewayHealth>(missionApiUrl("/health"));
}

export async function getGatewayReadyState(): Promise<{ ready: boolean; detail?: string }> {
  try {
    await fetchJson(missionApiUrl("/readyz"));
    return { ready: true };
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      return { ready: false, detail: error.message };
    }
    return { ready: false, detail: "Readiness check failed." };
  }
}

export async function getOperationsSummary(): Promise<OperationsSummary> {
  return fetchJson<OperationsSummary>(missionApiUrl("/v1/operations/summary"));
}

export async function getOperationsAgents(params?: OperationsAgentsQuery): Promise<OperationsAgentsSnapshot> {
  const searchParams = new URLSearchParams({
    mission_limit: String(params?.missionLimit ?? 1000),
    assignment_limit: String(params?.assignmentLimit ?? 1000),
    event_limit: String(params?.eventLimit ?? 300),
  });
  return fetchJson<OperationsAgentsSnapshot>(missionApiUrl(`/v1/operations/agents?${searchParams.toString()}`));
}

export async function getOperationsAgentIntegrations(): Promise<OperationsAgentIntegrationsSnapshot> {
  return fetchJson<OperationsAgentIntegrationsSnapshot>(missionApiUrl("/v1/operations/agent-integrations"));
}

export async function listOperationsEvents(limit: number): Promise<MissionEvent[]> {
  return fetchJson<MissionEvent[]>(missionApiUrl(`/v1/operations/events?limit=${limit}`));
}

export async function listOperationsLogicNodes(params: OperationsLogicNodesQuery): Promise<OperationsLogicNodeRecord[]> {
  const searchParams = new URLSearchParams({ limit: String(params.limit) });
  if (params.missionId) searchParams.set("mission_id", params.missionId);
  return fetchJson<OperationsLogicNodeRecord[]>(missionApiUrl(`/v1/operations/logicnodes?${searchParams.toString()}`));
}

export async function listOperationsPodAssignments(limit: number): Promise<PodAssignmentRecord[]> {
  return fetchJson<PodAssignmentRecord[]>(missionApiUrl(`/v1/operations/pod-assignments?limit=${limit}`));
}

export async function listOperationsProjects(limit: number): Promise<OperationsProjectRecord[]> {
  return fetchJson<OperationsProjectRecord[]>(missionApiUrl(`/v1/operations/projects?limit=${limit}`));
}

export async function listProjectAuditEvents(params: ProjectAuditEventsQuery): Promise<OperationsAuditEventRecord[]> {
  const searchParams = new URLSearchParams({ limit: String(params.limit) });
  if (params.missionId) searchParams.set("mission_id", params.missionId);
  return fetchJson<OperationsAuditEventRecord[]>(missionApiUrl(`/v1/operations/projects/${params.projectId}/audit-events?${searchParams.toString()}`));
}

export async function listOperationsAlerts(limit: number): Promise<OperationsAlertRecord[]> {
  return fetchJson<OperationsAlertRecord[]>(missionApiUrl(`/v1/operations/alerts?limit=${limit}`));
}

export async function updateAlertState(
  alertId: string,
  state: "acknowledged" | "resolved",
): Promise<{ alert_id: string; state: string }> {
  return fetchJson<{ alert_id: string; state: string }>(
    missionApiUrl(`/v1/operations/alerts/${encodeURIComponent(alertId)}/state`),
    {
      method: "POST",
      body: JSON.stringify({ state }),
    },
  );
}

export async function listMissionAuditReports(missionId: string, limit = 50): Promise<OperationsAuditReportRecord[]> {
  return fetchJson<OperationsAuditReportRecord[]>(missionApiUrl(`/v1/missions/${missionId}/audit-reports?limit=${limit}`));
}

export async function listMissionAuditEvents(missionId: string, limit = 100): Promise<OperationsAuditEventRecord[]> {
  return fetchJson<OperationsAuditEventRecord[]>(missionApiUrl(`/v1/missions/${missionId}/audit-events?limit=${limit}`));
}

export async function createBuilderPreview(payload: BuilderPreviewRequest): Promise<BuilderPreviewResponse> {
  const {
    viewMode,
    requestedTargetLanguage,
    ...rest
  } = payload as BuilderPreviewRequest & {
    viewMode?: unknown;
    requestedTargetLanguage?: unknown;
  };
  const normalizedPayload = {
    ...rest,
    ...(rest.view_mode === undefined && typeof viewMode === "string" ? { view_mode: viewMode } : {}),
    ...(rest.requested_target_language === undefined && typeof requestedTargetLanguage === "string"
      ? { requested_target_language: requestedTargetLanguage }
      : {}),
  };

  return fetchJson<BuilderPreviewResponse>(missionApiUrl("/v1/builder/preview"), {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(normalizedPayload),
  });
}

export async function createPmFeatureContract(payload: PmFeatureContractRequest): Promise<PmFeatureContractResponse> {
  const { requestedTargetLanguage, ...rest } = payload as PmFeatureContractRequest & {
    requestedTargetLanguage?: unknown;
  };
  const normalizedPayload = {
    ...rest,
    ...(rest.requested_target_language === undefined && typeof requestedTargetLanguage === "string"
      ? { requested_target_language: requestedTargetLanguage }
      : {}),
  };

  return fetchJson<PmFeatureContractResponse>("/api/pm/feature-contract", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(normalizedPayload),
  });
}

export async function createBuilderWorkspaceReview(payload: {
  request: string;
  constraints?: string[];
  viewMode?: string;
}): Promise<BuilderPreviewResponse> {
  return fetchJson<BuilderPreviewResponse>("/api/builder/review", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify({
      request: payload.request,
      constraints: payload.constraints,
      view_mode: payload.viewMode,
    }),
  });
}

export async function createRepoReview(payload: RepoReviewRequest): Promise<RepoReviewResponse> {
  return fetchJson<RepoReviewResponse>("/api/repo/review", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function importRepoZip(formData: FormData): Promise<RepoImportResponse> {
  return fetchFormData<RepoImportResponse>("/api/repo/import", formData, {
    timeoutMs: 30_000,
  });
}

export async function createRepoZipReview(formData: FormData): Promise<RepoReviewResponse> {
  return fetchFormData<RepoReviewResponse>("/api/repo/review", formData, {
    timeoutMs: 30_000,
  });
}

export async function indexRepoImport(payload: RepoIndexRequest): Promise<RepoIndexResponse> {
  return fetchJson<RepoIndexResponse>("/api/repo/index", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function approveReviewArtifact(payload: ReviewApprovalRequest): Promise<ReviewApprovalReceipt> {
  return fetchJson<ReviewApprovalReceipt>("/api/review/approve", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function verifyReviewApproval(payload: {
  scope: string;
  approvalId: string;
  fingerprint: string;
  receiptDigest: string;
}): Promise<ReviewApprovalVerificationResult> {
  return fetchJson<ReviewApprovalVerificationResult>("/api/review/verify", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify({
      scope: payload.scope,
      approval_id: payload.approvalId,
      fingerprint: payload.fingerprint,
      receipt_digest: payload.receiptDigest,
    }),
  });
}

export async function getMissionTokenUsage(missionId: string): Promise<LlmUsageSummary | null> {
  try {
    return await fetchJson<LlmUsageSummary>(missionApiUrl(`/v1/missions/${encodeURIComponent(missionId)}/token-usage`));
  } catch {
    return null;
  }
}

export async function createDiagnosticBundle(missionId?: string): Promise<{ bundle_path: string }> {
  const url = missionId 
    ? missionApiUrl(`/v1/maintenance/diagnostics?mission_id=${encodeURIComponent(missionId)}`)
    : missionApiUrl("/v1/maintenance/diagnostics");
  return fetchJson(url, { method: "POST" });
}

export async function triggerBackup(): Promise<{ backup_path: string }> {
  return fetchJson(missionApiUrl("/v1/maintenance/backup"), { method: "POST" });
}
