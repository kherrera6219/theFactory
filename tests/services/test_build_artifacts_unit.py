import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

build_artifacts = importlib.import_module("orchestrator.build_artifacts")


def test_build_source_bundle_artifact_generates_manifest_and_digest() -> None:
    artifact = build_artifacts.build_source_bundle_artifact(
        mission_id="mission-1",
        requested_target_language="python",
        metadata={
            "source": "builder",
            "source_code": "## FILE app.py\nprint('a')\n\n## FILE worker.py\nprint('b')\n",
            "builder_fingerprint": "builder-123",
        },
    )

    assert artifact["artifact_id"] == build_artifacts.SOURCE_BUNDLE_ARTIFACT_ID
    assert artifact["artifact_type"] == build_artifacts.SOURCE_BUNDLE_ARTIFACT_TYPE
    assert artifact["status"] == "SUCCESS"
    assert artifact["manifest"]["file_count"] == 2
    assert artifact["manifest"]["files"][0]["path"] == "app.py"
    assert artifact["verification"]["verified"] is True
    assert artifact["digest_sha256"]


def test_record_build_artifact_metadata_appends_chain_trace_once() -> None:
    metadata = {"chain_trace": []}
    artifact_record = {
        "artifact_id": "source-bundle-package",
        "artifact_type": "source_bundle_package",
        "stage": "package",
        "status": "SUCCESS",
        "storage_backend": "database",
        "storage_ref": "database://missions/mission-1/build-artifacts/source-bundle-package",
        "digest_sha256": "abc123",
        "size_bytes": 128,
    }

    build_artifacts.record_build_artifact_metadata(
        metadata,
        agent_id="AGENT-14-PYTHON",
        artifact_record=artifact_record,
    )
    build_artifacts.record_build_artifact_metadata(
        metadata,
        agent_id="AGENT-14-PYTHON",
        artifact_record=artifact_record,
    )

    assert metadata["mission_artifacts"]["build_packaged"]["event_type"] == (
        build_artifacts.BUILD_ARTIFACT_PACKAGED_EVENT
    )
    assert len(metadata["chain_trace"]) == 1


def test_mission_requires_build_artifact_detects_source_code() -> None:
    assert build_artifacts.mission_requires_build_artifact({"source_code": "print('a')"}) is True
    assert build_artifacts.mission_requires_build_artifact({"source_code": "   "}) is False
    assert build_artifacts.mission_requires_build_artifact({"source": "builder"}) is False


# ── resolve_builder_type ───────────────────────────────────────────────────────

def test_resolve_builder_type_defaults_to_source_bundle() -> None:
    assert build_artifacts.resolve_builder_type({}) == build_artifacts.BUILDER_TYPE_SOURCE_BUNDLE
    assert build_artifacts.resolve_builder_type(None) == build_artifacts.BUILDER_TYPE_SOURCE_BUNDLE
    assert build_artifacts.resolve_builder_type({"builder_type": "unknown"}) == build_artifacts.BUILDER_TYPE_SOURCE_BUNDLE


def test_resolve_builder_type_recognises_all_types() -> None:
    assert build_artifacts.resolve_builder_type({"builder_type": "source_bundle"}) == "source_bundle"
    assert build_artifacts.resolve_builder_type({"builder_type": "binary"}) == "binary"
    assert build_artifacts.resolve_builder_type({"builder_type": "container"}) == "container"
    # Case-insensitive
    assert build_artifacts.resolve_builder_type({"builder_type": "BINARY"}) == "binary"


# ── mission_requires_build_artifact (extended) ────────────────────────────────

def test_mission_requires_build_artifact_binary_type() -> None:
    assert build_artifacts.mission_requires_build_artifact(
        {"builder_type": "binary", "binary_ref": "s3://bucket/app.bin"}
    ) is True
    assert build_artifacts.mission_requires_build_artifact(
        {"builder_type": "binary", "binary_ref": "   "}
    ) is False
    assert build_artifacts.mission_requires_build_artifact(
        {"builder_type": "binary"}
    ) is False


def test_mission_requires_build_artifact_container_type() -> None:
    assert build_artifacts.mission_requires_build_artifact(
        {"builder_type": "container", "image_ref": "ghcr.io/org/app:latest"}
    ) is True
    assert build_artifacts.mission_requires_build_artifact(
        {"builder_type": "container", "image_ref": ""}
    ) is False


# ── build_binary_artifact ──────────────────────────────────────────────────────

def test_build_binary_artifact_computes_digest_from_ref() -> None:
    artifact = build_artifacts.build_binary_artifact(
        mission_id="mission-bin-1",
        requested_target_language="rust",
        metadata={"binary_ref": "s3://bucket/app.bin", "binary_format": "elf"},
    )
    assert artifact["artifact_id"] == build_artifacts.BINARY_ARTIFACT_ID
    assert artifact["artifact_type"] == build_artifacts.BINARY_ARTIFACT_TYPE
    assert artifact["stage"] == build_artifacts.BINARY_ARTIFACT_STAGE
    assert artifact["status"] == "SUCCESS"
    assert artifact["verification"]["verification_method"] == "sha256_of_ref"
    assert len(artifact["digest_sha256"]) == 64
    assert artifact["manifest"]["binary_format"] == "elf"
    assert artifact["manifest"]["binary_ref"] == "s3://bucket/app.bin"


def test_build_binary_artifact_uses_provided_digest() -> None:
    provided = "a" * 64
    artifact = build_artifacts.build_binary_artifact(
        mission_id="mission-bin-2",
        requested_target_language="go",
        metadata={"binary_ref": "s3://bucket/app", "binary_digest": provided},
    )
    assert artifact["digest_sha256"] == provided
    assert artifact["verification"]["verification_method"] == "provided"


def test_build_binary_artifact_raises_without_ref() -> None:
    import pytest
    with pytest.raises(ValueError, match="binary_ref"):
        build_artifacts.build_binary_artifact(
            mission_id="m", requested_target_language=None, metadata={}
        )


# ── build_container_artifact ───────────────────────────────────────────────────

def test_build_container_artifact_computes_digest_from_ref() -> None:
    artifact = build_artifacts.build_container_artifact(
        mission_id="mission-ctr-1",
        requested_target_language="python",
        metadata={"image_ref": "ghcr.io/org/app:sha-abc123"},
    )
    assert artifact["artifact_id"] == build_artifacts.CONTAINER_ARTIFACT_ID
    assert artifact["artifact_type"] == build_artifacts.CONTAINER_ARTIFACT_TYPE
    assert artifact["stage"] == build_artifacts.CONTAINER_ARTIFACT_STAGE
    assert artifact["status"] == "SUCCESS"
    assert artifact["verification"]["verification_method"] == "sha256_of_ref"
    assert artifact["manifest"]["image_ref"] == "ghcr.io/org/app:sha-abc123"


def test_build_container_artifact_uses_registry_digest() -> None:
    digest_hex = "b" * 64
    artifact = build_artifacts.build_container_artifact(
        mission_id="mission-ctr-2",
        requested_target_language="java",
        metadata={
            "image_ref": "docker.io/org/app:latest",
            "image_digest": f"sha256:{digest_hex}",
        },
    )
    assert artifact["digest_sha256"] == digest_hex
    assert artifact["verification"]["verification_method"] == "registry_manifest_digest"


def test_build_container_artifact_raises_without_ref() -> None:
    import pytest
    with pytest.raises(ValueError, match="image_ref"):
        build_artifacts.build_container_artifact(
            mission_id="m", requested_target_language=None, metadata={}
        )


# ── dispatch_build_artifact ────────────────────────────────────────────────────

def test_dispatch_routes_source_bundle_by_default() -> None:
    artifact = build_artifacts.dispatch_build_artifact(
        mission_id="mission-dispatch-1",
        requested_target_language="python",
        metadata={"source_code": "print('hello')"},
    )
    assert artifact["artifact_type"] == build_artifacts.SOURCE_BUNDLE_ARTIFACT_TYPE


def test_dispatch_routes_binary() -> None:
    artifact = build_artifacts.dispatch_build_artifact(
        mission_id="mission-dispatch-2",
        requested_target_language="rust",
        metadata={"builder_type": "binary", "binary_ref": "s3://bucket/app"},
    )
    assert artifact["artifact_type"] == build_artifacts.BINARY_ARTIFACT_TYPE


def test_dispatch_routes_container() -> None:
    artifact = build_artifacts.dispatch_build_artifact(
        mission_id="mission-dispatch-3",
        requested_target_language="go",
        metadata={"builder_type": "container", "image_ref": "ghcr.io/org/app:latest"},
    )
    assert artifact["artifact_type"] == build_artifacts.CONTAINER_ARTIFACT_TYPE
