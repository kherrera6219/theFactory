from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "phase13_smoke.py"

spec = importlib.util.spec_from_file_location("phase13_smoke", MODULE_PATH)
assert spec is not None and spec.loader is not None
smoke = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = smoke
spec.loader.exec_module(smoke)


def test_extract_event_types_from_chain_trace_payload() -> None:
    payload = {"events": [{"event_type": "MISSION_PM_INTAKE"}, {"event_type": " mission_complete "}]}
    assert smoke._extract_event_types(payload) == ["MISSION_PM_INTAKE", "MISSION_COMPLETE"]


def test_extract_chain_trace_event_types_from_chain_trace_payload() -> None:
    payload = {"chain_trace": [{"event_type": "MISSION_PM_INTAKE"}]}
    assert smoke._extract_chain_trace_event_types(payload) == ["MISSION_PM_INTAKE"]


def test_extract_metadata_chain_event_types_from_mission_payload() -> None:
    payload = {"metadata": {"chain_trace": [{"event_type": "MISSION_CEO_DELEGATED"}]}}
    assert smoke._extract_metadata_chain_event_types(payload) == ["MISSION_CEO_DELEGATED"]


def test_env_file_service_key_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _service_key_headers prefers an already-set process env var over the file,
    # so clear it to keep this test independent of suite ordering / a loaded .env.
    monkeypatch.delenv("INTERNAL_SERVICE_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("OTHER=value\nINTERNAL_SERVICE_API_KEY='secret-key'\n", encoding="utf-8")
    assert smoke._service_key_headers(str(env_file)) == {"x-api-key": "secret-key"}


def test_python_artifact_syntax_check_accepts_valid_source() -> None:
    valid, error = smoke._is_valid_python("def reverse_string(value: str) -> str:\n    return value[::-1]\n")
    assert valid is True
    assert error is None


def test_python_artifact_syntax_check_rejects_invalid_source() -> None:
    valid, error = smoke._is_valid_python("def broken(:\n")
    assert valid is False
    assert "line" in str(error)


def test_find_python_artifact_prefers_generated_python_record() -> None:
    artifact = smoke._find_python_artifact(
        [
            {"artifact_id": "notes", "artifact_type": "text"},
            {"artifact_id": "generated_code", "artifact_type": "python_source"},
        ]
    )
    assert artifact == {"artifact_id": "generated_code", "artifact_type": "python_source"}


def test_artifact_text_prefers_inline_artifact_text() -> None:
    assert smoke._artifact_text({"artifact_text": "print('ok')"}) == "print('ok')"


def test_build_mission_payload_marks_smoke_spec_as_finalized() -> None:
    payload = smoke._build_mission_payload("Build a Python utility.")
    assert payload["requested_target_language"] == "python"
    assert payload["metadata"]["source"] == "phase13_smoke"
    assert payload["metadata"]["mission_type"] == "BUILD_NEW"
    assert payload["metadata"]["user_intent"] == "finalize_plan"


def test_imported_ast_module_is_available_for_regression() -> None:
    assert ast.parse("x = 1") is not None
