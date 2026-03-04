import type {
  BuilderPreviewResponse,
  GatewayHealth,
  LiveStateStreamEvent,
  MissionEvent,
  MissionRecord,
  OperationsAgentIntegrationsSnapshot,
  OperationsAgentsSnapshot,
  OperationsAlertRecord,
  OperationsLogicNodeRecord,
  OperationsProjectRecord,
  OperationsSummary,
  PodAssignmentRecord,
} from "./types";

const DEFAULT_TIMEOUT_MS = 10_000;
const missionApiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

export class ApiError extends Error {
  statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.statusCode = statusCode;
  }
}

function withTimeout(timeoutMs: number): AbortSignal {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), timeoutMs);
  return controller.signal;
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

export async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    signal: init?.signal ?? withTimeout(DEFAULT_TIMEOUT_MS),
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }
  return (await response.json()) as T;
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

export function getOperatorApiKey(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const sessionKey = window.sessionStorage.getItem("mission-control:operator-api-key");
  if (sessionKey && sessionKey.trim().length > 0) {
    return sessionKey.trim();
  }
  const localKey = window.localStorage.getItem("mission-control:operator-api-key");
  if (localKey && localKey.trim().length > 0) {
    return localKey.trim();
  }
  return null;
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

export async function getMission(missionId: string): Promise<MissionRecord> {
  return fetchJson<MissionRecord>(missionApiUrl(`/v1/missions/${missionId}`), { method: "GET" });
}

export async function getMissionEvents(missionId: string, limit: number): Promise<MissionEvent[]> {
  return fetchJson<MissionEvent[]>(missionApiUrl(`/v1/missions/${missionId}/events?limit=${limit}`), {
    method: "GET",
  });
}

export async function createMission(payload: {
  prompt: string;
  requested_target_language: string | null;
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

export async function updateMissionState(payload: {
  missionId: string;
  newState: string;
  expectedState?: string;
  operatorApiKey?: string;
}): Promise<Record<string, unknown>> {
  const headers: Record<string, string> = {};
  const resolvedKey = payload.operatorApiKey ?? getOperatorApiKey();
  if (resolvedKey) {
    headers["x-api-key"] = resolvedKey;
  }
  return fetchJson<Record<string, unknown>>(missionApiUrl(`/v1/missions/${payload.missionId}/state`), {
    method: "POST",
    headers,
    body: JSON.stringify({
      new_state: payload.newState,
      expected_state: payload.expectedState,
    }),
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

export async function listOperationsAlerts(limit: number): Promise<OperationsAlertRecord[]> {
  return fetchJson<OperationsAlertRecord[]>(missionApiUrl(`/v1/operations/alerts?limit=${limit}`), {
    method: "GET",
  });
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
