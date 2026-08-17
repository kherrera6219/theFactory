export type MissionType =
  | "BUILD_NEW"
  | "IMPORT_MODERNIZE"
  | "PORT"
  | "DEBUG_REPAIR"
  | "SECURITY_HARDEN"
  | "REDUCE_DEPENDENCIES"
  | "RUN_QC"
  | "ARCHITECTURE_DOCS"
  | "ANALYZE_ONLY"
  | "SELF_ANALYZE";

export type DepthMode =
  | "SPRINT"
  | "STANDARD"
  | "PRODUCTION"
  | "REGULATED"
  | "AUTONOMOUS_LONG_RUN";

export type OutputMode =
  | "ANALYZE_ONLY"
  | "PLAN_ONLY"
  | "PATCH_PROPOSAL"
  | "APPLY_PATCH"
  | "FULL_BUILD"
  | "DEPENDENCY_REDUCTION"
  | "RUN_QC"
  | "FULL_TRANSFORMATION";

export type DataClassification =
  | "TIER_0_PUBLIC"
  | "TIER_1_INTERNAL"
  | "TIER_2_SENSITIVE"
  | "TIER_3_REGULATED";

export type MissionRecord = {
  mission_id: string;
  prompt?: string;
  state: string;
  requested_target_language: string | null;
  mission_type?: MissionType | null;
  depth_mode?: DepthMode | null;
  output_mode?: OutputMode | null;
  data_classification?: DataClassification | null;
  metadata?: Record<string, unknown>;
  project_id?: string | null;
  lifecycle_engine?: string | null;
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

export type MissionContractLogicNodeRequirement = {
  domain: string;
  concept: string;
  intent: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
};

export type MissionContract = {
  schema_version: "mission_contract.v1";
  contract_summary: string;
  mission_type: string;
  target_languages: string[];
  output_mode: string;
  output_format: string;
  required_domains: string[];
  logicnode_requirements: MissionContractLogicNodeRequirement[];
  acceptance_criteria: string[];
  risk_notes: string[];
  source: "llm" | "fallback";
  llm_route?: string;
  model_provider?: string;
  model?: string;
  created_at: string;
};

export type FeatureContract = {
  schema_version: "feature_contract.v1";
  title: string;
  summary: string;
  functional_requirements: string[];
  non_functional_requirements: string[];
  acceptance_criteria: string[];
  target_languages: string[];
  estimated_complexity: "low" | "medium" | "high" | "very_high";
  human_approval_required: boolean;
  risk_notes: string[];
  clarifying_questions: string[];
  assumptions?: string[];
  out_of_scope?: string[];
  deliverables?: Array<string | { name: string; artifact_hint?: string }>;
  engagement_type?: string;
  cost_estimate?: {
    likely_usd?: number | null;
    high_usd?: number | null;
    cap_usd?: number | null;
    pricing_known?: boolean;
    estimated_minutes_low?: number;
    estimated_minutes_high?: number;
    basis?: string;
  };
  timeline?: {
    estimated_minutes_low?: number;
    estimated_minutes_high?: number;
  };
  intake_status?: "needs_clarification" | "ready";
  ambiguity_score?: number;
  source: "llm" | "fallback";
  degraded?: boolean;
  degraded_reason?: string;
  llm_route?: string;
  model_provider?: string;
  model?: string;
  created_at: string;
};

export type PmFeatureContractResponse = {
  feature_contract: FeatureContract;
  mission_charter?: MissionCharter | null;
  source: "llm" | "fallback" | string;
  model_provider?: string | null;
  model?: string | null;
};

export type MissionCharter = {
  schema_version: string;
  charter_id: string;
  mission_id: string;
  created_at: string;
  requested_by: string;
  mission_mode: number;
  mission_mode_label?: string;
  depth_mode: string;
  output_mode: string;
  target: Record<string, unknown>;
  objective: string;
  raw_input?: string;
  scope?: Record<string, unknown>;
  success_criteria: string[];
  definition_of_done: Record<string, unknown>;
  non_functional_constraints?: Record<string, unknown>;
  metadata?: Record<string, string>;
};

export type LogicCluster = {
  cluster_id: string;
  title: string;
  domain: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  pod_manager_agent_id: string;
  specialist_agent_id: string;
  requirement_refs: string[];
  rationale: string;
};

export type LogicClusters = {
  schema_version: "logic_clusters.v1";
  clusters: LogicCluster[];
  source: "llm" | "fallback";
  llm_route?: string;
  model_provider?: string;
  model?: string;
  created_at: string;
};

export type PodGroupStandardNode = {
  standard_node_id: string;
  domain: string;
  concept: string;
  intent: string;
  source_node_ids: string[];
  languages: string[];
  confidence?: number | null;
};

export type PodGroupStandard = {
  schema_version: "pod_group_standard.v1";
  pod: string;
  pod_manager_agent_id: string;
  mission_id: string;
  canonical_logicnodes: PodGroupStandardNode[];
  eliminated_duplicates: number;
  summary: string;
  source: "llm" | "fallback";
  llm_route?: string;
  model_provider?: string;
  model?: string;
  created_at: string;
};

export type ApplicationIntelligenceMap = {
  schema_version: "aim.v1";
  aim_id: string;
  mission_id: string;
  mission_type: string;
  generated_at: string;
  source: "llm" | "fallback" | string;
  llm_route?: string;
  model_provider?: string;
  model?: string;
  repository_summary: string;
  detected_languages: string[];
  primary_language?: string | null;
  total_functions: number;
  total_classes: number;
  total_concepts?: number;
  domain_distribution: Record<string, number>;
  complexity_assessment: "low" | "medium" | "high" | "very_high" | string;
  key_patterns: string[];
  detected_dependencies: string[];
  risks: string[];
  risk_flags: string[];
  human_approval_recommended: boolean;
  recommended_approach: string;
  recommended_mission_type: string;
  extraction_summary?: {
    files_seen?: number;
    files_analyzed?: number;
    truncated?: boolean;
    file_manifest?: Array<{
      path: string;
      language?: string;
      size_bytes?: number;
      sha256?: string;
      analyzed?: boolean;
    }>;
  };
};

export type EquivalenceReport = {
  schema_version: "equivalence_report.v1";
  report_id: string;
  mission_id: string;
  generated_at: string;
  status: "passed" | "blocked" | "review_required" | string;
  passed: boolean;
  blocking: boolean;
  enforcement_enabled: boolean;
  risk_level: "low" | "medium" | "high" | string;
  target_language?: string | null;
  checks: Array<{
    check_id: string;
    title: string;
    status: "pass" | "fail" | "manual_review" | string;
    required: boolean;
    message: string;
    evidence?: Record<string, unknown>;
  }>;
  findings: string[];
  evidence_refs: Array<Record<string, unknown>>;
  source: string;
};

export type SecurityComplianceReport = {
  schema_version: "security_compliance_report.v1";
  report_id: string;
  mission_id: string;
  generated_at: string;
  status: "passed" | "warned" | "blocked" | string;
  passed: boolean;
  blocking: boolean;
  enforcement_enabled: boolean;
  regulated_context?: boolean;
  risk_level: "low" | "medium" | "high" | string;
  security: {
    passed: boolean;
    checks: SecurityComplianceCheck[];
  };
  compliance: {
    passed: boolean;
    checks: SecurityComplianceCheck[];
  };
  findings: string[];
  recommendations: string[];
  evidence_refs: Array<Record<string, unknown>>;
  source: string;
};

export type SecurityComplianceCheck = {
  check_id: string;
  title: string;
  status: "pass" | "warn" | "fail" | "manual_review" | string;
  required: boolean;
  message: string;
  evidence?: Record<string, unknown>;
  recommendation?: string;
};

export type DependencyInventory = {
  schema_version: "dependency_inventory.v1";
  inventory_id: string;
  mission_id: string;
  generated_at: string;
  dependency_count: number;
  dependencies: DependencyInventoryEntry[];
  sources: string[];
  source: string;
};

export type DependencyInventoryEntry = {
  dependency_id: string;
  name: string;
  normalized_name: string;
  ecosystem: string;
  version?: string | null;
  source_refs: string[];
  usage_hints: string[];
};

export type DependencyClassificationReport = {
  schema_version: "dependency_classification_report.v1";
  report_id: string;
  mission_id: string;
  generated_at: string;
  status: "classified" | "blocked" | string;
  blocking: boolean;
  classification_count: number;
  classifications: DependencyClassification[];
  source: string;
};

export type DependencyClassification = {
  dependency_id: string;
  name: string;
  normalized_name: string;
  decision: "absorb" | "reimplement" | "replace" | "vendor" | "wrap" | "pin" | "keep" | "block" | string;
  category: string;
  risk_level: "low" | "medium" | "high" | string;
  safety_blocked: boolean;
  blocking: boolean;
  license?: string | null;
  rationale: string;
  source_refs: string[];
  usage_hints: string[];
};

export type DependencyAbsorptionReport = {
  schema_version: "dependency_absorption_report.v1";
  report_id: string;
  mission_id: string;
  generated_at: string;
  status: "planned" | "gated" | "blocked" | "not_applicable" | string;
  blocking: boolean;
  modified_output_created: boolean;
  equivalence_required: boolean;
  equivalence_passed: boolean;
  security_compliance_required: boolean;
  security_compliance_passed: boolean;
  planned_replacements: DependencyReplacementPlan[];
  survival_justification_count: number;
  safety_block_count: number;
  recommendations: string[];
  evidence_refs: Array<Record<string, unknown>>;
  source: string;
};

export type DependencyReplacementPlan = {
  dependency_id: string;
  name: string;
  decision: string;
  status: "ready_for_planning" | "gated" | string;
  blocked_by: string[];
  replacement_scope: string;
  requires_operator_approval: boolean;
  modified_output_created: boolean;
  rationale: string;
};

export type DependencySurvivalJustification = {
  schema_version: "dependency_survival_justification.v1";
  justification_id: string;
  mission_id: string;
  dependency_id: string;
  name: string;
  decision: string;
  risk_level: "low" | "medium" | "high" | string;
  safety_blocked: boolean;
  rationale: string;
  review_required: boolean;
};

export type TestdataManifest = {
  schema_version?: "testdata_manifest.v1" | string;
  base_image: string;
  install_commands: string[];
  env_vars: Record<string, string>;
  synthetic_inputs: Array<{ input_id: string; description: string; input_data: string }>;
  run_command: string;
  timeout_seconds: number;
  memory_limit_mb: number;
  network_required: boolean;
  notes: string;
  language: string;
  test_framework: string;
  source: string;
};

export type RuntimeQcReport = {
  schema_version?: "runtime_qc_report.v1" | string;
  verdict: "PASS" | "FAIL" | "TIMEOUT" | "ERROR" | "DRY_RUN" | "SKIPPED" | string;
  passed: boolean;
  execution_type: "docker_live" | "dry_run" | "skipped" | string;
  exit_code?: number | null;
  expected_exit_code?: number | null;
  stdout_preview?: string | null;
  stderr_preview?: string | null;
  base_image?: string | null;
  language: string;
  filename: string;
  timeout_seconds?: number | null;
  dry_run_reason?: string | null;
  qc_assessment?: {
    qc_verdict: "PASS" | "WARN" | "FAIL" | "INCONCLUSIVE" | "ADVISORY" | string;
    confidence: "HIGH" | "MEDIUM" | "LOW" | string;
    findings: string[];
    remediation: string[];
    deployment_safe: boolean;
    source: string;
  } | null;
  source: string;
};

export type DepabsExecution = {
  schema_version?: "depabs_execution.v1" | string;
  status: string;
  absorption_count: number;
  splices: Array<{
    library: string;
    symbols_replaced: string[];
    filename?: string | null;
    status: string;
    reason?: string | null;
  }>;
};

export type SbomDelta = {
  schema_version?: "sbom_delta.v1" | string;
  original_dependency_count: number;
  removed: string[];
  remaining: string[];
  kept_with_justification: string[];
  reduction_percent: number;
};

export type MissionChainTrace = {
  mission_id: string;
  lifecycle_engine?: string | null;
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
  feature_contract?: FeatureContract | null;
  mission_charter?: MissionCharter | null;
  mission_contract?: MissionContract | null;
  logic_clusters?: LogicClusters | null;
  pod_group_standards?: Record<string, PodGroupStandard> | null;
  fetch_result?: {
    indexed_languages: string[];
    refreshed_languages?: string[];
    unchanged_languages?: string[];
    skipped_languages: string[];
    errors: string[];
    knowledge_ready: boolean;
    refresh_enabled?: boolean;
    embedding_provider?: string;
    embedding_model?: string;
    indexed_at: string;
    mission_id: string;
  } | null;
  application_intelligence_map?: ApplicationIntelligenceMap | null;
  equivalence_report?: EquivalenceReport | null;
  security_compliance_report?: SecurityComplianceReport | null;
  dependency_inventory?: DependencyInventory | null;
  dependency_classification_report?: DependencyClassificationReport | null;
  dependency_absorption_report?: DependencyAbsorptionReport | null;
  depabs_execution?: DepabsExecution | null;
  sbom_delta?: SbomDelta | null;
  dependency_survival_justifications?: DependencySurvivalJustification[] | null;
  testdata_manifest?: TestdataManifest | null;
  runtime_qc_report?: RuntimeQcReport | null;
  master_logic_stream?: {
    master_logic_stream: Array<{
      node_id: string;
      domain: string;
      concept: string;
      canonical_intent: string;
      source_pods: string[];
      dependency_order: number;
    }>;
    total_unified_nodes: number;
    eliminated_across_pods: number;
    ready_for_codegen: boolean;
    source: string;
    model_provider?: string;
    model?: string;
  } | null;
  delivery_summary?: {
    delivery_title: string;
    delivery_summary: string;
    criteria_met: string[];
    criteria_unmet: string[];
    usage_notes?: string;
    recommendations: string[];
    primary_artifact_type?: string | null;
    source: string;
    model_provider?: string;
    model?: string;
  } | null;
  route_provenance?: {
    ceo?: MissionRouteProvenanceStage | null;
    pod_manager?: MissionRouteProvenanceStage | null;
    specialist?: MissionRouteProvenanceStage | null;
    fallback_used?: boolean;
  };
  events: MissionChainEvent[];
  // PORT two-phase fields
  port_phase?: string | null;
  port_source_language?: string | null;
  port_target_language?: string | null;
  port_source_logicnodes?: Array<Record<string, unknown>> | null;
  // Mission type (surfaced in chain trace for UI)
  mission_type?: string | null;
  // Generated output metadata (for PORT phase indicator)
  generated_output?: {
    source?: string;
    filename?: string;
    language?: string;
    generated_code?: string;
    code_length_chars?: number;
  } | null;
  pm_clarification?: PmClarificationState | null;
  llm_usage_summary?: LlmUsageSummary | null;
  vc_commit_strategy?: VcCommitStrategy | null;
  integration_tests?: IntegrationTests | null;
  pod_audit_verdict?: PodAuditVerdict | null;
};

export type PmClarificationState = {
  questions: string[];
  ambiguity_score: number;
  pending: boolean;
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

export type AgentRuntimeClass = "shared_worker" | "synthesized_heartbeat";

export type TopologyMode = "condensed" | "dedicated" | "full-dedicated";

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

export type ProtocolBusLaneName = "alpha" | "beta" | "delta" | "sigma" | "omega" | "rho";

export type ProtocolBusLaneActivity = {
  messages_queued_total: number;
  dlq_writes_total: number;
  messages_deduplicated_total: number;
  messages_replayed_total: number;
  dlq_depth: number | null;
};

export type ProtocolBusLaneActivitySnapshot = {
  generated_at: string;
  redis_ready: boolean;
  lanes: Partial<Record<ProtocolBusLaneName, ProtocolBusLaneActivity>>;
};

export type OperationsSummary = {
  generated_at: string;
  topology_mode: TopologyMode;
  runtime: {
    redis_ready: boolean;
    db_ready: boolean;
    qdrant_ready?: boolean | null;
    milvus_ready?: boolean | null;
    neo4j_ready?: boolean | null;
    object_storage_ready?: boolean | null;
    jaeger_ready?: boolean | null;
    protocol_ready: boolean;
    consumer_running: boolean;
  };
  mission_state_counts: Record<string, number>;
  pod_assignment_counts: Record<string, number>;
  active_lifecycle_tasks: number;
  // PBLA-05: null when protocol-bus-mcp is unreachable — never blocks the
  // rest of the summary.
  lane_activity: ProtocolBusLaneActivitySnapshot | null;
};

export type OperationsLogicNodeRecord = {
  mission_id: string;
  node_id: string;
  node: Record<string, unknown>;
  created_at: string;
};

export type OperationsProjectRecord = {
  project_id: string;
  project_name?: string;
  source: string;
  mission_count: number;
  failed_count: number;
  complete_count: number;
  status: "active" | "paused" | "completed";
  last_updated_at: string;
};

export type OperationsAuditEventRecord = {
  event_id: string;
  project_id: string;
  mission_id: string;
  agent_id: string;
  service_name: string;
  event_type: string;
  status: string;
  object_type?: string | null;
  object_id?: string | null;
  tool_name?: string | null;
  trace_id?: string | null;
  span_id?: string | null;
  correlation_id?: string | null;
  parent_event_id?: string | null;
  started_at: string;
  ended_at?: string | null;
  duration_ms?: number | null;
  payload_summary?: Record<string, unknown>;
  content_sha256?: string | null;
  blob_ref?: string | null;
  prev_event_digest_sha256?: string | null;
  event_digest_sha256: string;
  created_at: string;
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

export type AgentHeartbeatSource = "live" | "stale" | "heuristic";

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
  heartbeat_age_seconds?: number | null;
  heartbeat_source?: AgentHeartbeatSource | null;
  active_mission_ids: string[];
  runtime_class: AgentRuntimeClass;
  persona_profile: OperationsAgentPersonaProfile;
};

export type OperationsAgentsSnapshot = {
  generated_at: string;
  total_agents: number;
  topology_mode?: TopologyMode;
  runtime: {
    redis_ready: boolean;
    db_ready: boolean;
    protocol_ready: boolean;
    consumer_running: boolean;
    langgraph_enabled?: boolean | null;
    langgraph_fail_open?: boolean | null;
    langgraph_checkpointer?: string | null;
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

export type OperationsAuditReportRecord = {
  mission_id: string;
  audit_id: string;
  status: string;
  report: Record<string, unknown>;
  created_at: string;
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
  scope: "builder" | "repo" | "delivery";
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
  scope: "builder" | "repo" | "delivery";
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

export type RepoImportResponse = {
  repository: {
    source: "zip";
    owner: string;
    repo: string;
    branch: string;
    default_branch: string;
    private: boolean;
    html_url: string | null;
    display_name: string;
    archive_id: string;
    archive_sha256: string;
    source_ref: string;
    root_prefix: string;
  };
  files: Array<{
    path: string;
    language: string;
    bytes: number;
    estimated_lines: number;
  }>;
  stats: {
    total_files: number;
    estimated_total_lines: number;
    selected_subdirectory: string;
    truncated: boolean;
    skipped_large_files: number;
    skipped_unsafe_entries: number;
    skipped_directory_entries: number;
    skipped_unreadable_entries: number;
    entry_limit_reached: boolean;
    byte_limit_reached: boolean;
    total_entries: number;
    total_uncompressed_bytes: number;
  };
  logs: string[];
};

export type RepoReviewResponse = {
  request_id: string;
  review_fingerprint: string;
  source: "repo-review";
  generated_at: string;
  repository: {
    source: "zip";
    owner: string;
    repo: string;
    branch: string;
    html_url: string | null;
    selected_subdirectory: string;
    archive_id: string;
    archive_sha256: string;
    display_name: string;
    source_ref: string;
    root_prefix: string;
  };
  mission_type: "analyze" | "update" | "add_feature" | "refactor" | "port";
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


export type LlmUsageSummary = {
  mission_id: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number | null;
  unknown_pricing_count: number;
  call_count: number;
  by_provider: Array<{
    provider: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    estimated_cost_usd: number | null;
  }>;
  by_agent: Array<{
    agent_id: string;
    provider: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number | null;
  }>;
};

export type VcCommitStrategy = {
  strategy_id: string;
  commit_hash?: string | null;
  branch_name?: string | null;
  message?: string | null;
  status: "pending" | "applied" | "failed" | string;
};

export type IntegrationTests = {
  framework: string;
  test_count: number;
  passed_count: number;
  failed_count: number;
  duration_ms: number;
  results: Array<{
    name: string;
    status: "pass" | "fail" | string;
    error_message?: string | null;
  }>;
};

export type PodAuditVerdict = {
  audit_id: string;
  pod_name: string;
  verdict: "APPROVED" | "REJECTED" | "WARNING" | string;
  rationale: string;
  audited_at: string;
};
