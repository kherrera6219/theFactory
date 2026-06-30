"""Deterministic equivalence verification for generated mission outputs."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

EQUIVALENCE_REPORT_SCHEMA_VERSION = "equivalence_report.v1"
GENERATED_OUTPUT_ARTIFACT_TYPE = "generated_code"

# Contract "<keyword> file" phrases that imply a required deliverable container,
# mapped to the file extensions that satisfy them. Keyed on the lowercased word
# that appears immediately before "file" in the contract text.
_ARTIFACT_FORMAT_EXTENSIONS: dict[str, set[str]] = {
    "html": {"html", "htm"},
    "html5": {"html", "htm"},
    "htm": {"html", "htm"},
    "markdown": {"md", "markdown"},
    "json": {"json"},
    "yaml": {"yaml", "yml"},
    "css": {"css"},
    "pdf": {"pdf"},
    "csv": {"csv"},
}

# Explicit "<word> file" mentions, e.g. "single HTML file".
_KEYWORD_FILE_PATTERN = re.compile(r"\b([a-z0-9+#]{2,12})\s+file\b")
# Explicit ".ext" mentions, restricted to a curated allowlist so incidental
# tokens (e.g. "console.log", domain names) do not register as format demands.
_EXPLICIT_EXTENSION_PATTERN = re.compile(r"\.([a-z][a-z0-9]{0,4})\b")
_KNOWN_ARTIFACT_EXTENSIONS = {
    "html", "htm", "js", "mjs", "ts", "tsx", "jsx", "py", "rb", "go", "rs",
    "java", "cs", "cpp", "c", "css", "json", "md", "sh", "sql", "yaml", "yml",
    "pdf", "csv",
}
# Filler words excluded when reducing an acceptance criterion to salient terms.
_CRITERION_STOPWORDS = {
    "that", "this", "with", "from", "into", "when", "then", "must", "should",
    "will", "shall", "without", "successfully", "directly", "allows", "using",
    "their", "there", "which", "while", "after", "before", "between", "single",
    "able", "they", "them", "have", "been", "such", "than", "each", "also",
}


def mission_requires_equivalence(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    generated_output = metadata.get("generated_output")
    if not isinstance(generated_output, dict):
        return False
    if str(generated_output.get("source", "")).strip().lower() == "fallback":
        return False
    generated_code = str(generated_output.get("generated_code") or "").strip()
    return len(generated_code) >= 10


def build_equivalence_report(
    *,
    mission_id: str,
    requested_target_language: str | None,
    metadata: dict[str, Any],
    build_artifacts: list[dict[str, Any]],
    enforcement_enabled: bool,
) -> dict[str, Any]:
    generated_output = metadata.get("generated_output")
    generated_output = generated_output if isinstance(generated_output, dict) else {}
    feature_contract = _dict_value(metadata.get("feature_contract"))
    mission_contract = _dict_value(metadata.get("mission_contract"))
    aim = _dict_value(metadata.get("application_intelligence_map"))
    target_language = _target_language(
        requested_target_language=requested_target_language,
        mission_contract=mission_contract,
        generated_output=generated_output,
    )

    checks = [
        _check_generated_output_exists(generated_output),
        _check_generated_artifact(build_artifacts),
        _check_artifact_format(
            feature_contract, mission_contract, build_artifacts, generated_output
        ),
        _check_language_alignment(generated_output, target_language),
        _check_acceptance_criteria(feature_contract, mission_contract, generated_output),
        _check_aim_consistency(aim, generated_output),
    ]
    # PORT missions — add concept coverage checks (advisory, not required)
    port_source_logicnodes = metadata.get("port_source_logicnodes")
    if isinstance(port_source_logicnodes, list) and port_source_logicnodes:
        port_generated_output = generated_output
        checks.extend(_port_concept_coverage_checks(port_source_logicnodes, port_generated_output))
    findings = [
        check["message"]
        for check in checks
        if check["status"] in {"fail", "manual_review"}
    ]
    required_failures = [
        check for check in checks if check["required"] and check["status"] == "fail"
    ]
    passed = not required_failures
    blocking = enforcement_enabled and bool(required_failures)
    status = "passed" if passed else ("blocked" if blocking else "review_required")

    return {
        "schema_version": EQUIVALENCE_REPORT_SCHEMA_VERSION,
        "report_id": f"equivalence-{mission_id}",
        "mission_id": mission_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "passed": passed,
        "blocking": blocking,
        "enforcement_enabled": enforcement_enabled,
        "risk_level": _risk_level(checks=checks, blocking=blocking),
        "target_language": target_language,
        "checks": checks,
        "findings": findings,
        "evidence_refs": _evidence_refs(metadata, build_artifacts),
        "source": "deterministic",
    }


def _check_generated_output_exists(generated_output: dict[str, Any]) -> dict[str, Any]:
    code = str(generated_output.get("generated_code") or "").strip()
    if len(code) >= 10:
        return _check(
            check_id="generated_output_exists",
            title="Generated output exists",
            status="pass",
            required=True,
            message="Generated output has executable text.",
            evidence={"code_length_chars": len(code)},
        )
    return _check(
        check_id="generated_output_exists",
        title="Generated output exists",
        status="fail",
        required=True,
        message="Generated output is missing or too small to verify.",
        evidence={"code_length_chars": len(code)},
    )


def _check_generated_artifact(build_artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    artifact = next(
        (
            item
            for item in build_artifacts
            if str(item.get("artifact_type", "")).lower() == GENERATED_OUTPUT_ARTIFACT_TYPE
        ),
        None,
    )
    if artifact is None:
        return _check(
            check_id="generated_artifact_verified",
            title="Generated artifact verified",
            status="fail",
            required=True,
            message="No generated-code build artifact is available.",
        )
    verification = artifact.get("verification") if isinstance(artifact, dict) else {}
    verification = verification if isinstance(verification, dict) else {}
    verified = bool(verification.get("verified"))
    digest = str(artifact.get("digest_sha256") or "").strip()
    if verified and digest:
        return _check(
            check_id="generated_artifact_verified",
            title="Generated artifact verified",
            status="pass",
            required=True,
            message="Generated-code artifact has digest verification.",
            evidence={
                "artifact_id": artifact.get("artifact_id"),
                "digest_sha256": digest,
                "verification_method": verification.get("verification_method"),
            },
        )
    return _check(
        check_id="generated_artifact_verified",
        title="Generated artifact verified",
        status="fail",
        required=True,
        message="Generated-code artifact is present but not verified.",
        evidence={
            "artifact_id": artifact.get("artifact_id"),
            "digest_sha256": digest,
            "verified": verified,
        },
    )


def _check_artifact_format(
    feature_contract: dict[str, Any],
    mission_contract: dict[str, Any],
    build_artifacts: list[dict[str, Any]],
    generated_output: dict[str, Any],
) -> dict[str, Any]:
    """Require the delivered artifact form to match an explicit contract format.

    The feature contract sometimes names a required deliverable container
    (e.g. "single self-contained HTML file"). Language equivalence is not
    enough: a JavaScript file does not satisfy a contract for an HTML file even
    though both are "javascript-adjacent". When the contract names a format and
    the packaged artifact's extension does not match, this is a required failure.
    When no explicit format is named, the check is advisory.
    """
    artifact = next(
        (
            item
            for item in build_artifacts
            if str(item.get("artifact_type", "")).lower() == GENERATED_OUTPUT_ARTIFACT_TYPE
        ),
        None,
    )
    manifest = artifact.get("manifest") if isinstance(artifact, dict) else {}
    manifest = manifest if isinstance(manifest, dict) else {}
    filename = str(
        manifest.get("filename") or generated_output.get("filename") or ""
    ).strip()
    actual_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    expected = _expected_artifact_extensions(
        _contract_format_text(feature_contract, mission_contract)
    )
    if not expected:
        return _check(
            check_id="artifact_format_matches_contract",
            title="Artifact format matches contract",
            status="manual_review",
            required=False,
            message="No explicit deliverable format was specified in the contract.",
            evidence={"artifact_filename": filename, "artifact_extension": actual_ext},
        )
    if not actual_ext:
        return _check(
            check_id="artifact_format_matches_contract",
            title="Artifact format matches contract",
            status="manual_review",
            required=False,
            message="Artifact filename has no extension to verify against the contract.",
            evidence={"expected_extensions": sorted(expected), "artifact_filename": filename},
        )
    if actual_ext in expected:
        return _check(
            check_id="artifact_format_matches_contract",
            title="Artifact format matches contract",
            status="pass",
            required=True,
            message="Delivered artifact format matches the contracted deliverable format.",
            evidence={
                "expected_extensions": sorted(expected),
                "artifact_extension": actual_ext,
                "artifact_filename": filename,
            },
        )
    return _check(
        check_id="artifact_format_matches_contract",
        title="Artifact format matches contract",
        status="fail",
        required=True,
        message=(
            f"Delivered artifact format '.{actual_ext}' does not match the "
            f"contracted deliverable format(s): {sorted(expected)}."
        ),
        evidence={
            "expected_extensions": sorted(expected),
            "artifact_extension": actual_ext,
            "artifact_filename": filename,
        },
    )


def _contract_format_text(
    feature_contract: dict[str, Any],
    mission_contract: dict[str, Any],
) -> str:
    parts: list[str] = []
    for contract in (feature_contract, mission_contract):
        if not isinstance(contract, dict):
            continue
        for key in ("summary", "title"):
            value = contract.get(key)
            if isinstance(value, str):
                parts.append(value)
        for key in ("functional_requirements", "acceptance_criteria", "deliverables"):
            parts.extend(_string_list(contract.get(key), limit=20))
    return " ".join(parts)


def _expected_artifact_extensions(contract_text: str) -> set[str]:
    text = contract_text.lower()
    expected: set[str] = set()
    for match in _KEYWORD_FILE_PATTERN.finditer(text):
        keyword = match.group(1)
        if keyword in _ARTIFACT_FORMAT_EXTENSIONS:
            expected |= _ARTIFACT_FORMAT_EXTENSIONS[keyword]
    for match in _EXPLICIT_EXTENSION_PATTERN.finditer(text):
        ext = match.group(1)
        if ext in _KNOWN_ARTIFACT_EXTENSIONS:
            expected.add(ext)
    return expected


def _check_language_alignment(
    generated_output: dict[str, Any],
    target_language: str | None,
) -> dict[str, Any]:
    generated_language = str(generated_output.get("language") or "").strip().lower()
    target = str(target_language or "").strip().lower()
    if not generated_language or not target:
        return _check(
            check_id="language_alignment",
            title="Language alignment",
            status="manual_review",
            required=False,
            message="Language metadata is incomplete and needs review.",
            evidence={"generated_language": generated_language, "target_language": target},
        )
    if generated_language == target:
        return _check(
            check_id="language_alignment",
            title="Language alignment",
            status="pass",
            required=True,
            message="Generated output language matches the target language.",
            evidence={"generated_language": generated_language, "target_language": target},
        )
    return _check(
        check_id="language_alignment",
        title="Language alignment",
        status="fail",
        required=True,
        message="Generated output language does not match the target language.",
        evidence={"generated_language": generated_language, "target_language": target},
    )


def _check_acceptance_criteria(
    feature_contract: dict[str, Any],
    mission_contract: dict[str, Any],
    generated_output: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate each acceptance criterion against the generated output.

    Previously this check always returned ``manual_review`` without inspecting
    the artifact — acceptance criteria were never actually verified. It now
    reduces each criterion to salient terms and reports per-criterion coverage
    against the generated code and description. The check stays advisory
    (``required=False``) because keyword coverage is a heuristic signal, not a
    proof, but it surfaces *which* criteria are unaddressed rather than deferring
    all of them wholesale.
    """
    criteria = _string_list(feature_contract.get("acceptance_criteria"), limit=10)
    if not criteria:
        criteria = _string_list(mission_contract.get("acceptance_criteria"), limit=10)
    if not criteria:
        return _check(
            check_id="acceptance_criteria_mapped",
            title="Acceptance criteria mapped",
            status="manual_review",
            required=False,
            message="No explicit acceptance criteria were available for equivalence verification.",
        )

    search_text = (
        str(generated_output.get("description") or "")
        + " "
        + str(generated_output.get("generated_code") or "")
    ).lower()

    criteria_status: list[dict[str, Any]] = []
    for criterion in criteria:
        keywords = _criterion_keywords(criterion)
        covered = [keyword for keyword in keywords if keyword in search_text]
        ratio = round(len(covered) / len(keywords), 3) if keywords else 0.0
        criteria_status.append(
            {
                "criterion": criterion,
                "covered_ratio": ratio,
                "status": "covered" if ratio >= 0.5 else "needs_review",
            }
        )

    needs_review = [item for item in criteria_status if item["status"] == "needs_review"]
    if needs_review:
        return _check(
            check_id="acceptance_criteria_mapped",
            title="Acceptance criteria mapped",
            status="manual_review",
            required=False,
            message=(
                f"{len(needs_review)} of {len(criteria)} acceptance criteria are not "
                "clearly reflected in the generated output and need manual review."
            ),
            evidence={"criteria_status": criteria_status, "criteria_count": len(criteria)},
        )
    return _check(
        check_id="acceptance_criteria_mapped",
        title="Acceptance criteria mapped",
        status="pass",
        required=False,
        message="All acceptance criteria are heuristically reflected in the generated output.",
        evidence={"criteria_status": criteria_status, "criteria_count": len(criteria)},
    )


def _criterion_keywords(criterion: str) -> list[str]:
    """Reduce an acceptance criterion to salient lowercased terms for matching."""
    tokens = re.split(r"[^a-z0-9]+", criterion.lower())
    seen: list[str] = []
    for token in tokens:
        if len(token) < 4 or token in _CRITERION_STOPWORDS:
            continue
        if token not in seen:
            seen.append(token)
    return seen


def _check_aim_consistency(
    aim: dict[str, Any],
    generated_output: dict[str, Any],
) -> dict[str, Any]:
    if not aim:
        return _check(
            check_id="aim_context_available",
            title="AIM context available",
            status="manual_review",
            required=False,
            message="No AIM was available for source-context comparison.",
        )
    detected_languages = {
        str(item).strip().lower()
        for item in aim.get("detected_languages", [])
        if str(item).strip()
    }
    generated_language = str(generated_output.get("language") or "").strip().lower()
    if generated_language and generated_language in detected_languages:
        status = "pass"
        message = "Generated output language is represented in the AIM language inventory."
    else:
        status = "manual_review"
        message = "AIM is available, but language equivalence needs review."
    return _check(
        check_id="aim_context_available",
        title="AIM context available",
        status=status,
        required=False,
        message=message,
        evidence={
            "aim_id": aim.get("aim_id"),
            "detected_languages": sorted(detected_languages),
            "generated_language": generated_language,
        },
    )


def _check(
    *,
    check_id: str,
    title: str,
    status: str,
    required: bool,
    message: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "title": title,
        "status": status,
        "required": required,
        "message": message,
        "evidence": evidence or {},
    }


def _target_language(
    *,
    requested_target_language: str | None,
    mission_contract: dict[str, Any],
    generated_output: dict[str, Any],
) -> str | None:
    generated_language = str(generated_output.get("language") or "").strip().lower()
    if generated_language:
        return str(requested_target_language or generated_language).strip().lower()
    target_languages = mission_contract.get("target_languages")
    if isinstance(target_languages, list):
        for item in target_languages:
            candidate = str(item or "").strip().lower()
            if candidate:
                return candidate
    candidate = str(requested_target_language or "").strip().lower()
    return candidate or None


def _evidence_refs(
    metadata: dict[str, Any],
    build_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if isinstance(metadata.get("feature_contract"), dict):
        refs.append({"type": "metadata", "ref": "feature_contract"})
    if isinstance(metadata.get("mission_contract"), dict):
        refs.append({"type": "metadata", "ref": "mission_contract"})
    if isinstance(metadata.get("application_intelligence_map"), dict):
        refs.append({"type": "metadata", "ref": "application_intelligence_map"})
    for artifact in build_artifacts[:10]:
        refs.append(
            {
                "type": "build_artifact",
                "ref": artifact.get("artifact_id"),
                "artifact_type": artifact.get("artifact_type"),
                "digest_sha256": artifact.get("digest_sha256"),
            }
        )
    return refs


def _risk_level(*, checks: list[dict[str, Any]], blocking: bool) -> str:
    if blocking:
        return "high"
    if any(check["status"] == "fail" for check in checks):
        return "medium"
    if any(check["status"] == "manual_review" for check in checks):
        return "medium"
    return "low"


def _port_concept_coverage_checks(
    source_logicnodes: list[dict[str, Any]],
    generated_output: dict[str, Any],
) -> list[dict[str, Any]]:
    """Advisory concept coverage checks for PORT missions.

    Verifies that domain.concept pairs from the source extraction are
    reflected in the generated output description. All checks are
    required=False — semantic equivalence is advisory for PORT.
    """
    source_concepts = {
        f"{str(n.get('domain') or '').strip()}.{str(n.get('concept') or '').strip()}"
        for n in source_logicnodes
        if isinstance(n, dict) and n.get("concept")
    }
    if not source_concepts:
        return []

    description = str(generated_output.get("description") or "").lower()
    generated_code = str(generated_output.get("generated_code") or "").lower()
    search_text = description + " " + generated_code

    checks = []
    for concept_key in sorted(source_concepts)[:20]:
        parts = concept_key.split(".", 1)
        concept_name = parts[1] if len(parts) > 1 else concept_key
        concept_slug = concept_name.replace("_", " ").replace("-", " ").lower()
        present = concept_slug in search_text or concept_name.lower() in search_text
        checks.append({
            "check": f"port_concept_preserved:{concept_key}",
            "status": "pass" if present else "manual_review",
            "required": False,
            "message": (
                f"Source concept '{concept_key}' found in generated output."
                if present
                else (
                    f"Source concept '{concept_key}' not detected"
                    " in generated output — manual review."
                )
            ),
        })
    return checks


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:220] for item in value if str(item).strip()][:limit]
