from __future__ import annotations

import asyncio
import importlib
import logging
from datetime import UTC, datetime
from typing import Any

from .. import build_artifacts as build_artifact_support
from .. import knowledge_lake
from ..agent_scaling import (
    compute_scaling_decision,
    embed_scaling_decision,
    is_scalable_agent,
)
from ..llm_delegation import (
    generate_pod_audit_verdict,
)
from ..mission_flow import (
    CEO_AGENT_ID,
    POD_MANAGER_BY_LANGUAGE,
    append_chain_event,
    normalize_language,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
    with_chain_defaults,
)
from ..models import MissionState
from ..port_coordinator import run_port_extraction_phase
from ..protocol_bus_emissions import EMISSION_KEY, PBLA_POD_AUDIT_TELEMETRY
from ..storage_core import PodAssignmentConflictError
from .base import (
    _chain_event_exists,
    _mission_context,
    _pod_key_for_manager,
    _record_artifact,
    _scaling_workload_items,
    _setting_bool,
    _setting_int,
    _validate_agent_id,
)
from .phases_intake import _persist_metadata

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


def _language_pod_manager_agent_id(requested_target_language: Any) -> str | None:
    """Return the registry pod manager for a *known* language, else ``None``.

    ``resolve_pod_manager_agent_id`` falls back to Pod A for anything it does not
    recognise, which makes it useless as a routing *check*: an unset or unknown
    language would look like a legitimate Pod A mission and would "correct"
    every CEO choice back to Pod A.  Returning ``None`` instead lets callers
    leave the CEO's judgement alone when the registry has no opinion.
    """
    return POD_MANAGER_BY_LANGUAGE.get(normalize_language(requested_target_language))


async def _persist_pod_assignment_record(
    *,
    app: Any,
    settings: Any,
    mission: Any,
    mission_id: str,
    pod_manager_agent_id: str,
    specialist_agent_id: str,
) -> dict[str, Any] | None:
    """Record the pod this mission was routed to, alongside the chain event.

    ``MISSION_POD_MANAGER_ASSIGNED`` asserts that a pod manager was assigned, so
    the assignment must be queryable.  Historically the only writer of
    ``mission_pod_assignments`` was the pod worker, which writes when it *claims*
    execution -- a different fact, and one that never happens for missions no
    worker picks up (a BUILD_NEW mission with no source to extract, or one whose
    language and routed agent send it past every worker's filters).  Those
    missions reached VERIFIED with the event emitted and a 404 on the record.

    The row is written as *provisional*: a worker claim supersedes it, and it can
    never overwrite a claim.  Failure is logged, never fatal -- this is a
    reporting record and mission progression must not hinge on it.
    """
    pod_name = _pod_key_for_manager(pod_manager_agent_id)
    details = {
        "assigned_by": "orchestrator",
        "pod_name": pod_name,
        "agent_id": pod_manager_agent_id,
        "specialist_agent_id": specialist_agent_id,
        "requested_target_language": mission.requested_target_language or "",
        "reason": "delegation-routing",
    }
    try:
        record = await asyncio.to_thread(
            _pkg().storage.upsert_pod_assignment,
            settings,
            mission_id,
            pod_name,
            details,
            datetime.now(UTC).isoformat(),
            provisional=True,
        )
    except PodAssignmentConflictError as exc:
        # A pod worker already claimed this mission -- its record is the
        # authoritative one and must not be downgraded to provisional.
        LOGGER.info(
            "v2: mission %s already claimed by pod %s; keeping the worker assignment",
            mission_id,
            (exc.existing_assignment or {}).get("pod_name"),
        )
        return None
    except Exception as exc:
        LOGGER.warning(
            "v2: failed to record pod assignment for mission %s: %s",
            mission_id,
            type(exc).__name__,
        )
        return None

    await _pkg().record_audit_event(
        app,
        mission_id=mission_id,
        mission=mission,
        agent_id=pod_manager_agent_id,
        service_name="orchestrator",
        event_type="MISSION_POD_ASSIGNMENT_WRITTEN",
        object_type="pod_assignment",
        object_id=pod_name,
        payload_summary=dict(details),
        content_hash_source=details,
    )
    return record


async def _prepare_pod_assignment(
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
    ceo_delegation = (
        metadata.get("ceo_delegation") if isinstance(metadata.get("ceo_delegation"), dict) else {}
    )
    pod_manager_agent_id = _validate_agent_id(
        ceo_delegation.get("pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )

    # The CEO's delegation prompt is constrained to "one of the four pod
    # managers" but not to the one that owns the mission's language, so it can
    # route a Python mission to the Pod C manager.  Nothing downstream reconciles
    # that: pod workers filter on language *and* (in the dedicated topology) on
    # bound agent id, so a cross-pod choice makes the mission invisible to every
    # worker -- Pod A rejects the agent, Pod C rejects the language, and neither
    # logs an error.  Prefer the registry when it has an opinion, and record the
    # correction rather than silently discarding the CEO's answer.
    language_pod_manager_agent_id = _language_pod_manager_agent_id(
        mission.requested_target_language
    )
    routing_correction: dict[str, Any] | None = None
    if (
        language_pod_manager_agent_id is not None
        and pod_manager_agent_id != language_pod_manager_agent_id
    ):
        routing_correction = {
            "delegated_pod_manager_agent_id": pod_manager_agent_id,
            "corrected_pod_manager_agent_id": language_pod_manager_agent_id,
            "requested_target_language": mission.requested_target_language or "",
            "reason": "delegated-pod-manager-does-not-own-target-language",
            "corrected_at": datetime.now(UTC).isoformat(),
        }
        LOGGER.warning(
            "v2: mission %s delegated to %s but %s owns language %r; using %s",
            mission_id,
            pod_manager_agent_id,
            language_pod_manager_agent_id,
            mission.requested_target_language,
            language_pod_manager_agent_id,
        )
        pod_manager_agent_id = language_pod_manager_agent_id
        metadata["pod_manager_routing_correction"] = routing_correction

    default_specialist_agent_id = _validate_agent_id(
        ceo_delegation.get("specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )

    pod_manager_delegation = await _pkg().generate_pod_manager_delegation(
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

    assignment_record = await _persist_pod_assignment_record(
        app=app,
        settings=settings,
        mission=mission,
        mission_id=mission_id,
        pod_manager_agent_id=pod_manager_agent_id,
        specialist_agent_id=specialist_agent_id,
    )

    assignment_details = {
        "specialist_agent_id": specialist_agent_id,
        "source": normalized.get("source"),
        "llm_route": normalized.get("llm_route"),
        "model_provider": normalized.get("model_provider"),
        "model": normalized.get("model"),
        "pod_name": _pod_key_for_manager(pod_manager_agent_id),
        "pod_assignment_recorded": assignment_record is not None,
        **({"routing_correction": routing_correction} if routing_correction else {}),
    }

    if not _chain_event_exists(metadata, "MISSION_POD_MANAGER_ASSIGNED"):
        append_chain_event(
            metadata,
            event_type="MISSION_POD_MANAGER_ASSIGNED",
            agent_id=pod_manager_agent_id,
            details=dict(assignment_details),
        )
    _record_artifact(
        metadata,
        stage="pod_assigned",
        event_type="MISSION_POD_MANAGER_ASSIGNED",
        agent_id=pod_manager_agent_id,
        details=dict(assignment_details),
    )
    await _pkg().record_audit_event(
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

    # Emit a Protocol Alpha (directive) message for the CEO → Pod Manager
    # delegation. Fire-and-forget — a bus outage must never block mission flow.
    await _send_alpha_delegation_directive(
        settings=settings,
        mission_id=mission_id,
        pod_manager_agent_id=pod_manager_agent_id,
        specialist_agent_id=specialist_agent_id,
        requested_target_language=mission.requested_target_language,
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


async def _send_alpha_delegation_directive(
    *,
    settings: Any,
    mission_id: str,
    pod_manager_agent_id: str,
    specialist_agent_id: str,
    requested_target_language: str | None,
) -> None:
    """Broadcast the CEO → Pod Manager assignment as a Protocol Alpha directive.

    Non-blocking: the bus call runs in a thread and any failure is swallowed by
    the producer (it logs and returns False) so mission progression is unaffected.
    """
    from ..protocol_bus_producer import send_alpha_directive  # noqa: PLC0415

    try:
        await asyncio.to_thread(
            send_alpha_directive,
            settings=settings,
            sender=CEO_AGENT_ID,
            recipient=pod_manager_agent_id,
            target_pod=_pod_key_for_manager(pod_manager_agent_id),
            directive_type="pod_manager_delegation",
            directive={
                "mission_id": mission_id,
                "pod_manager_agent_id": pod_manager_agent_id,
                "specialist_agent_id": specialist_agent_id,
                "requested_target_language": requested_target_language,
            },
            correlation_id=f"alpha-{mission_id}-{pod_manager_agent_id}",
        )
    except Exception:
        # Defensive: send_alpha_directive already swallows its own errors, but
        # the thread dispatch itself must never bubble into mission flow.
        LOGGER.warning(
            "Alpha directive dispatch failed for mission %s (non-blocking)",
            mission_id,
        )


def _map_verdict_to_audit_result(verdict: Any) -> str:
    """Map the pod audit verdict vocabulary onto ``DeltaPayload.audit_result``.

    ``audit_result`` is a strict ``Literal["pass", "fail", "warning"]``. The pod
    audit verdict produced by ``generate_pod_audit_verdict`` is one of
    ``{"PASS", "FAIL", "WARN"}``; lower-casing first makes PASS->pass, FAIL->fail,
    WARN->warning. The fallthrough is a defensive default if the audit vocabulary
    is ever extended.
    """
    value = str(verdict or "").strip().lower()
    if value in ("pass", "passed", "approved", "verified"):
        return "pass"
    if value in ("fail", "failed", "rejected"):
        return "fail"
    return "warning"


async def _send_delta_audit_verdict(
    *,
    settings: Any,
    mission_id: str,
    pod_name: str,
    pod_manager_agent_id: str,
    pod_audit: dict[str, Any],
) -> None:
    """Broadcast the pod audit verdict as a Protocol Delta message (PBLA-01).

    Non-blocking: failures are swallowed by the producer and by this wrapper so
    mission progression is never affected by a bus outage. Stamps the PBLA
    telemetry discriminator (``protocol_bus_emissions``) so a future EDCP Delta
    consumer can filter this shadow traffic from load-bearing verified /
    correction replies on the shared broadcast channel.
    """
    from ..protocol_bus_producer import send_delta_audit  # noqa: PLC0415

    try:
        await asyncio.to_thread(
            send_delta_audit,
            settings=settings,
            sender=pod_audit.get("agent_id", pod_manager_agent_id),
            recipient="broadcast",
            audit_result=_map_verdict_to_audit_result(pod_audit.get("verdict")),
            verification_method=str(pod_audit.get("source", "pod_audit")),
            tolerance_score=float(pod_audit.get("quality_score") or 0.0),
            findings={
                EMISSION_KEY: PBLA_POD_AUDIT_TELEMETRY,
                "mission_id": mission_id,
                "pod": pod_name,
                "verdict": pod_audit.get("verdict"),
            },
            correlation_id=f"delta-{mission_id}-{pod_name}",
        )
    except Exception:
        LOGGER.warning(
            "Delta audit dispatch failed for mission %s pod %s (non-blocking)",
            mission_id,
            pod_name,
        )


async def _prepare_specialist_assignment(
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
    mission = await asyncio.to_thread(_pkg().storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)

    # PORT two-phase: run extraction phase on first pass
    if (
        str(metadata.get("mission_type") or "").strip().upper() == "PORT"
        and _setting_bool(settings, "port_two_phase_enabled")
        and str(metadata.get("port_phase") or "").strip().lower() == "extraction"
        # Unlike every sibling branch in this function, this one had no
        # re-entrancy guard: mission state stays at specialist_assigned for
        # the whole extraction+generation two-phase flow, so nothing in the
        # transition-based dedup protects a second invocation while
        # port_phase is still "extraction" -- it would re-run two LLM calls,
        # mint a fresh non-deterministic port_source_aim/source_logicnodes,
        # and append a duplicate MISSION_PORT_EXTRACTION_COMPLETE event.
        and not _chain_event_exists(metadata, "MISSION_PORT_EXTRACTION_COMPLETE")
    ):
        extraction_updates = await run_port_extraction_phase(
            mission_id=mission_id,
            mission=mission,
            metadata=metadata,
            settings=settings,
        )
        for key, value in extraction_updates.items():
            metadata[key] = value
        # Persist extraction results — port_phase is now "generation".
        # The lifecycle engine will re-enter _prepare_specialist_plan on the
        # next SPECIALIST_ASSIGNED transition and take the generation path.
        updated = await asyncio.to_thread(
            _pkg().storage.update_mission_metadata, settings, mission_id, metadata
        )
        return updated is not None

    pod_manager_agent_id = _validate_agent_id(
        metadata.get("assigned_pod_manager_agent_id"),
        fallback=resolve_pod_manager_agent_id(mission.requested_target_language),
    )
    specialist_agent_id = _validate_agent_id(
        metadata.get("assigned_specialist_agent_id"),
        fallback=resolve_specialist_agent_id(mission.requested_target_language),
    )

    # PORT generation phase: inject source logicnodes into context
    port_source_logicnodes = None
    if (
        str(metadata.get("mission_type") or "").strip().upper() == "PORT"
        and _setting_bool(settings, "port_two_phase_enabled")
        and str(metadata.get("port_phase") or "").strip().lower() == "generation"
    ):
        port_source_logicnodes = metadata.get("port_source_logicnodes") or []
        specialist_agent_id = _validate_agent_id(
            metadata.get("assigned_specialist_agent_id"),
            fallback=resolve_specialist_agent_id(
                metadata.get("port_target_language") or mission.requested_target_language
            ),
        )

    specialist_plan = await _pkg().generate_specialist_plan(
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
        # Build codegen context — inject PORT source logicnodes when in generation phase
        _codegen_context: dict[str, Any] = {
            **_mission_context(mission, metadata),
            "mission_contract": mission_contract,
            "specialist_plan": normalized,
        }
        if port_source_logicnodes:
            _codegen_context["port_source_logicnodes"] = port_source_logicnodes
            _codegen_context["port_source_language"] = metadata.get("port_source_language", "")
            _codegen_context["port_target_language"] = metadata.get("port_target_language", "")
        source_bundle = metadata.get("source_code")
        if isinstance(source_bundle, str) and source_bundle.strip():
            _codegen_context["imported_source_code"] = source_bundle[:80_000]

        _target_lang = (
            str(metadata.get("port_target_language") or "").strip()
            or mission.requested_target_language
            or "python"
        )
        # Knowledge Lake retrieval (Phase 2): inject documentation context the
        # IS-Agent stocked during FETCH into the specialist codegen prompt.
        knowledge_context = await asyncio.to_thread(
            knowledge_lake.get_language_context,
            settings=settings,
            language=_target_lang,
        )
        if knowledge_context:
            _codegen_context["knowledge_context"] = knowledge_context
            LOGGER.info(
                "Injected Knowledge Lake context for mission %s language=%s (%d chars)",
                mission_id,
                _target_lang,
                len(knowledge_context),
            )
        generated_output = await _pkg().generate_code_from_contract(
            mission_context=_codegen_context,
            specialist_agent_id=specialist_agent_id,
            mission_contract=mission_contract,
            logicnodes=list(port_source_logicnodes) if port_source_logicnodes else [],
            target_language=_target_lang,
        )
        metadata["generated_output"] = generated_output
        # PBLA-03: emit the specialist result on the Beta lane (fire-and-forget).
        # This is the primary Beta emission site: generated_output is set here,
        # before fusion ever runs, so by the time _prepare_fusion's own Beta call
        # (phases_runtime.py) executes, mission_has_generated_output(metadata) is
        # already True and that call is a no-op for a normal BUILD_NEW mission —
        # it remains the fallback emission for missions whose codegen only
        # succeeds on a later fusion-stage retry. The shared
        # mission_has_generated_output guard keeps the two call sites mutually
        # exclusive, so no separate idempotency marker is needed here.
        from .phases_runtime import _send_beta_production_result  # noqa: PLC0415

        await _send_beta_production_result(
            settings=settings,
            mission_id=mission_id,
            specialist_agent_id=generated_output.get(
                "specialist_agent_id", specialist_agent_id
            ),
            pod_manager_agent_id=pod_manager_agent_id,
            logicnode_id=f"ln-{mission_id}-specialist",
            confidence_score=0.0,
            source_language=str(generated_output.get("language") or _target_lang),
        )
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
        # PORT generation phase complete
        if port_source_logicnodes and not _chain_event_exists(
            metadata, "MISSION_PORT_GENERATION_COMPLETE"
        ):
            append_chain_event(
                metadata,
                event_type="MISSION_PORT_GENERATION_COMPLETE",
                agent_id=specialist_agent_id,
                details={
                    "target_language": metadata.get("port_target_language", ""),
                    "source_logicnode_count": len(port_source_logicnodes),
                    "filename": generated_output.get("filename"),
                    "source": generated_output.get("source"),
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
    await _pkg().record_audit_event(
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
        await _pkg().record_audit_event(
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

    # Compute scaling decision when feature is enabled. Guarded so this
    # function's re-entrant invocations (the PORT two-phase flow explicitly
    # re-enters _prepare_specialist_plan, and any retry while the mission
    # is still at specialist_assigned would too) don't recompute a fresh
    # decision with new random partition IDs — that would orphan any
    # partition work already emitted/completed under the original IDs and
    # silently defeat the per-partition emitted-ID dedup in
    # _emit_partition_work_items.
    existing_scaling_decision = metadata.get("scaling_decision")
    if (
        _setting_bool(settings, "agent_scaling_enabled", False)
        and is_scalable_agent(specialist_agent_id)
        and not isinstance(existing_scaling_decision, dict)
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
        await _pkg().record_audit_event(
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
        _pkg().storage.update_mission_metadata,
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
        _pkg().storage.list_logicnodes,
        settings,
        mission.mission_id,
        500,
    )
    logicnodes = raw_logicnodes if isinstance(raw_logicnodes, list) else []
    standard = await _pkg().generate_pod_group_standard(
        pod_name=pod_name,
        pod_manager_agent_id=pod_manager_agent_id,
        mission_id=mission.mission_id,
        logicnodes=[record for record in logicnodes if isinstance(record, dict)],
        mission_contract=mission_contract,
        source_code=str(metadata.get("source_code") or metadata.get("prompt") or ""),
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
    coverage_verdict = standard.get("coverage_verdict")
    if (
        isinstance(coverage_verdict, dict)
        and bool(coverage_verdict.get("coverage_thin", False))
        and not _chain_event_exists(metadata, "MISSION_POD_STANDARD_THIN_COVERAGE")
    ):
        append_chain_event(
            metadata,
            event_type="MISSION_POD_STANDARD_THIN_COVERAGE",
            agent_id=pod_manager_agent_id,
            details={
                "pod": pod_name,
                "raw_logicnode_count": coverage_verdict.get("raw_logicnode_count"),
                "canonical_logicnode_count": coverage_verdict.get(
                    "canonical_logicnode_count"
                ),
                "expected_minimum_canonical_logicnodes": coverage_verdict.get(
                    "expected_minimum_canonical_logicnodes"
                ),
                "findings": coverage_verdict.get("findings", []),
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
    await _pkg().record_audit_event(
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

    # S2-05: Pod audit verdict — QC agent reviews the pod standard.
    _raw_gen_output = metadata.get("generated_output")
    generated_output = _raw_gen_output if isinstance(_raw_gen_output, dict) else None
    pod_audit = await generate_pod_audit_verdict(
        mission_id=mission.mission_id,
        pod_name=pod_name,
        mission_context=_mission_context(mission, metadata),
        pod_group_standard=standard,
        generated_output=generated_output,
    )
    pod_audits = dict(metadata.get("pod_audit_verdicts") or {})
    pod_audits[pod_name] = pod_audit
    metadata["pod_audit_verdicts"] = pod_audits
    if not _chain_event_exists(metadata, "MISSION_POD_AUDIT_COMPLETE"):
        append_chain_event(
            metadata,
            event_type="MISSION_POD_AUDIT_COMPLETE",
            agent_id=pod_audit.get("agent_id", pod_manager_agent_id),
            details={
                "pod": pod_name,
                "verdict": pod_audit.get("verdict"),
                "quality_score": pod_audit.get("quality_score"),
                "source": pod_audit.get("source"),
            },
        )
        # PBLA-01: emit the verdict on the Delta lane (fire-and-forget telemetry).
        # Inside the idempotency guard so it fires once per pod per mission rather
        # than relying on the bus dedup window for resume/retry.
        await _send_delta_audit_verdict(
            settings=settings,
            mission_id=mission.mission_id,
            pod_name=pod_name,
            pod_manager_agent_id=pod_manager_agent_id,
            pod_audit=pod_audit,
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


def _write_artifact_to_disk(settings: Any, mission_id: str, artifact_record: dict[str, Any]) -> None:
    try:
        import os
        from pathlib import Path

        delivery_dir = Path(settings.delivery_dir)
        mission_dir = delivery_dir / mission_id
        
        # Ensure mission directory exists
        mission_dir.mkdir(parents=True, exist_ok=True)
        
        artifact_type = artifact_record.get("artifact_type")
        artifact_text = artifact_record.get("artifact_text")
        if not artifact_text:
            return

        manifest = artifact_record.get("manifest") or {}

        if artifact_type == "generated_code":
            filename = str(manifest.get("filename") or "generated.txt")
            # Clean up paths to prevent directory traversal
            filename = os.path.basename(filename)
            file_path = mission_dir / filename
            file_path.write_text(artifact_text, encoding="utf-8")
            LOGGER.info("Wrote generated code to %s", file_path)

        elif artifact_type == "source_bundle_package":
            # Parse files out of the source bundle
            import re
            pattern = re.compile(r"^## FILE (.+)$", re.MULTILINE)
            matches = list(pattern.finditer(artifact_text))
            
            if not matches:
                # Fallback to inline source if no ## FILE markers found
                filename = str(manifest.get("filename") or "inline_source.txt")
                filename = os.path.basename(filename)
                file_path = mission_dir / filename
                file_path.write_text(artifact_text, encoding="utf-8")
                LOGGER.info("Wrote inline source to %s", file_path)
            else:
                resolved_mission_dir = mission_dir.resolve()
                for index, match in enumerate(matches):
                    rel_path = str(match.group(1)).strip()
                    # Strip Windows drive-letter prefix ("C:path" → "path")
                    # before any further sanitisation.  On Linux the colon is
                    # a valid filename character, so a path like "C:evil.txt"
                    # would otherwise resolve *inside* the mission directory
                    # and pass the containment check below unchanged — meaning
                    # the file would land as "C:evil.txt" instead of
                    # "evil.txt".  Stripping the prefix here ensures
                    # drive-relative paths are normalised the same way on
                    # every platform.
                    rel_path = re.sub(r"^[A-Za-z]:", "", rel_path)
                    # Prevent directory traversal. Checking the raw fragment
                    # for ".."/os.path.isabs() is not platform-safe on its
                    # own — e.g. a Windows drive-relative path like
                    # "C:evil.txt" is neither absolute nor "..'"-prefixed, so
                    # it can pass that check. Instead resolve the actual
                    # joined path and confirm it is still inside the mission
                    # directory before writing.
                    candidate_path = (mission_dir / rel_path).resolve()
                    if (
                        candidate_path != resolved_mission_dir
                        and resolved_mission_dir not in candidate_path.parents
                    ):
                        rel_path = os.path.basename(os.path.normpath(rel_path))
                        candidate_path = (mission_dir / rel_path).resolve()

                    content_start = match.end()
                    content_end = (
                        matches[index + 1].start()
                        if index + 1 < len(matches)
                        else len(artifact_text)
                    )
                    content = artifact_text[content_start:content_end].lstrip("\r\n")

                    file_path = candidate_path
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")
                    LOGGER.info("Wrote source bundle file to %s", file_path)
    except Exception as exc:
        LOGGER.warning("failed to write build artifact to disk for mission %s: %s", mission_id, exc)


async def _ensure_verified_build_artifact(
    *,
    app: Any,
    settings: Any,
    mission: Any,
) -> Any:
    if not build_artifact_support.mission_requires_build_artifact(mission.metadata):
        return mission

    artifact_metadata = mission.metadata if isinstance(mission.metadata, dict) else {}
    source_code = str(artifact_metadata.get("source_code") or "").strip()
    if build_artifact_support.mission_has_generated_output(artifact_metadata):
        artifact_record = build_artifact_support.build_generated_output_artifact(
            mission_id=mission.mission_id,
            requested_target_language=mission.requested_target_language,
            metadata=artifact_metadata,
        )
    elif source_code:
        artifact_record = build_artifact_support.build_source_bundle_artifact(
            mission_id=mission.mission_id,
            requested_target_language=mission.requested_target_language,
            metadata=artifact_metadata,
        )
    else:
        LOGGER.error(
            "mission %s charter expects a generated_output build artifact but neither "
            "generated_output nor source_code is available; recording a failed build "
            "artifact instead of leaving the mission stuck with no signal",
            mission.mission_id,
        )
        artifact_record = build_artifact_support.build_missing_source_artifact_failure(
            mission_id=mission.mission_id,
            requested_target_language=mission.requested_target_language,
        )
    await asyncio.to_thread(
        _pkg().storage.upsert_build_artifact,
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
    # Write to local delivery directory on host
    await asyncio.to_thread(
        _write_artifact_to_disk,
        settings,
        mission.mission_id,
        artifact_record,
    )
    await _pkg().record_audit_event(
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
        _pkg().storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission

