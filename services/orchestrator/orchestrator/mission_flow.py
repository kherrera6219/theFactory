from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

PM_AGENT_ID = "AGENT-01-PM"
CEO_AGENT_ID = "AGENT-02-CEO"
DEFAULT_POD_MANAGER_AGENT_ID = "AGENT-12-PODA-MGR"
DEFAULT_SPECIALIST_AGENT_ID = "AGENT-14-PYTHON"
ROUTING_VERSION = "v1.1"

_POD_A_LANGUAGES = {"python", "javascript", "typescript", "ruby", "php"}
_POD_B_LANGUAGES = {"go", "rust", "c", "cpp", "zig"}
_POD_C_LANGUAGES = {"java", "csharp", "kotlin", "scala"}
_POD_D_LANGUAGES = {"matlab", "r", "julia", "mathematica", "haskell", "ocaml"}

POD_MANAGER_BY_LANGUAGE: dict[str, str] = {
    **{language: "AGENT-12-PODA-MGR" for language in _POD_A_LANGUAGES},
    **{language: "AGENT-18-PODB-MGR" for language in _POD_B_LANGUAGES},
    **{language: "AGENT-24-PODC-MGR" for language in _POD_C_LANGUAGES},
    **{language: "AGENT-30-PODD-MGR" for language in _POD_D_LANGUAGES},
}

SPECIALIST_BY_LANGUAGE: dict[str, str] = {
    "python": "AGENT-14-PYTHON",
    "javascript": "AGENT-15-JAVASCRIPT",
    "typescript": "AGENT-15-JAVASCRIPT",
    "ruby": "AGENT-16-RUBY",
    "php": "AGENT-17-PHP",
    "c": "AGENT-20-C",
    "cpp": "AGENT-21-CPP",
    "rust": "AGENT-22-RUST",
    "zig": "AGENT-23-ZIG",
    "java": "AGENT-26-JAVA",
    "csharp": "AGENT-27-CSHARP",
    "scala": "AGENT-28-SCALA",
    "kotlin": "AGENT-29-KOTLIN",
    "matlab": "AGENT-32-MATLAB",
    "r": "AGENT-33-R",
    "julia": "AGENT-34-JULIA",
    "mathematica": "AGENT-35-MATHEMATICA",
}


def normalize_agent_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


def normalize_language(value: str | None) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def resolve_pod_manager_agent_id(language: str | None) -> str:
    return POD_MANAGER_BY_LANGUAGE.get(normalize_language(language), DEFAULT_POD_MANAGER_AGENT_ID)


def resolve_specialist_agent_id(language: str | None) -> str:
    return SPECIALIST_BY_LANGUAGE.get(normalize_language(language), DEFAULT_SPECIALIST_AGENT_ID)


def completion_policy_exempt(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    for key in ("completion_policy_exempt", "allow_empty_artifacts"):
        value = metadata.get(key)
        if isinstance(value, bool) and value:
            return True
    return False


def with_chain_defaults(metadata: Any, requested_target_language: str | None) -> dict[str, Any]:
    normalized: dict[str, Any] = dict(metadata) if isinstance(metadata, dict) else {}
    normalized["routing_version"] = ROUTING_VERSION
    normalized["routing_enforced"] = True
    normalized["intake_agent_id"] = PM_AGENT_ID
    normalized["executive_agent_id"] = CEO_AGENT_ID
    normalized["expected_pod_manager_agent_id"] = resolve_pod_manager_agent_id(
        requested_target_language
    )
    normalized["expected_specialist_agent_id"] = resolve_specialist_agent_id(
        requested_target_language
    )

    selected = normalize_agent_id(
        normalized.get("selected_agent_id")
        or normalized.get("target_agent_id")
        or normalized.get("assigned_agent_id")
        or normalized.get("agent_id")
    )
    if selected:
        normalized["selected_agent_id"] = selected
        normalized["agent_id"] = selected
    else:
        normalized["selected_agent_id"] = PM_AGENT_ID
        normalized["agent_id"] = PM_AGENT_ID

    chain_trace = normalized.get("chain_trace")
    if isinstance(chain_trace, list):
        normalized["chain_trace"] = [record for record in chain_trace if isinstance(record, dict)]
    else:
        normalized["chain_trace"] = []
    return normalized


def append_chain_event(
    metadata: dict[str, Any],
    *,
    event_type: str,
    agent_id: str,
    details: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    trace = metadata.get("chain_trace")
    if not isinstance(trace, list):
        trace = []
    record = {
        "event_type": event_type,
        "agent_id": agent_id,
        "ts": timestamp or datetime.now(UTC).isoformat(),
    }
    if details:
        record["details"] = details
    trace.append(record)
    metadata["chain_trace"] = trace
    metadata["last_chain_event_type"] = event_type
    metadata["last_chain_event_at"] = record["ts"]
    return metadata
