// Typed surface for the Mission Control API client.
//
// `api.gen.ts` is generated from docs/openapi/api-gateway.v1.json by
// `npm run gen:api` and must not be edited by hand. This module re-exports the
// generated component schemas under friendly names and adds the request/query
// shapes the client needs that the OpenAPI spec does not (yet) describe.

import type { components } from "./api.gen";

export type { components, paths, operations } from "./api.gen";

/** Schemas generated directly from the OpenAPI spec. */
export type ApiSchemas = components["schemas"];

/**
 * Request body for POST /v1/missions. The OpenAPI spec only describes
 * `prompt`, `metadata`, and `requested_target_language`; the UI also forwards
 * optional routing hints (mission_type, depth_mode, …) and inline source that
 * the gateway accepts but does not yet publish in the schema.
 */
export type MissionCreatePayload = ApiSchemas["MissionCreate"] & {
  mission_type?: string;
  depth_mode?: string;
  output_mode?: string;
  data_classification?: string;
  source_code?: string;
  [key: string]: unknown;
};

/** Request body for POST /v1/missions/{mission_id}/state. */
export type MissionStateUpdatePayload = ApiSchemas["MissionStateUpdate"];

/** FastAPI validation error envelope returned with HTTP 422. */
export type HttpValidationError = ApiSchemas["HTTPValidationError"];

/**
 * Local-First standard error payload. The backend returns this either at the
 * top level or nested under `detail` on non-2xx responses.
 */
export type FactoryErrorPayload = {
  user_message?: string;
  recovery_action?: string;
  error_code?: string;
};

/** Body shape returned by an error response from the backend or gateway. */
export type ErrorResponseBody = {
  detail?: string | FactoryErrorPayload | { message?: string } | unknown;
  user_message?: string;
};

/** Query options for GET /v1/operations/agents. */
export type OperationsAgentsQuery = {
  missionLimit?: number;
  assignmentLimit?: number;
  eventLimit?: number;
};

/** Query options for GET /v1/operations/logicnodes. */
export type OperationsLogicNodesQuery = {
  limit: number;
  missionId?: string;
};

/** Query options for GET /v1/operations/projects/{projectId}/audit-events. */
export type ProjectAuditEventsQuery = {
  projectId: string;
  limit: number;
  missionId?: string;
};

/** Request body for POST /api/operator/mission-state. */
export type MissionStateVaultUpdate = {
  mission_id: string;
  new_state: string;
  expected_state?: string | null;
  api_key?: string;
  [key: string]: unknown;
};

/** Request payload for POST /v1/builder/preview. */
export type BuilderPreviewRequest = {
  request: string;
  constraints?: string[];
  view_mode?: string;
  requested_target_language?: string | null;
  [key: string]: unknown;
};

/** Request payload for POST /api/pm/feature-contract. */
export type PmFeatureContractRequest = {
  prompt: string;
  mission_type?: string;
  conversation_context?: Record<string, unknown>;
  user_intent?: "clarify" | "draft" | "finalize_plan" | string;
  [key: string]: unknown;
};

/** Request payload for POST /api/repo/review. */
export type RepoReviewRequest = {
  owner?: string;
  repo?: string;
  branch?: string;
  url?: string;
  requested_target_language?: string | null;
  [key: string]: unknown;
};

/** Request payload for POST /api/review/approve. */
export type ReviewApprovalRequest = {
  scope: "builder" | "repo" | "delivery" | string;
  fingerprint: string;
  summary?: string;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
};
