"""PII and prompt-injection input scanning helpers for api-gateway."""

from __future__ import annotations

from typing import Any

from shared_runtime.pii_guard import detect_pii, scan_dict_for_pii
from shared_runtime.prompt_guard import check_prompt

from .schemas import MissionCreate

_PROMPT_RISK_PRIORITY = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def build_sensitive_input_scan(payload: MissionCreate) -> dict[str, Any]:
    """Return deterministic PII/secret scan metadata for user mission input.

    This intentionally records only field names, PII types, and counts. It never
    stores the matched values, which keeps the audit trail useful without
    duplicating sensitive input in metadata.
    """
    field_counts: dict[tuple[str, str], int] = {}

    def _record(field: str, text: str | None) -> None:
        if not text:
            return
        for match in detect_pii(text):
            key = (field, match.pii_type)
            field_counts[key] = field_counts.get(key, 0) + 1

    _record("prompt", payload.prompt)
    _record("source_code", payload.source_code)
    for index, directive in enumerate(payload.global_style_directives):
        _record(f"global_style_directives[{index}]", directive)
    for index, attachment in enumerate(payload.attachments):
        _record(f"attachments[{index}].filename", attachment.filename)
        _record(f"attachments[{index}].content_type", attachment.content_type)

    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    for field_path, pii_type in scan_dict_for_pii(metadata, max_depth=4):
        if field_path in {"source_code", "prompt", "chain_trace"} or field_path.startswith("vault"):
            continue
        key = (f"metadata.{field_path}", pii_type)
        field_counts[key] = field_counts.get(key, 0) + 1

    fields = [
        {"field": field, "pii_type": pii_type, "match_count": count}
        for (field, pii_type), count in sorted(field_counts.items())
    ]
    pii_types = sorted({field["pii_type"] for field in fields})
    total_matches = sum(field["match_count"] for field in fields)
    return {
        "schema_version": "sensitive_input_scan.v1",
        "scanner": "shared_runtime.pii_guard",
        "has_sensitive_input": total_matches > 0,
        "total_matches": total_matches,
        "pii_types": pii_types,
        "fields": fields,
    }


def metadata_prompt_fields(
    value: Any,
    *,
    prefix: str = "metadata",
    depth: int = 0,
    max_depth: int = 4,
) -> list[tuple[str, str]]:
    if depth > max_depth:
        return []
    fields: list[tuple[str, str]] = []
    if isinstance(value, str):
        fields.append((prefix, value))
    elif isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                continue
            if key in {"source_code", "prompt", "chain_trace", "vault"}:
                continue
            fields.extend(
                metadata_prompt_fields(
                    child,
                    prefix=f"{prefix}.{key}",
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            )
    elif isinstance(value, list):
        for index, child in enumerate(value[:20]):
            fields.extend(
                metadata_prompt_fields(
                    child,
                    prefix=f"{prefix}[{index}]",
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            )
    return fields


def build_prompt_input_scan(payload: MissionCreate) -> dict[str, Any]:
    """Return prompt-injection scan metadata without copying matched text."""
    findings: dict[tuple[str, str], dict[str, Any]] = {}

    def _record(field: str, text: str | None) -> None:
        if not text:
            return
        result = check_prompt(text)
        if not result.is_suspicious:
            return
        for match in result.matches:
            key = (field, match.attack_type)
            row = findings.setdefault(
                key,
                {
                    "field": field,
                    "attack_type": match.attack_type,
                    "risk_level": result.risk_level,
                    "count": 0,
                },
            )
            row["count"] += 1
            if _PROMPT_RISK_PRIORITY.get(result.risk_level, 0) > _PROMPT_RISK_PRIORITY.get(
                str(row["risk_level"]), 0
            ):
                row["risk_level"] = result.risk_level

    _record("prompt", payload.prompt)
    for index, directive in enumerate(payload.global_style_directives):
        _record(f"global_style_directives[{index}]", directive)
    for index, attachment in enumerate(payload.attachments):
        _record(f"attachments[{index}].filename", attachment.filename)
        _record(f"attachments[{index}].content_type", attachment.content_type)

    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    for field_path, text in metadata_prompt_fields(metadata):
        _record(field_path, text)

    finding_rows = sorted(findings.values(), key=lambda row: (row["field"], row["attack_type"]))
    max_risk = "low"
    for row in finding_rows:
        if _PROMPT_RISK_PRIORITY.get(str(row["risk_level"]), 0) > _PROMPT_RISK_PRIORITY.get(
            max_risk, 0
        ):
            max_risk = str(row["risk_level"])

    return {
        "schema_version": "prompt_input_scan.v1",
        "scanner": "shared_runtime.prompt_guard",
        "has_prompt_injection_risk": bool(finding_rows),
        "max_risk_level": max_risk,
        "attack_types": sorted({str(row["attack_type"]) for row in finding_rows}),
        "total_matches": sum(int(row["count"]) for row in finding_rows),
        "fields": finding_rows,
    }
