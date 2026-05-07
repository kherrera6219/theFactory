import type {
  BuilderPreviewResponse,
  DataClassification,
  DepthMode,
  GatewayHealth,
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
  RepoReviewResponse,
  ReviewApprovalReceipt,
  ReviewApprovalVerificationResult,
} from "./types";

const DEFAULT_TIMEOUT_MS = 10_000;
const missionApiBase = process.env.NEXT_PUBLIC_API_PROXY_BASE_URL ?? "/api/gateway";

export class ApiError extends Error {
  statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.statusCode = statusCode;
  }
}

function withTimeout(timeoutMs: number): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  return {
    signal: controller.signal,
    cleanup: () => clearTimeout(timeoutId),
  };
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail;
    }
    if (
      payload.detail &&
      typeof payload.detail === "object" &&
      "message" in payload.detail &&
      typeof payload.detail.message === "string"
    ) {
      return payload.detail.message;
    }
  } catch {
    // Use default error text if JSON parse fails.
  }

  if (response.status === 429) {
    return "Rate limit exceeded. Retry shortly.";
  }
  if (response.status >= 500) {
    return "Service is temporarily unavailable.";
  }
  return `Request failed with status ${response.status}`;
}

type FetchJsonInit = RequestInit & {
  timeoutMs?: number;
};

export async function fetchJson<T>(input: string, init?: FetchJsonInit): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...requestInit } = init ?? {};
  const timeout = requestInit.signal ? null : withTimeout(timeoutMs);
  try {
    const response = await fetch(input, {
      ...requestInit,
      signal: requestInit.signal ?? timeout?.signal,
      headers: {
        "Content-Type": "application/json",
        ...(requestInit.headers ?? {}),
      },
      cache: "no-store",
    });

    if (!response.ok) {
      throw new ApiError(await parseError(response), response.status);
    }
    const payload = (await response.json()) as T & {
      __gateway_error?: boolean;
      detail?: string;
      status?: number;
    };
    if (payload.__gateway_error) {
      throw new ApiError(payload.detail ?? "Local runtime gateway is unavailable.", payload.status ?? 503);
    }
    return payload as T;
  } finally {
    timeout?.cleanup();
  }
}

export function missionApiUrl(path: string): string {
  return `${missionApiBase}${path}`;
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
  if (!query) {
    return missionApiUrl("/v1/stream/state");
  }
  return missionApiUrl(`/v1/stream/state?${query}`);
}

export function parseLiveStateStreamMessage(raw: string): LiveStateStreamEvent | null {
  try {
    const parsed = JSON.parse(raw) as LiveStateStreamEvent;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    if (typeof parsed.event_type !== "string" || typeof parsed.stream_id !== "string") {
      return null;
    }
    if (!parsed.payload || typeof parsed.payload !== "object") {
      return null;
    }
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
  return fetchJson<MissionRecord[]>(missionApiUrl(`/v1/missions?limit=${limit}`), { method: "GET" });
}

export async function getMission(missionId: string, maxRetries = 3): Promise<MissionRecord> {
  let attempt = 0;
  while (true) {
    try {
      return await fetchJson<MissionRecord>(missionApiUrl(`/v1/missions/${missionId}`), { method: "GET" });
    } catch (error) {
      if (error instanceof ApiError && error.statusCode === 404 && attempt < maxRetries) {
        attempt++;
        // Defensive retry for short-lived propagation gaps after mission creation
        await new Promise((resolve) => setTimeout(resolve, 500 * attempt));
        continue;
      }
      throw error;
    }
  }
}

export async function getMissionEvents(missionId: string, limit: number): Promise<MissionEvent[]> {
  return fetchJson<MissionEvent[]>(missionApiUrl(`/v1/missions/${missionId}/events?limit=${limit}`), {
    method: "GET",
  });
}

export async function getMissionChainTrace(missionId: string): Promise<MissionChainTrace> {
  return fetchJson<MissionChainTrace>(missionApiUrl(`/v1/missions/${missionId}/chain-trace`), {
    method: "GET",
  });
}

export async function createMission(payload: {
  prompt: string;
  requested_target_language: string | null;
  mission_type?: MissionType | null;
  depth_mode?: DepthMode | null;
  output_mode?: OutputMode | null;
  data_classification?: DataClassification | null;
  source_code?: string;
  metadata: Record<string, unknown>;
}): Promise<MissionRecord> {
  return fetchJson<MissionRecord>(missionApiUrl("/v1/missions"), {
    method: "POST",
    headers: {
      "Idempotency-Key": buildIdempotencyKey(),
    },
    body: JSON.stringify(payload),
  });
}

export async function updateMissionStateWithVault(payload: {
  missionId: string;
  newState: string;
  expectedState?: string;
}): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/operator/mission-state", {
    method: "POST",
    body: JSON.stringify({
      mission_id: payload.missionId,
      new_state: payload.newState,
      expected_state: payload.expectedState,
    }),
  });
}

export async function getGatewayHealth(): Promise<GatewayHealth> {
  return fetchJson<GatewayHealth>(missionApiUrl("/health"), { method: "GET" });
}

export async function getGatewayReadyState(): Promise<{ ready: boolean; detail?: string }> {
  try {
    await fetchJson<Record<string, unknown>>(missionApiUrl("/readyz"), { method: "GET" });
    return { ready: true };
  } catch (error) {
    if (error instanceof ApiError) {
      return { ready: false, detail: error.message };
    }
    return { ready: false, detail: "Readiness check failed." };
  }
}

export async function getOperationsSummary(): Promise<OperationsSummary> {
  return fetchJson<OperationsSummary>(missionApiUrl("/v1/operations/summary"), { method: "GET" });
}

export async function getOperationsAgents(params?: {
  missionLimit?: number;
  assignmentLimit?: number;
  eventLimit?: number;
}): Promise<OperationsAgentsSnapshot> {
  const searchParams = new URLSearchParams({
    mission_limit: String(params?.missionLimit ?? 1000),
    assignment_limit: String(params?.assignmentLimit ?? 1000),
    event_limit: String(params?.eventLimit ?? 300),
  });
  return fetchJson<OperationsAgentsSnapshot>(
    missionApiUrl(`/v1/operations/agents?${searchParams.toString()}`),
    { method: "GET" },
  );
}

export async function getOperationsAgentIntegrations(): Promise<OperationsAgentIntegrationsSnapshot> {
  return fetchJson<OperationsAgentIntegrationsSnapshot>(
    missionApiUrl("/v1/operations/agent-integrations"),
    { method: "GET" },
  );
}

export async function listOperationsEvents(limit: number): Promise<MissionEvent[]> {
  return fetchJson<MissionEvent[]>(missionApiUrl(`/v1/operations/events?limit=${limit}`), {
    method: "GET",
  });
}

export async function listOperationsLogicNodes(params: {
  limit: number;
  missionId?: string;
}): Promise<OperationsLogicNodeRecord[]> {
  const searchParams = new URLSearchParams({ limit: String(params.limit) });
  if (params.missionId) {
    searchParams.set("mission_id", params.missionId);
  }
  return fetchJson<OperationsLogicNodeRecord[]>(
    missionApiUrl(`/v1/operations/logicnodes?${searchParams.toString()}`),
    {
      method: "GET",
    },
  );
}

export async function listOperationsPodAssignments(limit: number): Promise<PodAssignmentRecord[]> {
  return fetchJson<PodAssignmentRecord[]>(
    missionApiUrl(`/v1/operations/pod-assignments?limit=${limit}`),
    { method: "GET" },
  );
}

export async function listOperationsProjects(limit: number): Promise<OperationsProjectRecord[]> {
  return fetchJson<OperationsProjectRecord[]>(missionApiUrl(`/v1/operations/projects?limit=${limit}`), {
    method: "GET",
  });
}

export async function listProjectAuditEvents(params: {
  projectId: string;
  limit: number;
  missionId?: string;
  agentId?: string;
  toolName?: string;
}): Promise<OperationsAuditEventRecord[]> {
  const searchParams = new URLSearchParams({ limit: String(params.limit) });
  if (params.missionId) {
    searchParams.set("mission_id", params.missionId);
  }
  if (params.agentId) {
    searchParams.set("agent_id", params.agentId);
  }
  if (params.toolName) {
    searchParams.set("tool_name", params.toolName);
  }
  return fetchJson<OperationsAuditEventRecord[]>(
    missionApiUrl(`/v1/operations/projects/${params.projectId}/audit-events?${searchParams.toString()}`),
    { method: "GET" },
  );
}

export async function listOperationsAlerts(limit: number): Promise<OperationsAlertRecord[]> {
  return fetchJson<OperationsAlertRecord[]>(missionApiUrl(`/v1/operations/alerts?limit=${limit}`), {
    method: "GET",
  });
}

export async function listMissionAuditReports(
  missionId: string,
  limit = 50,
): Promise<OperationsAuditReportRecord[]> {
  return fetchJson<OperationsAuditReportRecord[]>(
    missionApiUrl(`/v1/missions/${missionId}/audit-reports?limit=${limit}`),
    { method: "GET" },
  );
}

export async function listMissionAuditEvents(
  missionId: string,
  limit = 100,
): Promise<OperationsAuditEventRecord[]> {
  return fetchJson<OperationsAuditEventRecord[]>(
    missionApiUrl(`/v1/missions/${missionId}/audit-events?limit=${limit}`),
    { method: "GET" },
  );
}

export async function createBuilderPreview(payload: {
  request: string;
  constraints: string[];
  viewMode?: "desktop" | "tablet" | "mobile";
}): Promise<BuilderPreviewResponse> {
  return fetchJson<BuilderPreviewResponse>(missionApiUrl("/v1/builder/preview"), {
    method: "POST",
    body: JSON.stringify({
      request: payload.request,
      constraints: payload.constraints,
      view_mode: payload.viewMode,
    }),
  });
}

export async function createBuilderWorkspaceReview(payload: {
  request: string;
  constraints: string[];
  viewMode?: "desktop" | "tablet" | "mobile";
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

export async function createRepoReview(payload: {
  repo_url: string;
  branch: string;
  subdirectory: string;
  mission_type: "analyze" | "update" | "add_feature" | "refactor";
  description: string;
  selected_files: Array<{
    path: string;
    overlay_action: "include" | "reference";
    language: string;
    bytes: number;
    estimated_lines: number;
  }>;
}): Promise<RepoReviewResponse> {
  return fetchJson<RepoReviewResponse>("/api/repo/review", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function approveReviewArtifact(payload: {
  scope: "builder" | "repo";
  fingerprint: string;
  summary: string;
  metadata?: Record<string, unknown>;
}): Promise<ReviewApprovalReceipt> {
  return fetchJson<ReviewApprovalReceipt>("/api/review/approve", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function verifyReviewApproval(payload: {
  scope: "builder" | "repo";
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
