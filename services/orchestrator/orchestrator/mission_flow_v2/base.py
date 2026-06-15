from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..agent_registry import AGENT_REGISTRY
from ..models import MissionState

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
# Handle both local dev and containerized path structures
_MISSION_CHARTER_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4] / "schemas" / "mission_charter.v1.json"
    if len(Path(__file__).resolve().parents) > 4
    else Path(__file__).resolve().parents[2] / "schemas" / "mission_charter.v1.json"
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


def _extract_support_agent_flags(
    ceo_delegation: dict[str, Any],
    mission_type: str,
) -> list[str]:
    text = f"{ceo_delegation.get('rationale', '')} {mission_type}".upper()
    flags: list[str] = []
    keyword_map = {
        "SECURITY": "AGENT-05-SECURITY",
        "COMPLIANCE": "AGENT-08-COMPLIANCE",
        "DEPABS": "AGENT-39-DEPABS",
        "DEPENDENC": "AGENT-39-DEPABS",
        "TEST": "AGENT-10-TESTER",
        "VC": "AGENT-07-VC",
    }
    for keyword, agent_id in keyword_map.items():
        if keyword in text and agent_id not in flags:
            flags.append(agent_id)
    return flags


def _extract_cross_pod_flags(logic_clusters: dict[str, Any]) -> list[str]:
    clusters = logic_clusters.get("clusters") if isinstance(logic_clusters, dict) else []
    if not isinstance(clusters, list):
        return []
    pod_ids = {
        str(cluster.get("pod_manager_agent_id") or "").strip().upper()
        for cluster in clusters
        if isinstance(cluster, dict)
    }
    pod_ids.discard("")
    return sorted(pod_ids) if len(pod_ids) > 1 else []


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


def _build_pm_planning_package(
    *,
    feature_contract: dict[str, Any],
    requested_target_language: str | None,
    mission_type: str,
    gates: list[str],
) -> dict[str, Any]:
    requirements = list(feature_contract.get("functional_requirements") or [])[:8]
    constraints = list(feature_contract.get("non_functional_requirements") or [])[:6]
    acceptance = list(feature_contract.get("acceptance_criteria") or [])[:8]
    risk_notes = list(feature_contract.get("risk_notes") or [])[:6]
    objective = str(feature_contract.get("summary") or "Complete the requested mission.").strip()
    language = (requested_target_language or "auto").strip().lower() or "auto"
    return {
        "statement_of_work": {
            "objective": objective,
            "mission_type": mission_type.strip().upper() or "BUILD_NEW",
            "target_language": language,
            "deliverables": requirements or ["Complete the requested mission deliverable."],
            "out_of_scope": [],
        },
        "product_requirements": {
            "functional_requirements": requirements,
            "non_functional_requirements": constraints,
            "acceptance_criteria": acceptance,
        },
        "phased_build_plan": [
            {
                "phase": "intake",
                "owner_agent_id": "AGENT-01-PM",
                "objective": "Confirm scope, assumptions, acceptance criteria, and operator approval.",
            },
            {
                "phase": "delegation",
                "owner_agent_id": "AGENT-02-CEO",
                "objective": "Translate the approved PM plan into pod and support-ring work packages.",
            },
            {
                "phase": "implementation",
                "owner_agent_id": "selected_specialist",
                "objective": "Build the requested artifact against the mission contract and LogicNodes.",
            },
            {
                "phase": "verification",
                "owner_agent_id": "audit_and_support_ring",
                "objective": "Run required gates and prove each acceptance criterion.",
            },
        ],
        "risk_register": [
            {"risk": risk, "mitigation": "Carry into CEO delegation and verification gates."}
            for risk in risk_notes
        ],
        "test_strategy": {
            "acceptance_tests": acceptance or ["Mission completes without error."],
            "required_gates": gates,
        },
    }


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
    planning_package = _build_pm_planning_package(
        feature_contract=feature_contract,
        requested_target_language=requested_target_language,
        mission_type=normalized_mission_type,
        gates=gates,
    )
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
        "risk_level": str((feature_contract.get("risk_assessment") or {}).get("complexity") or "medium").lower(),
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
            "assumptions": list(feature_contract.get("assumptions") or [])[:5],
        },
        "planning_package": planning_package,
        "statement_of_work": planning_package["statement_of_work"],
        "product_requirements": planning_package["product_requirements"],
        "phased_build_plan": planning_package["phased_build_plan"],
        "risk_register": planning_package["risk_register"],
        "test_strategy": planning_package["test_strategy"],
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


def _extension_for_language(language: str) -> str:
    return {
        "python": "py",
        "javascript": "js",
        "typescript": "ts",
        "java": "java",
        "csharp": "cs",
        "rust": "rs",
        "go": "go",
    }.get(str(language or "").lower(), "txt")

