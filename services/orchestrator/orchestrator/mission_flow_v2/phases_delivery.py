from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any

from ..equivalence_verifier import (
    attach_behavioural_report,
    build_equivalence_report,
    mission_requires_equivalence,
)
from ..llm_delegation import (
    generate_compliance_assessment,
    generate_integration_tests,
    generate_security_analysis,
    generate_vc_commit_strategy,
)
from ..mission_flow import PM_AGENT_ID, append_chain_event, with_chain_defaults
from ..protocol_bus_emissions import OMEGA_MESSAGE_TYPE_KEY, PBLA_DELIVERY_HANDOFF
from ..security_compliance import (
    build_security_compliance_report,
    mission_requires_security_compliance,
)
from .base import (
    _chain_event_exists,
    _mission_context,
    _record_artifact,
    _setting_bool,
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


async def _send_omega_handoff(
    *,
    settings: Any,
    mission_id: str,
    pm_agent_id: str,
    delivery_summary: dict[str, Any],
    feature_contract: dict[str, Any] | None,
) -> None:
    """Broadcast the PM delivery handoff as a Protocol Omega message (PBLA-02).

    Non-blocking: failures are swallowed by the producer and by this wrapper so
    mission progression is never affected by a bus outage. Omega's bus schema is
    intentionally user-intent shaped (per the EDCP-02 deferral in
    ``protocol_bus_producer.py``) — do not extend ``OmegaPayload``; the handoff
    discriminator rides inside ``feature_contract``. The ``message_type``
    (``protocol_bus_emissions``) lets EDCP-02's charter handler filter this
    handoff out of the shared Omega broadcast channel.
    """
    from ..protocol_bus_producer import send_omega_message  # noqa: PLC0415

    try:
        await asyncio.to_thread(
            send_omega_message,
            settings=settings,
            sender=pm_agent_id,
            recipient="broadcast",
            user_intent=str(
                delivery_summary.get("delivery_title")
                or delivery_summary.get("summary")
                or "mission handoff"
            ),
            feature_contract={
                OMEGA_MESSAGE_TYPE_KEY: PBLA_DELIVERY_HANDOFF,
                **(feature_contract or {}),
            },
            correlation_id=f"omega-{mission_id}",
        )
    except Exception:
        LOGGER.warning(
            "Omega handoff dispatch failed for mission %s (non-blocking)",
            mission_id,
        )


async def _prepare_delivery_summary(
    *,
    app: Any,
    settings: Any,
    mission: Any,
) -> Any:
    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    mission_context = _mission_context(mission, metadata)
    _raw_gen = metadata.get("generated_output")
    generated_output: dict[str, Any] = _raw_gen if isinstance(_raw_gen, dict) else {}
    _raw_contract = metadata.get("mission_contract")
    mission_contract: dict[str, Any] = _raw_contract if isinstance(_raw_contract, dict) else {}

    build_artifacts = await asyncio.to_thread(
        _pkg().storage.list_build_artifacts,
        settings,
        mission.mission_id,
        50,
    )
    delivery_summary = await _pkg().generate_pm_delivery_summary(
        mission_context=mission_context,
        generated_output=generated_output,
        build_artifacts=build_artifacts,
        feature_contract=metadata.get("feature_contract") or {},
        mission_contract=mission_contract,
    )
    metadata["delivery_summary"] = delivery_summary

    # PBLA-02: broadcast the PM delivery handoff on the Omega lane (fire-and-forget).
    await _send_omega_handoff(
        settings=settings,
        mission_id=mission.mission_id,
        pm_agent_id=PM_AGENT_ID,
        delivery_summary=delivery_summary if isinstance(delivery_summary, dict) else {},
        feature_contract=metadata.get("feature_contract") or {},
    )

    # S2-02: Security threat analysis — run once at delivery.
    if not isinstance(metadata.get("security_analysis"), dict):
        security_analysis = await generate_security_analysis(
            mission_id=mission.mission_id,
            mission_context=mission_context,
            generated_output=generated_output,
            mission_contract=mission_contract,
        )
        metadata["security_analysis"] = security_analysis
        append_chain_event(
            metadata,
            event_type="MISSION_SECURITY_ANALYSIS_COMPLETE",
            agent_id="AGENT-05-SECURITY",
            details={
                "risk_level": security_analysis.get("risk_level"),
                "deployment_safe": security_analysis.get("deployment_safe"),
                "threat_count": len(security_analysis.get("threats") or []),
                "passed": security_analysis.get("passed"),
                "source": security_analysis.get("source"),
            },
        )

    # S2-03: VC commit strategy — generate once at delivery.
    if not isinstance(metadata.get("vc_commit_strategy"), dict):
        vc_commit_strategy = await generate_vc_commit_strategy(
            mission_id=mission.mission_id,
            mission_context=mission_context,
            generated_output=generated_output,
            delivery_summary=delivery_summary,
        )
        metadata["vc_commit_strategy"] = vc_commit_strategy
        append_chain_event(
            metadata,
            event_type="MISSION_VC_COMMIT_STRATEGY_READY",
            agent_id="AGENT-07-VC",
            details={
                "conventional_type": vc_commit_strategy.get("conventional_type"),
                "branch_name": vc_commit_strategy.get("branch_name"),
                "source": vc_commit_strategy.get("source"),
            },
        )

    # S2-04: Integration tests — generate once at delivery.
    if not isinstance(metadata.get("integration_tests"), dict):
        integration_tests = await generate_integration_tests(
            mission_id=mission.mission_id,
            mission_context=mission_context,
            generated_output=generated_output,
            mission_contract=mission_contract,
        )
        metadata["integration_tests"] = integration_tests
        append_chain_event(
            metadata,
            event_type="MISSION_INTEGRATION_TESTS_GENERATED",
            agent_id="AGENT-10-TESTER",
            details={
                "test_filename": integration_tests.get("test_filename"),
                "test_case_count": len(integration_tests.get("test_cases") or []),
                "framework": integration_tests.get("framework"),
                "source": integration_tests.get("source"),
            },
        )

    # Compliance assessment — run once at delivery, unconditionally, mirroring
    # Security/VC/Tester above. Previously AGENT-08-COMPLIANCE only activated
    # on a literal "COMPLIANCE" substring in the CEO's delegation rationale
    # (_extract_support_agent_flags in base.py), which essentially never fired
    # for ordinary prompts (findings §6.3, 2026-06-30 battery).
    if not isinstance(metadata.get("compliance_assessment"), dict):
        compliance_assessment = await generate_compliance_assessment(
            mission_id=mission.mission_id,
            mission_context=mission_context,
            generated_output=generated_output,
            mission_contract=mission_contract,
        )
        metadata["compliance_assessment"] = compliance_assessment
        append_chain_event(
            metadata,
            event_type="MISSION_COMPLIANCE_ASSESSMENT_COMPLETE",
            agent_id="AGENT-08-COMPLIANCE",
            details={
                "compliance_status": compliance_assessment.get("compliance_status"),
                "passed": compliance_assessment.get("passed"),
                "note_count": len(compliance_assessment.get("regulatory_notes") or []),
                "source": compliance_assessment.get("source"),
            },
        )

    # S2-08: Write pm_clarification into chain trace if present and not already written.
    pm_clarification = metadata.get("pm_clarification")
    if pm_clarification and not _chain_event_exists(metadata, "MISSION_CLARIFICATION_APPLIED"):
        append_chain_event(
            metadata,
            event_type="MISSION_CLARIFICATION_APPLIED",
            agent_id=PM_AGENT_ID,
            details={"clarification_length": len(str(pm_clarification))},
        )

    # S2-08: Write llm_usage_summary from cost ledger into metadata at delivery.
    try:
        from ..llm_cost_ledger import get_mission_token_usage as _get_token_usage  # noqa: PLC0415
        llm_usage_summary = await _get_token_usage(
            settings=settings, mission_id=mission.mission_id
        )
        metadata["llm_usage_summary"] = llm_usage_summary
    except Exception as exc:
        LOGGER.debug("failed to fetch llm_usage_summary for %s: %s", mission.mission_id, exc)

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
    await _pkg().record_audit_event(
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
        _pkg().storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission


async def _run_behavioural_equivalence(
    mission: Any, metadata: dict[str, Any], settings: Any
) -> dict[str, Any] | None:
    """Execute the mission's equivalence vectors, or return ``None``.

    Returns ``None`` rather than raising when anything required is missing, so a
    mission is never failed by the *verification* step itself. Every reason for
    not running is recorded in the returned report's ``reason`` field where a
    report can be produced at all.
    """
    try:
        from ..equivalence_execution import run_behavioural_equivalence

        generated_output = metadata.get("generated_output")
        if not isinstance(generated_output, dict):
            return None
        code = str(generated_output.get("generated_code") or "")
        if not code.strip():
            return None
        language = str(
            generated_output.get("language") or mission.requested_target_language or ""
        )
        filename = str(generated_output.get("filename") or "artifact.py")

        rir_module = metadata.get("refined_ir_module")
        if not isinstance(rir_module, dict):
            # The RIR module is written to disk per mission; when the mission
            # metadata does not carry it there are no vectors to execute.
            return {
                "schema_version": "1.0.0",
                "verification_scope": "behavioural",
                "mission_id": mission.mission_id,
                "status": "skipped",
                "reason": "no Refined-IR module in mission metadata",
                "equivalence_vectors_passed": 0,
                "equivalence_vectors_total": 0,
                "findings": [],
            }

        return await run_behavioural_equivalence(
            mission_id=mission.mission_id,
            language=language,
            artifact_filename=filename,
            artifact_code=code,
            rir_module=rir_module,
            docker_bin=str(getattr(settings, "docker_bin", "docker") or "docker"),
        )
    except Exception as exc:  # noqa: BLE001 - verification must not fail a mission
        LOGGER.warning(
            "behavioural equivalence unavailable for %s: %s",
            getattr(mission, "mission_id", "?"),
            type(exc).__name__,
        )
        return None


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
        _pkg().storage.list_build_artifacts,
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

    # UPG-51: behavioural equivalence, gated on the flag UPG-21 identified as
    # dead. Default false ⇒ the report below is byte-identical to before this
    # code existed. Failures here never raise: a verification step that can
    # crash a mission is worse than one that reports it could not run.
    if _setting_bool(settings, "mission_equivalence_python_execution_enabled", False):
        behavioural = await _run_behavioural_equivalence(mission, metadata, settings)
        if behavioural:
            report = attach_behavioural_report(report, behavioural)

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
    await _pkg().record_audit_event(
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
        _pkg().storage.update_mission_metadata,
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

    cached_report = metadata.get("security_compliance_report")
    if isinstance(cached_report, dict) and not cached_report.get("skipped"):
        # This completion-gate preparer re-runs its entire body on every
        # retry (e.g. an orchestrator restart recovering a mission still
        # blocked by a later gate). Without this guard, the report would be
        # unconditionally rebuilt and re-signed every retry -- overwriting
        # the prior signature_record and, since the record_audit_event call
        # below is not itself deduplicated the way the chain-event append
        # is, emitting a duplicate audit event each time.
        return mission, not bool(cached_report.get("blocking")), cached_report

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
    try:
        from shared_runtime.crypto_keystore import load_or_create_signing_key
        from shared_runtime.crypto_signing import _keystore_path, sign_payload
        report_to_sign = {k: v for k, v in report.items() if k != "signature_record"}
        key = load_or_create_signing_key(_keystore_path())
        signature_record = sign_payload(key, report_to_sign)
        report["signature_record"] = signature_record
    except Exception as exc:
        LOGGER.warning("failed to sign security compliance report: %s", exc)
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
    await _pkg().record_audit_event(
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
        _pkg().storage.update_mission_metadata,
        settings,
        mission.mission_id,
        metadata,
    )
    return updated or mission, not bool(report.get("blocking")), report

