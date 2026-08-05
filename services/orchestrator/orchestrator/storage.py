"""storage.py — Re-export façade for the orchestrator storage layer.

The storage layer is split across domain modules for maintainability.
This module re-exports every public symbol so all existing callers
(``from . import storage; storage.fetch_mission(...)``) continue
working unchanged.

Domain modules
--------------
storage_core        — DB connection, helpers, PodAssignmentConflictError
storage_missions    — Mission CRUD, state-event log, partition-result recording
storage_pods        — Pod assignments, project aggregation
storage_logicnodes  — LogicNode and knowledge-fragment persistence
storage_artifacts   — Audit reports, review approvals, build artifacts
storage_agents      — Agent heartbeats and runtime event log
"""
from __future__ import annotations

from .storage_agents import (
    create_agent_action_event,
    get_agent_heartbeat,
    insert_agent_action_event,
    list_agent_heartbeats,
    list_mission_agent_action_events,
    list_project_agent_action_events,
    list_recent_agent_events,
    prune_audit_tables,
    upsert_agent_heartbeat,
)
from .storage_artifacts import (
    get_build_artifact,
    get_review_approval,
    get_runtime_qc_report,
    get_testdata_manifest,
    insert_runtime_qc_report,
    insert_testdata_manifest,
    list_audit_reports,
    list_build_artifacts,
    list_recent_audit_reports,
    upsert_audit_report,
    upsert_build_artifact,
    upsert_review_approval,
)
from .storage_core import (
    PodAssignmentConflictError,
    _json_to_dict,
    _json_to_list,
    _to_iso,
    close_connection_pool,
    db_connect,
    ensure_db_schema,
    get_connection,
    init_connection_pool,
)
from .storage_logicnodes import (
    list_knowledge,
    list_logicnodes,
    list_recent_logicnodes,
    upsert_knowledge,
    upsert_knowledge_batch,
    upsert_logicnode,
    upsert_logicnodes_batch,
)
from .storage_missions import (
    count_missions,
    fetch_mission,
    insert_mission_event,
    list_mission_events,
    list_missions,
    list_missions_in_states,
    list_recent_mission_events,
    mission_state_counts,
    persist_intake_mission,
    record_partition_result,
    row_to_mission,
    transition_mission_state,
    update_mission_metadata,
    upsert_mission,
)
from .storage_pods import (
    PROVISIONAL_ASSIGNED_BY,
    get_pod_assignment,
    is_provisional_assignment,
    list_pod_assignments,
    summarize_projects,
    upsert_pod_assignment,
)

__all__ = [
    # core
    "PodAssignmentConflictError",
    "db_connect",
    "get_connection",
    "init_connection_pool",
    "close_connection_pool",
    "ensure_db_schema",
    "_to_iso",
    "_json_to_dict",
    "_json_to_list",
    # missions
    "row_to_mission",
    "upsert_mission",
    "persist_intake_mission",
    "fetch_mission",
    "update_mission_metadata",
    "list_missions",
    "list_missions_in_states",
    "insert_mission_event",
    "list_mission_events",
    "list_recent_mission_events",
    "transition_mission_state",
    "count_missions",
    "mission_state_counts",
    "record_partition_result",
    # pods
    "PROVISIONAL_ASSIGNED_BY",
    "upsert_pod_assignment",
    "get_pod_assignment",
    "is_provisional_assignment",
    "list_pod_assignments",
    "summarize_projects",
    # logicnodes
    "upsert_logicnode",
    "upsert_logicnodes_batch",
    "list_logicnodes",
    "list_recent_logicnodes",
    "upsert_knowledge",
    "upsert_knowledge_batch",
    "list_knowledge",
    # artifacts
    "upsert_audit_report",
    "list_audit_reports",
    "list_recent_audit_reports",
    "upsert_review_approval",
    "get_review_approval",
    "upsert_build_artifact",
    "list_build_artifacts",
    "get_build_artifact",
    "insert_testdata_manifest",
    "get_testdata_manifest",
    "insert_runtime_qc_report",
    "get_runtime_qc_report",
    # agents
    "create_agent_action_event",
    "upsert_agent_heartbeat",
    "get_agent_heartbeat",
    "list_agent_heartbeats",
    "list_recent_agent_events",
    "insert_agent_action_event",
    "list_mission_agent_action_events",
    "list_project_agent_action_events",
    "prune_audit_tables",
]
