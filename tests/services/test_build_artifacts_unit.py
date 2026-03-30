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
