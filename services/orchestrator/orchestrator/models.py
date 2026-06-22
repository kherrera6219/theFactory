from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ==============================================================================
# Domain Models
# ==============================================================================


class MissionType(str, Enum):
    build_new = "BUILD_NEW"
    import_modernize = "IMPORT_MODERNIZE"
    port = "PORT"
    debug_repair = "DEBUG_REPAIR"
    security_harden = "SECURITY_HARDEN"
    reduce_dependencies = "REDUCE_DEPENDENCIES"
    run_qc = "RUN_QC"
    architecture_docs = "ARCHITECTURE_DOCS"
    analyze_only = "ANALYZE_ONLY"
    self_analyze = "SELF_ANALYZE"


class DepthMode(str, Enum):
    sprint = "SPRINT"
    standard = "STANDARD"
    production = "PRODUCTION"
    regulated = "REGULATED"
    autonomous_long_run = "AUTONOMOUS_LONG_RUN"


class OutputMode(str, Enum):
    analyze_only = "ANALYZE_ONLY"
    plan_only = "PLAN_ONLY"
    patch_proposal = "PATCH_PROPOSAL"
    apply_patch = "APPLY_PATCH"
    full_build = "FULL_BUILD"
    dependency_reduction = "DEPENDENCY_REDUCTION"
    run_qc = "RUN_QC"
    full_transformation = "FULL_TRANSFORMATION"


class DataClassification(str, Enum):
    tier_0_public = "TIER_0_PUBLIC"
    tier_1_internal = "TIER_1_INTERNAL"
    tier_2_sensitive = "TIER_2_SENSITIVE"
    tier_3_regulated = "TIER_3_REGULATED"


class MissionState(str, Enum):
    intake = "INTAKE"
    queued = "QUEUED"
    # v2 intermediate states (feature-flagged via MISSION_FLOW_V2_ENABLED)
    pm_intake = "PM_INTAKE"
    fetch = "FETCH"              # Phase 8: IS Agent knowledge-lake preload
    ceo_delegated = "CEO_DELEGATED"
    pod_assigned = "POD_ASSIGNED"
    specialist_assigned = "SPECIALIST_ASSIGNED"
    # Optional clarification hold — PM pauses pipeline awaiting operator input.
    # Entered from pm_intake when the intent is ambiguous; exits back to pm_intake.
    clarifying = "CLARIFYING"
    # v1.1 + v2 shared states
    running = "RUNNING"
    gating = "GATING"
    fusion = "FUSION"
    verified = "VERIFIED"
    complete = "COMPLETE"
    failed = "FAILED"


# State sets for validation mapping
V1_STATES: set[MissionState] = {
    MissionState.intake,
    MissionState.queued,
    MissionState.gating,
    MissionState.running,
    MissionState.fusion,
    MissionState.verified,
    MissionState.complete,
    MissionState.failed,
}

V2_STATES: set[MissionState] = {
    MissionState.intake,
    MissionState.queued,
    MissionState.pm_intake,
    MissionState.fetch,
    MissionState.ceo_delegated,
    MissionState.pod_assigned,
    MissionState.specialist_assigned,
    MissionState.clarifying,
    MissionState.running,
    MissionState.gating,
    MissionState.fusion,
    MissionState.verified,
    MissionState.complete,
    MissionState.failed,
}

# All valid event_type strings that can appear on a MissionEvent or be emitted
# by the runtime, mission_flow_v2, or langgraph_lifecycle modules.
EventType = Literal[
    # State-transition events (one per MissionState value)
    "MISSION_INTAKE",
    "MISSION_QUEUED",
    "MISSION_PM_INTAKE",
    "MISSION_FETCH",
    "MISSION_FETCH_COMPLETE",
    "MISSION_CEO_DELEGATED",
    "MISSION_POD_ASSIGNED",
    "MISSION_SPECIALIST_ASSIGNED",
    "MISSION_CLARIFYING",
    "MISSION_RUNNING",
    "MISSION_GATING",
    "MISSION_FUSION",
    "MISSION_VERIFIED",
    "MISSION_COMPLETE",
    "MISSION_FAILED",
    # Delegation / planning events
    "MISSION_POD_MANAGER_ASSIGNED",
    "MISSION_SPECIALIST_PLANNED",
    "MISSION_SCALING_DECIDED",
    "MISSION_AIM_GENERATED",
    # Operational / lifecycle events
    "MISSION_LOGICNODE_WRITTEN",
    "MISSION_COMPLETION_BLOCKED",
    "MISSION_DELIVERED",
    # Intelligence-layer agent events (Sprint 2)
    "MISSION_CLARIFICATION_RECEIVED",
    "MISSION_CLARIFICATION_APPLIED",
    "MISSION_POD_AUDIT_COMPLETE",
    "MISSION_SECURITY_ANALYSIS_COMPLETE",
    "MISSION_VC_COMMIT_STRATEGY_READY",
    "MISSION_INTEGRATION_TESTS_GENERATED",
    "MISSION_DEPLOY_READINESS_ASSESSED",
    "MISSION_POD_GROUP_STANDARD_PRODUCED",
    "MISSION_BUILD_ARTIFACT_WRITTEN",
    "MISSION_DEPABS_EXECUTED",
    "MISSION_RUNTIME_QC_COMPLETE",
    "MISSION_EQUIVALENCE_VERIFIED",
    "MISSION_SECURITY_COMPLIANCE_PASSED",
    "MISSION_SECURITY_COMPLIANCE_WARNED",
    "MISSION_TESTDATA_MANIFEST_READY",
    # Agent events
    "AGENT_STATE_CHANGED",
]


VALID_TRANSITIONS: dict[MissionState, set[MissionState]] = {
    # Common entry point
    MissionState.intake: {MissionState.queued},
    # V1 direct: queued → running; V2: queued → pm_intake; legacy: queued → gating
    MissionState.queued: {
        MissionState.pm_intake,
        MissionState.gating,
        MissionState.running,
        MissionState.failed,
    },

    # V2-only routing chain
    MissionState.pm_intake: {
        MissionState.fetch,
        MissionState.ceo_delegated,
        MissionState.clarifying,
        MissionState.failed,
    },
    # Clarification hold: PM pauses awaiting operator response, then re-queues
    # so PM intake can rebuild the feature contract with the operator answer.
    MissionState.clarifying: {
        MissionState.queued,
        MissionState.pm_intake,
        MissionState.fetch,
        MissionState.failed,
    },
    MissionState.fetch: {MissionState.ceo_delegated, MissionState.failed},
    MissionState.ceo_delegated: {MissionState.pod_assigned, MissionState.failed},
    MissionState.pod_assigned: {MissionState.specialist_assigned, MissionState.failed},
    MissionState.specialist_assigned: {MissionState.running, MissionState.failed},

    # V1: queued → gating → running; V2: ... → running → gating → fusion
    # Both directions are valid; the active engine determines the path used.
    MissionState.gating: {MissionState.running, MissionState.fusion, MissionState.failed},
    # V1 direct: running → verified; V2: running → gating → fusion → verified
    MissionState.running: {
        MissionState.gating,
        MissionState.fusion,
        MissionState.verified,
        MissionState.failed,
    },

    # Shared terminal path
    MissionState.fusion: {MissionState.verified, MissionState.failed},
    MissionState.verified: {MissionState.complete, MissionState.failed},
    MissionState.complete: set(),
    MissionState.failed: set(),
}

# ==============================================================================
# Database & Storage Models
# ==============================================================================


class MissionAttachment(BaseModel):
    """Refers to a file stored in object storage as mission context."""
    file_id: str
    filename: str
    content_type: str
    size_bytes: int = 0
    purpose: str | None = "reference"  # reference | PRD | spec | legacy_source
    created_at: datetime = Field(default_factory=datetime.utcnow)
    object_key: str | None = None  # explicit object-storage key for the file bytes
    content: str | None = None  # extracted document text, populated during intake

class MissionRecord(BaseModel):
    mission_id: str
    prompt: str
    requested_target_language: str | None = None
    mission_type: MissionType | None = None
    depth_mode: DepthMode | None = None
    output_mode: OutputMode | None = None
    data_classification: DataClassification | None = None
    attachments: list[MissionAttachment] = Field(default_factory=list)
    risk_assessment: dict[str, Any] | None = None
    global_style_directives: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None
    state: MissionState
    created_at: datetime


class MissionEvent(BaseModel):
    mission_id: str
    previous_state: MissionState | None = None
    new_state: MissionState
    event_type: EventType
    ts: datetime


# ==============================================================================
# API Request/Response Models
# ==============================================================================


class MissionCreate(BaseModel):
    mission_id: str = Field(min_length=1)
    prompt: str = Field(min_length=3)
    requested_target_language: str | None = None
    mission_type: MissionType | None = None
    depth_mode: DepthMode | None = None
    output_mode: OutputMode | None = None
    data_classification: DataClassification | None = None
    attachments: list[MissionAttachment] = Field(default_factory=list)
    global_style_directives: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None
    created_at: datetime | None = None


class MissionStateUpdate(BaseModel):
    new_state: MissionState
    expected_state: MissionState | None = None


class MissionClarifyRequest(BaseModel):
    """Operator-supplied clarification that resolves a CLARIFYING-state mission.

    ``clarification`` is stored in ``metadata["pm_clarification"]`` and the
    mission is re-queued so the PM Agent can re-process the intent with the
    additional context.
    """

    clarification: str = Field(min_length=3, max_length=2000)


class PodAssignmentUpsert(BaseModel):
    mission_id: str = Field(min_length=1)
    pod_name: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    assigned_at: datetime | None = None


class LogicNodeUpsert(BaseModel):
    mission_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    node: dict[str, Any]
    created_at: datetime | None = None


class KnowledgeUpsert(BaseModel):
    mission_id: str = Field(min_length=1)
    knowledge_id: str = Field(min_length=1)
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class AuditReportUpsert(BaseModel):
    mission_id: str = Field(min_length=1)
    audit_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    report: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class AgentActionEventUpsert(BaseModel):
    event_id: str | None = None
    mission_id: str = Field(min_length=1)
    project_id: str | None = None
    agent_id: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    status: str = Field(default="SUCCESS", min_length=1)
    object_type: str | None = None
    object_id: str | None = None
    tool_name: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    correlation_id: str | None = None
    parent_event_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    payload_summary: dict[str, Any] = Field(default_factory=dict)
    content_sha256: str | None = None
    blob_ref: str | None = None


class AgentActionEventRecord(BaseModel):
    event_id: str
    project_id: str
    mission_id: str
    agent_id: str
    service_name: str
    event_type: str
    status: str
    object_type: str | None = None
    object_id: str | None = None
    tool_name: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    correlation_id: str | None = None
    parent_event_id: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None
    payload_summary: dict[str, Any] = Field(default_factory=dict)
    content_sha256: str | None = None
    blob_ref: str | None = None
    prev_event_digest_sha256: str | None = None
    event_digest_sha256: str
    created_at: datetime


class ReviewApprovalUpsert(BaseModel):
    scope: Literal["builder", "repo", "delivery"]
    fingerprint: str = Field(min_length=12, max_length=200)
    summary: str = Field(min_length=3, max_length=400)
    approved_at: datetime | None = None
    expires_at: datetime | None = None
    hmac_digest: str | None = Field(default=None, min_length=16, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewApprovalRecord(BaseModel):
    approval_id: str
    scope: Literal["builder", "repo", "delivery"]
    fingerprint: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    receipt_digest: str
    storage_backend: str
    approved_at: datetime
    expires_at: datetime | None = None
    hmac_digest: str | None = None
    updated_at: datetime


class MissionBuildArtifactRecord(BaseModel):
    mission_id: str
    artifact_id: str
    artifact_type: str
    stage: str
    status: str
    storage_backend: str
    storage_ref: str | None = None
    digest_sha256: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    manifest: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] = Field(default_factory=dict)
    build_log: str = ""
    artifact_text: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentHeartbeatUpsert(BaseModel):
    agent_id: str = Field(min_length=1)
    state: str = Field(min_length=1)
    queue_depth: int = Field(default=0, ge=0)
    workload_pct: int = Field(default=0, ge=0, le=100)
    active_mission_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_heartbeat: datetime | None = None
