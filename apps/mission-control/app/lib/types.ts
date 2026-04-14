export type MissionRecord = {
  mission_id: string;
  prompt?: string;
  state: string;
  requested_target_language: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
};

export type MissionEvent = {
  mission_id?: string;
  previous_state: string | null;
  new_state: string;
  event_type: string;
  ts: string;
};

export type MissionChainEvent = {
  event_type: string;
  agent_id?: string | null;
  ts: string;
  details?: Record<string, unknown>;
};

export type MissionRouteProvenanceStage = {
  role: "ceo" | "pod_manager" | "specialist";
  source?: string | null;
  llm_route?: string | null;
  model_provider?: string | null;
  model?: string | null;
  target_agent_id?: string | null;
  specialist_agent_id?: string | null;
  pod_manager_agent_id?: string | null;
  rationale?: string | null;
  plan_summary?: string | null;
  deliverables?: string[] | null;
  risk_notes?: string[] | null;
  mission_source?: string | null;
};

export type MissionBuildArtifactRecord = {
  mission_id: string;
  artifact_id: string;
  artifact_type: string;
  stage: string;
  status: string;
  storage_backend: string;
  storage_ref?: string | null;
  digest_sha256?: string | null;
  size_bytes: number;
  manifest?: Record<string, unknown>;
  verification?: Record<string, unknown>;
  build_log?: string;
  artifact_text?: string | null;
  created_at: string;
  updated_at: string;
};

export type MissionChainTrace = {
  mission_id: string;
  routing_enforced: boolean;
  routing_version?: string | null;
  selected_agent_id?: string | null;
  intake_agent_id?: string | null;
  executive_agent_id?: string | null;
  assigned_pod_manager_agent_id?: string | null;
  assigned_specialist_agent_id?: string | null;
  pod_assignment?: Record<string, unknown> | null;
  logicnode_count: number;
  artifact_summary?: Record<string, Record<string, unknown>>;
  build_artifacts?: MissionBuildArtifactRecord[];
  route_provenance?: {
    ceo?: MissionRouteProvenanceStage | null;
    pod_manager?: MissionRouteProvenanceStage | null;
    specialist?: MissionRouteProvenanceStage | null;
    fallback_used?: boolean;
  };
  events: MissionChainEvent[];
};

export type LiveStateStreamEvent = {
  stream_id: string;
  event_type: string;
  mission_id: string | null;
  state: string | null;
  topic: string | null;
  producer: string | null;
  created_at: string | null;
  payload: Record<string, unknown>;
};

export type AgentState = "IDLE" | "ACTIVE" | "RUNNING" | "VERIFYING" | "ERROR" | "PAUSED";

export type AgentRecord = {
  id: string;
  name: string;
  role: string;
  pod: string;
  state: AgentState;
  workloadPct: number;
  queueDepth: number;
  lastHeartbeatIso: string;
};

export type LogicNodeRecord = {
  id: string;
  missionId: string;
  domain: string;
  intent: string;
  confidence: number;
  status: "PENDING" | "VERIFIED" | "FAILED";
  sourceRef: string;
};

export type BusEventRecord = {
  id: string;
  ts: string;
  protocol: "ALPHA" | "BETA" | "DELTA" | "SIGMA" | "OMEGA" | "RHO";
  producer: string;
  consumer?: string;
  message_type?: string;
  topic: string;
  summary: string;
  priority: "NORMAL" | "HIGH";
  payload?: Record<string, unknown>;
};

export type AlertRecord = {
  id: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low";
  state: "open" | "acknowledged" | "resolved";
  source: string;
  createdAt: string;
  recommendation: string;
};

export type ProjectRecord = {
  id: string;
  name: string;
  status: "active" | "paused" | "completed";
  lastUpdatedAt: string;
  missionCount: number;
};

export type TemplateRecord = {
  id: string;
  title: string;
  category: string;
  summary: string;
};

export type GatewayHealth = {
  ok: boolean;
  service: string;
  orchestrator_url: string;
  orchestrator_healthy: boolean;
  redis_url: string;
  redis_healthy: boolean;
  intake_stream: string;
  intake_topic: string;
};

export type PodAssignmentRecord = {
  mission_id: string;
  pod_name: string;
  metadata: Record<string, unknown>;
  assigned_at: string;
  updated_at: string;
};

export type OperationsSummary = {
  generated_at: string;
  runtime: {
    redis_ready: boolean;
    db_ready: boolean;
    qdrant_ready?: boolean | null;
    milvus_ready?: boolean | null;
    neo4j_ready?: boolean | null;
    object_storage_ready?: boolean | null;
    protocol_ready: boolean;
    consumer_running: boolean;
  };
  mission_state_counts: Record<string, number>;
  pod_assignment_counts: Record<string, number>;
  active_lifecycle_tasks: number;
};

export type OperationsLogicNodeRecord = {
  mission_id: string;
  node_id: string;
  node: Record<string, unknown>;
  created_at: string;
};

export type OperationsProjectRecord = {
  project_id: string;
  source: string;
  mission_count: number;
  failed_count: number;
  complete_count: number;
  status: "active" | "paused" | "completed";
  last_updated_at: string;
};

export type OperationsAlertRecord = {
  alert_id: string;
  severity: "critical" | "high" | "medium" | "low";
  state: "open" | "acknowledged" | "resolved";
  title: string;
  source: string;
  created_at: string;
  recommendation: string;
};

export type OperationsAgentState = "IDLE" | "ACTIVE" | "RUNNING" | "VERIFYING" | "ERROR" | "PAUSED";

export type OperationsAgentPersonaProfile = {
  job_role: {
    title: string;
    primary_function: string;
    scope: string;
  };
  education_certifications: string[];
  traits_skills: string[];
  methods_procedures: string[];
  tools: string[];
  master_instruction: string;
  protocol: {
    primary_code: string;
    primary_name: string;
    primary_purpose: string;
    message_format: string;
    supported_codes: string[];
    supported_names: string[];
  };
  api_configuration: {
    api_key_env_var: string;
    api_slot_id: string;
    context_window_tokens: number;
    cached_content: string[];
    model_routing: {
      provider: string;
      model: string;
      [key: string]: unknown;
    };
  };
  standards_alignment: Array<{
    standard_id: string;
    framework: string;
    version: string;
    role_mapping: string;
    focus_areas: string[];
  }>;
  evidence_sources: Array<{
    source_id: string;
    title: string;
    organization: string;
    version: string;
    url: string;
    last_verified: string;
    applicability: string;
  }>;
};

export type OperationsAgentRecord = {
  index: number;
  agent_id: string;
  short_code: string;
  name: string;
  tier: string;
  pod: string;
  role: string;
  category: string;
  specialties: string[];
  state: OperationsAgentState;
  queue_depth: number;
  workload_pct: number;
  last_heartbeat_iso: string;
  active_mission_ids: string[];
  persona_profile: OperationsAgentPersonaProfile;
};

export type OperationsAgentsSnapshot = {
  generated_at: string;
  total_agents: number;
  runtime: {
    redis_ready: boolean;
    db_ready: boolean;
    protocol_ready: boolean;
    consumer_running: boolean;
  };
  mission_backlog: {
    active: number;
    verified: number;
    complete: number;
    assigned_active: number;
  };
  tier_counts: Record<string, number>;
  pod_counts: Record<string, number>;
  state_counts: Record<string, number>;
  agents: OperationsAgentRecord[];
  runtime_error?: string;
};

export type OperationsAgentIntegrationRecord = {
  agent_id: string;
  name: string;
  short_code: string;
  tier: string;
  pod: string;
  llm_recommendation: {
    provider: string;
    model: string;
    [key: string]: unknown;
  };
  persona_profile: OperationsAgentPersonaProfile;
};

export type OperationsAgentIntegrationsSnapshot = {
  generated_at: string;
  total_agents: number;
  persona_profile_framework: string;
  persona_profile_sections: string[];
  llm_strategy_version: string;
  llm_provider_counts: Record<string, number>;
  llm_model_counts: Record<string, number>;
  agents: OperationsAgentIntegrationRecord[];
};

export type BuilderPlanItem = {
  title: string;
  description: string;
};

export type BuilderDiffLine = {
  kind: "context" | "add" | "remove";
  value: string;
};

export type BuilderSourceStats = {
  selected_files: number;
  source_characters: number;
  patch_characters: number;
  high_risk_files: number;
};

export type BuilderPreviewFile = {
  path: string;
  operation: "modify" | "create";
  risk: "low" | "medium" | "high";
  summary: string;
  excerpt?: string;
  lines: BuilderDiffLine[];
};

export type BuilderPreviewResponse = {
  request_id: string;
  source: string;
  generated_at: string;
  plan: BuilderPlanItem[];
  diff_summary: string[];
  risk_notes: string[];
  test_plan: string[];
  builder_fingerprint?: string;
  requested_target_language?: string | null;
  source_code?: string;
  patch_text?: string;
  source_stats?: BuilderSourceStats;
  files?: BuilderPreviewFile[];
  notice?: string;
};

export type ReviewApprovalReceipt = {
  approval_id: string;
  scope: "builder" | "repo";
  fingerprint: string;
  approved_at: string;
  expires_at?: string | null;
  summary: string;
  receipt_digest: string;
  record_path: string;
};

export type ReviewApprovalVerificationResult = {
  valid: boolean;
  approval_id: string;
  scope: "builder" | "repo";
  fingerprint: string;
  approved_at: string;
  expires_at: string | null;
};

export type RepoReviewFileRecord = {
  path: string;
  overlay_action: "include" | "reference";
  language: string;
  requested_language: string | null;
  bytes: number;
  estimated_lines: number;
  summary: string;
  content_excerpt: string;
  text_available: boolean;
  included_in_source: boolean;
  truncated_in_source: boolean;
  sha: string | null;
};

export type RepoReviewResponse = {
  request_id: string;
  review_fingerprint: string;
  source: "repo-review";
  generated_at: string;
  repository: {
    owner: string;
    repo: string;
    branch: string;
    html_url: string;
    selected_subdirectory: string;
  };
  mission_type: "analyze" | "update" | "add_feature" | "refactor";
  requested_target_language: string | null;
  source_code: string;
  source_stats: {
    selected_files: number;
    include_files: number;
    reference_files: number;
    source_characters: number;
    bundled_files: number;
    truncated_files: number;
    unavailable_files: number;
  };
  plan: BuilderPlanItem[];
  diff_summary: string[];
  risk_notes: string[];
  test_plan: string[];
  files: RepoReviewFileRecord[];
  notice?: string;
};

