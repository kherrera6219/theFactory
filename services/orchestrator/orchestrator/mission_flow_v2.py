"""
mission_flow_v2.py — 11-phase Mission Flow v2 lifecycle engine.

Provides the expanded state-machine that replaces v1.1's coarse
``QUEUED → RUNNING → VERIFIED → COMPLETE`` with 11 granular phases.

Gated behind ``MISSION_FLOW_V2_ENABLED=true``.  When disabled the
legacy/LangGraph v1.1 engines handle mission progression as before.

Phase order
-----------
1. INTAKE          (gateway receipt)
2. QUEUED          (persisted + queued)
3. PM_INTAKE       (PM intent translation)
4. CEO_DELEGATED   (CEO delegation plan)
5. POD_ASSIGNED    (pod manager assigned)
6. SPECIALIST_ASSIGNED (specialist assigned)
7. RUNNING         (extraction active)
8. GATING          (QC gating pass)
9. FUSION          (artifact fusion)
10. VERIFIED       (verification gate)
11. COMPLETE       (delivered)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import build_artifacts as build_artifact_support
from . import storage
from .agent_registry import AGENT_REGISTRY
from .agent_scaling import (
    all_partitions_complete,
    compute_scaling_decision,
    embed_scaling_decision,
    is_scalable_agent,
    scaling_decision_from_metadata,
)
from .aim_generator import generate_aim, mission_requires_aim
from .audit_events import record_audit_event
from .dependency_absorption import (
    build_dependency_absorption_reports,
    mission_requires_dependency_absorption,
)
from .equivalence_verifier import build_equivalence_report, mission_requires_equivalence
from .llm_delegation import (
    generate_ceo_delegation,
    generate_code_from_contract,
    generate_logic_clusters,
    generate_master_logic_stream,
    generate_mission_contract,
    generate_pm_delivery_summary,
    generate_pm_feature_contract,
    generate_pod_group_standard,
    generate_pod_manager_delegation,
    generate_specialist_plan,
)
from .mission_flow import (
    CEO_AGENT_ID,
    PM_AGENT_ID,
    append_chain_event,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
    with_chain_defaults,
)
from .models import MissionState
from .security_compliance import (
    build_security_compliance_report,
    mission_requires_security_compliance,
)

LOGGER = logging.getLogger(__name__)
VALID_AGENT_IDS = frozenset(agent.agent_id for agent in AGENT_REGISTRY)
RUNTIME_PHASES = frozenset(
    {
        MissionState.running,
        MissionState.gating,
        MissionState.fusion,
        MissionState.verified,
        MissionState.complete,
    }
)
_SOURCE_BUNDLE_FILE_PATTERN = re.compile(r"^## FILE (.+)$", re.MULTILINE)
_MISSION_CHARTER_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "schemas" / "mission_charter.v1.json"
)


def _setting_bool(settings: Any, name: str, default: bool = False) -> bool:
    raw = getattr(settings, name, default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return bool(raw)
    if isinstance(raw, str):
        candidate = raw.strip().lower()
        if candidate in {"1", "true", "yes", "on"}:
            return True
        if candidate in {"0", "false", "no", "off", ""}:
            return False
    return default


def _setting_int(settings: Any, name: str, default: int) -> int:
    raw = getattr(settings, name, default)
    if isinstance(raw, bool):
        return default
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        candidate = raw.strip()
        if not candidate:
            return default
        try:
            return int(candidate)
        except ValueError:
            return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _chain_event_exists(metadata: dict[str, Any], event_type: str) -> bool:
    return any(
        isinstance(record, dict) and str(record.get("event_type", "")).upper() == event_type
        for record in metadata.get("chain_trace", [])
    )


def _record_artifact(
    metadata: dict[str, Any],
    *,
    stage: str,
    event_type: str,
    agent_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    artifacts = metadata.get("mission_artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    artifacts[stage] = {
        "event_type": event_type,
        "agent_id": agent_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "details": details or {},
    }
    metadata["mission_artifacts"] = artifacts


def _validate_agent_id(candidate: Any, *, fallback: str) -> str:
    normalized = str(candidate or "").strip().upper()
    if normalized in VALID_AGENT_IDS:
        return normalized
    return fallback


def _pod_key_for_manager(agent_id: str) -> str:
    normalized = str(agent_id or "").strip().upper()
    agent = next(
        (candidate for candidate in AGENT_REGISTRY if candidate.agent_id == normalized),
        None,
    )
    pod_name = str(getattr(agent, "pod", "") or "").strip()
    pod_map = {
        "Pod A": "podA",
        "Pod B": "podB",
        "Pod C": "podC",
        "Pod D": "podD",
    }
    return pod_map.get(pod_name, pod_name.replace(" ", "") or "pod")


def _mission_context(mission: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": mission.mission_id,
        "prompt": mission.prompt,
        "requested_target_language": mission.requested_target_language,
        "source": metadata.get("source"),
        "routing_version": metadata.get("routing_version"),
        "routing_enforced": metadata.get("routing_enforced"),
    }


def _workload_items_from_source_bundle(source_code: Any) -> list[str]:
    if not isinstance(source_code, str) or not source_code.strip():
        return []

    items: list[str] = []
    for match in _SOURCE_BUNDLE_FILE_PATTERN.finditer(source_code):
        candidate = str(match.group(1)).strip()
        if candidate and candidate not in items:
            items.append(candidate)
    return items


def _scaling_workload_items(metadata: dict[str, Any], specialist_plan: dict[str, Any]) -> list[str]:
    source_items = _workload_items_from_source_bundle(metadata.get("source_code"))
    if source_items:
        return source_items

    workload_items = [
        str(item).strip()
        for item in specialist_plan.get("deliverables", [])
        if str(item).strip()
    ]
    return workload_items or ["default_workload"]


def _mission_mode_for_type(mission_type: str) -> int:
    mapping = {
        "BUILD_NEW": 1,
        "IMPORT_MODERNIZE": 2,
        "PORT": 3,
        "DEBUG_REPAIR": 4,
        "SECURITY_HARDEN": 5,
        "REDUCE_DEPENDENCIES": 6,
        "RUN_QC": 7,
        "ARCHITECTURE_DOCS": 8,
        "ANALYZE_ONLY": 9,
        "SELF_ANALYZE": 10,
    }
    return mapping.get(mission_type.strip().upper(), 1)


def _schema_depth_mode(depth_mode: str) -> str:
    mapping = {
        "SPRINT": "quick_scan",
        "STANDARD": "standard",
        "PRODUCTION": "deep_audit",
        "REGULATED": "deep_audit",
        "AUTONOMOUS_LONG_RUN": "autonomous_long_run",
    }
    return mapping.get(depth_mode.strip().upper(), "standard")


def _schema_output_mode(output_mode: str) -> str:
    mapping = {
        "ANALYZE_ONLY": "report_only",
        "PLAN_ONLY": "report_only",
        "PATCH_PROPOSAL": "patch_files",
        "APPLY_PATCH": "patch_files",
        "FULL_BUILD": "full_branch",
        "DEPENDENCY_REDUCTION": "full_branch",
        "RUN_QC": "report_only",
        "FULL_TRANSFORMATION": "full_branch",
    }
    return mapping.get(output_mode.strip().upper(), "full_branch")


@lru_cache(maxsize=1)
def _mission_charter_schema() -> dict[str, Any]:
    with _MISSION_CHARTER_SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    return loaded if isinstance(loaded, dict) else {}


def _validate_schema_type(value: Any, expected: Any) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    if isinstance(expected, list):
        return any(_validate_schema_type(value, item) for item in expected)
    return True


def validate_mission_charter_schema(charter: dict[str, Any]) -> dict[str, Any]:
    """Validate generated mission charters against the checked-in schema subset."""
    schema = _mission_charter_schema()
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    missing = [key for key in required if key not in charter]
    if missing:
        raise ValueError(f"mission charter missing required fields: {', '.join(missing)}")

    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    for key, rules in properties.items():
        if key not in charter or not isinstance(rules, dict):
            continue
        value = charter[key]
        if "const" in rules and value != rules["const"]:
            raise ValueError(f"mission charter field {key!r} must be {rules['const']!r}")
        enum_values = rules.get("enum")
        if isinstance(enum_values, list) and value not in enum_values:
            raise ValueError(f"mission charter field {key!r} has unsupported value {value!r}")
        if "type" in rules and not _validate_schema_type(value, rules["type"]):
            raise ValueError(f"mission charter field {key!r} has invalid type")
        min_length = rules.get("minLength")
        if isinstance(min_length, int) and isinstance(value, str) and len(value) < min_length:
            raise ValueError(f"mission charter field {key!r} is too short")

    if schema.get("additionalProperties") is False:
        extras = sorted(set(charter) - set(properties))
        if extras:
            raise ValueError(f"mission charter has unexpected fields: {', '.join(extras)}")
    return charter


def build_mission_charter(
    *,
    mission_id: str,
    prompt: str,
    requested_target_language: str | None,
    feature_contract: dict[str, Any],
    mission_type: str,
    depth_mode: str,
    output_mode: str,
) -> dict[str, Any]:
    schema_depth = _schema_depth_mode(depth_mode)
    schema_output = _schema_output_mode(output_mode)
    approval_required = bool(feature_contract.get("human_approval_required", False))
    if schema_depth in {"deep_audit", "autonomous_long_run"}:
        approval_required = True
    gates = ["pod_audit_pass"]
    if schema_depth != "quick_scan":
        gates.extend(["security_scan_pass", "integration_tests_pass"])
    if approval_required:
        gates.append("operator_approval")
    objective = str(feature_contract.get("summary") or prompt or "Complete mission")[:500]
    if len(objective.strip()) < 10:
        objective = "Complete the requested mission."
    normalized_mission_type = mission_type.strip().upper() or "BUILD_NEW"
    normalized_depth_mode = depth_mode.strip().upper() or "STANDARD"
    normalized_output_mode = output_mode.strip().upper() or "FULL_BUILD"
    charter = {
        "schema": "mission_charter.v1",
        "schema_version": "1.0.0",
        "charter_id": f"charter-{uuid.uuid4()}",
        "mission_id": mission_id,
        "created_at": datetime.now(UTC).isoformat(),
        "requested_by": "operator:mission-control",
        "mission_type": normalized_mission_type,
        "mission_mode": _mission_mode_for_type(mission_type),
        "mission_mode_label": normalized_mission_type,
        "depth_mode": schema_depth,
        "depth_mode_label": normalized_depth_mode,
        "output_mode": schema_output,
        "output_mode_label": normalized_output_mode,
        "data_classification": "TIER_1_INTERNAL",
        "source_type": "direct_input",
        "target_outcome": objective,
        "risk_level": "medium" if approval_required else "low",
        "human_approval_required": approval_required,
        "approval_gates_required": gates,
        "expected_artifacts": ["mission_contract", "logic_clusters", "generated_output"],
        "target": {
            "type": "local_repo" if prompt else "self",
            "primary_language": (requested_target_language or "unknown").strip().lower(),
            "detected_languages": (
                [(requested_target_language or "").strip().lower()]
                if requested_target_language
                else []
            ),
        },
        "objective": objective,
        "raw_input": prompt,
        "scope": {
            "in_scope": list(feature_contract.get("functional_requirements") or [])[:8],
            "out_of_scope": [],
            "assumptions": list(feature_contract.get("risk_notes") or [])[:5],
        },
        "success_criteria": list(feature_contract.get("acceptance_criteria") or [])
        or ["Mission completes without error."],
        "definition_of_done": {
            "depth_mode": schema_depth,
            "gates": gates,
            "requires_operator_approval": approval_required,
            "requires_runtime_qc": schema_depth in {"deep_audit", "autonomous_long_run"},
            "requires_dependency_absorption": mission_type.strip().upper() == "REDUCE_DEPENDENCIES",
        },
        "non_functional_constraints": {
            "sensitive_code_tier": 1,
            "provider_restriction": "any",
        },
        "metadata": {
            "source": str(feature_contract.get("source") or "fallback"),
        },
    }
    return validate_mission_charter_schema(charter)


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

    emitted_count = 0
    for partition in decision.partitions:
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
            "priority": settings.default_priority,
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
        emitted_count += 1

    metadata["scaling_partition_events_emitted"] = True
    metadata["scaling_partition_events_emitted_at"] = datetime.now(UTC).isoformat()
    metadata["scaling_partition_event_count"] = emitted_count
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
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
        storage.update_mission_metadata,
        settings,
        mission_id,
        metadata,
    )
    if record is None or emit_event_type is None or event_state is None:
        return record

    await asyncio.to_thread(
        storage.insert_mission_event,
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


async def _prepare_pm_intake(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    metadata["selected_agent_id"] = PM_AGENT_ID
    metadata["agent_id"] = PM_AGENT_ID
    mission_type = str(metadata.get("mission_type") or "BUILD_NEW").strip().upper()
    depth_mode = str(metadata.get("depth_mode") or "STANDARD").strip().upper()
    output_mode = str(metadata.get("output_mode") or "FULL_BUILD").strip().upper()
    feature_contract = await generate_pm_feature_contract(
        prompt=str(mission.prompt or ""),
        mission_type=mission_type,
        depth_mode=depth_mode,
        output_mode=output_mode,
        requested_target_language=mission.requested_target_language,
    )
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
    await record_audit_event(
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
        aim = await generate_aim(
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
        await record_audit_event(
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
    from .is_agent import detect_required_languages, run_fetch_phase

    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
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
    )

    metadata["fetch_result"] = fetch_result
    metadata["knowledge_lake_ready"] = fetch_result["knowledge_ready"]

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
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    mission_context = {
        **_mission_context(mission, metadata),
        "feature_contract": metadata.get("feature_contract"),
        "mission_charter": metadata.get("mission_charter"),
    }
    delegation = await generate_ceo_delegation(
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
    await record_audit_event(
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
    await record_audit_event(
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
    await record_audit_event(
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


async def _prepare_pod_assignment(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    ceo_delegation = (
        metadata.get("ceo_delegation") if isinstance(metadata.get("ceo_delegation"), dict) else {}
    )
    pod_manager_agent_id = _validate_agent_id(
        ceo_delegation.get("pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    default_specialist_agent_id = _validate_agent_id(
        ceo_delegation.get("specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )

    pod_manager_delegation = await generate_pod_manager_delegation(
        mission_context={
            **_mission_context(mission, metadata),
            "ceo_delegation": ceo_delegation,
            "logic_clusters": metadata.get("logic_clusters"),
        },
        requested_target_language=mission.requested_target_language,
        pod_manager_agent_id=pod_manager_agent_id,
        default_specialist_agent_id=default_specialist_agent_id,
    )
    specialist_agent_id = _validate_agent_id(
        pod_manager_delegation.get("specialist_agent_id"),
        fallback=default_specialist_agent_id,
    )
    normalized = dict(pod_manager_delegation)
    normalized["pod_manager_agent_id"] = pod_manager_agent_id
    normalized["specialist_agent_id"] = specialist_agent_id

    metadata["pod_manager_delegation"] = normalized
    metadata["assigned_pod_manager_agent_id"] = pod_manager_agent_id
    metadata["assigned_specialist_agent_id"] = specialist_agent_id
    metadata["selected_agent_id"] = pod_manager_agent_id
    metadata["agent_id"] = pod_manager_agent_id

    if not _chain_event_exists(metadata, "MISSION_POD_MANAGER_ASSIGNED"):
        append_chain_event(
            metadata,
            event_type="MISSION_POD_MANAGER_ASSIGNED",
            agent_id=pod_manager_agent_id,
            details={
                "specialist_agent_id": specialist_agent_id,
                "source": normalized.get("source"),
                "llm_route": normalized.get("llm_route"),
                "model_provider": normalized.get("model_provider"),
                "model": normalized.get("model"),
            },
        )
    _record_artifact(
        metadata,
        stage="pod_assigned",
        event_type="MISSION_POD_MANAGER_ASSIGNED",
        agent_id=pod_manager_agent_id,
        details={
            "specialist_agent_id": specialist_agent_id,
            "source": normalized.get("source"),
            "llm_route": normalized.get("llm_route"),
            "model_provider": normalized.get("model_provider"),
            "model": normalized.get("model"),
        },
    )
    await record_audit_event(
        app,
        mission_id=mission_id,
        mission=mission,
        agent_id=pod_manager_agent_id,
        service_name="orchestrator",
        event_type="AGENT_DELEGATION_PLANNED",
        object_type="delegation",
        object_id="pod_manager",
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


async def _prepare_specialist_assignment(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    pod_manager_agent_id = _validate_agent_id(
        metadata.get("assigned_pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    specialist_agent_id = _validate_agent_id(
        metadata.get("assigned_specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )

    metadata["assigned_pod_manager_agent_id"] = pod_manager_agent_id
    metadata["assigned_specialist_agent_id"] = specialist_agent_id
    metadata["selected_agent_id"] = specialist_agent_id
    metadata["agent_id"] = specialist_agent_id

    if not _chain_event_exists(metadata, "MISSION_SPECIALIST_ASSIGNED"):
        append_chain_event(
            metadata,
            event_type="MISSION_SPECIALIST_ASSIGNED",
            agent_id=specialist_agent_id,
            details={"pod_manager_agent_id": pod_manager_agent_id},
        )
    _record_artifact(
        metadata,
        stage="specialist_assigned",
        event_type="MISSION_SPECIALIST_ASSIGNED",
        agent_id=specialist_agent_id,
        details={"pod_manager_agent_id": pod_manager_agent_id},
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


async def _prepare_specialist_plan(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    pod_manager_agent_id = _validate_agent_id(
        metadata.get("assigned_pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    specialist_agent_id = _validate_agent_id(
        metadata.get("assigned_specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )
    specialist_plan = await generate_specialist_plan(
        mission_context={
            **_mission_context(mission, metadata),
            "ceo_delegation": metadata.get("ceo_delegation"),
            "pod_manager_delegation": metadata.get("pod_manager_delegation"),
        },
        requested_target_language=mission.requested_target_language,
        specialist_agent_id=specialist_agent_id,
        pod_manager_agent_id=pod_manager_agent_id,
    )
    normalized = dict(specialist_plan)
    normalized["specialist_agent_id"] = specialist_agent_id
    normalized["pod_manager_agent_id"] = pod_manager_agent_id
    metadata["specialist_plan"] = normalized
    metadata["selected_agent_id"] = specialist_agent_id
    metadata["agent_id"] = specialist_agent_id

    mission_contract = metadata.get("mission_contract")
    output_mode = str(metadata.get("output_mode") or "FULL_BUILD").strip().upper()
    if (
        isinstance(mission_contract, dict)
        and output_mode != "ANALYZE_ONLY"
        and not isinstance(metadata.get("generated_output"), dict)
    ):
        generated_output = await generate_code_from_contract(
            mission_context={
                **_mission_context(mission, metadata),
                "mission_contract": mission_contract,
                "specialist_plan": normalized,
            },
            specialist_agent_id=specialist_agent_id,
            mission_contract=mission_contract,
            logicnodes=[],
            target_language=mission.requested_target_language or "python",
        )
        metadata["generated_output"] = generated_output
        if not _chain_event_exists(metadata, "GENERATED_OUTPUT_CREATED"):
            append_chain_event(
                metadata,
                event_type="GENERATED_OUTPUT_CREATED",
                agent_id=specialist_agent_id,
                details={
                    "source": generated_output.get("source"),
                    "filename": generated_output.get("filename"),
                    "language": generated_output.get("language"),
                    "code_length_chars": generated_output.get("code_length_chars", 0),
                    "model_provider": generated_output.get("model_provider"),
                    "model": generated_output.get("model"),
                },
            )

    should_emit = not _chain_event_exists(metadata, "MISSION_SPECIALIST_PLANNED")
    if should_emit:
        append_chain_event(
            metadata,
            event_type="MISSION_SPECIALIST_PLANNED",
            agent_id=specialist_agent_id,
            details={
                "pod_manager_agent_id": pod_manager_agent_id,
                "source": normalized.get("source"),
                "llm_route": normalized.get("llm_route"),
                "model_provider": normalized.get("model_provider"),
                "model": normalized.get("model"),
            },
        )
    _record_artifact(
        metadata,
        stage="specialist_planned",
        event_type="MISSION_SPECIALIST_PLANNED",
        agent_id=specialist_agent_id,
        details={
            "pod_manager_agent_id": pod_manager_agent_id,
            "source": normalized.get("source"),
            "llm_route": normalized.get("llm_route"),
            "model_provider": normalized.get("model_provider"),
            "model": normalized.get("model"),
        },
    )
    await record_audit_event(
        app,
        mission_id=mission_id,
        mission=mission,
        agent_id=specialist_agent_id,
        service_name="orchestrator",
        event_type="AGENT_PLAN_GENERATED",
        object_type="plan",
        object_id="specialist",
        tool_name="llm_delegation",
        payload_summary={
            "source": normalized.get("source"),
            "llm_route": normalized.get("llm_route"),
            "model_provider": normalized.get("model_provider"),
            "model": normalized.get("model"),
            "deliverable_count": len(normalized.get("deliverables", []) or []),
            "risk_note_count": len(normalized.get("risk_notes", []) or []),
        },
        content_hash_source=normalized,
    )
    generated_output_for_audit = metadata.get("generated_output")
    if isinstance(generated_output_for_audit, dict):
        await record_audit_event(
            app,
            mission_id=mission_id,
            mission=mission,
            agent_id=specialist_agent_id,
            service_name="orchestrator",
            event_type="GENERATED_OUTPUT_CREATED",
            object_type="generated_output",
            object_id=str(generated_output_for_audit.get("filename") or "generated_output"),
            tool_name="llm_delegation",
            payload_summary={
                "source": generated_output_for_audit.get("source"),
                "filename": generated_output_for_audit.get("filename"),
                "language": generated_output_for_audit.get("language"),
                "code_length_chars": generated_output_for_audit.get("code_length_chars", 0),
            },
            content_hash_source=generated_output_for_audit,
        )

    # Compute scaling decision when feature is enabled.
    if _setting_bool(settings, "agent_scaling_enabled", False) and is_scalable_agent(
        specialist_agent_id
    ):
        workload_items = _scaling_workload_items(metadata, normalized)
        scaling = compute_scaling_decision(
            agent_id=specialist_agent_id,
            workload_items=workload_items,
            max_instances=_setting_int(settings, "agent_scaling_max_instances", 4),
            items_per_instance=_setting_int(settings, "agent_scaling_items_per_instance", 3),
        )
        embed_scaling_decision(metadata, scaling)
        metadata["scaling_partition_events_emitted"] = False
        if not _chain_event_exists(metadata, "MISSION_SCALING_DECIDED"):
            append_chain_event(
                metadata,
                event_type="MISSION_SCALING_DECIDED",
                agent_id=specialist_agent_id,
                details={
                    "instance_count": scaling.instance_count,
                    "reason": scaling.reason,
                    "scaling_version": scaling.scaling_version,
                },
            )
        _record_artifact(
            metadata,
            stage="scaling_decided",
            event_type="MISSION_SCALING_DECIDED",
            agent_id=specialist_agent_id,
            details=scaling.to_dict(),
        )
        await record_audit_event(
            app,
            mission_id=mission_id,
            mission=mission,
            agent_id=specialist_agent_id,
            service_name="orchestrator",
            event_type="MISSION_SCALING_DECIDED",
            object_type="scaling_plan",
            object_id=specialist_agent_id,
            payload_summary=scaling.to_dict(),
            content_hash_source=scaling.to_dict(),
        )

    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
            emit_event_type="MISSION_SPECIALIST_PLANNED" if should_emit else None,
            event_state=MissionState.specialist_assigned if should_emit else None,
        )
        is not None
    )


async def _persist_runtime_phase_artifact(
    *,
    settings: Any,
    mission: Any,
    event_type: str,
) -> Any:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    selected_agent_id = _validate_agent_id(
        metadata.get("selected_agent_id"),
        fallback=metadata.get("assigned_specialist_agent_id") or CEO_AGENT_ID,
    )
    _record_artifact(
        metadata,
        stage=mission.state.value.lower(),
        event_type=event_type,
        agent_id=selected_agent_id,
        details={"state": mission.state.value},
    )
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


async def _produce_pod_group_standard(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission: Any,
) -> Any:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    pod_manager_agent_id = _validate_agent_id(
        metadata.get("assigned_pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    pod_name = _pod_key_for_manager(pod_manager_agent_id)
    existing_standards = metadata.get("pod_group_standards")
    if isinstance(existing_standards, dict) and isinstance(existing_standards.get(pod_name), dict):
        return mission

    mission_contract = metadata.get("mission_contract")
    if not isinstance(mission_contract, dict):
        mission_contract = {}
    raw_logicnodes = await asyncio.to_thread(
        storage.list_logicnodes,
        settings,
        mission.mission_id,
        500,
    )
    logicnodes = raw_logicnodes if isinstance(raw_logicnodes, list) else []
    standard = await generate_pod_group_standard(
        pod_name=pod_name,
        pod_manager_agent_id=pod_manager_agent_id,
        mission_id=mission.mission_id,
        logicnodes=[record for record in logicnodes if isinstance(record, dict)],
        mission_contract=mission_contract,
    )
    standards = dict(existing_standards) if isinstance(existing_standards, dict) else {}
    standards[pod_name] = standard
    metadata["pod_group_standards"] = standards
    metadata["selected_agent_id"] = pod_manager_agent_id
    metadata["agent_id"] = pod_manager_agent_id

    canonical_nodes = standard.get("canonical_logicnodes")
    canonical_count = len(canonical_nodes) if isinstance(canonical_nodes, list) else 0
    if not _chain_event_exists(metadata, "MISSION_POD_GROUP_STANDARD_PRODUCED"):
        append_chain_event(
            metadata,
            event_type="MISSION_POD_GROUP_STANDARD_PRODUCED",
            agent_id=pod_manager_agent_id,
            details={
                "pod": pod_name,
                "canonical_logicnode_count": canonical_count,
                "eliminated_duplicates": standard.get("eliminated_duplicates", 0),
                "source": standard.get("source"),
                "llm_route": standard.get("llm_route"),
                "model_provider": standard.get("model_provider"),
                "model": standard.get("model"),
            },
        )
    _record_artifact(
        metadata,
        stage="pod_group_standard",
        event_type="MISSION_POD_GROUP_STANDARD_PRODUCED",
        agent_id=pod_manager_agent_id,
        details={
            "pod": pod_name,
            "canonical_logicnode_count": canonical_count,
            "eliminated_duplicates": standard.get("eliminated_duplicates", 0),
        },
    )
    await record_audit_event(
        app,
        mission_id=mission.mission_id,
        mission=mission,
        agent_id=pod_manager_agent_id,
        service_name="orchestrator",
        event_type="MISSION_POD_GROUP_STANDARD_PRODUCED",
        object_type="pod_group_standard",
        object_id=pod_name,
        tool_name="llm_delegation",
        payload_summary={
            "pod": pod_name,
            "canonical_logicnode_count": canonical_count,
            "eliminated_duplicates": standard.get("eliminated_duplicates", 0),
            "source": standard.get("source"),
            "model_provider": standard.get("model_provider"),
            "model": standard.get("model"),
        },
        content_hash_source=standard,
    )
    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission.mission_id,
            metadata=metadata,
            emit_event_type="MISSION_POD_GROUP_STANDARD_PRODUCED",
            event_state=MissionState.gating,
        )
        or mission
    )


async def _ensure_verified_build_artifact(
    *,
    app: Any,
    settings: Any,
    mission: Any,
) -> Any:
    if not build_artifact_support.mission_requires_build_artifact(mission.metadata):
        return mission

    artifact_metadata = mission.metadata if isinstance(mission.metadata, dict) else {}
    if build_artifact_support.mission_has_generated_output(artifact_metadata):
        artifact_record = build_artifact_support.build_generated_output_artifact(
            mission_id=mission.mission_id,
            requested_target_language=mission.requested_target_language,
            metadata=artifact_metadata,
        )
    else:
        artifact_record = build_artifact_support.build_source_bundle_artifact(
            mission_id=mission.mission_id,
            requested_target_language=mission.requested_target_language,
            metadata=artifact_metadata,
        )
    await asyncio.to_thread(
        storage.upsert_build_artifact,
        settings,
        mission.mission_id,
        artifact_record["artifact_id"],
        artifact_record["artifact_type"],
        artifact_record["stage"],
        artifact_record["status"],
        artifact_record["storage_backend"],
        artifact_record["storage_ref"],
        artifact_record["digest_sha256"],
        artifact_record["size_bytes"],
        artifact_record["manifest"],
        artifact_record["verification"],
        artifact_record["build_log"],
        artifact_record["artifact_text"],
        artifact_record["created_at"],
    )
    await record_audit_event(
        app,
        mission_id=mission.mission_id,
        mission=mission,
        agent_id=str(
            (
                mission.metadata.get("selected_agent_id")
                if isinstance(mission.metadata, dict)
                else None
            )
            or CEO_AGENT_ID
        ),
        service_name="orchestrator",
        event_type="MISSION_BUILD_ARTIFACT_WRITTEN",
        object_type="build_artifact",
        object_id=str(artifact_record["artifact_id"]),
        payload_summary={
            "artifact_type": artifact_record["artifact_type"],
            "stage": artifact_record["stage"],
            "status": artifact_record["status"],
            "digest_sha256": artifact_record["digest_sha256"],
            "size_bytes": artifact_record["size_bytes"],
        },
        content_hash_source=artifact_record,
    )

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    selected_agent_id = _validate_agent_id(
        metadata.get("selected_agent_id"),
        fallback=metadata.get("assigned_specialist_agent_id") or CEO_AGENT_ID,
    )
    build_artifact_support.record_build_artifact_metadata(
        metadata,
        agent_id=selected_agent_id,
        artifact_record=artifact_record,
    )
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


async def _prepare_delivery_summary(
    *,
    app: Any,
    settings: Any,
    mission: Any,
) -> Any:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    build_artifacts = await asyncio.to_thread(
        storage.list_build_artifacts,
        settings,
        mission.mission_id,
        50,
    )
    delivery_summary = await generate_pm_delivery_summary(
        mission_context=_mission_context(mission, metadata),
        generated_output=metadata.get("generated_output") or {},
        build_artifacts=build_artifacts,
        feature_contract=metadata.get("feature_contract") or {},
        mission_contract=metadata.get("mission_contract") or {},
    )
    metadata["delivery_summary"] = delivery_summary

    if not _chain_event_exists(metadata, "MISSION_DELIVERED"):
        append_chain_event(
            metadata,
            event_type="MISSION_DELIVERED",
            agent_id=PM_AGENT_ID,
            details={
                "delivery_title": delivery_summary["delivery_title"],
                "artifact_type": delivery_summary.get("primary_artifact_type"),
                "criteria_met_count": len(delivery_summary.get("criteria_met", [])),
                "source": delivery_summary.get("source"),
            },
        )
    await record_audit_event(
        app,
        mission_id=mission.mission_id,
        mission=mission,
        agent_id=PM_AGENT_ID,
        service_name="orchestrator",
        event_type="MISSION_DELIVERED",
        object_type="delivery_summary",
        object_id=mission.mission_id,
        payload_summary={
            "delivery_title": delivery_summary["delivery_title"],
            "artifact_type": delivery_summary.get("primary_artifact_type"),
            "criteria_met_count": len(delivery_summary.get("criteria_met", [])),
            "source": delivery_summary.get("source"),
        },
        content_hash_source=delivery_summary,
    )
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


async def _prepare_equivalence_report(
    *,
    app: Any,
    settings: Any,
    mission: Any,
) -> tuple[Any, bool, dict[str, Any]]:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    if not mission_requires_equivalence(metadata):
        return mission, True, {"skipped": True, "reason": "generated output not present"}

    build_artifacts = await asyncio.to_thread(
        storage.list_build_artifacts,
        settings,
        mission.mission_id,
        50,
    )
    enforcement_enabled = _setting_bool(
        settings,
        "mission_equivalence_enforcement_enabled",
        False,
    )
    report = build_equivalence_report(
        mission_id=mission.mission_id,
        requested_target_language=mission.requested_target_language,
        metadata=metadata,
        build_artifacts=build_artifacts,
        enforcement_enabled=enforcement_enabled,
    )
    metadata["equivalence_report"] = report
    event_type = (
        "MISSION_EQUIVALENCE_BLOCKED"
        if report.get("blocking")
        else "MISSION_EQUIVALENCE_VERIFIED"
    )
    if not _chain_event_exists(metadata, event_type):
        append_chain_event(
            metadata,
            event_type=event_type,
            agent_id="AGENT-10-TESTER",
            details={
                "report_id": report["report_id"],
                "status": report["status"],
                "passed": report["passed"],
                "blocking": report["blocking"],
                "risk_level": report["risk_level"],
                "check_count": len(report.get("checks", [])),
            },
        )
    _record_artifact(
        metadata,
        stage="equivalence",
        event_type=event_type,
        agent_id="AGENT-10-TESTER",
        details={
            "report_id": report["report_id"],
            "status": report["status"],
            "passed": report["passed"],
            "blocking": report["blocking"],
            "risk_level": report["risk_level"],
        },
    )
    await record_audit_event(
        app,
        mission_id=mission.mission_id,
        mission=mission,
        agent_id="AGENT-10-TESTER",
        service_name="orchestrator",
        event_type=event_type,
        object_type="equivalence_report",
        object_id=str(report["report_id"]),
        payload_summary={
            "status": report["status"],
            "passed": report["passed"],
            "blocking": report["blocking"],
            "risk_level": report["risk_level"],
            "check_count": len(report.get("checks", [])),
        },
        content_hash_source=report,
    )
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission, not bool(report.get("blocking")), report


async def _prepare_security_compliance_report(
    *,
    app: Any,
    settings: Any,
    mission: Any,
) -> tuple[Any, bool, dict[str, Any]]:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    if not mission_requires_security_compliance(metadata):
        return mission, True, {"skipped": True, "reason": "no mission artifact to scan"}

    enforcement_enabled = _setting_bool(
        settings,
        "mission_security_compliance_enforcement_enabled",
        False,
    )
    report = build_security_compliance_report(
        mission_id=mission.mission_id,
        metadata=metadata,
        enforcement_enabled=enforcement_enabled,
    )
    metadata["security_compliance_report"] = report
    if report.get("blocking"):
        event_type = "MISSION_SECURITY_COMPLIANCE_BLOCKED"
    elif report.get("status") == "warned":
        event_type = "MISSION_SECURITY_COMPLIANCE_WARNED"
    else:
        event_type = "MISSION_SECURITY_COMPLIANCE_PASSED"

    if not _chain_event_exists(metadata, event_type):
        append_chain_event(
            metadata,
            event_type=event_type,
            agent_id="AGENT-05-SECURITY",
            details={
                "report_id": report["report_id"],
                "status": report["status"],
                "passed": report["passed"],
                "blocking": report["blocking"],
                "risk_level": report["risk_level"],
                "finding_count": len(report.get("findings", [])),
            },
        )
    _record_artifact(
        metadata,
        stage="security_compliance",
        event_type=event_type,
        agent_id="AGENT-05-SECURITY",
        details={
            "report_id": report["report_id"],
            "status": report["status"],
            "passed": report["passed"],
            "blocking": report["blocking"],
            "risk_level": report["risk_level"],
        },
    )
    await record_audit_event(
        app,
        mission_id=mission.mission_id,
        mission=mission,
        agent_id="AGENT-05-SECURITY",
        service_name="orchestrator",
        event_type=event_type,
        object_type="security_compliance_report",
        object_id=str(report["report_id"]),
        payload_summary={
            "status": report["status"],
            "passed": report["passed"],
            "blocking": report["blocking"],
            "risk_level": report["risk_level"],
            "finding_count": len(report.get("findings", [])),
        },
        content_hash_source=report,
    )
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission, not bool(report.get("blocking")), report


async def _prepare_dependency_absorption_reports(
    *,
    app: Any,
    settings: Any,
    mission: Any,
) -> tuple[Any, bool, dict[str, Any]]:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    if not mission_requires_dependency_absorption(metadata):
        return mission, True, {"skipped": True, "reason": "no dependency evidence"}

    reports = build_dependency_absorption_reports(
        mission_id=mission.mission_id,
        metadata=metadata,
    )
    inventory = reports["dependency_inventory"]
    classification_report = reports["dependency_classification_report"]
    absorption_report = reports["dependency_absorption_report"]
    metadata["dependency_inventory"] = inventory
    metadata["dependency_classification_report"] = classification_report
    metadata["dependency_absorption_report"] = absorption_report
    metadata["dependency_survival_justifications"] = reports[
        "dependency_survival_justifications"
    ]

    event_type = (
        "MISSION_DEPENDENCY_ABSORPTION_BLOCKED"
        if absorption_report.get("blocking")
        else "MISSION_DEPENDENCY_ABSORPTION_PLANNED"
        if absorption_report.get("planned_replacements")
        else "MISSION_DEPENDENCY_CLASSIFIED"
    )
    if not _chain_event_exists(metadata, "MISSION_DEPENDENCY_INVENTORY_CREATED"):
        append_chain_event(
            metadata,
            event_type="MISSION_DEPENDENCY_INVENTORY_CREATED",
            agent_id="AGENT-39-DEPABS",
            details={
                "inventory_id": inventory["inventory_id"],
                "dependency_count": inventory["dependency_count"],
                "sources": inventory.get("sources", []),
            },
        )
    if not _chain_event_exists(metadata, event_type):
        append_chain_event(
            metadata,
            event_type=event_type,
            agent_id="AGENT-39-DEPABS",
            details={
                "report_id": absorption_report["report_id"],
                "classification_report_id": classification_report["report_id"],
                "status": absorption_report["status"],
                "blocking": absorption_report["blocking"],
                "planned_replacement_count": len(
                    absorption_report.get("planned_replacements", [])
                ),
                "safety_block_count": absorption_report.get("safety_block_count", 0),
            },
        )
    _record_artifact(
        metadata,
        stage="dependency_absorption",
        event_type=event_type,
        agent_id="AGENT-39-DEPABS",
        details={
            "inventory_id": inventory["inventory_id"],
            "report_id": absorption_report["report_id"],
            "status": absorption_report["status"],
            "blocking": absorption_report["blocking"],
            "dependency_count": inventory["dependency_count"],
        },
    )
    await record_audit_event(
        app,
        mission_id=mission.mission_id,
        mission=mission,
        agent_id="AGENT-39-DEPABS",
        service_name="orchestrator",
        event_type=event_type,
        object_type="dependency_absorption_report",
        object_id=str(absorption_report["report_id"]),
        payload_summary={
            "status": absorption_report["status"],
            "blocking": absorption_report["blocking"],
            "dependency_count": inventory["dependency_count"],
            "planned_replacement_count": len(
                absorption_report.get("planned_replacements", [])
            ),
            "safety_block_count": absorption_report.get("safety_block_count", 0),
        },
        content_hash_source=reports,
    )
    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission, not bool(absorption_report.get("blocking")), absorption_report


async def _prepare_fusion(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission: Any,
) -> Any:
    """Phase 9: CEO Logic Folding — fuse pod Group Standards into Master Logic Stream.

    Runs after transitioning into FUSION. If pod_group_standards is empty the
    mission still proceeds; the master_logic_stream will be empty and
    ready_for_codegen will be False.
    """
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)

    pod_group_standards = metadata.get("pod_group_standards") or {}
    mission_contract = metadata.get("mission_contract") or {}

    try:
        master_stream = await generate_master_logic_stream(
            pod_group_standards=pod_group_standards,
            mission_contract=mission_contract,
            mission_context=_mission_context(mission, metadata),
        )
    except Exception as exc:
        LOGGER.warning("v2: fusion failed for mission %s: %s", mission.mission_id, exc)
        master_stream = {
            "master_logic_stream": [],
            "total_unified_nodes": 0,
            "eliminated_across_pods": 0,
            "ready_for_codegen": False,
            "source": "error",
        }

    metadata["master_logic_stream"] = master_stream

    output_mode = str(metadata.get("output_mode") or "FULL_BUILD").strip().upper()
    if (
        output_mode != "ANALYZE_ONLY"
        and master_stream.get("ready_for_codegen")
        and not build_artifact_support.mission_has_generated_output(metadata)
    ):
        specialist_agent_id = _validate_agent_id(
            metadata.get("assigned_specialist_agent_id"),
            fallback=resolve_specialist_agent_id(mission.requested_target_language),
        )
        try:
            generated_output = await generate_code_from_contract(
                mission_context={
                    **_mission_context(mission, metadata),
                    "mission_contract": mission_contract,
                    "specialist_plan": metadata.get("specialist_plan") or {},
                    "master_logic_stream": master_stream,
                },
                specialist_agent_id=specialist_agent_id,
                mission_contract=mission_contract,
                logicnodes=master_stream.get("master_logic_stream") or [],
                target_language=mission.requested_target_language or "python",
            )
            metadata["generated_output"] = generated_output
        except Exception as exc:
            LOGGER.warning("v2: fusion codegen failed for mission %s: %s", mission.mission_id, exc)

    if not _chain_event_exists(metadata, "MISSION_LOGIC_FOLDED"):
        append_chain_event(
            metadata,
            event_type="MISSION_LOGIC_FOLDED",
            agent_id=CEO_AGENT_ID,
            details={
                "unified_nodes": master_stream["total_unified_nodes"],
                "eliminated": master_stream["eliminated_across_pods"],
                "ready_for_codegen": master_stream["ready_for_codegen"],
                "source": master_stream.get("source"),
            },
        )

    updated = await asyncio.to_thread(
        storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


# ------------------------------------------------------------------
# V2 transition table (ordered)
# ------------------------------------------------------------------

V2_TRANSITIONS: tuple[tuple[MissionState, MissionState, str], ...] = (
    (MissionState.queued, MissionState.pm_intake, "MISSION_PM_INTAKE"),
    (MissionState.pm_intake, MissionState.fetch, "MISSION_FETCH"),
    (MissionState.fetch, MissionState.ceo_delegated, "MISSION_CEO_DELEGATED"),
    (
        MissionState.ceo_delegated,
        MissionState.pod_assigned,
        "MISSION_POD_MANAGER_ASSIGNED",
    ),
    (
        MissionState.pod_assigned,
        MissionState.specialist_assigned,
        "MISSION_SPECIALIST_ASSIGNED",
    ),
    (
        MissionState.specialist_assigned,
        MissionState.running,
        "MISSION_RUNNING",
    ),
    (MissionState.running, MissionState.gating, "MISSION_GATING"),
    (MissionState.gating, MissionState.fusion, "MISSION_FUSION"),
    (MissionState.fusion, MissionState.verified, "MISSION_VERIFIED"),
    (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
)

V1_TRANSITIONS: tuple[tuple[MissionState, MissionState, str], ...] = (
    (MissionState.queued, MissionState.running, "MISSION_RUNNING"),
    (MissionState.running, MissionState.verified, "MISSION_VERIFIED"),
    (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
)

# Ordered list of all 11 v2 phases (for deterministic progression).
V2_PHASE_ORDER: tuple[MissionState, ...] = (
    MissionState.intake,
    MissionState.queued,
    MissionState.pm_intake,
    MissionState.fetch,
    MissionState.ceo_delegated,
    MissionState.pod_assigned,
    MissionState.specialist_assigned,
    MissionState.running,
    MissionState.gating,
    MissionState.fusion,
    MissionState.verified,
    MissionState.complete,
)

# Maps v2 event types to the phases they represent.
V2_EVENT_TO_PHASE: dict[str, MissionState] = {
    "MISSION_INTAKE": MissionState.intake,
    "MISSION_QUEUED": MissionState.queued,
    "MISSION_PM_INTAKE": MissionState.pm_intake,
    "MISSION_FETCH": MissionState.fetch,
    "MISSION_FETCH_COMPLETE": MissionState.fetch,
    "MISSION_CEO_DELEGATED": MissionState.ceo_delegated,
    "MISSION_POD_MANAGER_ASSIGNED": MissionState.pod_assigned,
    "MISSION_SPECIALIST_ASSIGNED": MissionState.specialist_assigned,
    "MISSION_RUNNING": MissionState.running,
    "MISSION_GATING": MissionState.gating,
    "MISSION_FUSION": MissionState.fusion,
    "MISSION_VERIFIED": MissionState.verified,
    "MISSION_COMPLETE": MissionState.complete,
}


# ------------------------------------------------------------------
# Backward-compatible v1.1 mapping
# ------------------------------------------------------------------

_V2_TO_V1_MAP: dict[MissionState, MissionState] = {
    MissionState.intake: MissionState.intake,
    MissionState.queued: MissionState.queued,
    MissionState.pm_intake: MissionState.queued,
    MissionState.fetch: MissionState.queued,
    MissionState.ceo_delegated: MissionState.queued,
    MissionState.pod_assigned: MissionState.queued,
    MissionState.specialist_assigned: MissionState.queued,
    MissionState.running: MissionState.running,
    MissionState.gating: MissionState.running,
    MissionState.fusion: MissionState.running,
    MissionState.verified: MissionState.verified,
    MissionState.complete: MissionState.complete,
    MissionState.failed: MissionState.failed,
}


def v2_map_state_to_v1(state: MissionState) -> MissionState:
    """Map a v2 state to its canonical v1.1 equivalent.

    This allows APIs to expose backward-compatible state values
    when the consumer does not understand v2 microstates.
    """
    return _V2_TO_V1_MAP.get(state, state)


def v2_phase_index(state: MissionState) -> int:
    """Return the zero-based phase index for a v2 state.

    Returns -1 for states not in the v2 phase model (e.g. ``FAILED``).
    """
    try:
        return V2_PHASE_ORDER.index(state)
    except ValueError:
        return -1


# ------------------------------------------------------------------
# V2 lifecycle driver (legacy path, no LangGraph)
# ------------------------------------------------------------------


async def advance_mission_lifecycle_v2(
    *,
    app: Any,
    mission_id: str,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    prepare_chain_fn: Any,
    completion_check_fn: Any,
) -> None:
    """Drive a mission through all 11 v2 phases.

    This is the legacy (non-LangGraph) v2 driver. It mirrors the
    structure of ``runtime.advance_mission_lifecycle`` but uses the
    full v2 transition table.

    Parameters
    ----------
    app : FastAPI
        Application instance with ``app.state`` references.
    mission_id : str
        Mission to advance.
    settings : Settings
        Application settings (must have ``mission_flow_v2_enabled=True``).
    validator : EnvelopeValidator
        Protocol envelope validator.
    emit_state_event_fn : callable
        Async function to emit state events to Redis streams.
    prepare_chain_fn : callable
        Legacy compatibility hook. The v2 driver now performs its own
        PM, CEO, pod-manager, and specialist stage preparation.
    completion_check_fn : callable
        Async function ``(settings, mission) → (bool, dict)``
        that checks whether completion artifacts are ready.
    """

    stage_preparers = {
        MissionState.queued: _prepare_pm_intake,
        MissionState.pm_intake: _prepare_fetch_phase,   # Phase 8: IS Agent
        MissionState.fetch: _prepare_ceo_delegation,    # Phase 8: CEO after FETCH
        MissionState.ceo_delegated: _prepare_pod_assignment,
        MissionState.pod_assigned: _prepare_specialist_assignment,
        MissionState.specialist_assigned: _prepare_specialist_plan,
    }

    _ = prepare_chain_fn

    for expected_state, new_state, event_type in V2_TRANSITIONS:
        preparer = stage_preparers.get(expected_state)
        if preparer is not None:
            prepared = await preparer(
                app=app,
                settings=settings,
                validator=validator,
                emit_state_event_fn=emit_state_event_fn,
                mission_id=mission_id,
            )
            if not prepared:
                return

        if expected_state == MissionState.running and new_state == MissionState.gating:
            mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
            if mission is None:
                return
            metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
            if metadata.get("scaling_active"):
                if not metadata.get("scaling_partition_events_emitted"):
                    mission = await _emit_partition_work_items(
                        app=app,
                        settings=settings,
                        validator=validator,
                        mission=mission,
                    )
                    metadata = with_chain_defaults(
                        mission.metadata,
                        mission.requested_target_language,
                    )
                if not all_partitions_complete(metadata):
                    return

        # Completion gate before COMPLETE
        if (
            expected_state == MissionState.verified
            and new_state == MissionState.complete
        ):
            mission = await asyncio.to_thread(
                storage.fetch_mission, settings, mission_id
            )
            if mission is None:
                return
            ready, details = await completion_check_fn(
                settings=settings, mission=mission
            )
            if not ready:
                metadata = with_chain_defaults(
                    mission.metadata,
                    mission.requested_target_language,
                )
                append_chain_event(
                    metadata,
                    event_type="MISSION_COMPLETION_BLOCKED",
                    agent_id=CEO_AGENT_ID,
                    details=details,
                )
                await asyncio.to_thread(
                    storage.update_mission_metadata,
                    settings,
                    mission_id,
                    metadata,
                )
                await asyncio.to_thread(
                    storage.insert_mission_event,
                    settings,
                    mission_id,
                    MissionState.verified,
                    MissionState.verified,
                    "MISSION_COMPLETION_BLOCKED",
                )
                redis_ready = bool(getattr(app.state, "redis_ready", False))
                redis_client = getattr(app.state, "redis", None)
                if redis_ready and redis_client is not None:
                    try:
                        await emit_state_event_fn(
                            settings=settings,
                            validator=validator,
                            redis_client=redis_client,
                            mission=mission,
                            event_type="MISSION_COMPLETION_BLOCKED",
                        )
                    except Exception as exc:
                        LOGGER.warning(
                            "v2: failed to emit completion block event for mission %s: %s",
                            mission_id,
                            exc,
                        )
                return
            mission, equivalence_ready, equivalence_report = await _prepare_equivalence_report(
                app=app,
                settings=settings,
                mission=mission,
            )
            if not equivalence_ready:
                await asyncio.to_thread(
                    storage.insert_mission_event,
                    settings,
                    mission_id,
                    MissionState.verified,
                    MissionState.verified,
                    "MISSION_EQUIVALENCE_BLOCKED",
                )
                redis_ready = bool(getattr(app.state, "redis_ready", False))
                redis_client = getattr(app.state, "redis", None)
                if redis_ready and redis_client is not None:
                    try:
                        await emit_state_event_fn(
                            settings=settings,
                            validator=validator,
                            redis_client=redis_client,
                            mission=mission,
                            event_type="MISSION_EQUIVALENCE_BLOCKED",
                        )
                    except Exception as exc:
                        LOGGER.warning(
                            "v2: failed to emit equivalence block event for mission %s: %s",
                            mission_id,
                            exc,
                        )
                LOGGER.info(
                    "v2: mission %s blocked by equivalence report %s",
                    mission_id,
                    equivalence_report.get("report_id"),
                )
                return
            (
                mission,
                security_compliance_ready,
                security_compliance_report,
            ) = await _prepare_security_compliance_report(
                app=app,
                settings=settings,
                mission=mission,
            )
            if not security_compliance_ready:
                await asyncio.to_thread(
                    storage.insert_mission_event,
                    settings,
                    mission_id,
                    MissionState.verified,
                    MissionState.verified,
                    "MISSION_SECURITY_COMPLIANCE_BLOCKED",
                )
                redis_ready = bool(getattr(app.state, "redis_ready", False))
                redis_client = getattr(app.state, "redis", None)
                if redis_ready and redis_client is not None:
                    try:
                        await emit_state_event_fn(
                            settings=settings,
                            validator=validator,
                            redis_client=redis_client,
                            mission=mission,
                            event_type="MISSION_SECURITY_COMPLIANCE_BLOCKED",
                        )
                    except Exception as exc:
                        LOGGER.warning(
                            "v2: failed to emit security/compliance block event for "
                            "mission %s: %s",
                            mission_id,
                            exc,
                        )
                LOGGER.info(
                    "v2: mission %s blocked by security/compliance report %s",
                    mission_id,
                    security_compliance_report.get("report_id"),
                )
                return
            mission, dependency_absorption_ready, dependency_absorption_report = (
                await _prepare_dependency_absorption_reports(
                    app=app,
                    settings=settings,
                    mission=mission,
                )
            )
            if not dependency_absorption_ready:
                await asyncio.to_thread(
                    storage.insert_mission_event,
                    settings,
                    mission_id,
                    MissionState.verified,
                    MissionState.verified,
                    "MISSION_DEPENDENCY_ABSORPTION_BLOCKED",
                )
                redis_ready = bool(getattr(app.state, "redis_ready", False))
                redis_client = getattr(app.state, "redis", None)
                if redis_ready and redis_client is not None:
                    try:
                        await emit_state_event_fn(
                            settings=settings,
                            validator=validator,
                            redis_client=redis_client,
                            mission=mission,
                            event_type="MISSION_DEPENDENCY_ABSORPTION_BLOCKED",
                        )
                    except Exception as exc:
                        LOGGER.warning(
                            "v2: failed to emit dependency absorption block event for "
                            "mission %s: %s",
                            mission_id,
                            exc,
                        )
                LOGGER.info(
                    "v2: mission %s blocked by dependency absorption report %s",
                    mission_id,
                    dependency_absorption_report.get("report_id"),
                )
                return
            mission = await _prepare_delivery_summary(
                app=app,
                settings=settings,
                mission=mission,
            )

        await asyncio.sleep(settings.transition_step_seconds)

        record = await asyncio.to_thread(
            storage.transition_mission_state,
            settings,
            mission_id,
            expected_state,
            new_state,
            event_type,
        )
        if record is None:
            return

        if new_state in RUNTIME_PHASES:
            record = await _persist_runtime_phase_artifact(
                settings=settings,
                mission=record,
                event_type=event_type,
            )
            if new_state == MissionState.verified:
                try:
                    record = await _ensure_verified_build_artifact(
                        app=app,
                        settings=settings,
                        mission=record,
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "v2: failed to package verified build artifact for mission %s: %s",
                        mission_id,
                        exc,
                    )
            if new_state == MissionState.running:
                record = await _emit_partition_work_items(
                    app=app,
                    settings=settings,
                    validator=validator,
                    mission=record,
                )

        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if redis_ready and redis_client is not None:
            try:
                await emit_state_event_fn(
                    settings=settings,
                    validator=validator,
                    redis_client=redis_client,
                    mission=record,
                    event_type=event_type,
                )
            except Exception as exc:
                LOGGER.warning(
                    "v2: failed to emit %s for mission %s: %s",
                    event_type,
                    mission_id,
                    exc,
                )

        if new_state == MissionState.gating:
            record = await _produce_pod_group_standard(
                app=app,
                settings=settings,
                validator=validator,
                emit_state_event_fn=emit_state_event_fn,
                mission=record,
            )

        if new_state == MissionState.fusion:
            record = await _prepare_fusion(
                app=app,
                settings=settings,
                validator=validator,
                emit_state_event_fn=emit_state_event_fn,
                mission=record,
            )
