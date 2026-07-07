from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .. import milvus_store, neo4j_store, object_store, qdrant_store, storage
from ..audit_events import record_audit_event, summarize_mapping
from ..auth import AuthContext
from ..llm_delegation import generate_pm_feature_contract, get_provider_health_summary
from ..logicnode_schema import validate_logicnode
from ..mission_flow_v2 import build_mission_charter
from ..models import (
    AgentActionEventUpsert,
    AgentHeartbeatUpsert,
    AuditReportUpsert,
    KnowledgeUpsert,
    LogicNodeUpsert,
    MissionBuildArtifactRecord,
    MissionEvent,
    MissionRecord,
    MissionState,
    PodAssignmentUpsert,
    RepoImportIndexUpsert,
    ReviewApprovalRecord,
    ReviewApprovalUpsert,
)
from ..review_policy import (
    REVIEW_APPROVAL_STORAGE_BACKEND,
    _review_approval_digest,
    _review_approval_id,
    _review_approval_record_path,
    _sanitize_review_text,
)
from ._deps import INTERNAL_AUTH_DEP

LOGGER = logging.getLogger(__name__)

router = APIRouter()

MISSION_TYPE_ALIASES = {
    "": "BUILD_NEW",
    "BUILD": "BUILD_NEW",
    "BUILD_NEW": "BUILD_NEW",
    "CREATE": "BUILD_NEW",
    "FEATURE": "BUILD_NEW",
    "FULL_BUILD": "BUILD_NEW",
    "IMPLEMENTATION": "BUILD_NEW",
    "NEW": "BUILD_NEW",
    "IMPORT_MODERNIZE": "IMPORT_MODERNIZE",
    "MODERNIZE": "IMPORT_MODERNIZE",
    "PORT": "PORT",
    "DEBUG": "DEBUG_REPAIR",
    "DEBUG_REPAIR": "DEBUG_REPAIR",
    "REPAIR": "DEBUG_REPAIR",
    "SECURITY": "SECURITY_HARDEN",
    "SECURITY_HARDEN": "SECURITY_HARDEN",
    "REDUCE_DEPENDENCIES": "REDUCE_DEPENDENCIES",
    "DEPENDENCY_REDUCTION": "REDUCE_DEPENDENCIES",
    "RUN_QC": "RUN_QC",
    "QC": "RUN_QC",
    "ARCHITECTURE": "ARCHITECTURE_DOCS",
    "ARCHITECTURE_DOCS": "ARCHITECTURE_DOCS",
    "ANALYZE": "ANALYZE_ONLY",
    "ANALYZE_ONLY": "ANALYZE_ONLY",
    "ANALYSIS": "ANALYZE_ONLY",
    "SELF_ANALYZE": "SELF_ANALYZE",
}


def _normalize_pm_mission_type(value: Any) -> str:
    normalized = str(value or "BUILD_NEW").strip().upper().replace("-", "_").replace(" ", "_")
    return MISSION_TYPE_ALIASES.get(normalized, "BUILD_NEW")


# ---------------------------------------------------------------------------
# Mission chain-trace helpers (moved from main.py)
# ---------------------------------------------------------------------------


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


@router.post("/internal/pod-assignment")
async def upsert_pod_assignment(
    request: Request,
    payload: PodAssignmentUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, payload.mission_id)

    assigned_at = payload.assigned_at or datetime.now(UTC).isoformat()
    try:
        record = await asyncio.to_thread(
            storage.upsert_pod_assignment,
            app.state.settings,
            payload.mission_id,
            payload.pod_name,
            payload.metadata,
            assigned_at,
        )
        await record_audit_event(
            app,
            mission_id=payload.mission_id,
            mission=mission,
            agent_id=(
                _agent_id_from_metadata(payload.metadata)
                or _agent_id_from_metadata(mission.metadata)
                or "SYSTEM"
            ),
            service_name="orchestrator",
            event_type="MISSION_POD_ASSIGNMENT_WRITTEN",
            object_type="pod_assignment",
            object_id=payload.pod_name,
            payload_summary={
                "pod_name": payload.pod_name,
                "metadata": summarize_mapping(payload.metadata),
            },
        )
        return record
    except storage.PodAssignmentConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "mission already assigned to a different pod",
                "assignment": exc.existing_assignment,
            },
        ) from exc


@router.post("/internal/pm/feature-contract")
async def create_pm_feature_contract(
    payload: dict[str, Any],
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    from ..llm_delegation.config import current_vault_secrets

    prompt = str(payload.get("prompt") or payload.get("request") or "").strip()
    source_code = payload.get("source_code")
    if len(prompt) < 3:
        raise HTTPException(status_code=400, detail="prompt must be at least 3 characters")

    mission_type = _normalize_pm_mission_type(payload.get("mission_type"))
    depth_mode = str(payload.get("depth_mode") or "STANDARD").strip().upper()
    output_mode = str(payload.get("output_mode") or "FULL_BUILD").strip().upper()
    requested_target_language = payload.get("requested_target_language")
    if requested_target_language is None:
        requested_target_language = payload.get("requestedTargetLanguage")
    if requested_target_language is not None:
        requested_target_language = str(requested_target_language).strip() or None

    vault = payload.get("vault") or {}
    token_vault = current_vault_secrets.set(vault)
    try:
        feature_contract = await generate_pm_feature_contract(
            prompt=prompt,
            source_code=source_code,
            mission_type=mission_type,
            depth_mode=depth_mode,
            output_mode=output_mode,
            requested_target_language=requested_target_language,
            conversation_context=payload.get("conversation_context"),
            user_intent=str(payload.get("user_intent") or "").strip() or None,
        )
    finally:
        current_vault_secrets.reset(token_vault)

    mission_charter = build_mission_charter(
        mission_id=str(payload.get("mission_id") or "preview"),
        prompt=prompt,
        requested_target_language=requested_target_language,
        feature_contract=feature_contract,
        mission_type=mission_type,
        depth_mode=depth_mode,
        output_mode=output_mode,
    )
    return {
        "feature_contract": feature_contract,
        "mission_charter": mission_charter,
        "source": feature_contract.get("source", "fallback"),
        "model_provider": feature_contract.get("model_provider"),
        "model": feature_contract.get("model"),
    }


@router.get("/internal/broker/provider-health")
async def get_broker_provider_health(_: AuthContext = INTERNAL_AUTH_DEP) -> dict[str, Any]:
    return get_provider_health_summary()


@router.get("/internal/missions/{mission_id}/pod-assignment")
async def get_pod_assignment(
    request: Request,
    mission_id: str,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    record = await asyncio.to_thread(storage.get_pod_assignment, app.state.settings, mission_id)
    if record is None:
        raise HTTPException(status_code=404, detail="pod assignment not found")
    return record


@router.get("/internal/missions/{mission_id}/chain-trace")
async def get_chain_trace(
    request: Request,
    mission_id: str,
    event_limit: int = Query(default=200, ge=1, le=1000),
    logicnode_limit: int = Query(default=200, ge=1, le=2000),
    build_artifact_limit: int = Query(default=20, ge=1, le=200),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, mission_id)
    assignment = await asyncio.to_thread(storage.get_pod_assignment, app.state.settings, mission_id)
    logicnodes = await asyncio.to_thread(
        storage.list_logicnodes,
        app.state.settings,
        mission_id,
        logicnode_limit,
    )
    events = await asyncio.to_thread(
        storage.list_mission_events,
        app.state.settings,
        mission_id,
        event_limit,
    )
    build_artifacts = await asyncio.to_thread(
        storage.list_build_artifacts,
        app.state.settings,
        mission_id,
        build_artifact_limit,
    )
    return _build_mission_chain_trace(
        mission=mission,
        pod_assignment=assignment,
        logicnodes=logicnodes,
        events=events,
        build_artifacts=build_artifacts,
    )


@router.get("/internal/missions/{mission_id}/testdata-manifest")
async def get_mission_testdata_manifest(
    request: Request,
    mission_id: str,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, mission_id)
    record = await asyncio.to_thread(storage.get_testdata_manifest, app.state.settings, mission_id)
    if record is not None:
        return record
    metadata = mission.metadata if isinstance(mission.metadata, dict) else {}
    manifest = metadata.get("testdata_manifest")
    if isinstance(manifest, dict):
        return {"mission_id": mission_id, "manifest": manifest, "source": "mission_metadata"}
    raise HTTPException(status_code=404, detail="testdata manifest not found")


@router.get("/internal/missions/{mission_id}/runtime-qc")
async def get_mission_runtime_qc(
    request: Request,
    mission_id: str,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, mission_id)
    record = await asyncio.to_thread(storage.get_runtime_qc_report, app.state.settings, mission_id)
    if record is not None:
        return record
    metadata = mission.metadata if isinstance(mission.metadata, dict) else {}
    report = metadata.get("runtime_qc_report")
    if isinstance(report, dict):
        return {"mission_id": mission_id, "runtime_qc_report": report, "source": "mission_metadata"}
    raise HTTPException(status_code=404, detail="runtime QC report not found")


@router.post("/internal/audit-events")
async def create_audit_event(
    request: Request,
    payload: AgentActionEventUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, payload.mission_id)
    return await record_audit_event(
        app,
        mission_id=payload.mission_id,
        mission=mission,
        agent_id=payload.agent_id,
        service_name=payload.service_name,
        event_type=payload.event_type,
        status=payload.status,
        object_type=payload.object_type,
        object_id=payload.object_id,
        tool_name=payload.tool_name,
        correlation_id=payload.correlation_id,
        parent_event_id=payload.parent_event_id,
        started_at=payload.started_at.isoformat() if payload.started_at else None,
        ended_at=payload.ended_at.isoformat() if payload.ended_at else None,
        payload_summary=payload.payload_summary,
        content_hash_source=payload.payload_summary,
        content_sha256_value=payload.content_sha256,
        blob_ref=payload.blob_ref,
    ) or {}


@router.get("/internal/missions/{mission_id}/audit-events")
async def get_mission_audit_events(
    request: Request,
    mission_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    return await asyncio.to_thread(
        storage.list_mission_agent_action_events,
        app.state.settings,
        mission_id,
        limit,
    )


@router.post("/internal/logicnodes")
async def upsert_logicnode(
    request: Request,
    payload: LogicNodeUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, payload.mission_id)

    created_at = (
        payload.created_at.isoformat()
        if isinstance(payload.created_at, datetime)
        else (payload.created_at or datetime.now(UTC).isoformat())
    )

    # Enforce schemas/logicnode.schema.json at the write boundary. Validation is
    # non-fatal: an invalid node is logged and persisted with the errors recorded
    # so a single malformed extraction does not abort the whole mission.
    validation_errors: list[str] = []
    try:
        validation_errors = validate_logicnode(
            payload.node, schema_path=app.state.settings.logicnode_schema_path
        )
    except Exception as exc:  # pragma: no cover - schema file misconfiguration
        LOGGER.error("logicnode schema unavailable; skipping validation: %s", exc)
    if validation_errors:
        LOGGER.warning(
            "logicnode %s for mission %s failed schema validation: %s",
            payload.node_id,
            payload.mission_id,
            "; ".join(validation_errors),
        )

    record = await asyncio.to_thread(
        storage.upsert_logicnode,
        app.state.settings,
        payload.mission_id,
        payload.node_id,
        payload.node,
        created_at,
    )
    if validation_errors:
        record["validation_errors"] = validation_errors
    await record_audit_event(
        app,
        mission_id=payload.mission_id,
        mission=mission,
        agent_id=(
            _agent_id_from_node(payload.node)
            or _agent_id_from_metadata(mission.metadata)
            or "SYSTEM"
        ),
        service_name="orchestrator",
        event_type="MISSION_LOGICNODE_WRITTEN",
        object_type="logicnode",
        object_id=payload.node_id,
        status="ERROR" if validation_errors else "SUCCESS",
        payload_summary={
            "node_id": payload.node_id,
            "node": summarize_mapping(payload.node),
            "validation_errors": validation_errors,
        },
    )
    return record


@router.get("/internal/missions/{mission_id}/logicnodes")
async def get_logicnodes(
    request: Request,
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    return await asyncio.to_thread(storage.list_logicnodes, app.state.settings, mission_id, limit)


@router.post("/internal/knowledge")
async def upsert_knowledge(
    request: Request,
    payload: KnowledgeUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, payload.mission_id)

    created_at = (
        payload.created_at.isoformat()
        if isinstance(payload.created_at, datetime)
        else (payload.created_at or datetime.now(UTC).isoformat())
    )
    record = await asyncio.to_thread(
        storage.upsert_knowledge,
        app.state.settings,
        payload.mission_id,
        payload.knowledge_id,
        payload.content,
        created_at,
    )
    if app.state.settings.qdrant_enabled:
        try:
            await asyncio.to_thread(
                qdrant_store.upsert_knowledge,
                app.state.settings,
                payload.mission_id,
                payload.knowledge_id,
                payload.content,
                created_at,
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to upsert qdrant knowledge for mission %s/%s: %s",
                payload.mission_id,
                payload.knowledge_id,
                exc,
            )
    if app.state.settings.milvus_enabled:
        try:
            await _main._run_optional_mirror_write(
                adapter="milvus",
                artifact="knowledge",
                fn=milvus_store.upsert_knowledge,
                args=(
                    app.state.settings,
                    payload.mission_id,
                    payload.knowledge_id,
                    payload.content,
                    created_at,
                ),
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to upsert milvus knowledge for mission %s/%s: %s",
                payload.mission_id,
                payload.knowledge_id,
                exc,
            )
    if app.state.settings.neo4j_enabled:
        try:
            await _main._run_optional_mirror_write(
                adapter="neo4j",
                artifact="knowledge",
                fn=neo4j_store.upsert_knowledge,
                args=(
                    app.state.settings,
                    payload.mission_id,
                    payload.knowledge_id,
                    payload.content,
                    created_at,
                ),
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to upsert neo4j knowledge for mission %s/%s: %s",
                payload.mission_id,
                payload.knowledge_id,
                exc,
            )
    await record_audit_event(
        app,
        mission_id=payload.mission_id,
        mission=mission,
        agent_id=(
            _agent_id_from_metadata(payload.content.get("metadata"))
            if isinstance(payload.content, dict)
            else None
        )
        or _agent_id_from_metadata(mission.metadata)
        or "SYSTEM",
        service_name="orchestrator",
        event_type="MISSION_KNOWLEDGE_WRITTEN",
        object_type="knowledge",
        object_id=payload.knowledge_id,
        payload_summary={
            "knowledge_id": payload.knowledge_id,
            "content": summarize_mapping(payload.content),
        },
        content_hash_source=payload.content,
    )
    return record


@router.get("/internal/missions/{mission_id}/knowledge")
async def get_knowledge(
    request: Request,
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    if app.state.settings.qdrant_enabled:
        try:
            records = await asyncio.to_thread(
                qdrant_store.list_knowledge,
                app.state.settings,
                mission_id,
                limit,
            )
            if records:
                return records
        except Exception as exc:
            LOGGER.warning("failed to query qdrant knowledge for mission %s: %s", mission_id, exc)
    if app.state.settings.milvus_enabled:
        try:
            records = await asyncio.to_thread(
                milvus_store.list_knowledge,
                app.state.settings,
                mission_id,
                limit,
            )
            if records:
                return records
        except Exception as exc:
            LOGGER.warning("failed to query milvus knowledge for mission %s: %s", mission_id, exc)
    return await asyncio.to_thread(storage.list_knowledge, app.state.settings, mission_id, limit)


def _repo_chunk_batch_items(
    chunk_records: list[dict[str, Any]],
    created_at: str,
) -> list[dict[str, Any]]:
    return [
        {
            "knowledge_id": str(chunk["knowledge_id"]),
            "content": {k: v for k, v in chunk.items() if k != "knowledge_id"},
            "created_at": created_at,
        }
        for chunk in chunk_records
        if chunk.get("knowledge_id")
    ]


def _persist_repo_chunk_batch(
    settings: Any,
    mission_id: str,
    items: list[dict[str, Any]],
) -> int:
    """Sync helper — bulk-writes repo chunk knowledge rows on one connection.

    Runs off the event loop via ``asyncio.to_thread``. Chunk records skip the
    Qdrant/Milvus/Neo4j mirrors that the manifest/summary records get below —
    per-file chunks are numerous and, per the migration plan, deliberately
    bounded/compact for PostgreSQL keyword retrieval rather than semantic
    search; mirroring every chunk would mean one embedding call per file.
    """
    with storage.get_connection() as conn:
        return storage.upsert_knowledge_batch(conn, mission_id, items)


@router.post("/internal/missions/{mission_id}/repo-import-index")
async def upsert_repo_import_index(
    request: Request,
    mission_id: str,
    payload: RepoImportIndexUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    """Repo ZIP Import Phase 6 — ingest Mission-Control-built repo manifest/
    summary/chunk records into ``mission_knowledge`` and resume the queued
    mission (Phase 5's ``_prepare_pm_intake`` guard was blocking on
    ``index_status``). See docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md."""
    import orchestrator.main as _main

    from ..runtime import start_lifecycle_task

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, mission_id)

    created_at = datetime.now(UTC).isoformat()
    knowledge_ids: list[str] = []

    for record in (payload.import_manifest, payload.summary_record):
        knowledge_id = str(record.get("knowledge_id") or "").strip()
        if not knowledge_id:
            continue
        content = {k: v for k, v in record.items() if k != "knowledge_id"}
        await asyncio.to_thread(
            storage.upsert_knowledge,
            app.state.settings,
            mission_id,
            knowledge_id,
            content,
            created_at,
        )
        knowledge_ids.append(knowledge_id)
        if app.state.settings.qdrant_enabled:
            try:
                await asyncio.to_thread(
                    qdrant_store.upsert_knowledge,
                    app.state.settings,
                    mission_id,
                    knowledge_id,
                    content,
                    created_at,
                )
            except Exception as exc:
                LOGGER.warning(
                    "failed to mirror repo-import knowledge %s to qdrant: %s", knowledge_id, exc
                )

    chunk_items = _repo_chunk_batch_items(payload.chunk_records, created_at)
    if chunk_items:
        await asyncio.to_thread(
            _persist_repo_chunk_batch, app.state.settings, mission_id, chunk_items
        )
        knowledge_ids.extend(item["knowledge_id"] for item in chunk_items)

    metadata = dict(mission.metadata or {})
    repo_import = dict(metadata.get("repo_import") or {})
    repo_import["index_status"] = payload.index_status
    repo_import["index_errors"] = payload.index_errors
    repo_import["indexed_knowledge_count"] = len(knowledge_ids)
    repo_import["repo_knowledge_ids"] = knowledge_ids
    metadata["repo_import"] = repo_import
    updated = await asyncio.to_thread(
        storage.update_mission_metadata, app.state.settings, mission_id, metadata
    )

    await record_audit_event(
        app,
        mission_id=mission_id,
        mission=updated or mission,
        agent_id="AGENT-06-IS",
        service_name="orchestrator",
        event_type="MISSION_REPO_INDEX_COMPLETE",
        object_type="repo_import",
        object_id=mission_id,
        payload_summary={
            "index_status": repo_import["index_status"],
            "indexed_knowledge_count": repo_import["indexed_knowledge_count"],
        },
        content_hash_source=repo_import,
    )

    if payload.index_status == "complete":
        start_lifecycle_task(app, mission_id)

    return {
        "mission_id": mission_id,
        "index_status": repo_import["index_status"],
        "indexed_knowledge_count": repo_import["indexed_knowledge_count"],
    }


@router.get("/internal/missions/{mission_id}/knowledge-graph")
async def get_knowledge_graph(
    request: Request,
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    if not app.state.settings.neo4j_enabled:
        return []
    try:
        return await asyncio.to_thread(
            neo4j_store.list_mission_graph,
            app.state.settings,
            mission_id,
            limit,
        )
    except Exception as exc:
        LOGGER.warning("failed to query neo4j graph for mission %s: %s", mission_id, exc)
        return []


@router.post("/internal/audit-reports")
async def upsert_audit_report(
    request: Request,
    payload: AuditReportUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, payload.mission_id)

    created_at = (
        payload.created_at.isoformat()
        if isinstance(payload.created_at, datetime)
        else (payload.created_at or datetime.now(UTC).isoformat())
    )

    report_dict = payload.report
    if isinstance(report_dict, dict) and "signature_record" in report_dict:
        from shared_runtime.crypto_signing import verify_payload
        signature_record = report_dict["signature_record"]
        payload_to_verify = {k: v for k, v in report_dict.items() if k != "signature_record"}
        if not verify_payload(payload_to_verify, signature_record):
            raise HTTPException(status_code=422, detail="invalid digital signature on audit report")
    elif app.state.settings.environment == "production":
        raise HTTPException(status_code=422, detail="digital signature is required in production environment")
    record = await asyncio.to_thread(
        storage.upsert_audit_report,
        app.state.settings,
        payload.mission_id,
        payload.audit_id,
        payload.status,
        payload.report,
        created_at,
    )
    if app.state.settings.neo4j_enabled:
        try:
            await _main._run_optional_mirror_write(
                adapter="neo4j",
                artifact="audit_report",
                fn=neo4j_store.upsert_audit_report,
                args=(
                    app.state.settings,
                    payload.mission_id,
                    payload.audit_id,
                    payload.status,
                    payload.report,
                    created_at,
                ),
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to upsert neo4j audit report for mission %s/%s: %s",
                payload.mission_id,
                payload.audit_id,
                exc,
            )
    if app.state.settings.object_storage_enabled:
        try:
            await _main._run_optional_mirror_write(
                adapter="object_storage",
                artifact="audit_report",
                fn=object_store.put_audit_report,
                args=(
                    app.state.settings,
                    payload.mission_id,
                    payload.audit_id,
                    payload.status,
                    payload.report,
                    created_at,
                ),
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to store audit artifact in object storage for mission %s/%s: %s",
                payload.mission_id,
                payload.audit_id,
                exc,
            )
    await record_audit_event(
        app,
        mission_id=payload.mission_id,
        mission=mission,
        agent_id=(
            _agent_id_from_metadata(payload.report)
            or _agent_id_from_metadata(
                payload.report.get("result") if isinstance(payload.report, dict) else None
            )
            or _agent_id_from_metadata(mission.metadata)
            or "SYSTEM"
        ),
        service_name="orchestrator",
        event_type="MISSION_AUDIT_REPORT_WRITTEN",
        object_type="audit_report",
        object_id=payload.audit_id,
        payload_summary={
            "audit_id": payload.audit_id,
            "status": payload.status,
            "report": summarize_mapping(payload.report),
        },
        content_hash_source=payload.report,
    )
    return record


@router.post("/internal/review-approvals")
async def create_review_approval(
    request: Request,
    payload: ReviewApprovalUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    scope = payload.scope
    fingerprint = _sanitize_review_text(payload.fingerprint, 200)
    summary = _sanitize_review_text(payload.summary, 400)
    if len(fingerprint) < 12:
        raise HTTPException(status_code=400, detail="fingerprint must be at least 12 characters")
    if len(summary) < 3:
        raise HTTPException(status_code=400, detail="summary must be at least 3 characters")

    approval_id = _review_approval_id(scope, fingerprint)
    approved_at = (payload.approved_at or datetime.now(UTC)).isoformat()
    record_without_digest = {
        "approval_id": approval_id,
        "scope": scope,
        "fingerprint": fingerprint,
        "summary": summary,
        "metadata": payload.metadata,
        "storage_backend": REVIEW_APPROVAL_STORAGE_BACKEND,
        "approved_at": approved_at,
        "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
        "hmac_digest": payload.hmac_digest,
    }
    receipt_digest = _review_approval_digest(record_without_digest)
    record = await asyncio.to_thread(
        storage.upsert_review_approval,
        app.state.settings,
        approval_id,
        scope,
        fingerprint,
        summary,
        payload.metadata,
        receipt_digest,
        REVIEW_APPROVAL_STORAGE_BACKEND,
        approved_at,
        payload.expires_at.isoformat() if payload.expires_at else None,
        payload.hmac_digest,
    )
    validated = ReviewApprovalRecord(**record).model_dump(mode="json")
    validated["record_path"] = _review_approval_record_path(approval_id)
    return validated


@router.get("/internal/review-approvals/{approval_id}")
async def get_review_approval(
    request: Request,
    approval_id: str,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    record = await asyncio.to_thread(storage.get_review_approval, app.state.settings, approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="review approval not found")
    validated = ReviewApprovalRecord(**record).model_dump(mode="json")
    validated["record_path"] = _review_approval_record_path(approval_id)
    return validated


@router.get("/internal/missions/{mission_id}/audit-reports")
async def get_audit_reports(
    request: Request,
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    return await asyncio.to_thread(
        storage.list_audit_reports, app.state.settings, mission_id, limit
    )


@router.get("/internal/missions/{mission_id}/audit-artifacts")
async def get_audit_artifacts(
    request: Request,
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[dict[str, Any]]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    if not app.state.settings.object_storage_enabled:
        return []
    try:
        return await asyncio.to_thread(
            object_store.list_audit_artifacts,
            app.state.settings,
            mission_id,
            limit,
        )
    except Exception as exc:
        LOGGER.warning(
            "failed to list object-storage audit artifacts for mission %s: %s",
            mission_id,
            exc,
        )
        return []


@router.get("/internal/missions/{mission_id}/build-artifacts")
async def get_build_artifacts(
    request: Request,
    mission_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> list[MissionBuildArtifactRecord]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    records = await asyncio.to_thread(
        storage.list_build_artifacts,
        app.state.settings,
        mission_id,
        limit,
    )
    return [MissionBuildArtifactRecord(**record) for record in records]


@router.get("/internal/missions/{mission_id}/build-artifacts/{artifact_id}")
async def get_build_artifact(
    request: Request,
    mission_id: str,
    artifact_id: str,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> Any:
    """Return the build artifact record.

    When the artifact is stored in object storage (``storage_backend == "s3"``),
    a 302 redirect to a presigned download URL is returned instead of the full
    record.  This keeps large artifacts out of the API response body.
    """
    from fastapi.responses import RedirectResponse

    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, mission_id)
    record = await asyncio.to_thread(
        storage.get_build_artifact,
        app.state.settings,
        mission_id,
        artifact_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="build artifact not found")

    # S4-05: redirect to presigned URL when artifact lives in object storage
    if record.get("storage_backend") == "s3" and record.get("storage_ref"):
        settings = app.state.settings
        if settings.object_storage_enabled:
            try:
                from ..object_store import get_presigned_url
                presigned = await asyncio.to_thread(
                    get_presigned_url, settings, record["storage_ref"]
                )
                return RedirectResponse(url=presigned, status_code=302)
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not generate presigned URL: {exc}",
                ) from exc

    if (
        record
        and record.get("artifact_text") is not None
        and isinstance(record.get("verification"), dict)
    ):
        verification = record["verification"]
        if "signature_record" in verification:
            from shared_runtime.crypto_signing import verify_payload
            verification["verified"] = verify_payload(
                record["artifact_text"], verification["signature_record"]
            )
        elif verification.get("artifact_digest_sha256") or verification.get(
            "bundle_digest_sha256"
        ):
            # No signature was produced at build time (e.g. the signing key
            # was unavailable) -- without this fallback, "verified" was a
            # write-time-only assertion never re-checked against the
            # currently stored bytes, so a corrupted/tampered artifact_text
            # would still report verified=true forever. Independently
            # re-hash and compare against whichever digest field this
            # artifact type recorded.
            expected_digest = verification.get("artifact_digest_sha256") or verification.get(
                "bundle_digest_sha256"
            )
            actual_digest = hashlib.sha256(record["artifact_text"].encode("utf-8")).hexdigest()
            verification["verified"] = hmac.compare_digest(actual_digest, str(expected_digest))

    return MissionBuildArtifactRecord(**record)


@router.post("/internal/missions/{mission_id}/partition-results")
async def upsert_partition_result(
    request: Request,
    mission_id: str,
    payload: dict[str, Any],
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    mission = await _main._fetch_existing_mission(app, mission_id)

    partition_id = str(payload.get("partition_id", "")).strip()
    agent_id = str(payload.get("agent_id", "")).strip()
    if not partition_id or not agent_id:
        raise HTTPException(status_code=422, detail="partition_id and agent_id are required")

    result_payload = {
        "partition_id": partition_id,
        "instance_index": int(payload.get("instance_index", 0)),
        "agent_id": agent_id,
        "logicnodes": [node for node in payload.get("logicnodes", []) if isinstance(node, dict)],
        "artifacts": [
            artifact for artifact in payload.get("artifacts", []) if isinstance(artifact, dict)
        ],
        "report": payload.get("report") if isinstance(payload.get("report"), dict) else {},
        "completed_at": payload.get("completed_at") or datetime.now(UTC).isoformat(),
    }

    record = await asyncio.to_thread(
        storage.record_partition_result,
        app.state.settings,
        mission_id,
        result_payload,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="mission not found")

    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    if record.state == MissionState.running and bool(metadata.get("scaling_merge_complete")):
        _main.start_lifecycle_task(app, mission_id)
    await record_audit_event(
        app,
        mission_id=mission_id,
        mission=record,
        agent_id=agent_id,
        service_name="orchestrator",
        event_type="MISSION_PARTITION_RESULT_RECORDED",
        object_type="partition_result",
        object_id=partition_id,
        payload_summary={
            "partition_id": partition_id,
            "instance_index": result_payload["instance_index"],
            "logicnode_count": len(result_payload["logicnodes"]),
            "artifact_count": len(result_payload["artifacts"]),
            "report": summarize_mapping(result_payload["report"]),
            "scaling_complete": bool(metadata.get("scaling_merge_complete", False)),
        },
        content_hash_source=result_payload,
    )

    partition_results = metadata.get("partition_results")
    return {
        "mission_id": mission_id,
        "state": record.state.value,
        "partition_id": partition_id,
        "partition_result_count": (
            len(partition_results) if isinstance(partition_results, dict) else 0
        ),
        "scaling_complete": bool(metadata.get("scaling_merge_complete", False)),
        "merged_partition_result": (
            metadata.get("merged_partition_result")
            if isinstance(metadata.get("merged_partition_result"), dict)
            else None
        ),
        "target_language": mission.requested_target_language,
    }


@router.post("/internal/agents/heartbeat")
async def upsert_agent_heartbeat(
    request: Request,
    payload: AgentHeartbeatUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    record = await _main._upsert_agent_heartbeat(app, payload, emit_stream_event=True)
    if record.get("state_changed") or payload.active_mission_ids:
        for mission_id in payload.active_mission_ids[:10]:
            try:
                mission = await _main._fetch_existing_mission(app, mission_id)
            except HTTPException:
                continue
            await record_audit_event(
                app,
                mission_id=mission_id,
                mission=mission,
                agent_id=payload.agent_id,
                service_name="orchestrator",
                event_type="AGENT_HEARTBEAT_UPDATED",
                status="SUCCESS",
                object_type="heartbeat",
                object_id=payload.agent_id,
                payload_summary={
                    "state": payload.state,
                    "queue_depth": payload.queue_depth,
                    "workload_pct": payload.workload_pct,
                    "metadata": summarize_mapping(payload.metadata),
                    "state_changed": bool(record.get("state_changed")),
                },
            )
    return record


@router.get("/internal/prompt-registry", dependencies=[INTERNAL_AUTH_DEP])
async def get_prompt_registry() -> Any:
    """Return all registered versioned prompt assets."""
    from ..prompt_registry import list_prompts
    return {"prompts": list_prompts(), "count": len(list_prompts())}


@router.post("/internal/maintenance/diagnostics")
async def create_diagnostics(
    request: Request,
    mission_id: str | None = None,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    """Generate a sanitized diagnostic bundle."""
    from ..system_maintenance import get_maintenance_manager
    manager = get_maintenance_manager(request.app)
    path = await manager.create_diagnostic_bundle(mission_id=mission_id)
    return {"ok": True, "bundle_path": path}


@router.post("/internal/maintenance/backup")
async def trigger_backup(
    request: Request,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    """Trigger a full stateful backup."""
    from ..system_maintenance import get_maintenance_manager
    manager = get_maintenance_manager(request.app)
    path = await manager.run_full_backup()
    if path.startswith("ERROR"):
        raise HTTPException(status_code=500, detail=path)
    return {"ok": True, "backup_path": path}
