from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .. import milvus_store, neo4j_store, object_store, qdrant_store, storage
from ..auth import AuthContext
from ..models import (
    AgentHeartbeatUpsert,
    AuditReportUpsert,
    KnowledgeUpsert,
    LogicNodeUpsert,
    MissionBuildArtifactRecord,
    MissionState,
    PodAssignmentUpsert,
    ReviewApprovalRecord,
    ReviewApprovalUpsert,
)
from ._deps import INTERNAL_AUTH_DEP

LOGGER = logging.getLogger(__name__)

router = APIRouter()

REVIEW_APPROVAL_STORAGE_BACKEND = "postgres"


@router.post("/internal/pod-assignment")
async def upsert_pod_assignment(
    request: Request,
    payload: PodAssignmentUpsert,
    _: AuthContext = INTERNAL_AUTH_DEP,
) -> dict[str, Any]:
    import orchestrator.main as _main

    app = request.app
    await _main._ensure_db_ready(app)
    await _main._fetch_existing_mission(app, payload.mission_id)

    assigned_at = payload.assigned_at or datetime.now(UTC).isoformat()
    try:
        return await asyncio.to_thread(
            storage.upsert_pod_assignment,
            app.state.settings,
            payload.mission_id,
            payload.pod_name,
            payload.metadata,
            assigned_at,
        )
    except storage.PodAssignmentConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "mission already assigned to a different pod",
                "assignment": exc.existing_assignment,
            },
        ) from exc


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
    return _main._build_mission_chain_trace(
        mission=mission,
        pod_assignment=assignment,
        logicnodes=logicnodes,
        events=events,
        build_artifacts=build_artifacts,
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
    await _main._fetch_existing_mission(app, payload.mission_id)

    created_at = payload.created_at or datetime.now(UTC).isoformat()
    return await asyncio.to_thread(
        storage.upsert_logicnode,
        app.state.settings,
        payload.mission_id,
        payload.node_id,
        payload.node,
        created_at,
    )


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
    await _main._fetch_existing_mission(app, payload.mission_id)

    created_at = payload.created_at or datetime.now(UTC).isoformat()
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
    await _main._fetch_existing_mission(app, payload.mission_id)

    created_at = payload.created_at or datetime.now(UTC).isoformat()
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
    fingerprint = _main._sanitize_review_text(payload.fingerprint, 200)
    summary = _main._sanitize_review_text(payload.summary, 400)
    if len(fingerprint) < 12:
        raise HTTPException(status_code=400, detail="fingerprint must be at least 12 characters")
    if len(summary) < 3:
        raise HTTPException(status_code=400, detail="summary must be at least 3 characters")

    approval_id = _main._review_approval_id(scope, fingerprint)
    approved_at = datetime.now(UTC).isoformat()
    record_without_digest = {
        "approval_id": approval_id,
        "scope": scope,
        "fingerprint": fingerprint,
        "summary": summary,
        "metadata": payload.metadata,
        "storage_backend": REVIEW_APPROVAL_STORAGE_BACKEND,
        "approved_at": approved_at,
    }
    receipt_digest = _main._review_approval_digest(record_without_digest)
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
    )
    validated = ReviewApprovalRecord(**record).model_dump(mode="json")
    validated["record_path"] = _main._review_approval_record_path(approval_id)
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
    validated["record_path"] = _main._review_approval_record_path(approval_id)
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
) -> MissionBuildArtifactRecord:
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
    return await _main._upsert_agent_heartbeat(app, payload, emit_stream_event=True)
