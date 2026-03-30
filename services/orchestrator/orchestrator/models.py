from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ==============================================================================
# Domain Models
# ==============================================================================


class MissionState(str, Enum):
    intake = "INTAKE"
    queued = "QUEUED"
    # v2 intermediate states (feature-flagged via MISSION_FLOW_V2_ENABLED)
    pm_intake = "PM_INTAKE"
    ceo_delegated = "CEO_DELEGATED"
    pod_assigned = "POD_ASSIGNED"
    specialist_assigned = "SPECIALIST_ASSIGNED"
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
    MissionState.ceo_delegated,
    MissionState.pod_assigned,
    MissionState.specialist_assigned,
    MissionState.running,
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
    "MISSION_CEO_DELEGATED",
    "MISSION_POD_ASSIGNED",
    "MISSION_SPECIALIST_ASSIGNED",
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
    # Operational / lifecycle events
    "MISSION_LOGICNODE_WRITTEN",
    "MISSION_COMPLETION_BLOCKED",
    # Agent events
    "AGENT_STATE_CHANGED",
]


VALID_TRANSITIONS: dict[MissionState, set[MissionState]] = {
    MissionState.intake: {MissionState.queued},
    MissionState.queued: {MissionState.pm_intake, MissionState.gating, MissionState.failed},

    # V2 flow
    MissionState.pm_intake: {MissionState.ceo_delegated, MissionState.failed},
    MissionState.ceo_delegated: {MissionState.pod_assigned, MissionState.failed},
    MissionState.pod_assigned: {MissionState.specialist_assigned, MissionState.failed},
    MissionState.specialist_assigned: {MissionState.running, MissionState.failed},

    # V1/V2 overlap
    MissionState.gating: {MissionState.running, MissionState.failed},
    MissionState.running: {MissionState.fusion, MissionState.failed},
    MissionState.fusion: {MissionState.verified, MissionState.failed},
    MissionState.verified: {MissionState.complete, MissionState.failed},
    MissionState.complete: set(),
    MissionState.failed: set(),
}

# ==============================================================================
# Database & Storage Models
# ==============================================================================


class MissionRecord(BaseModel):
    mission_id: str
    prompt: str
    requested_target_language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
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
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class MissionStateUpdate(BaseModel):
    new_state: MissionState
    expected_state: MissionState | None = None


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


class ReviewApprovalUpsert(BaseModel):
    scope: Literal["builder", "repo"]
    fingerprint: str = Field(min_length=12, max_length=200)
    summary: str = Field(min_length=3, max_length=400)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewApprovalRecord(BaseModel):
    approval_id: str
    scope: Literal["builder", "repo"]
    fingerprint: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    receipt_digest: str
    storage_backend: str
    approved_at: datetime
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
