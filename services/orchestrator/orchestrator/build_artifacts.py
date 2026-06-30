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


def mission_requires_build_artifact(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    if mission_has_generated_output(metadata):
        return True
    source_code = metadata.get("source_code")
    return isinstance(source_code, str) and bool(source_code.strip())


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
    generated_code = str(generated_output.get("generated_code") or "").strip()
    if len(generated_code) < 10:
        raise ValueError("generated_output.generated_code is too small to package")

    generated_at = datetime.now(UTC).isoformat()
    digest_sha256 = hashlib.sha256(generated_code.encode("utf-8")).hexdigest()
    size_bytes = len(generated_code.encode("utf-8"))
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
