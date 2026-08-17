"""Proof-script contracts: PORT must COMPLETE with files; FAIL QC must not COMPLETE."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

import prove_end_state_live as proof  # noqa: E402
from orchestrator.sow_store import validate_sow_for_accept  # noqa: E402


def test_port_proof_requires_complete_and_output_files() -> None:
    assert proof.port_proof_passed("COMPLETE", ["main.go", "go.mod"]) is True
    assert proof.port_proof_passed("COMPLETE", []) is False
    assert proof.port_proof_passed("VERIFIED", ["main.go"]) is False


def test_fail_qc_proof_rejects_complete_even_if_fail_reported() -> None:
    assert proof.fail_qc_proof_passed("VERIFIED", "FAIL", True) is True
    assert proof.fail_qc_proof_passed("VERIFIED", "FAIL", False) is True
    assert proof.fail_qc_proof_passed("COMPLETE", "FAIL", True) is False
    assert proof.fail_qc_proof_passed("COMPLETE", "ADVISORY", False) is False


def test_sow_contract_is_acceptable_without_unpriced_ack() -> None:
    contract = proof.sow_contract("Port add.py", "PORT", "Port the adder")
    assert contract["engagement_type"] == "PORT"
    assert validate_sow_for_accept(contract) == []


def test_port_proof_rejects_none_files() -> None:
    assert proof.port_proof_passed("COMPLETE", None) is False


def test_fail_qc_passes_on_blocked_event_without_verdict() -> None:
    assert proof.fail_qc_proof_passed("VERIFIED", "", True) is True
    assert proof.fail_qc_proof_passed("VERIFIED", None, False) is False


def test_wait_for_mission_treats_verified_fail_as_terminal(monkeypatch) -> None:
    mission = {
        "state": "VERIFIED",
        "metadata": {"runtime_qc_report": {"qc_assessment": {"qc_verdict": "FAIL"}}},
    }
    monkeypatch.setattr(proof, "get_mission", lambda _mid: mission)
    monkeypatch.setattr(proof, "get_chain", lambda _mid: {"events": []})
    monkeypatch.setattr(proof.time, "sleep", lambda _s: (_ for _ in ()).throw(AssertionError("should not wait")))
    assert proof.wait_for_mission("mission-x", timeout_seconds=30) is mission


def test_wait_for_mission_treats_blocked_event_as_terminal(monkeypatch) -> None:
    mission = {"state": "VERIFIED", "metadata": {}}
    monkeypatch.setattr(proof, "get_mission", lambda _mid: mission)
    monkeypatch.setattr(
        proof,
        "get_chain",
        lambda _mid: {"events": [{"event_type": "MISSION_RUNTIME_QC_BLOCKED"}]},
    )
    monkeypatch.setattr(proof.time, "sleep", lambda _s: (_ for _ in ()).throw(AssertionError("should not wait")))
    assert proof.wait_for_mission("mission-x", timeout_seconds=30) is mission


def test_python_qc_command_uses_stdlib_unittest_not_pytest() -> None:
    from orchestrator import rqca_agent

    cmd = rqca_agent._resolve_test_command(
        filename="adder.py",
        test_filename="test_adder.py",
        language="python",
        settings=type("S", (), {"rqca_test_command_template": ""})(),
    )
    assert cmd is not None
    assert "unittest" in cmd
    assert "pytest" not in cmd
    assert "test_adder.py" in cmd
