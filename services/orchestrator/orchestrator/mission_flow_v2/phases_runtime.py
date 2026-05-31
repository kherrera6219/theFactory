from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any

from .. import build_artifacts as build_artifact_support
from ..dependency_absorption import (
    build_dependency_absorption_reports,
    build_sbom_delta,
    execute_absorption,
    mission_requires_dependency_absorption,
)
from ..llm_delegation import (
    generate_rqca_assessment,
)
from ..mission_flow import (
    CEO_AGENT_ID,
    append_chain_event,
    resolve_specialist_agent_id,
    with_chain_defaults,
)
from ..rqca_agent import run_runtime_qc
from ..testdata_agent import generate_testdata_manifest
from .base import (
    _chain_event_exists,
    _extension_for_language,
    _mission_context,
    _record_artifact,
    _validate_agent_id,
)
from .phases_build import _ensure_verified_build_artifact

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
    await _pkg().record_audit_event(
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
        _pkg().storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission, not bool(absorption_report.get("blocking")), absorption_report


async def _prepare_depabs_execution(
    *,
    app: Any,
    settings: Any,
    mission: Any,
) -> Any:
    if not bool(getattr(settings, "depabs_execution_enabled", False)):
        return mission
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    source_code = str(metadata.get("source_code") or "")
    absorption_report = metadata.get("dependency_absorption_report")
    if not source_code.strip() or not isinstance(absorption_report, dict):
        return mission
    if isinstance(metadata.get("depabs_execution"), dict):
        return mission
    execution = await execute_absorption(
        mission_id=mission.mission_id,
        source_code=source_code,
        language=mission.requested_target_language or "python",
        absorption_report=absorption_report,
        settings=settings,
    )
    metadata["depabs_execution"] = execution
    inventory = metadata.get("dependency_inventory")
    survival = metadata.get("dependency_survival_justifications")
    sbom_delta = build_sbom_delta(
        original_dependencies=(
            inventory.get("dependencies", []) if isinstance(inventory, dict) else []
        ),
        absorption_result=execution,
        survival_justifications=survival if isinstance(survival, list) else [],
    )
    metadata["sbom_delta"] = sbom_delta
    absorption_count = int(execution.get("absorption_count") or 0)
    if absorption_count > 0:
        language = mission.requested_target_language or "python"
        metadata["generated_output"] = {
            "schema_version": "generated_output.v1",
            "generated_code": execution.get("modified_source") or source_code,
            "filename": f"absorbed_{mission.mission_id}.{_extension_for_language(language)}",
            "language": language,
            "description": (
                f"Source with {absorption_count} dependencies absorbed into first-party code."
            ),
            "dependencies": sbom_delta.get("remaining", []),
            "source": "depabs_execution",
            "code_length_chars": len(str(execution.get("modified_source") or "")),
        }
    append_chain_event(
        metadata,
        event_type="MISSION_DEPABS_EXECUTED",
        agent_id="AGENT-39-DEPABS",
        details={
            "status": execution.get("status"),
            "absorption_count": absorption_count,
            "reduction_percent": sbom_delta.get("reduction_percent"),
        },
    )
    await _pkg().record_audit_event(
        app,
        mission_id=mission.mission_id,
        mission=mission,
        agent_id="AGENT-39-DEPABS",
        service_name="orchestrator",
        event_type="MISSION_DEPABS_EXECUTED",
        object_type="depabs_execution",
        object_id=mission.mission_id,
        payload_summary={
            "status": execution.get("status"),
            "absorption_count": absorption_count,
            "reduction_percent": sbom_delta.get("reduction_percent"),
        },
        content_hash_source={"depabs_execution": execution, "sbom_delta": sbom_delta},
    )
    updated = await asyncio.to_thread(
        _pkg().storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    if updated is not None and absorption_count > 0:
        try:
            updated = await _ensure_verified_build_artifact(
                app=app,
                settings=settings,
                mission=updated,
            )
        except Exception as exc:
            LOGGER.warning("failed to package DEPABS artifact for %s: %s", mission.mission_id, exc)
    return updated or mission


async def _prepare_runtime_qc(
    *,
    app: Any,
    settings: Any,
    mission: Any,
) -> tuple[Any, bool, dict[str, Any]]:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    generated_output = metadata.get("generated_output")
    if not isinstance(generated_output, dict):
        return mission, True, {"skipped": True, "reason": "no generated output"}
    if not bool(getattr(settings, "testdata_agent_enabled", False)):
        return mission, True, {"skipped": True, "reason": "TESTDATA disabled"}
    target_language = mission.requested_target_language or str(
        generated_output.get("language") or "python"
    )
    manifest = metadata.get("testdata_manifest")
    if not isinstance(manifest, dict):
        manifest = await generate_testdata_manifest(
            mission_id=mission.mission_id,
            generated_output=generated_output,
            integration_tests=metadata.get("integration_tests")
            if isinstance(metadata.get("integration_tests"), dict)
            else None,
            mission_contract=metadata.get("mission_contract")
            if isinstance(metadata.get("mission_contract"), dict)
            else {},
            language=target_language,
            settings=settings,
        )
        metadata["testdata_manifest"] = manifest
        append_chain_event(
            metadata,
            event_type="MISSION_TESTDATA_MANIFEST_READY",
            agent_id="AGENT-40-TESTDATA",
            details={
                "base_image": manifest.get("base_image"),
                "timeout_seconds": manifest.get("timeout_seconds"),
                "synthetic_input_count": len(manifest.get("synthetic_inputs") or []),
                "source": manifest.get("source"),
            },
        )
        try:
            await asyncio.to_thread(
                _pkg().storage.insert_testdata_manifest,
                settings,
                mission.mission_id,
                manifest,
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to persist testdata manifest for %s: %s",
                mission.mission_id,
                exc,
            )

    if not bool(getattr(settings, "rqca_agent_enabled", False)):
        updated = await asyncio.to_thread(
            _pkg().storage.update_mission_metadata,
            settings,
            mission.mission_id,
            metadata,
        )
        return updated or mission, True, {"skipped": True, "reason": "RQCA disabled"}

    execution = await run_runtime_qc(
        mission_id=mission.mission_id,
        generated_output=generated_output,
        testdata_manifest=manifest,
        integration_tests=metadata.get("integration_tests")
        if isinstance(metadata.get("integration_tests"), dict)
        else None,
        language=target_language,
        settings=settings,
    )
    qc_assessment = await generate_rqca_assessment(
        mission_id=mission.mission_id,
        execution_result=execution,
        mission_contract=metadata.get("mission_contract")
        if isinstance(metadata.get("mission_contract"), dict)
        else {},
        language=target_language,
    )
    runtime_qc_report = {**execution, "qc_assessment": qc_assessment}
    metadata["runtime_qc_report"] = runtime_qc_report
    append_chain_event(
        metadata,
        event_type="MISSION_RUNTIME_QC_COMPLETE",
        agent_id="AGENT-41-RQCA",
        details={
            "execution_verdict": execution.get("verdict"),
            "qc_verdict": qc_assessment.get("qc_verdict"),
            "execution_type": execution.get("execution_type"),
            "deployment_safe": qc_assessment.get("deployment_safe"),
            "source": execution.get("source"),
        },
    )
    try:
        await asyncio.to_thread(
            _pkg().storage.insert_runtime_qc_report,
            settings,
            mission.mission_id,
            execution,
            qc_assessment,
        )
    except Exception as exc:
        LOGGER.warning("failed to persist runtime QC report for %s: %s", mission.mission_id, exc)
    await _pkg().record_audit_event(
        app,
        mission_id=mission.mission_id,
        mission=mission,
        agent_id="AGENT-41-RQCA",
        service_name="orchestrator",
        event_type="MISSION_RUNTIME_QC_COMPLETE",
        object_type="runtime_qc_report",
        object_id=mission.mission_id,
        payload_summary={
            "execution_verdict": execution.get("verdict"),
            "qc_verdict": qc_assessment.get("qc_verdict"),
            "execution_type": execution.get("execution_type"),
        },
        content_hash_source=runtime_qc_report,
    )
    updated = await asyncio.to_thread(
        _pkg().storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    blocked = (
        bool(getattr(settings, "rqca_enforcement_enabled", False))
        and qc_assessment.get("qc_verdict") == "FAIL"
    )
    return updated or mission, not blocked, runtime_qc_report


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

    # ── Neo4j dependency-depth sort (S4-04) ──────────────────────────────────
    # When Neo4j is enabled, reorder pod_group_standards keys so that nodes
    # with deeper dependency chains (i.e. more things depend on them) are
    # processed first by generate_master_logic_stream. This avoids producing
    # a master stream that references unresolved dependencies.
    if settings.neo4j_enabled and pod_group_standards:
        try:
            from . import neo4j_store as _neo4j
            graph_nodes = await asyncio.to_thread(
                _neo4j.list_logicnodes_by_depth,
                settings,
                mission.mission_id,
                2000,
            )
            if graph_nodes:
                # Build an ordered node_id list from deepest → shallowest
                depth_order = [n["node_id"] for n in graph_nodes]
                ordered: dict[str, Any] = {}
                # First insert nodes in depth order (they exist in pod_group_standards)
                for nid in depth_order:
                    if nid in pod_group_standards:
                        ordered[nid] = pod_group_standards[nid]
                # Append any remaining nodes not yet in the ordered dict
                for nid, val in pod_group_standards.items():
                    if nid not in ordered:
                        ordered[nid] = val
                pod_group_standards = ordered
        except Exception as neo_exc:
            LOGGER.warning(
                "v2: neo4j depth sort skipped for %s: %s", mission.mission_id, neo_exc
            )

    try:
        master_stream = await _pkg().generate_master_logic_stream(
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
            generated_output = await _pkg().generate_code_from_contract(
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
        _pkg().storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


# ------------------------------------------------------------------
# V2 transition table (ordered)
# ------------------------------------------------------------------

