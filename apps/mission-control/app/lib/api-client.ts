import { isElectron } from "./electron-bridge";
import type {
  BuilderPreviewResponse,
  PmFeatureContractResponse,
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

// 7E — In Electron, talk directly to the local API Gateway.
// In the browser, proxy through Next.js /api/gateway.
const getMissionApiBase = () => {
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_PROXY_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_PROXY_BASE_URL;
  }
  if (isElectron()) {
    return "http://localhost:8100/v1";
  }
  return "/api/gateway";
};

const missionApiBase = getMissionApiBase();

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
      typeof (payload.detail as any).message === "string"
    ) {
      return (payload.detail as any).message;
    }
  } catch {
    // ignore
  }

  if (response.status === 429) {
    return "Rate limit exceeded. Retry shortly.";
  }
  if (response.status >= 500) {
    return "Service is temporarily unavailable.";
  }
  return `Request failed with status ${response.status}`;
}

export async function fetchJson<T>(input: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...requestInit } = init ?? {};
  const { signal, cleanup } = withTimeout(timeoutMs);
  try {
    const response = await fetch(input, {
      ...requestInit,
      signal: requestInit.signal ?? signal,
      headers: {
        "Content-Type": "application/json",
        ...(requestInit.headers ?? {}),
      },
    });

    if (!response.ok) {
      throw new ApiError(await parseError(response), response.status);
    }
    const payload = (await response.json()) as T & {
      __gateway_error?: boolean;
      detail?: string;
      status?: number;
    };

    if (payload && typeof payload === "object" && payload.__gateway_error) {
      throw new ApiError(payload.detail || "Internal Gateway Error", payload.status || 500);
    }

    return payload;
  } finally {
    cleanup();
  }
}

export function missionApiUrl(path: string): string {
    const base = missionApiBase.endsWith("/") ? missionApiBase.slice(0, -1) : missionApiBase;
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    
    // 7E — If talkling directly to v1 gateway, we don't need the /v1 prefix in path 
    // if the base already has it.
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
  return fetchJson<MissionChainTrace>(missionApiUrl(`/v1/missions/${missionId}/chain-trace`));
}

export async function createMission(payload: any): Promise<MissionRecord> {
  return fetchJson<MissionRecord>(missionApiUrl("/v1/missions"), {
    method: "POST",
    headers: { "Idempotency-Key": buildIdempotencyKey() },
    body: JSON.stringify(payload),
  });
}

export async function updateMissionMetadata(missionId: string, metadata: any): Promise<MissionRecord> {
  return fetchJson<MissionRecord>(missionApiUrl(`/v1/missions/${encodeURIComponent(missionId)}`), {
    method: "PATCH",
    body: JSON.stringify({ metadata }),
  });
}

export async function updateMissionStateWithVault(payload: any): Promise<any> {
  // In Admin Mode, this might be simplified, but keep for compat
  return fetchJson("/api/operator/mission-state", {
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
  } catch (error: any) {
    return { ready: false, detail: error.message };
  }
}

export async function getOperationsSummary(): Promise<OperationsSummary> {
  return fetchJson<OperationsSummary>(missionApiUrl("/v1/operations/summary"));
}

export async function getOperationsAgents(params?: any): Promise<OperationsAgentsSnapshot> {
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

export async function listOperationsLogicNodes(params: any): Promise<OperationsLogicNodeRecord[]> {
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

export async function listProjectAuditEvents(params: any): Promise<OperationsAuditEventRecord[]> {
  const searchParams = new URLSearchParams({ limit: String(params.limit) });
  if (params.missionId) searchParams.set("mission_id", params.missionId);
  return fetchJson<OperationsAuditEventRecord[]>(missionApiUrl(`/v1/operations/projects/${params.projectId}/audit-events?${searchParams.toString()}`));
}

export async function listOperationsAlerts(limit: number): Promise<OperationsAlertRecord[]> {
  return fetchJson<OperationsAlertRecord[]>(missionApiUrl(`/v1/operations/alerts?limit=${limit}`));
}

export async function listMissionAuditReports(missionId: string, limit = 50): Promise<OperationsAuditReportRecord[]> {
  return fetchJson<OperationsAuditReportRecord[]>(missionApiUrl(`/v1/missions/${missionId}/audit-reports?limit=${limit}`));
}

export async function listMissionAuditEvents(missionId: string, limit = 100): Promise<OperationsAuditEventRecord[]> {
  return fetchJson<OperationsAuditEventRecord[]>(missionApiUrl(`/v1/missions/${missionId}/audit-events?limit=${limit}`));
}

export async function createBuilderPreview(payload: any): Promise<BuilderPreviewResponse> {
  return fetchJson<BuilderPreviewResponse>(missionApiUrl("/v1/builder/preview"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createPmFeatureContract(payload: any): Promise<PmFeatureContractResponse> {
  return fetchJson<PmFeatureContractResponse>("/api/pm/feature-contract", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function createBuilderWorkspaceReview(payload: any): Promise<BuilderPreviewResponse> {
  return fetchJson<BuilderPreviewResponse>("/api/builder/review", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function createRepoReview(payload: any): Promise<RepoReviewResponse> {
  return fetchJson<RepoReviewResponse>("/api/repo/review", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function approveReviewArtifact(payload: any): Promise<ReviewApprovalReceipt> {
  return fetchJson<ReviewApprovalReceipt>("/api/review/approve", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function verifyReviewApproval(payload: any): Promise<ReviewApprovalVerificationResult> {
  return fetchJson<ReviewApprovalVerificationResult>("/api/review/verify", {
    method: "POST",
    timeoutMs: 30_000,
    body: JSON.stringify(payload),
  });
}

export async function getMissionTokenUsage(missionId: string): Promise<any | null> {
  try {
    return await fetchJson(missionApiUrl(`/v1/missions/${encodeURIComponent(missionId)}/token-usage`));
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
