"""Mission-local security and compliance verdict generation."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

SECURITY_COMPLIANCE_SCHEMA_VERSION = "security_compliance_report.v1"

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
)
_DANGEROUS_PATTERNS = (
    ("python_eval", re.compile(r"\beval\s*\(")),
    ("python_exec", re.compile(r"\bexec\s*\(")),
    ("shell_subprocess", re.compile(r"\bsubprocess\.(Popen|run|call)\s*\(")),
    ("node_child_process", re.compile(r"child_process")),
    ("unsafe_inner_html", re.compile(r"dangerouslySetInnerHTML|innerHTML\s*=")),
)


def mission_requires_security_compliance(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    if isinstance(metadata.get("generated_output"), dict):
        return True
    if isinstance(metadata.get("application_intelligence_map"), dict):
        return True
    source_code = metadata.get("source_code")
    return isinstance(source_code, str) and bool(source_code.strip())


def build_security_compliance_report(
    *,
    mission_id: str,
    metadata: dict[str, Any],
    enforcement_enabled: bool,
) -> dict[str, Any]:
    generated_output = _dict_value(metadata.get("generated_output"))
    code = str(generated_output.get("generated_code") or "")
    aim = _dict_value(metadata.get("application_intelligence_map"))
    equivalence_report = _dict_value(metadata.get("equivalence_report"))
    mission_charter = _dict_value(metadata.get("mission_charter"))
    regulated_context = _requires_blocking_context(metadata, mission_charter)

    security_checks = [
        _check_secret_patterns(code),
        _check_dangerous_patterns(code),
        _check_aim_risk_flags(aim),
    ]
    compliance_checks = [
        _check_equivalence_presence(metadata, equivalence_report),
        _check_data_classification(metadata, mission_charter),
        _check_provenance(generated_output, aim),
    ]
    all_checks = security_checks + compliance_checks
    failed_required = [
        check for check in all_checks if check["required"] and check["status"] == "fail"
    ]
    warning_checks = [
        check for check in all_checks if check["status"] in {"warn", "manual_review"}
    ]
    should_block = bool(failed_required) and (enforcement_enabled or regulated_context)
    passed = not failed_required
    status = "passed"
    if should_block:
        status = "blocked"
    elif failed_required or warning_checks:
        status = "warned"

    findings = [
        check["message"]
        for check in all_checks
        if check["status"] in {"fail", "warn", "manual_review"}
    ]
    return {
        "schema_version": SECURITY_COMPLIANCE_SCHEMA_VERSION,
        "report_id": f"security-compliance-{mission_id}",
        "mission_id": mission_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "passed": passed,
        "blocking": should_block,
        "enforcement_enabled": enforcement_enabled,
        "regulated_context": regulated_context,
        "risk_level": _risk_level(
            blocked=should_block,
            failed=bool(failed_required),
            warned=bool(warning_checks),
        ),
        "security": {
            "passed": not any(check["status"] == "fail" for check in security_checks),
            "checks": security_checks,
        },
        "compliance": {
            "passed": not any(check["status"] == "fail" for check in compliance_checks),
            "checks": compliance_checks,
        },
        "findings": findings,
        "recommendations": _recommendations(all_checks),
        "evidence_refs": _evidence_refs(metadata),
        "source": "deterministic",
    }


def _check_secret_patterns(code: str) -> dict[str, Any]:
    matched = []
    for pattern in _SECRET_PATTERNS:
        if pattern.search(code):
            matched.append(pattern.pattern[:80])
    if matched:
        return _check(
            check_id="secret_pattern_scan",
            title="Secret pattern scan",
            status="fail",
            required=True,
            message="Generated output contains secret-like text.",
            evidence={"matched_patterns": matched},
            recommendation="Remove hard-coded secrets and reference runtime configuration.",
        )
    return _check(
        check_id="secret_pattern_scan",
        title="Secret pattern scan",
        status="pass",
        required=True,
        message="No obvious secret-like text was detected.",
    )


def _check_dangerous_patterns(code: str) -> dict[str, Any]:
    matched = [name for name, pattern in _DANGEROUS_PATTERNS if pattern.search(code)]
    if matched:
        return _check(
            check_id="dangerous_api_scan",
            title="Dangerous API scan",
            status="warn",
            required=False,
            message="Generated output uses APIs that need security review.",
            evidence={"matched_patterns": matched},
            recommendation="Review dynamic execution, shell, or unsafe DOM usage before release.",
        )
    return _check(
        check_id="dangerous_api_scan",
        title="Dangerous API scan",
        status="pass",
        required=False,
        message="No dangerous API hints were detected.",
    )


def _check_aim_risk_flags(aim: dict[str, Any]) -> dict[str, Any]:
    flags = [str(item).strip().lower() for item in aim.get("risk_flags", []) if str(item).strip()]
    high_flags = sorted({item for item in flags if item in {"security", "data", "approval"}})
    if high_flags:
        return _check(
            check_id="aim_risk_flags",
            title="AIM risk flags",
            status="warn",
            required=False,
            message="AIM includes risk flags that need review.",
            evidence={"risk_flags": high_flags, "aim_id": aim.get("aim_id")},
            recommendation="Review AIM risk flags before approving the mission output.",
        )
    return _check(
        check_id="aim_risk_flags",
        title="AIM risk flags",
        status="pass",
        required=False,
        message="No high-risk AIM flags were detected.",
    )


def _check_equivalence_presence(
    metadata: dict[str, Any],
    equivalence_report: dict[str, Any],
) -> dict[str, Any]:
    generated_output = metadata.get("generated_output")
    if not isinstance(generated_output, dict):
        return _check(
            check_id="equivalence_evidence_present",
            title="Equivalence evidence present",
            status="pass",
            required=False,
            message="No generated output requires equivalence evidence.",
        )
    if equivalence_report.get("passed") is True:
        return _check(
            check_id="equivalence_evidence_present",
            title="Equivalence evidence present",
            status="pass",
            required=True,
            message="Passing equivalence evidence is present.",
            evidence={"report_id": equivalence_report.get("report_id")},
        )
    # Equivalence owns its own enforcement switch. When it ran in advisory mode
    # (``enforcement_enabled`` false, hence ``blocking`` false) its failures are
    # review signals, not delivery gates — re-raising them as a *required*
    # compliance failure here would silently re-arm the switch the operator
    # turned off. Only a report that is missing entirely, or one that declared
    # itself blocking, hard-fails this check.
    ran = bool(equivalence_report)
    advisory_only = ran and equivalence_report.get("blocking") is not True
    if advisory_only:
        return _check(
            check_id="equivalence_evidence_present",
            title="Equivalence evidence present",
            status="manual_review",
            required=False,
            message=(
                "Equivalence verification reported findings in advisory mode; "
                "review them before delivery."
            ),
            evidence={
                "report_id": equivalence_report.get("report_id"),
                "equivalence_status": equivalence_report.get("status"),
                "equivalence_enforcement_enabled": equivalence_report.get(
                    "enforcement_enabled"
                ),
            },
            recommendation="Review the equivalence findings before approving delivery.",
        )
    return _check(
        check_id="equivalence_evidence_present",
        title="Equivalence evidence present",
        status="fail",
        required=True,
        message=(
            "Generated output does not have passing equivalence evidence."
            if ran
            else "Generated output has no equivalence evidence at all."
        ),
        evidence={"report_id": equivalence_report.get("report_id")},
        recommendation="Run or repair equivalence verification before delivery.",
    )


def _check_data_classification(
    metadata: dict[str, Any],
    mission_charter: dict[str, Any],
) -> dict[str, Any]:
    classification = str(
        metadata.get("data_classification") or mission_charter.get("data_classification") or ""
    ).strip().upper()
    if classification in {"TIER_3_REGULATED", "REGULATED"}:
        return _check(
            check_id="data_classification_review",
            title="Data classification review",
            status="manual_review",
            required=False,
            message="Regulated data classification requires manual compliance review.",
            evidence={"data_classification": classification},
            recommendation="Confirm regulated-data handling before release.",
        )
    return _check(
        check_id="data_classification_review",
        title="Data classification review",
        status="pass",
        required=False,
        message="No regulated data classification was detected.",
        evidence={"data_classification": classification or "unknown"},
    )


def _check_provenance(
    generated_output: dict[str, Any],
    aim: dict[str, Any],
) -> dict[str, Any]:
    refs = []
    if generated_output:
        refs.append("generated_output")
    if aim:
        refs.append("application_intelligence_map")
    if refs:
        return _check(
            check_id="provenance_available",
            title="Provenance available",
            status="pass",
            required=False,
            message="Mission output has provenance evidence.",
            evidence={"refs": refs},
        )
    return _check(
        check_id="provenance_available",
        title="Provenance available",
        status="manual_review",
        required=False,
        message="Mission output has limited provenance evidence.",
        recommendation="Attach source/AIM/build evidence for stronger compliance review.",
    )


def _check(
    *,
    check_id: str,
    title: str,
    status: str,
    required: bool,
    message: str,
    evidence: dict[str, Any] | None = None,
    recommendation: str | None = None,
) -> dict[str, Any]:
    result = {
        "check_id": check_id,
        "title": title,
        "status": status,
        "required": required,
        "message": message,
        "evidence": evidence or {},
    }
    if recommendation:
        result["recommendation"] = recommendation
    return result


def _requires_blocking_context(
    metadata: dict[str, Any],
    mission_charter: dict[str, Any],
) -> bool:
    if str(metadata.get("depth_mode") or "").strip().upper() == "REGULATED":
        return True
    if str(mission_charter.get("depth_mode_label") or "").strip().upper() == "REGULATED":
        return True
    classification = str(
        metadata.get("data_classification") or mission_charter.get("data_classification") or ""
    ).strip().upper()
    return classification in {"TIER_3_REGULATED", "REGULATED"}


def _risk_level(*, blocked: bool, failed: bool, warned: bool) -> str:
    if blocked:
        return "high"
    if failed:
        return "high"
    if warned:
        return "medium"
    return "low"


def _recommendations(checks: list[dict[str, Any]]) -> list[str]:
    recommendations = [
        str(check.get("recommendation")).strip()
        for check in checks
        if str(check.get("recommendation") or "").strip()
    ]
    return sorted(set(recommendations))


def _evidence_refs(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    for key in (
        "feature_contract",
        "mission_contract",
        "application_intelligence_map",
        "equivalence_report",
        "generated_output",
    ):
        if isinstance(metadata.get(key), dict):
            refs.append({"type": "metadata", "ref": key})
    return refs


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
