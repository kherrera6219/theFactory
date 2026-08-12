from __future__ import annotations

import asyncio
import importlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from ..agent_scaling import (
    scaling_decision_from_metadata,
)
from ..aim_generator import mission_requires_aim
from ..llm_delegation import (
    generate_logic_clusters,
    generate_mission_contract,
)
from ..mission_flow import (
    CEO_AGENT_ID,
    PM_AGENT_ID,
    append_chain_event,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
    with_chain_defaults,
)
from ..models import MissionState
from ..port_coordinator import _setup_port_two_phase
from ..protocol import to_event_priority
from .base import (
    _chain_event_exists,
    _extract_cross_pod_flags,
    _extract_support_agent_flags,
    _mission_context,
    _record_artifact,
    _setting_bool,
    _validate_agent_id,
    build_mission_charter,
)

LOGGER = logging.getLogger(__name__)

def _pkg() -> Any:
    """Return the public ``mission_flow_v2`` package module.

    Dependencies that tests patch on the package namespace (``storage``,
    ``record_audit_event``, ``generate_aim`` and the LLM ``generate_*``
    helpers) are resolved through this accessor so that
    ``unittest.mock.patch('orchestrator.mission_flow_v2.<name>')`` keeps
    reaching the live call sites after the monolith was split into this
    package (issue #186).
    """
    return importlib.import_module(__package__)


async def _emit_partition_work_items(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    mission: Any,
) -> Any:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    decision = scaling_decision_from_metadata(metadata)
    if decision is None or decision.instance_count <= 1:
        return mission
    if metadata.get("scaling_partition_events_emitted"):
        return mission

    redis_ready = bool(getattr(app.state, "redis_ready", False))
    redis_client = getattr(app.state, "redis", None)
    if not redis_ready or redis_client is None:
        return mission

    specialist_agent_id = _validate_agent_id(
        metadata.get("assigned_specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )
    pod_manager_agent_id = _validate_agent_id(
        metadata.get("assigned_pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )

    # Track which partitions have already been emitted so a retry after a
    # mid-batch failure (validation error or a transient Redis error) only
    # emits the remaining ones, instead of re-emitting every partition —
    # each envelope's event_id is freshly randomized, so a naive retry would
    # produce genuine duplicate MISSION_PARTITION_READY events for
    # partitions that already succeeded.
    already_emitted_ids = set(metadata.get("scaling_partition_emitted_ids") or [])
    emitted_count = len(already_emitted_ids)
    for partition in decision.partitions:
        if partition.partition_id in already_emitted_ids:
            continue

        envelope = {
            "event_id": f"evt-{uuid.uuid4()}",
            "topic": "mission.partition.ready",
            "timestamp": datetime.now(UTC).isoformat(),
            "producer": settings.producer_name,
            "correlation_id": mission.mission_id,
            "payload_ref": (
                f"registry://missions/{mission.mission_id}/partitions/{partition.partition_id}"
            ),
            "schema": "missions.partition.v1",
            # Normalised so a lowercase DEFAULT_EVENT_PRIORITY cannot silently
            # fail validation below and drop the partition envelope (UPG-22).
            "priority": to_event_priority(settings.default_priority),
        }
        try:
            validator.validate(envelope)
        except Exception as exc:
            LOGGER.warning(
                "v2: failed to validate partition envelope for mission %s/%s: %s",
                mission.mission_id,
                partition.partition_id,
                exc,
            )
            metadata["scaling_partition_emitted_ids"] = sorted(already_emitted_ids)
            metadata["scaling_partition_event_count"] = emitted_count
            await asyncio.to_thread(
                _pkg().storage.update_mission_metadata,
                settings,
                mission.mission_id,
                metadata,
            )
            return mission

        payload = {
            "mission_id": mission.mission_id,
            "state": mission.state.value,
            "event_type": "MISSION_PARTITION_READY",
            "requested_target_language": mission.requested_target_language,
            "agent_id": specialist_agent_id,
            "selected_agent_id": specialist_agent_id,
            "assigned_specialist_agent_id": specialist_agent_id,
            "assigned_pod_manager_agent_id": pod_manager_agent_id,
            "partition": partition.to_dict(),
        }
        try:
            await redis_client.xadd(
                settings.state_stream,
                {
                    "envelope": json.dumps(envelope),
                    "payload": json.dumps(payload),
                    "event_type": "MISSION_PARTITION_READY",
                    "mission_id": mission.mission_id,
                    "state": mission.state.value,
                    "created_at": (
                        mission.created_at.isoformat()
                        if isinstance(mission.created_at, datetime)
                        else str(mission.created_at)
                    ),
                },
                maxlen=settings.max_stream_len,
                approximate=True,
            )
        except Exception as exc:
            LOGGER.warning(
                "v2: failed to emit partition event for mission %s/%s: %s",
                mission.mission_id,
                partition.partition_id,
                exc,
            )
            metadata["scaling_partition_emitted_ids"] = sorted(already_emitted_ids)
            metadata["scaling_partition_event_count"] = emitted_count
            await asyncio.to_thread(
                _pkg().storage.update_mission_metadata,
                settings,
                mission.mission_id,
                metadata,
            )
            return mission

        already_emitted_ids.add(partition.partition_id)
        emitted_count += 1

    metadata["scaling_partition_events_emitted"] = True
    metadata["scaling_partition_events_emitted_at"] = datetime.now(UTC).isoformat()
    metadata["scaling_partition_event_count"] = emitted_count
    metadata["scaling_partition_emitted_ids"] = sorted(already_emitted_ids)
    updated = await asyncio.to_thread(
        _pkg().storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


async def _persist_metadata(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
    metadata: dict[str, Any],
    emit_event_type: str | None = None,
    event_state: MissionState | None = None,
) -> Any | None:
    record = await asyncio.to_thread(
        _pkg().storage.update_mission_metadata,
        settings,
        mission_id,
        metadata,
    )
    if record is None or emit_event_type is None or event_state is None:
        return record

    await asyncio.to_thread(
        _pkg().storage.insert_mission_event,
        settings,
        mission_id,
        event_state,
        event_state,
        emit_event_type,
    )

    redis_ready = bool(getattr(app.state, "redis_ready", False))
    redis_client = getattr(app.state, "redis", None)
    if not redis_ready or redis_client is None:
        return record

    try:
        await emit_state_event_fn(
            settings=settings,
            validator=validator,
            redis_client=redis_client,
            mission=record,
            event_type=emit_event_type,
        )
    except Exception as exc:
        LOGGER.warning(
            "v2: failed to emit auxiliary event %s for mission %s: %s",
            emit_event_type,
            mission_id,
            exc,
        )
    return record


async def _resolve_attachment_content(
    *,
    mission_id: str,
    attachments: Any,
    settings: Any,
) -> list[dict[str, Any]]:
    """Convert mission attachments to dicts enriched with extracted document text.

    Each attachment is normalised to a dict (``filename``/``content_type``/
    ``purpose``/``content``). When the raw bytes are available (inline or in
    object storage) the document is parsed and its text placed in ``content`` so
    the PM prompt can embed it; otherwise the attachment degrades to metadata
    only. Never raises — intake proceeds even if every attachment fails to parse.
    """
    from ..document_parser import parse_document
    from ..is_agent import _attachment_field, _load_attachment_bytes

    resolved: list[dict[str, Any]] = []
    for att in attachments or []:
        filename = _attachment_field(att, "filename", "unknown")
        file_id = _attachment_field(att, "file_id", "unknown")
        purpose = _attachment_field(att, "purpose", "reference")
        content_type = _attachment_field(att, "content_type", "")

        existing = att.get("content") if isinstance(att, dict) else getattr(att, "content", None)
        extracted = str(existing).strip() if existing else None
        if not extracted:
            try:
                raw = _load_attachment_bytes(att, settings, mission_id, file_id)
            except Exception:  # noqa: BLE001 - degrade to metadata-only
                raw = None
            if raw is not None:
                extracted = parse_document(raw, content_type, filename)

        resolved.append(
            {
                "file_id": file_id,
                "filename": filename,
                "content_type": content_type,
                "purpose": purpose,
                "content": extracted or "",
            }
        )
    return resolved


_REPO_CONTEXT_MAX_CHARS = 6_000
_MAX_REPO_CHUNK_RECORDS = 20


async def load_repo_context(
    *,
    settings: Any,
    mission_id: str,
    repo_import: dict[str, Any],
) -> str | None:
    """Build a bounded repository-context text block for PM intake.

    Reads the ``mission_knowledge`` rows the Repo ZIP Import Phase 6 endpoint
    (``/internal/missions/{mission_id}/repo-import-index``) wrote for this
    mission — the ``repo_manifest`` and ``repo_summary`` records plus up to
    ``_MAX_REPO_CHUNK_RECORDS`` ``repo_source_chunk`` records — and merges
    them into one bounded block, truncating at ``_REPO_CONTEXT_MAX_CHARS`` so
    it stays compact enough for prompt inclusion (see
    docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md). Returns None when nothing is
    indexed yet or storage is unavailable — the caller degrades gracefully.
    """
    _ = repo_import  # reserved for future per-import filtering; unused today
    try:
        records = await asyncio.to_thread(_pkg().storage.list_knowledge, settings, mission_id, 200)
    except Exception as exc:
        LOGGER.warning("load_repo_context: failed to list knowledge for %s: %s", mission_id, exc)
        return None

    manifest_text: str | None = None
    summary_text: str | None = None
    chunk_texts: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        content = record.get("content")
        if not isinstance(content, dict):
            continue
        kind = str(content.get("kind") or "")
        text = str(content.get("combined_text") or "").strip()
        if not text:
            continue
        if kind == "repo_manifest" and manifest_text is None:
            manifest_text = text
        elif kind == "repo_summary" and summary_text is None:
            summary_text = text
        elif kind == "repo_source_chunk" and len(chunk_texts) < _MAX_REPO_CHUNK_RECORDS:
            path = content.get("path")
            chunk_texts.append(f"# {path}\n{text}" if path else text)

    parts = [text for text in (manifest_text, summary_text) if text]
    parts.extend(chunk_texts)
    if not parts:
        return None
    merged = "\n\n".join(parts)
    if len(merged) > _REPO_CONTEXT_MAX_CHARS:
        merged = merged[:_REPO_CONTEXT_MAX_CHARS] + "\n...[truncated]"
    return merged


async def _prepare_pm_intake(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(_pkg().storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    metadata["selected_agent_id"] = PM_AGENT_ID
    metadata["agent_id"] = PM_AGENT_ID

    # Repo ZIP Import Phase 5 guard: a repo-sourced mission must wait for
    # Phase 6 indexing (POST /internal/missions/{mission_id}/repo-import-index)
    # to finish before PM contract generation runs, otherwise the PM Agent
    # would generate a contract with no repository context available.
    repo_import = metadata.get("repo_import")
    has_repo_import = isinstance(repo_import, dict) and bool(repo_import.get("index_required"))
    if has_repo_import and str(repo_import.get("index_status") or "pending").strip().lower() != "complete":
        if not _chain_event_exists(metadata, "REPO_INDEX_PENDING"):
            append_chain_event(
                metadata,
                event_type="REPO_INDEX_PENDING",
                agent_id=PM_AGENT_ID,
                details={
                    "import_id": repo_import.get("import_id"),
                    "index_status": repo_import.get("index_status"),
                },
            )
            await asyncio.to_thread(_pkg().storage.update_mission_metadata, settings, mission_id, metadata)
        return False

    conversation_context = metadata.get("conversation_context")
    if not isinstance(conversation_context, dict):
        conversation_context = {}
    pm_clarification = str(metadata.get("pm_clarification") or "").strip()
    if pm_clarification:
        conversation_context = dict(conversation_context)
        conversation_context["operator_clarification"] = pm_clarification
    if has_repo_import:
        repository_context = await load_repo_context(
            settings=settings, mission_id=mission_id, repo_import=repo_import
        )
        if repository_context:
            conversation_context = dict(conversation_context)
            conversation_context["repository_context"] = repository_context
    user_intent = str(metadata.get("user_intent") or "").strip() or None
    mission_type = str(metadata.get("mission_type") or "BUILD_NEW").strip().upper()
    depth_mode = str(metadata.get("depth_mode") or "STANDARD").strip().upper()
    output_mode = str(metadata.get("output_mode") or "FULL_BUILD").strip().upper()
    pm_attachments = await _resolve_attachment_content(
        mission_id=mission_id,
        attachments=getattr(mission, "attachments", []),
        settings=settings,
    )
    feature_contract = await _pkg().generate_pm_feature_contract(
        prompt=str(mission.prompt or ""),
        mission_type=mission_type,
        depth_mode=depth_mode,
        output_mode=output_mode,
        requested_target_language=mission.requested_target_language,
        attachments=pm_attachments,
        global_style_directives=getattr(mission, "global_style_directives", []),
        conversation_context=conversation_context,
        user_intent=user_intent,
    )

    ambiguity_score = feature_contract.get("ambiguity_score", 0.0)

    # Auto-accept the PM's own recommended defaults instead of parking.
    #
    # Measured across 12 consecutive real missions, every one scored 0.95-1.0
    # against this 0.7 gate -- including prompts that specified sort order,
    # separator, exit code and error behaviour explicitly. `_pm_ambiguity_score`
    # sums signals a *thorough* PM emits on any prompt (0.55 for its own
    # needs_clarification flag, 0.15 per question, 0.10 per risk note), so it
    # measures how much the PM said rather than how unclear the request was, and
    # 100% of missions stopped for an operator.
    #
    # The PM prompt already requires "a recommended default in each question",
    # and already knows how to close gaps itself: given
    # user_intent="finalize_plan" it must return intake_status "ready" and list
    # every assumption it relied on. That is exactly what an operator triggers by
    # answering "proceed with the defaults" -- so this takes the same path rather
    # than inventing a second one, and the questions stay visible on the mission.
    auto_accept = _setting_bool(settings, "pm_auto_accept_defaults_enabled", True)
    questions = feature_contract.get("clarifying_questions") or []
    if (
        ambiguity_score >= 0.7
        and auto_accept
        and isinstance(questions, list)
        and questions
        and str(metadata.get("user_intent") or "").strip().lower() != "finalize_plan"
    ):
        LOGGER.info(
            "Auto-accepting PM defaults for mission %s (%d question(s), score %.2f)",
            mission_id,
            len(questions),
            float(ambiguity_score),
        )
        metadata["pm_auto_accepted_defaults"] = {
            "questions": [str(q) for q in questions],
            "ambiguity_score": ambiguity_score,
            "applied_at": datetime.now(UTC).isoformat(),
            "reason": "clarifying questions carried recommended defaults",
        }
        metadata["user_intent"] = "finalize_plan"
        append_chain_event(
            metadata,
            event_type="MISSION_CLARIFICATION_APPLIED",
            agent_id=PM_AGENT_ID,
            details={
                "auto_accepted": True,
                "question_count": len(questions),
                "prior_ambiguity_score": ambiguity_score,
            },
        )
        feature_contract = await _pkg().generate_pm_feature_contract(
            prompt=str(mission.prompt or ""),
            mission_type=mission_type,
            depth_mode=depth_mode,
            output_mode=output_mode,
            requested_target_language=mission.requested_target_language,
            attachments=pm_attachments,
            global_style_directives=getattr(mission, "global_style_directives", []),
            conversation_context=conversation_context,
            user_intent="finalize_plan",
        )
        ambiguity_score = feature_contract.get("ambiguity_score", 0.0)

    if ambiguity_score >= 0.7:
        LOGGER.warning("High ambiguity detected for mission %s; pausing for clarification", mission_id)
        metadata["last_ambiguity_score"] = ambiguity_score
        metadata["clarifying_questions"] = feature_contract.get("clarifying_questions")
        await asyncio.to_thread(_pkg().storage.update_mission_metadata, settings, mission_id, metadata)
        # The preparer runs while the mission is still in QUEUED state —
        # the loop transitions to PM_INTAKE only after the preparer returns True.
        # Use the actual current state (queued) as expected_state here.
        clarifying_record = await asyncio.to_thread(
            _pkg().storage.transition_mission_state,
            settings,
            mission_id,
            MissionState.queued,
            MissionState.clarifying,
            "MISSION_CLARIFYING",
        )
        if clarifying_record is not None:
            redis_ready = bool(getattr(app.state, "redis_ready", False))
            redis_client = getattr(app.state, "redis", None)
            if redis_ready and redis_client is not None:
                try:
                    await emit_state_event_fn(
                        settings=settings,
                        validator=validator,
                        redis_client=redis_client,
                        mission=clarifying_record,
                        event_type="MISSION_CLARIFYING",
                    )
                except Exception as _exc:
                    LOGGER.warning(
                        "v2: failed to emit MISSION_CLARIFYING for mission %s: %s",
                        mission_id,
                        _exc,
                    )
        return False

    mission_charter = build_mission_charter(
        mission_id=mission_id,
        prompt=str(mission.prompt or ""),
        requested_target_language=mission.requested_target_language,
        feature_contract=feature_contract,
        mission_type=mission_type,
        depth_mode=depth_mode,
        output_mode=output_mode,
    )
    metadata["feature_contract"] = feature_contract
    metadata["mission_charter"] = mission_charter
    metadata["risk_assessment"] = feature_contract.get("risk_assessment")

    if not _chain_event_exists(metadata, "MISSION_PM_INTAKE"):
        append_chain_event(
            metadata,
            event_type="MISSION_PM_INTAKE",
            agent_id=PM_AGENT_ID,
            details={
                "source": metadata.get("source", "mission-flow-v2"),
                "feature_contract_source": feature_contract.get("source"),
                "title": feature_contract.get("title"),
            },
        )
    if not _chain_event_exists(metadata, "FEATURE_CONTRACT_CREATED"):
        append_chain_event(
            metadata,
            event_type="FEATURE_CONTRACT_CREATED",
            agent_id=PM_AGENT_ID,
            details={
                "source": feature_contract.get("source"),
                "requirement_count": len(feature_contract.get("functional_requirements", [])),
                "acceptance_criteria_count": len(feature_contract.get("acceptance_criteria", [])),
                "human_approval_required": feature_contract.get("human_approval_required"),
            },
        )
    _record_artifact(
        metadata,
        stage="pm_intake",
        event_type="MISSION_PM_INTAKE",
        agent_id=PM_AGENT_ID,
        details={
            "source": metadata.get("source", "mission-flow-v2"),
            "feature_contract_source": feature_contract.get("source"),
            "mission_charter_id": mission_charter.get("charter_id"),
        },
    )
    await _pkg().record_audit_event(
        app,
        mission_id=mission_id,
        mission=mission,
        agent_id=PM_AGENT_ID,
        service_name="orchestrator",
        event_type="FEATURE_CONTRACT_CREATED",
        object_type="feature_contract",
        object_id="feature_contract",
        tool_name="llm_delegation",
        payload_summary={
            "source": feature_contract.get("source"),
            "title": feature_contract.get("title"),
            "requirement_count": len(feature_contract.get("functional_requirements", [])),
            "human_approval_required": feature_contract.get("human_approval_required"),
        },
        content_hash_source=feature_contract,
    )
    if mission_requires_aim(mission_type) and isinstance(metadata.get("source_code"), str):
        aim = await _pkg().generate_aim(
            mission_id=mission_id,
            source_code=str(metadata["source_code"]),
            prompt=str(mission.prompt or ""),
            mission_type=mission_type,
            requested_target_language=mission.requested_target_language,
            feature_contract=feature_contract,
            settings=settings,
        )
        metadata["application_intelligence_map"] = aim
        if not _chain_event_exists(metadata, "MISSION_AIM_GENERATED"):
            append_chain_event(
                metadata,
                event_type="MISSION_AIM_GENERATED",
                agent_id=CEO_AGENT_ID,
                details={
                    "aim_id": aim.get("aim_id"),
                    "primary_language": aim.get("primary_language"),
                    "detected_languages": aim.get("detected_languages", []),
                    "files_analyzed": (aim.get("extraction_summary") or {}).get(
                        "files_analyzed", 0
                    ),
                    "total_functions": aim.get("total_functions", 0),
                    "total_classes": aim.get("total_classes", 0),
                    "complexity": aim.get("complexity_assessment"),
                    "human_approval_recommended": aim.get("human_approval_recommended", False),
                    "source": aim.get("source"),
                },
            )
        _record_artifact(
            metadata,
            stage="aim",
            event_type="MISSION_AIM_GENERATED",
            agent_id=CEO_AGENT_ID,
            details={
                "aim_id": aim.get("aim_id"),
                "schema_version": aim.get("schema_version"),
                "source": aim.get("source"),
                "model_provider": aim.get("model_provider"),
                "model": aim.get("model"),
            },
        )
        await _pkg().record_audit_event(
            app,
            mission_id=mission_id,
            mission=mission,
            agent_id=CEO_AGENT_ID,
            service_name="orchestrator",
            event_type="MISSION_AIM_GENERATED",
            object_type="application_intelligence_map",
            object_id=str(aim.get("aim_id") or "application_intelligence_map"),
            tool_name="aim_generator",
            payload_summary={
                "source": aim.get("source"),
                "primary_language": aim.get("primary_language"),
                "files_analyzed": (aim.get("extraction_summary") or {}).get(
                    "files_analyzed", 0
                ),
                "human_approval_recommended": aim.get("human_approval_recommended", False),
            },
            content_hash_source=aim,
        )
    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
        )
        is not None
    )


async def _prepare_fetch_phase(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    """Phase 8: IS Agent knowledge-lake preload.

    Indexes bootstrap documentation for the mission's target language(s) so
    pod workers have documentation context during extraction. Never blocks the
    mission — errors are captured in fetch_result and the mission proceeds.
    """
    from ..is_agent import detect_required_languages, run_fetch_phase
    from ..knowledge_lake import broadcast_knowledge_ready, is_stocked

    mission = await asyncio.to_thread(_pkg().storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    mission_type = str(metadata.get("mission_type") or "BUILD_NEW").strip().upper()

    languages = detect_required_languages(
        prompt=str(mission.prompt or ""),
        requested_target_language=mission.requested_target_language,
        source_code=metadata.get("source_code"),
        mission_type=mission_type,
    )

    fetch_result = await run_fetch_phase(
        mission_id=mission_id,
        required_languages=languages,
        settings=settings,
        attachments=getattr(mission, "attachments", []),
    )

    metadata["fetch_result"] = fetch_result
    metadata["knowledge_lake_ready"] = fetch_result["knowledge_ready"]

    # Verify the IS-Agent actually persisted knowledge for this mission by
    # reading it back from PostgreSQL (the unified source of truth). A mismatch
    # between "fetch reported ready" and "storage has rows" indicates a silent
    # write failure that would otherwise leave codegen without context.
    stocked = await asyncio.to_thread(is_stocked, settings=settings, mission_id=mission_id)
    metadata["knowledge_lake_stocked"] = stocked
    if fetch_result.get("knowledge_ready") and not stocked:
        LOGGER.warning(
            "FETCH reported knowledge_ready but no rows found in storage for mission %s",
            mission_id,
        )

    if not _chain_event_exists(metadata, "MISSION_FETCH_COMPLETE"):
        append_chain_event(
            metadata,
            event_type="MISSION_FETCH_COMPLETE",
            agent_id="AGENT-06-IS",
            details={
                "indexed_languages": fetch_result["indexed_languages"],
                "skipped": fetch_result["skipped_languages"],
                "errors": fetch_result["errors"],
                "knowledge_ids": fetch_result.get("knowledge_ids", []),
                "knowledge_ready": fetch_result["knowledge_ready"],
                "refreshed_languages": fetch_result.get("refreshed_languages", []),
                "unchanged_languages": fetch_result.get("unchanged_languages", []),
                "embedding_provider": fetch_result.get("embedding_provider"),
                "embedding_model": fetch_result.get("embedding_model"),
            },
        )

    # Publish Protocol Sigma knowledge_ready event to the semantic bus.
    # Fire-and-forget — never blocks mission progression on bus failure.
    if fetch_result.get("knowledge_ready") and fetch_result.get("indexed_languages"):
        await asyncio.to_thread(
            broadcast_knowledge_ready,
            settings=settings,
            languages=fetch_result["indexed_languages"],
            mission_id=mission_id,
        )

    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
        )
        is not None
    )


async def _prepare_ceo_delegation(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(_pkg().storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    mission_context = {
        **_mission_context(mission, metadata),
        "feature_contract": metadata.get("feature_contract"),
        "mission_charter": metadata.get("mission_charter"),
    }
    delegation = await _pkg().generate_ceo_delegation(
        mission_context=mission_context,
        requested_target_language=mission.requested_target_language,
    )
    pod_manager_agent_id = _validate_agent_id(
        delegation.get("pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    specialist_agent_id = _validate_agent_id(
        delegation.get("specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )
    normalized = dict(delegation)
    normalized["pod_manager_agent_id"] = pod_manager_agent_id
    normalized["specialist_agent_id"] = specialist_agent_id

    metadata["ceo_delegation"] = normalized
    metadata["selected_agent_id"] = pod_manager_agent_id
    metadata["agent_id"] = pod_manager_agent_id

    mission_contract = await generate_mission_contract(
        mission_context=mission_context,
        prompt=str(mission.prompt or ""),
        mission_type=str(metadata.get("mission_type") or "BUILD_NEW"),
        output_mode=str(metadata.get("output_mode") or "FULL_BUILD"),
        requested_target_language=mission.requested_target_language,
        ceo_delegation=normalized,
    )
    metadata["mission_contract"] = mission_contract
    logic_clusters = await generate_logic_clusters(
        mission_context={**mission_context, "mission_contract": mission_contract},
        mission_contract=mission_contract,
        requested_target_language=mission.requested_target_language,
        ceo_delegation=normalized,
    )
    metadata["logic_clusters"] = logic_clusters

    if not _chain_event_exists(metadata, "MISSION_CEO_DELEGATED"):
        append_chain_event(
            metadata,
            event_type="MISSION_CEO_DELEGATED",
            agent_id=CEO_AGENT_ID,
            details={
                "target_agent_id": pod_manager_agent_id,
                "specialist_agent_id": specialist_agent_id,
                "source": normalized.get("source"),
                "llm_route": normalized.get("llm_route"),
                "model_provider": normalized.get("model_provider"),
                "model": normalized.get("model"),
            },
        )
    if not _chain_event_exists(metadata, "MISSION_CONTRACT_GENERATED"):
        append_chain_event(
            metadata,
            event_type="MISSION_CONTRACT_GENERATED",
            agent_id=CEO_AGENT_ID,
            details={
                "source": mission_contract.get("source"),
                "output_format": mission_contract.get("output_format"),
                "requirement_count": len(mission_contract.get("logicnode_requirements", [])),
                "acceptance_criteria_count": len(
                    mission_contract.get("acceptance_criteria", [])
                ),
                "model_provider": mission_contract.get("model_provider"),
                "model": mission_contract.get("model"),
            },
        )
    if not _chain_event_exists(metadata, "LOGIC_CLUSTERS_DECOMPOSED"):
        clusters = logic_clusters.get("clusters") if isinstance(logic_clusters, dict) else []
        append_chain_event(
            metadata,
            event_type="LOGIC_CLUSTERS_DECOMPOSED",
            agent_id=CEO_AGENT_ID,
            details={
                "source": logic_clusters.get("source"),
                "cluster_count": len(clusters) if isinstance(clusters, list) else 0,
                "model_provider": logic_clusters.get("model_provider"),
                "model": logic_clusters.get("model"),
            },
        )
    if not _chain_event_exists(metadata, "CEO_REASONING_SUMMARY"):
        clusters = logic_clusters.get("clusters") if isinstance(logic_clusters, dict) else []
        support_agent_flags = _extract_support_agent_flags(
            normalized,
            str(metadata.get("mission_type") or "BUILD_NEW"),
        )
        metadata["ceo_support_agent_flags"] = support_agent_flags
        append_chain_event(
            metadata,
            event_type="CEO_REASONING_SUMMARY",
            agent_id=CEO_AGENT_ID,
            details={
                "delegation_rationale": normalized.get("rationale"),
                "contract_summary": mission_contract.get("contract_summary"),
                "cluster_count": len(clusters) if isinstance(clusters, list) else 0,
                "cross_pod_flags": _extract_cross_pod_flags(logic_clusters),
                "support_agent_flags": support_agent_flags,
            },
        )
    _record_artifact(
        metadata,
        stage="ceo_delegated",
        event_type="MISSION_CEO_DELEGATED",
        agent_id=CEO_AGENT_ID,
        details={
            "target_agent_id": pod_manager_agent_id,
            "specialist_agent_id": specialist_agent_id,
            "source": normalized.get("source"),
            "llm_route": normalized.get("llm_route"),
            "model_provider": normalized.get("model_provider"),
            "model": normalized.get("model"),
        },
    )
    _record_artifact(
        metadata,
        stage="mission_contract",
        event_type="MISSION_CONTRACT_GENERATED",
        agent_id=CEO_AGENT_ID,
        details={
            "source": mission_contract.get("source"),
            "output_format": mission_contract.get("output_format"),
            "requirement_count": len(mission_contract.get("logicnode_requirements", [])),
        },
    )
    clusters = logic_clusters.get("clusters") if isinstance(logic_clusters, dict) else []
    _record_artifact(
        metadata,
        stage="logic_clusters",
        event_type="LOGIC_CLUSTERS_DECOMPOSED",
        agent_id=CEO_AGENT_ID,
        details={
            "source": logic_clusters.get("source"),
            "cluster_count": len(clusters) if isinstance(clusters, list) else 0,
        },
    )
    await _pkg().record_audit_event(
        app,
        mission_id=mission_id,
        mission=mission,
        agent_id=CEO_AGENT_ID,
        service_name="orchestrator",
        event_type="AGENT_DELEGATION_PLANNED",
        object_type="delegation",
        object_id="ceo",
        tool_name="llm_delegation",
        payload_summary={
            "source": normalized.get("source"),
            "llm_route": normalized.get("llm_route"),
            "model_provider": normalized.get("model_provider"),
            "model": normalized.get("model"),
            "pod_manager_agent_id": pod_manager_agent_id,
            "specialist_agent_id": specialist_agent_id,
        },
        content_hash_source=normalized,
    )
    await _pkg().record_audit_event(
        app,
        mission_id=mission_id,
        mission=mission,
        agent_id=CEO_AGENT_ID,
        service_name="orchestrator",
        event_type="MISSION_CONTRACT_GENERATED",
        object_type="mission_contract",
        object_id="mission_contract",
        tool_name="llm_delegation",
        payload_summary={
            "source": mission_contract.get("source"),
            "output_format": mission_contract.get("output_format"),
            "requirement_count": len(mission_contract.get("logicnode_requirements", [])),
            "acceptance_criteria_count": len(mission_contract.get("acceptance_criteria", [])),
        },
        content_hash_source=mission_contract,
    )
    await _pkg().record_audit_event(
        app,
        mission_id=mission_id,
        mission=mission,
        agent_id=CEO_AGENT_ID,
        service_name="orchestrator",
        event_type="LOGIC_CLUSTERS_DECOMPOSED",
        object_type="logic_clusters",
        object_id="logic_clusters",
        tool_name="llm_delegation",
        payload_summary={
            "source": logic_clusters.get("source"),
            "cluster_count": len(clusters) if isinstance(clusters, list) else 0,
        },
        content_hash_source=logic_clusters,
    )
    # PORT two-phase setup — extract source/target language and cluster assignments
    mission_type_now = str(metadata.get("mission_type") or "BUILD_NEW").strip().upper()
    if mission_type_now == "PORT" and _setting_bool(settings, "port_two_phase_enabled"):
        _setup_port_two_phase(metadata, mission, clusters)

    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
        )
        is not None
    )

