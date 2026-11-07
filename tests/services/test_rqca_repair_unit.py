"""Unit tests for surgical file-level self-repair and multi-turn Runtime QC (Phase 4)."""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

rqca_repair = importlib.import_module("orchestrator.rqca_repair")
mission_flow_v2 = importlib.import_module("orchestrator.mission_flow_v2")
phases_runtime = importlib.import_module("orchestrator.mission_flow_v2.phases_runtime")


def test_extract_failing_files_and_surgical_context() -> None:
    bundle = (
        "## FILE README.md\n# Docs\n"
        + ("A" * 10000)
        + "\n## FILE src/math_utils.py\ndef divide(a, b):\n    return a / 0\n"
    )
    execution = {
        "exit_code": 1,
        "stderr_preview": 'Traceback (most recent call last):\n  File "/workspace/src/math_utils.py", line 2, in divide\nZeroDivisionError: division by zero',
        "stdout_preview": "",
        "command": "pytest -q",
    }
    ctx = rqca_repair.build_surgical_repair_context(
        execution=execution,
        generated_code=bundle,
        attempt=1,
        max_attempts=2,
        previous_errors=[],
    )
    assert ctx["failing_files"] == ["src/math_utils.py"]
    assert ctx["file_tree_manifest"] == ["README.md", "src/math_utils.py"]
    # Failing file is placed first in surgical previous_code so it is never truncated!
    assert ctx["previous_code"].startswith("## FILE src/math_utils.py\n")


def test_merge_repaired_files_preserves_untouched_files() -> None:
    original = (
        "## FILE README.md\n# Project\n\n"
        "## FILE src/app.py\ndef broken():\n    return 1 / 0\n\n"
        "## FILE src/helper.py\nHELPER = True\n"
    )
    partial_repair = "## FILE src/app.py\ndef broken():\n    return 42\n"
    merged = rqca_repair.merge_repaired_files(original, partial_repair)
    assert "## FILE README.md" in merged
    assert "## FILE src/helper.py" in merged
    assert "return 42" in merged
    assert "1 / 0" not in merged


def test_duplicate_error_signature_normalizes_hex_and_tmp_paths() -> None:
    sig1 = rqca_repair.compute_error_signature(
        "Error at 0x7fff5fbff8c0 in /tmp/run_abc123/app.py: NameError: x",
        "",
        exit_code=1,
    )
    is_dup, sig2 = rqca_repair.is_duplicate_error_signature(
        "Error at 0x123456789abc in /tmp/run_xyz999/app.py: NameError: x",
        "",
        [sig1],
        exit_code=1,
    )
    assert is_dup is True
    assert sig1 == sig2


def test_multi_turn_self_repair_succeeds_on_second_attempt(monkeypatch) -> None:
    qc_calls: list[str] = []

    async def fake_run_runtime_qc(**kwargs: Any) -> dict[str, Any]:
        code = kwargs["generated_output"]["generated_code"]
        qc_calls.append(code)
        if len(qc_calls) == 1:
            return {
                "verdict": "FAIL",
                "passed": False,
                "exit_code": 1,
                "stderr_preview": "File 'src/calc.py', line 2: SyntaxError: invalid syntax",
                "stdout_preview": "",
                "command": "pytest -q",
                "execution_type": "single_container",
                "verified_scope_detail": "tests",
                "source": "sandbox",
            }
        if len(qc_calls) == 2:
            return {
                "verdict": "FAIL",
                "passed": False,
                "exit_code": 1,
                "stderr_preview": "File 'src/calc.py', line 2: AssertionError: expected 4 got 5",
                "stdout_preview": "",
                "command": "pytest -q",
                "execution_type": "single_container",
                "verified_scope_detail": "tests",
                "source": "sandbox",
            }
        return {
            "verdict": "PASS",
            "passed": True,
            "exit_code": 0,
            "stderr_preview": "",
            "stdout_preview": "2 passed",
            "command": "pytest -q",
            "execution_type": "single_container",
            "verified_scope_detail": "tests",
            "source": "sandbox",
        }

    repair_calls: list[dict[str, Any]] = []

    async def fake_generate_code_from_contract(**kwargs: Any) -> dict[str, Any]:
        repair_ctx = kwargs["mission_context"]["runtime_qc_repair_context"]
        repair_calls.append(repair_ctx)
        if repair_ctx["attempt"] == 1:
            return {
                "generated_code": "## FILE src/calc.py\ndef add(a, b):\n    return a + b + 1\n",
                "filename": "src/calc.py",
                "language": "python",
                "source": "llm",
            }
        return {
            "generated_code": "## FILE src/calc.py\ndef add(a, b):\n    return a + b\n",
            "filename": "src/calc.py",
            "language": "python",
            "source": "llm",
        }

    async def fake_record_audit(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(phases_runtime, "run_runtime_qc", fake_run_runtime_qc)
    monkeypatch.setattr(mission_flow_v2, "generate_code_from_contract", fake_generate_code_from_contract)
    monkeypatch.setattr(mission_flow_v2, "record_audit_event", fake_record_audit)
    monkeypatch.setattr(mission_flow_v2.storage, "insert_runtime_qc_report", lambda *_a, **_k: None)

    class _DummyMission:
        mission_id = "m-multi-repair"
        project_id = "p-1"
        title = "Multi-turn repair"
        objective = "Test 2-turn repair"
        status = "GATING"
        state = "GATING"
        prompt = "add numbers"
        correlation_id = "c-1"
        requested_target_language = "python"
        metadata: dict[str, Any] = {}

    metadata: dict[str, Any] = {
        "requested_target_language": "python",
        "assigned_specialist_agent_id": "AGENT-14-PYTHON",
        "generated_output": {
            "generated_code": (
                "## FILE README.md\n# Calculator\n\n"
                "## FILE src/calc.py\ndef add(a, b): SYNTAX_ERR\n"
            ),
            "filename": "src/calc.py",
            "language": "python",
            "source": "llm",
        },
        "testdata_manifest": {"multi_container": False, "fixtures": []},
        "integration_tests": {"test_code": "def test_add(): assert add(2, 2) == 4\n", "source": "llm"},
        "mission_contract": {"summary": "add numbers"},
    }
    _DummyMission.metadata = metadata
    monkeypatch.setattr(
        mission_flow_v2.storage,
        "update_mission_metadata",
        lambda _s, _m_id, meta: metadata.update(meta) or _DummyMission(),
    )
    settings = SimpleNamespace(
        rqca_agent_enabled=True,
        rqca_enforcement_enabled=True,
        testdata_agent_enabled=False,
        runtime_qc_max_repair_attempts=2,
    )
    asyncio.run(phases_runtime._prepare_runtime_qc(app=object(), settings=settings, mission=_DummyMission()))

    assert len(qc_calls) == 3
    assert len(repair_calls) == 2
    assert metadata["runtime_qc_repair_attempts"] == 2
    report = metadata["runtime_qc_report"]
    assert report["verdict"] == "PASS"
    assert report["repair_succeeded"] is True
    assert report["repair_attempts"] == 2
    assert report["repair_stop_reason"] == "passed"
    assert "## FILE README.md" in metadata["generated_output"]["generated_code"]


def test_multi_turn_self_repair_stops_early_on_duplicate_error_signature(monkeypatch) -> None:
    qc_calls = 0

    async def fake_run_runtime_qc(**_kwargs: Any) -> dict[str, Any]:
        nonlocal qc_calls
        qc_calls += 1
        return {
            "verdict": "FAIL",
            "passed": False,
            "exit_code": 1,
            "stderr_preview": "NameError: name 'missing_fn' is not defined",
            "stdout_preview": "",
            "command": "pytest -q",
            "execution_type": "single_container",
            "verified_scope_detail": "tests",
            "source": "sandbox",
        }

    repair_calls = 0

    async def fake_generate_code_from_contract(**_kwargs: Any) -> dict[str, Any]:
        nonlocal repair_calls
        repair_calls += 1
        return {
            "generated_code": "def still_broken():\n    return missing_fn()\n",
            "filename": "app.py",
            "language": "python",
            "source": "llm",
        }

    async def fake_record_audit(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(phases_runtime, "run_runtime_qc", fake_run_runtime_qc)
    monkeypatch.setattr(mission_flow_v2, "generate_code_from_contract", fake_generate_code_from_contract)
    monkeypatch.setattr(mission_flow_v2, "record_audit_event", fake_record_audit)
    monkeypatch.setattr(mission_flow_v2.storage, "insert_runtime_qc_report", lambda *_a, **_k: None)

    class _DummyMission:
        mission_id = "m-dup-sig"
        project_id = "p-1"
        title = "Duplicate sig"
        objective = "Test duplicate sig stop"
        status = "GATING"
        state = "GATING"
        prompt = "test"
        correlation_id = "c-1"
        requested_target_language = "python"
        metadata: dict[str, Any] = {}

    metadata: dict[str, Any] = {
        "requested_target_language": "python",
        "assigned_specialist_agent_id": "AGENT-14-PYTHON",
        "generated_output": {
            "generated_code": "def broken():\n    return missing_fn()\n",
            "filename": "app.py",
            "language": "python",
            "source": "llm",
        },
        "testdata_manifest": {"multi_container": False, "fixtures": []},
        "integration_tests": {"test_code": "def test_x(): assert broken() == 1\n", "source": "llm"},
        "mission_contract": {"summary": "test"},
    }
    _DummyMission.metadata = metadata
    monkeypatch.setattr(
        mission_flow_v2.storage,
        "update_mission_metadata",
        lambda _s, _m_id, meta: metadata.update(meta) or _DummyMission(),
    )
    settings = SimpleNamespace(
        rqca_agent_enabled=True,
        rqca_enforcement_enabled=True,
        testdata_agent_enabled=False,
        runtime_qc_max_repair_attempts=3,
    )
    asyncio.run(phases_runtime._prepare_runtime_qc(app=object(), settings=settings, mission=_DummyMission()))

    # Stopped after attempt 1 because the error signature was identical!
    assert repair_calls == 1
    assert qc_calls == 2
    assert metadata["runtime_qc_report"]["repair_stop_reason"] == "duplicate_error_signature"
