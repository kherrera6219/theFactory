from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MissionState(str, Enum):
    intake = "INTAKE"
    queued = "QUEUED"
    running = "RUNNING"
    verified = "VERIFIED"
    complete = "COMPLETE"
    failed = "FAILED"


class MissionCreate(BaseModel):
    mission_id: str = Field(min_length=1)
    prompt: str = Field(min_length=3)
    requested_target_language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class MissionRecord(BaseModel):
    mission_id: str
    prompt: str
    requested_target_language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    state: MissionState
    created_at: str


class MissionEvent(BaseModel):
    mission_id: str
    previous_state: MissionState | None = None
    new_state: MissionState
    event_type: str
    ts: str


class MissionStateUpdate(BaseModel):
    new_state: MissionState
    expected_state: MissionState | None = None


class PodAssignmentUpsert(BaseModel):
    mission_id: str = Field(min_length=1)
    pod_name: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    assigned_at: str | None = None


class LogicNodeUpsert(BaseModel):
    mission_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    node: dict[str, Any]
    created_at: str | None = None


class KnowledgeUpsert(BaseModel):
    mission_id: str = Field(min_length=1)
    knowledge_id: str = Field(min_length=1)
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class AuditReportUpsert(BaseModel):
    mission_id: str = Field(min_length=1)
    audit_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    report: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class AgentHeartbeatUpsert(BaseModel):
    agent_id: str = Field(min_length=1)
    state: str = Field(min_length=1)
    queue_depth: int = Field(default=0, ge=0)
    workload_pct: int = Field(default=0, ge=0, le=100)
    active_mission_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_heartbeat: str | None = None
