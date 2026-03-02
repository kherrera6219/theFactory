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
};

export type OperationsAgentIntegrationsSnapshot = {
  generated_at: string;
  total_agents: number;
  llm_strategy_version: string;
  llm_provider_counts: Record<string, number>;
  llm_model_counts: Record<string, number>;
  agents: OperationsAgentIntegrationRecord[];
};

export type BuilderPlanItem = {
  title: string;
  description: string;
};

export type BuilderPreviewResponse = {
  request_id: string;
  source: string;
  generated_at: string;
  plan: BuilderPlanItem[];
  diff_summary: string[];
  risk_notes: string[];
  test_plan: string[];
  notice?: string;
};
