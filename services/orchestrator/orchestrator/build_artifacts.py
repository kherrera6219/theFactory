from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from .mission_flow import append_chain_event

SOURCE_BUNDLE_ARTIFACT_ID = "source-bundle-package"
SOURCE_BUNDLE_ARTIFACT_TYPE = "source_bundle_package"
SOURCE_BUNDLE_ARTIFACT_STAGE = "package"
GENERATED_CODE_ARTIFACT_ID = "generated-code-output"
GENERATED_CODE_ARTIFACT_TYPE = "generated_code"
GENERATED_CODE_ARTIFACT_STAGE = "squeeze"
BUILD_ARTIFACT_PACKAGED_EVENT = "MISSION_BUILD_ARTIFACT_PACKAGED"
BUILD_ARTIFACT_FAILED_EVENT = "MISSION_BUILD_ARTIFACT_FAILED"

_SOURCE_BUNDLE_FILE_PATTERN = re.compile(r"^## FILE (.+)$", re.MULTILINE)
_MOJIBAKE_MARKERS = ("â", "Ã", "Â", "ðŸ", "�")
_COMMON_MOJIBAKE_REPLACEMENTS = {
    "â†’": "→",
    "â€œ": "“",
    "â€�": "”",
    "â€˜": "‘",
    "â€™": "’",
    "â€“": "–",
    "â€”": "—",
    "â€¦": "…",
    "ðŸš€": "🚀",
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _non_ascii_count(value: str) -> int:
    return sum(1 for char in value if ord(char) > 127)


def _mojibake_score(value: str) -> int:
    score = value.count("�") * 4
    for marker in _MOJIBAKE_MARKERS:
        score += value.count(marker)
    return score


def _repair_common_mojibake(value: str) -> str:
    """Repair common UTF-8 bytes decoded as Windows-1252/Latin-1 mojibake."""
    best = value
    best_score = _mojibake_score(value)
    mapped = value
    for mojibake, replacement in _COMMON_MOJIBAKE_REPLACEMENTS.items():
        mapped = mapped.replace(mojibake, replacement)
    if _mojibake_score(mapped) < best_score:
        best = mapped
        best_score = _mojibake_score(mapped)
    for source_encoding in ("cp1252", "latin-1"):
        try:
            candidate = value.encode(source_encoding).decode("utf-8")
        except UnicodeError:
            continue
        candidate_score = _mojibake_score(candidate)
        if candidate_score < best_score:
            best = candidate
            best_score = candidate_score
    return best


def _apply_encoding_guard(value: str) -> tuple[str, dict[str, Any]]:
    input_digest = _sha256_text(value)
    input_score = _mojibake_score(value)
    repaired = _repair_common_mojibake(value) if input_score > 0 else value
    output_score = _mojibake_score(repaired)
    repaired_changed = repaired != value and output_score < input_score
    output = repaired if repaired_changed else value
    status = "clean"
    if repaired_changed:
        status = "repaired"
    elif input_score > 0:
        status = "suspect"
    guard = {
        "schema_version": "encoding_guard.v1",
        "status": status,
        "repaired": repaired_changed,
        "input_digest_sha256": input_digest,
        "output_digest_sha256": _sha256_text(output),
        "input_length_chars": len(value),
        "output_length_chars": len(output),
        "input_size_bytes": len(value.encode("utf-8")),
        "output_size_bytes": len(output.encode("utf-8")),
        "non_ascii_count": _non_ascii_count(output),
        "mojibake_score_before": input_score,
        "mojibake_score_after": _mojibake_score(output),
    }
    return output, guard


def mission_requires_build_artifact(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    if mission_has_generated_output(metadata):
        return True
    source_code = metadata.get("source_code")
    if isinstance(source_code, str) and bool(source_code.strip()):
        return True
    return mission_expects_generated_output_artifact(metadata)


def mission_expects_generated_output_artifact(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False

    output_mode = str(
        metadata.get("output_mode_label")
        or metadata.get("__output_mode__")
        or metadata.get("output_mode")
        or "FULL_BUILD"
    ).strip().upper()
    if output_mode in {"ANALYZE_ONLY", "REPORT_ONLY", "PLAN_ONLY", "REPORT", "ANALYZE"}:
        return False

    expected_artifacts = metadata.get("expected_artifacts")
    if isinstance(expected_artifacts, list):
        normalized = {str(item).strip().lower() for item in expected_artifacts}
        return "generated_output" in normalized

    mission_charter = metadata.get("mission_charter")
    if isinstance(mission_charter, dict):
        charter_artifacts = mission_charter.get("expected_artifacts")
        if isinstance(charter_artifacts, list):
            normalized = {str(item).strip().lower() for item in charter_artifacts}
            return "generated_output" in normalized

    return False


def mission_has_generated_output(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    generated_output = metadata.get("generated_output")
    if not isinstance(generated_output, dict):
        return False
    if str(generated_output.get("source", "")).strip().lower() == "fallback":
        return False
    generated_code = generated_output.get("generated_code")
    return isinstance(generated_code, str) and len(generated_code.strip()) >= 10


def build_generated_output_artifact(
    *,
    mission_id: str,
    requested_target_language: str | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    generated_output = metadata.get("generated_output")
    if not isinstance(generated_output, dict):
        raise ValueError("generated_output is required to build a generated code artifact")
    raw_generated_code = str(generated_output.get("generated_code") or "").strip()
    generated_code, encoding_guard = _apply_encoding_guard(raw_generated_code)
    if len(generated_code) < 10:
        raise ValueError("generated_output.generated_code is too small to package")

    generated_at = datetime.now(UTC).isoformat()
    digest_sha256 = encoding_guard["output_digest_sha256"]
    size_bytes = encoding_guard["output_size_bytes"]
    upstream_encoding_trace = generated_output.get("encoding_trace")
    encoding_trace = upstream_encoding_trace if isinstance(upstream_encoding_trace, dict) else {}
    encoding_trace = {
        **encoding_trace,
        "packaging": {
            "status": encoding_guard["status"],
            "repaired": encoding_guard["repaired"],
            "input_digest_sha256": encoding_guard["input_digest_sha256"],
            "output_digest_sha256": encoding_guard["output_digest_sha256"],
            "mojibake_score_before": encoding_guard["mojibake_score_before"],
            "mojibake_score_after": encoding_guard["mojibake_score_after"],
        },
    }
    manifest = {
        "manifest_version": "build-artifact.v1",
        "mission_id": mission_id,
        "artifact_id": GENERATED_CODE_ARTIFACT_ID,
        "artifact_type": GENERATED_CODE_ARTIFACT_TYPE,
        "stage": GENERATED_CODE_ARTIFACT_STAGE,
        "generated_at": generated_at,
        "requested_target_language": requested_target_language,
        "filename": generated_output.get("filename") or "generated.txt",
        "language": generated_output.get("language") or requested_target_language or "text",
        "description": generated_output.get("description"),
        "dependencies": generated_output.get("dependencies") or [],
        "source": generated_output.get("source"),
        "specialist_agent_id": generated_output.get("specialist_agent_id"),
        "model_provider": generated_output.get("model_provider"),
        "model": generated_output.get("model"),
        "encoding_trace": encoding_trace,
    }
    verification = {
        "verified": True,
        # Integrity only: this attests the bytes are intact (digest/signature),
        # not that the artifact is correct or runnable. Correctness is assessed
        # separately by the equivalence report (verification_scope="correctness").
        "verification_scope": "integrity",
        "verification_method": "sha256",
        "verified_at": generated_at,
        "artifact_digest_sha256": digest_sha256,
        "encoding_guard": encoding_guard,
    }
    try:
        from shared_runtime.crypto_keystore import load_or_create_signing_key
        from shared_runtime.crypto_signing import _keystore_path, sign_payload
        key = load_or_create_signing_key(_keystore_path())
        signature_record = sign_payload(key, generated_code)
        verification["signature_record"] = signature_record
        verification["verification_method"] = "ECDSA-P256-SHA256"
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("failed to sign generated code artifact: %s", exc)
    build_log = "\n".join(
        [
            f"[{generated_at}] generated-code packaging started for mission {mission_id}",
            f"[{generated_at}] packaged generated code artifact",
            f"[{generated_at}] computed sha256 {digest_sha256}",
            f"[{generated_at}] package completed with status SUCCESS",
        ]
    )
    return {
        "artifact_id": GENERATED_CODE_ARTIFACT_ID,
        "artifact_type": GENERATED_CODE_ARTIFACT_TYPE,
        "stage": GENERATED_CODE_ARTIFACT_STAGE,
        "status": "SUCCESS",
        "storage_backend": "database",
        "storage_ref": (
            f"database://missions/{mission_id}/build-artifacts/{GENERATED_CODE_ARTIFACT_ID}"
        ),
        "digest_sha256": digest_sha256,
        "size_bytes": size_bytes,
        "manifest": manifest,
        "verification": verification,
        "build_log": build_log,
        "artifact_text": generated_code,
        "created_at": generated_at,
    }


def build_source_bundle_artifact(
    *,
    mission_id: str,
    requested_target_language: str | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    source_code = str(metadata.get("source_code") or "").strip()
    if not source_code:
        raise ValueError("source_code is required to build a source bundle artifact")

    generated_at = datetime.now(UTC).isoformat()
    files = _parse_source_bundle(source_code)
    digest_sha256 = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
    size_bytes = len(source_code.encode("utf-8"))
    fingerprints = {
        key: metadata.get(key)
        for key in ("builder_fingerprint", "review_fingerprint")
        if isinstance(metadata.get(key), str) and str(metadata.get(key)).strip()
    }
    manifest = {
        "manifest_version": "build-artifact.v1",
        "mission_id": mission_id,
        "artifact_id": SOURCE_BUNDLE_ARTIFACT_ID,
        "artifact_type": SOURCE_BUNDLE_ARTIFACT_TYPE,
        "stage": SOURCE_BUNDLE_ARTIFACT_STAGE,
        "generated_at": generated_at,
        "requested_target_language": requested_target_language,
        "source": metadata.get("source"),
        "source_kind": "multi_file_bundle" if len(files) > 1 else "inline_source",
        "file_count": len(files),
        "files": files,
        "fingerprints": fingerprints,
    }
    verification = {
        "verified": True,
        # Integrity only — see build_generated_output_artifact for the scope note.
        "verification_scope": "integrity",
        "verification_method": "sha256",
        "verified_at": generated_at,
        "bundle_digest_sha256": digest_sha256,
    }
    try:
        from shared_runtime.crypto_keystore import load_or_create_signing_key
        from shared_runtime.crypto_signing import _keystore_path, sign_payload
        key = load_or_create_signing_key(_keystore_path())
        signature_record = sign_payload(key, source_code)
        verification["signature_record"] = signature_record
        verification["verification_method"] = "ECDSA-P256-SHA256"
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("failed to sign source bundle artifact: %s", exc)
    build_log = "\n".join(
        [
            f"[{generated_at}] package started for mission {mission_id}",
            f"[{generated_at}] packaged {len(files)} file(s) into source bundle artifact",
            f"[{generated_at}] computed sha256 {digest_sha256}",
            f"[{generated_at}] stored artifact metadata in postgres",
            f"[{generated_at}] package completed with status SUCCESS",
        ]
    )
    return {
        "artifact_id": SOURCE_BUNDLE_ARTIFACT_ID,
        "artifact_type": SOURCE_BUNDLE_ARTIFACT_TYPE,
        "stage": SOURCE_BUNDLE_ARTIFACT_STAGE,
        "status": "SUCCESS",
        "storage_backend": "database",
        "storage_ref": (
            f"database://missions/{mission_id}/build-artifacts/{SOURCE_BUNDLE_ARTIFACT_ID}"
        ),
        "digest_sha256": digest_sha256,
        "size_bytes": size_bytes,
        "manifest": manifest,
        "verification": verification,
        "build_log": build_log,
        "artifact_text": source_code,
        "created_at": generated_at,
    }


def build_missing_source_artifact_failure(
    *,
    mission_id: str,
    requested_target_language: str | None,
) -> dict[str, Any]:
    """FAILED build-artifact record for missions whose charter expects a
    generated_output artifact but neither generated_output nor source_code
    exists to package. Recording this (instead of raising) keeps the failure
    visible in the mission's build-artifacts list and chain trace via
    record_build_artifact_metadata's status-based event routing, instead of a
    silently swallowed exception that leaves the mission stuck at "verified"
    with no signal.
    """
    generated_at = datetime.now(UTC).isoformat()
    reason = "no generated output or source code available to package"
    build_log = "\n".join(
        [
            f"[{generated_at}] package started for mission {mission_id}",
            f"[{generated_at}] package failed: {reason}",
        ]
    )
    return {
        "artifact_id": SOURCE_BUNDLE_ARTIFACT_ID,
        "artifact_type": SOURCE_BUNDLE_ARTIFACT_TYPE,
        "stage": SOURCE_BUNDLE_ARTIFACT_STAGE,
        "status": "FAILED",
        "storage_backend": "database",
        "storage_ref": None,
        "digest_sha256": None,
        "size_bytes": 0,
        "manifest": {
            "manifest_version": "build-artifact.v1",
            "mission_id": mission_id,
            "artifact_id": SOURCE_BUNDLE_ARTIFACT_ID,
            "artifact_type": SOURCE_BUNDLE_ARTIFACT_TYPE,
            "stage": SOURCE_BUNDLE_ARTIFACT_STAGE,
            "generated_at": generated_at,
            "requested_target_language": requested_target_language,
            "failure_reason": reason,
        },
        "verification": {
            "verified": False,
            "verification_scope": "integrity",
            "verification_method": "none",
            "verified_at": generated_at,
        },
        "build_log": build_log,
        "artifact_text": "",
        "created_at": generated_at,
    }


def record_build_artifact_metadata(
    metadata: dict[str, Any],
    *,
    agent_id: str,
    artifact_record: dict[str, Any],
) -> None:
    status = str(artifact_record.get("status", "")).upper()
    event_type = (
        BUILD_ARTIFACT_PACKAGED_EVENT if status == "SUCCESS" else BUILD_ARTIFACT_FAILED_EVENT
    )
    details = {
        "artifact_id": artifact_record.get("artifact_id"),
        "artifact_type": artifact_record.get("artifact_type"),
        "stage": artifact_record.get("stage"),
        "status": status or "UNKNOWN",
        "storage_backend": artifact_record.get("storage_backend"),
        "storage_ref": artifact_record.get("storage_ref"),
        "digest_sha256": artifact_record.get("digest_sha256"),
        "size_bytes": int(artifact_record.get("size_bytes", 0) or 0),
    }
    chain_trace = metadata.get("chain_trace")
    if not isinstance(chain_trace, list):
        chain_trace = []
        metadata["chain_trace"] = chain_trace
    if not any(
        isinstance(entry, dict)
        and str(entry.get("event_type", "")).upper() == event_type
        and str((entry.get("details") or {}).get("artifact_id", "")) == str(details["artifact_id"])
        for entry in chain_trace
    ):
        append_chain_event(
            metadata,
            event_type=event_type,
            agent_id=agent_id,
            details=details,
        )

    artifacts = metadata.get("mission_artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    artifacts["build_packaged"] = {
        "event_type": event_type,
        "agent_id": agent_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "details": details,
    }
    metadata["mission_artifacts"] = artifacts


def has_successful_build_artifact(records: list[dict[str, Any]]) -> bool:
    return any(str(record.get("status", "")).upper() == "SUCCESS" for record in records)


def latest_build_artifact_status(records: list[dict[str, Any]]) -> str:
    if not records:
        return "MISSING"
    return str(records[0].get("status", "UNKNOWN")).upper() or "UNKNOWN"


def _parse_source_bundle(source_code: str) -> list[dict[str, Any]]:
    matches = list(_SOURCE_BUNDLE_FILE_PATTERN.finditer(source_code))
    if not matches:
        return [_file_manifest_entry("inline_source.txt", source_code)]

    files: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        path = str(match.group(1)).strip() or f"file-{index + 1}.txt"
        content_start = match.end()
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(source_code)
        content = source_code[content_start:content_end].lstrip("\r\n")
        files.append(_file_manifest_entry(path, content))
    return files


def _file_manifest_entry(path: str, content: str) -> dict[str, Any]:
    payload = content.encode("utf-8")
    return {
        "path": path,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
