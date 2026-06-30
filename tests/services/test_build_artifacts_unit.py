import hashlib
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
    assert artifact["verification"]["verification_scope"] == "integrity"
    assert artifact["digest_sha256"]


def test_generated_output_artifact_verification_is_integrity_scoped() -> None:
    artifact = build_artifacts.build_generated_output_artifact(
        mission_id="mission-1",
        requested_target_language="javascript",
        metadata={
            "generated_output": {
                "source": "llm",
                "generated_code": "console.log('neon pong');\n",
                "filename": "neon-pong.js",
                "language": "javascript",
            }
        },
    )
    # The artifact's verification block attests integrity (digest/signature) only,
    # never correctness.
    assert artifact["verification"]["verification_scope"] == "integrity"
    assert artifact["verification"]["verified"] is True


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


def test_build_generated_output_artifact_generates_manifest_and_digest() -> None:
    metadata = {
        "generated_output": {
            "generated_code": "def count_words(text: str) -> dict[str, int]:\n    return {}\n",
            "filename": "count_words.py",
            "language": "python",
            "description": "Word counter",
            "dependencies": [],
            "source": "llm",
            "specialist_agent_id": "AGENT-14-PYTHON",
            "model_provider": "openai",
            "model": "gpt-5.5",
        }
    }
    artifact = build_artifacts.build_generated_output_artifact(
        mission_id="mission-2",
        requested_target_language="python",
        metadata=metadata,
    )
    assert artifact["artifact_id"] == build_artifacts.GENERATED_CODE_ARTIFACT_ID
    assert artifact["artifact_type"] == build_artifacts.GENERATED_CODE_ARTIFACT_TYPE
    assert artifact["manifest"]["filename"] == "count_words.py"
    assert artifact["artifact_text"].startswith("def count_words")
    assert artifact["digest_sha256"]


def test_build_generated_output_artifact_preserves_non_ascii_text() -> None:
    generated_code = (
        "<!doctype html><html><body>"
        "<button>Start → “Neon Pong” 🚀</button>"
        "</body></html>\n"
    )
    artifact = build_artifacts.build_generated_output_artifact(
        mission_id="mission-unicode",
        requested_target_language="javascript",
        metadata={
            "generated_output": {
                "generated_code": generated_code,
                "filename": "neon-pong.html",
                "language": "javascript",
                "source": "llm",
            }
        },
    )

    assert artifact["artifact_text"] == generated_code.strip()
    assert artifact["size_bytes"] == len(generated_code.strip().encode("utf-8"))
    assert artifact["digest_sha256"] == hashlib.sha256(
        generated_code.strip().encode("utf-8")
    ).hexdigest()
    guard = artifact["verification"]["encoding_guard"]
    assert guard["status"] == "clean"
    assert guard["repaired"] is False
    assert guard["non_ascii_count"] >= 4


def test_build_generated_output_artifact_repairs_common_mojibake_before_digest() -> None:
    mojibake_code = "<button>Start â†’ â€œNeon Pongâ€� ðŸš€</button>"
    repaired_code = "<button>Start → “Neon Pong” 🚀</button>"

    artifact = build_artifacts.build_generated_output_artifact(
        mission_id="mission-mojibake",
        requested_target_language="javascript",
        metadata={
            "generated_output": {
                "generated_code": mojibake_code,
                "filename": "neon-pong.html",
                "language": "javascript",
                "source": "llm",
            }
        },
    )

    assert artifact["artifact_text"] == repaired_code
    assert artifact["digest_sha256"] == hashlib.sha256(repaired_code.encode("utf-8")).hexdigest()
    guard = artifact["verification"]["encoding_guard"]
    assert guard["status"] == "repaired"
    assert guard["repaired"] is True
    assert guard["input_digest_sha256"] != guard["output_digest_sha256"]
    assert artifact["manifest"]["encoding_trace"]["packaging"]["status"] == "repaired"


def test_mission_has_generated_output_rejects_fallback() -> None:
    assert (
        build_artifacts.mission_has_generated_output(
            {"generated_output": {"generated_code": "print('hello')", "source": "fallback"}}
        )
        is False
    )
    assert (
        build_artifacts.mission_requires_build_artifact(
            {"generated_output": {"generated_code": "print('hello')", "source": "llm"}}
        )
        is True
    )
