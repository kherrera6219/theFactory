"""Chain-trace, routing, and agent-id helpers for internal orchestrator routes."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from shared_runtime.mission_types import UnknownMissionTypeError, normalize_mission_type

from ..models import MissionEvent, MissionRecord


def _normalize_pm_mission_type(value: Any) -> str:
    try:
        return normalize_mission_type(value)
    except UnknownMissionTypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _route_provenance_snapshot(payload: Any, *, role: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    mission_context = payload.get("mission_context")
    snapshot = {
        "role": role,
        "source": payload.get("source"),
        "llm_route": payload.get("llm_route"),
        "model_provider": payload.get("model_provider"),
        "model": payload.get("model"),
    }
    if role == "ceo":
        snapshot["target_agent_id"] = payload.get("pod_manager_agent_id")
        snapshot["specialist_agent_id"] = payload.get("specialist_agent_id")
        snapshot["rationale"] = payload.get("rationale")
    elif role == "pod_manager":
        snapshot["target_agent_id"] = payload.get("specialist_agent_id")
        snapshot["pod_manager_agent_id"] = payload.get("pod_manager_agent_id")
        snapshot["rationale"] = payload.get("rationale")
    else:
        snapshot["specialist_agent_id"] = payload.get("specialist_agent_id")
        snapshot["pod_manager_agent_id"] = payload.get("pod_manager_agent_id")
        snapshot["plan_summary"] = payload.get("plan_summary")
        snapshot["deliverables"] = payload.get("deliverables")
        snapshot["risk_notes"] = payload.get("risk_notes")
    if isinstance(mission_context, dict):
        snapshot["mission_source"] = mission_context.get("source")
    return snapshot


def _artifact_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    artifacts = metadata.get("mission_artifacts")
    if not isinstance(artifacts, dict):
        return {}
    return {
        str(stage): artifact
        for stage, artifact in artifacts.items()
        if isinstance(stage, str) and isinstance(artifact, dict)
    }


def _scaling_summary(metadata: dict[str, Any]) -> dict[str, Any] | None:
    decision = metadata.get("scaling_decision")
    if not isinstance(decision, dict):
        return None

    partition_results = metadata.get("partition_results")
    partition_result_count = len(partition_results) if isinstance(partition_results, dict) else 0
    return {
        "active": bool(metadata.get("scaling_active", False)),
        "decision": decision,
        "partition_result_count": partition_result_count,
        "partition_events_emitted": bool(metadata.get("scaling_partition_events_emitted", False)),
        "complete": bool(metadata.get("scaling_merge_complete", False)),
        "merged_result": (
            metadata.get("merged_partition_result")
            if isinstance(metadata.get("merged_partition_result"), dict)
            else None
        ),
    }


def _build_mission_chain_trace(
    *,
    mission: MissionRecord,
    pod_assignment: dict[str, Any] | None,
    logicnodes: list[dict[str, Any]],
    events: list[MissionEvent],
    build_artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    metadata = mission.metadata if isinstance(mission.metadata, dict) else {}
    ceo_delegation = metadata.get("ceo_delegation")
    pod_manager_delegation = metadata.get("pod_manager_delegation")
    specialist_plan = metadata.get("specialist_plan")
    raw_trace = metadata.get("chain_trace")
    chain_trace = (
        [record for record in raw_trace if isinstance(record, dict)]
        if isinstance(raw_trace, list)
        else []
    )
    has_pod_assigned = any(
        str(record.get("event_type", "")).upper()
        in {"MISSION_POD_ASSIGNED", "MISSION_POD_MANAGER_ASSIGNED"}
        for record in chain_trace
    )
    if pod_assignment and not has_pod_assigned:
        chain_trace.append(
            {
                "event_type": "MISSION_POD_ASSIGNED",
                "agent_id": str(metadata.get("assigned_pod_manager_agent_id", "")),
                "ts": str(pod_assignment.get("updated_at", mission.created_at)),
                "details": {"pod_name": pod_assignment.get("pod_name")},
            }
        )
    has_logicnode_event = any(
        str(record.get("event_type", "")).upper() == "MISSION_LOGICNODE_WRITTEN"
        for record in chain_trace
    )
    if logicnodes and not has_logicnode_event:
        chain_trace.append(
            {
                "event_type": "MISSION_LOGICNODE_WRITTEN",
                "agent_id": str(metadata.get("assigned_specialist_agent_id", "")),
                "ts": str(logicnodes[0].get("created_at", mission.created_at)),
                "details": {"logicnode_count": len(logicnodes)},
            }
        )
    if not any(
        str(record.get("event_type", "")).upper() == "MISSION_COMPLETION_BLOCKED"
        for record in chain_trace
    ):
        blocked_event = next(
            (record for record in events if record.event_type == "MISSION_COMPLETION_BLOCKED"),
            None,
        )
        if blocked_event is not None:
            chain_trace.append(
                {
                    "event_type": "MISSION_COMPLETION_BLOCKED",
                    "agent_id": str(metadata.get("executive_agent_id", "")),
                    "ts": blocked_event.ts,
                    "details": {"source": "mission-events"},
                }
            )

    chain_trace = sorted(
        chain_trace,
        key=lambda record: str(record.get("ts", "")),
    )
    route_provenance = {
        "ceo": _route_provenance_snapshot(ceo_delegation, role="ceo"),
        "pod_manager": _route_provenance_snapshot(pod_manager_delegation, role="pod_manager"),
        "specialist": _route_provenance_snapshot(specialist_plan, role="specialist"),
    }
    route_provenance["fallback_used"] = any(
        isinstance(snapshot, dict) and snapshot.get("source") == "fallback"
        for snapshot in route_provenance.values()
        if snapshot is not None
    )
    return {
        "mission_id": mission.mission_id,
        "lifecycle_engine": mission.lifecycle_engine or metadata.get("lifecycle_engine"),
        "routing_enforced": bool(metadata.get("routing_enforced", False)),
        "routing_version": metadata.get("routing_version"),
        "selected_agent_id": metadata.get("selected_agent_id"),
        "intake_agent_id": metadata.get("intake_agent_id"),
        "executive_agent_id": metadata.get("executive_agent_id"),
        "assigned_pod_manager_agent_id": metadata.get("assigned_pod_manager_agent_id"),
        "assigned_specialist_agent_id": metadata.get("assigned_specialist_agent_id"),
        "pod_assignment": pod_assignment,
        "logicnode_count": len(logicnodes),
        "artifact_summary": _artifact_summary(metadata),
        "build_artifacts": build_artifacts or [],
        "scaling": _scaling_summary(metadata),
        "route_provenance": route_provenance,
        "feature_contract": metadata.get("feature_contract"),
        "mission_charter": metadata.get("mission_charter"),
        "mission_contract": metadata.get("mission_contract"),
        "logic_clusters": metadata.get("logic_clusters"),
        "pod_group_standards": metadata.get("pod_group_standards"),
        "fetch_result": metadata.get("fetch_result"),
        "application_intelligence_map": metadata.get("application_intelligence_map"),
        "equivalence_report": metadata.get("equivalence_report"),
        "security_compliance_report": metadata.get("security_compliance_report"),
        "dependency_inventory": metadata.get("dependency_inventory"),
        "dependency_classification_report": metadata.get("dependency_classification_report"),
        "dependency_absorption_report": metadata.get("dependency_absorption_report"),
        "depabs_execution": metadata.get("depabs_execution"),
        "sbom_delta": metadata.get("sbom_delta"),
        "dependency_survival_justifications": metadata.get(
            "dependency_survival_justifications"
        ),
        "testdata_manifest": metadata.get("testdata_manifest"),
        "runtime_qc_report": metadata.get("runtime_qc_report"),
        "master_logic_stream": metadata.get("master_logic_stream"),
        "delivery_summary": metadata.get("delivery_summary"),
        "events": chain_trace,
    }


def _agent_id_from_value(candidate: Any) -> str | None:
    normalized = str(candidate or "").strip().upper()
    return normalized or None


def _agent_id_from_metadata(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in (
        "agent_id",
        "selected_agent_id",
        "assigned_agent_id",
        "assigned_specialist_agent_id",
        "assigned_pod_manager_agent_id",
        "target_agent_id",
    ):
        normalized = _agent_id_from_value(metadata.get(key))
        if normalized:
            return normalized
    return None


def _agent_id_from_node(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    normalized = _agent_id_from_value(node.get("agent_id"))
    if normalized:
        return normalized
    nested = node.get("payload")
    if isinstance(nested, dict):
        return _agent_id_from_metadata(nested)
    return None
