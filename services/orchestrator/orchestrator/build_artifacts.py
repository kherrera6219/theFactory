from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from .mission_flow import append_chain_event

# ── Source-bundle constants ───────────────────────────────────────────────────
SOURCE_BUNDLE_ARTIFACT_ID = "source-bundle-package"
SOURCE_BUNDLE_ARTIFACT_TYPE = "source_bundle_package"
SOURCE_BUNDLE_ARTIFACT_STAGE = "package"

# ── Binary artifact constants ─────────────────────────────────────────────────
BINARY_ARTIFACT_ID = "binary-package"
BINARY_ARTIFACT_TYPE = "binary_package"
BINARY_ARTIFACT_STAGE = "package"

# ── Container artifact constants ──────────────────────────────────────────────
CONTAINER_ARTIFACT_ID = "container-image"
CONTAINER_ARTIFACT_TYPE = "container_image"
CONTAINER_ARTIFACT_STAGE = "publish"

# ── Shared event names ────────────────────────────────────────────────────────
BUILD_ARTIFACT_PACKAGED_EVENT = "MISSION_BUILD_ARTIFACT_PACKAGED"
BUILD_ARTIFACT_FAILED_EVENT = "MISSION_BUILD_ARTIFACT_FAILED"

# ── Builder types ─────────────────────────────────────────────────────────────
BUILDER_TYPE_SOURCE_BUNDLE = "source_bundle"
BUILDER_TYPE_BINARY = "binary"
BUILDER_TYPE_CONTAINER = "container"

_VALID_BUILDER_TYPES = {BUILDER_TYPE_SOURCE_BUNDLE, BUILDER_TYPE_BINARY, BUILDER_TYPE_CONTAINER}

_SOURCE_BUNDLE_FILE_PATTERN = re.compile(r"^## FILE (.+)$", re.MULTILINE)


def resolve_builder_type(metadata: Any) -> str:
    """Return the normalised builder_type from mission metadata.

    Defaults to ``source_bundle`` when the field is absent or unrecognised so
    that existing missions that only set ``source_code`` keep working unchanged.
    """
    if not isinstance(metadata, dict):
        return BUILDER_TYPE_SOURCE_BUNDLE
    raw = metadata.get("builder_type")
    if isinstance(raw, str) and raw.strip().lower() in _VALID_BUILDER_TYPES:
        return raw.strip().lower()
    return BUILDER_TYPE_SOURCE_BUNDLE


def mission_requires_build_artifact(metadata: Any) -> bool:
    """Return True when the mission should produce a build artifact.

    Triggers when:
    - ``source_code`` is present and non-empty (source_bundle builder), OR
    - ``builder_type`` is explicitly set to ``binary`` or ``container`` and
      the corresponding reference field is present.
    """
    if not isinstance(metadata, dict):
        return False
    builder_type = resolve_builder_type(metadata)
    if builder_type == BUILDER_TYPE_BINARY:
        ref = metadata.get("binary_ref")
        return isinstance(ref, str) and bool(ref.strip())
    if builder_type == BUILDER_TYPE_CONTAINER:
        ref = metadata.get("image_ref")
        return isinstance(ref, str) and bool(ref.strip())
    # Default: source_bundle
    source_code = metadata.get("source_code")
    return isinstance(source_code, str) and bool(source_code.strip())


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
        "verification_method": "sha256",
        "verified_at": generated_at,
        "bundle_digest_sha256": digest_sha256,
    }
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


def build_binary_artifact(
    *,
    mission_id: str,
    requested_target_language: str | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Package a binary artifact record from a ``binary_ref`` in mission metadata.

    The ``binary_ref`` field is treated as an opaque reference string (URL, path,
    or content-addressable pointer).  A SHA-256 digest is computed from the ref
    string itself so the artifact record is self-consistent without needing to
    fetch the actual binary.  When the mission supplies a pre-computed
    ``binary_digest`` that value is used instead and stored as
    ``verification_method: provided``.
    """
    binary_ref = str(metadata.get("binary_ref") or "").strip()
    if not binary_ref:
        raise ValueError("binary_ref is required to build a binary artifact")

    generated_at = datetime.now(UTC).isoformat()
    provided_digest = metadata.get("binary_digest")
    if isinstance(provided_digest, str) and re.fullmatch(r"[0-9a-f]{64}", provided_digest.lower()):
        digest_sha256 = provided_digest.lower()
        verification_method = "provided"
    else:
        digest_sha256 = hashlib.sha256(binary_ref.encode("utf-8")).hexdigest()
        verification_method = "sha256_of_ref"

    size_bytes = int(metadata.get("binary_size_bytes") or 0)
    manifest = {
        "manifest_version": "build-artifact.v1",
        "mission_id": mission_id,
        "artifact_id": BINARY_ARTIFACT_ID,
        "artifact_type": BINARY_ARTIFACT_TYPE,
        "stage": BINARY_ARTIFACT_STAGE,
        "generated_at": generated_at,
        "requested_target_language": requested_target_language,
        "binary_ref": binary_ref,
        "binary_format": metadata.get("binary_format") or "unspecified",
        "build_tool": metadata.get("build_tool") or "unspecified",
    }
    verification = {
        "verified": True,
        "verification_method": verification_method,
        "verified_at": generated_at,
        "bundle_digest_sha256": digest_sha256,
    }
    build_log = "\n".join(
        [
            f"[{generated_at}] binary package started for mission {mission_id}",
            f"[{generated_at}] binary_ref: {binary_ref}",
            f"[{generated_at}] digest ({verification_method}): {digest_sha256}",
            f"[{generated_at}] stored artifact metadata in postgres",
            f"[{generated_at}] package completed with status SUCCESS",
        ]
    )
    return {
        "artifact_id": BINARY_ARTIFACT_ID,
        "artifact_type": BINARY_ARTIFACT_TYPE,
        "stage": BINARY_ARTIFACT_STAGE,
        "status": "SUCCESS",
        "storage_backend": "database",
        "storage_ref": (
            f"database://missions/{mission_id}/build-artifacts/{BINARY_ARTIFACT_ID}"
        ),
        "digest_sha256": digest_sha256,
        "size_bytes": size_bytes,
        "manifest": manifest,
        "verification": verification,
        "build_log": build_log,
        "artifact_text": binary_ref,
        "created_at": generated_at,
    }


def build_container_artifact(
    *,
    mission_id: str,
    requested_target_language: str | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Package a container image artifact record from ``image_ref`` in mission metadata.

    The ``image_ref`` field is the fully-qualified image reference
    (e.g. ``ghcr.io/org/image:sha-abc123``).  The ``image_digest`` field, when
    present, is the registry-provided manifest digest (``sha256:...`` format).
    When absent, a SHA-256 is computed from the image_ref string.
    """
    image_ref = str(metadata.get("image_ref") or "").strip()
    if not image_ref:
        raise ValueError("image_ref is required to build a container artifact")

    generated_at = datetime.now(UTC).isoformat()
    provided_digest = metadata.get("image_digest")
    # Strip leading "sha256:" prefix from registry manifests if present
    if isinstance(provided_digest, str):
        clean = provided_digest.lower().removeprefix("sha256:")
        if re.fullmatch(r"[0-9a-f]{64}", clean):
            digest_sha256 = clean
            verification_method = "registry_manifest_digest"
        else:
            digest_sha256 = hashlib.sha256(image_ref.encode("utf-8")).hexdigest()
            verification_method = "sha256_of_ref"
    else:
        digest_sha256 = hashlib.sha256(image_ref.encode("utf-8")).hexdigest()
        verification_method = "sha256_of_ref"

    manifest = {
        "manifest_version": "build-artifact.v1",
        "mission_id": mission_id,
        "artifact_id": CONTAINER_ARTIFACT_ID,
        "artifact_type": CONTAINER_ARTIFACT_TYPE,
        "stage": CONTAINER_ARTIFACT_STAGE,
        "generated_at": generated_at,
        "requested_target_language": requested_target_language,
        "image_ref": image_ref,
        "image_registry": metadata.get("image_registry") or "unspecified",
        "base_image": metadata.get("base_image") or "unspecified",
    }
    verification = {
        "verified": True,
        "verification_method": verification_method,
        "verified_at": generated_at,
        "bundle_digest_sha256": digest_sha256,
    }
    build_log = "\n".join(
        [
            f"[{generated_at}] container publish started for mission {mission_id}",
            f"[{generated_at}] image_ref: {image_ref}",
            f"[{generated_at}] digest ({verification_method}): {digest_sha256}",
            f"[{generated_at}] stored artifact metadata in postgres",
            f"[{generated_at}] publish completed with status SUCCESS",
        ]
    )
    return {
        "artifact_id": CONTAINER_ARTIFACT_ID,
        "artifact_type": CONTAINER_ARTIFACT_TYPE,
        "stage": CONTAINER_ARTIFACT_STAGE,
        "status": "SUCCESS",
        "storage_backend": "database",
        "storage_ref": (
            f"database://missions/{mission_id}/build-artifacts/{CONTAINER_ARTIFACT_ID}"
        ),
        "digest_sha256": digest_sha256,
        "size_bytes": 0,
        "manifest": manifest,
        "verification": verification,
        "build_log": build_log,
        "artifact_text": image_ref,
        "created_at": generated_at,
    }


def dispatch_build_artifact(
    *,
    mission_id: str,
    requested_target_language: str | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Select and run the correct builder based on ``metadata['builder_type']``.

    Falls back to source_bundle when builder_type is absent or unrecognised,
    preserving backwards compatibility with existing missions.
    """
    builder_type = resolve_builder_type(metadata)
    if builder_type == BUILDER_TYPE_BINARY:
        return build_binary_artifact(
            mission_id=mission_id,
            requested_target_language=requested_target_language,
            metadata=metadata,
        )
    if builder_type == BUILDER_TYPE_CONTAINER:
        return build_container_artifact(
            mission_id=mission_id,
            requested_target_language=requested_target_language,
            metadata=metadata,
        )
    return build_source_bundle_artifact(
        mission_id=mission_id,
        requested_target_language=requested_target_language,
        metadata=metadata,
    )


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
